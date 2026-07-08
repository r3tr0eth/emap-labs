"""Retriever semántico local: clasificación de categoría por embeddings.

Arquitectura en dos etapas (la misma que tendrá /nearby en producción):

  1. SEMÁNTICA — la consulta (con la cláusula de ubicación recortada) se
     compara por coseno contra un texto descriptivo por categoría; bajo el
     umbral se abstiene, y las categorías empatadas entran juntas.
  2. ESTRUCTURADA — heredada del baseline: filtros de atributo, nombre
     citado y orden geográfico. Solo cambia CÓMO se decide la categoría.

El primer intento (embeder cada POI con su nombre) puntuó 13/60: el nombre
ahogaba la señal de categoría. Documentado en results/.

Modelo: paraphrase-multilingual-MiniLM-L12-v2 vía fastembed (ONNX, sin GPU).

AVISO de honestidad: las descripciones de categoría y las paráfrasis del
corpus las escribió la misma persona; la validación real llegará con
consultas de usuarios.
"""
from __future__ import annotations

import numpy as np
from fastembed import TextEmbedding

from baseline import BaselineRetriever, norm

# L3 carril 1: modelo intercambiable por env para el benchmark.
# BGE-M3 (objetivo del roadmap) no está en fastembed y no cabe en este Mac
# (2.3GB libres) — queda para la caja de 8GB; mpnet es el paso intermedio.
import os
MODEL = os.environ.get("EMAP_EMBED_MODEL",
                       "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
SIM_THRESHOLD = float(os.environ.get("EMAP_SIM_TAU", "0.45"))  # bajo esto: "no sé"
TIE_WINDOW = float(os.environ.get("EMAP_TIE_WIN", "0.08"))  # categorías a menos de esto del top entran también

CATEGORY_TEXT = {
    "fountains": ("Fuente de agua potable: beber agua, rellenar la botella o el "
                  "bidón, quitar la sed. Edateko ur-iturria: ura edan, botila "
                  "edo bidoia bete, egarria kendu, egarri naiz, kantinplora."),
    "toilets": ("Aseo público, baño, servicio, WC: ir al baño, hacer pis, "
                "cambiar al bebé. Komun publikoa, komuna, bainugela: txiza "
                "egin, haurra aldatu, komunera joan."),
    "parking": ("Aparcamiento para dejar, guardar o estacionar el coche. "
                "Autoa aparkatzeko edo uzteko aparkalekua, autoarentzako "
                "lekua, non aparkatu."),
    "bikepark": ("Aparcabicis: dejar, atar o candar la bicicleta de forma "
                 "segura. Bizikleta-aparkalekua: bizikleta utzi, lotu, "
                 "seguru utzi."),
    "ev": ("Punto de carga de vehículo eléctrico: cargar o enchufar el coche "
           "eléctrico o el patinete. Autoa kargatzeko puntua, kargagailua, "
           "elektrolinera, autoa entxufatu, patinete elektrikoa kargatu."),
    "defib": ("Desfibrilador DEA para una emergencia cardiaca, un infarto, un "
              "desmayo, reanimación. Desfibriladorea, DEA, KDA, bihotzeko "
              "larrialdia, bihotzekoa eman dio, konortea galdu du."),
    "beaches": ("Playa para bañarse, nadar, darse un chapuzón, mojarse, "
                "tumbarse en la arena, tomar el sol. Hondartza: bainatu, "
                "igeri egin itsasoan, uretara sartu, hondarretan etzan, "
                "eguzkia hartu, oinak busti."),
    "cameras": ("Cámara de tráfico para ver el estado de la carretera ahora "
                "mismo en directo. Trafiko-kamera: errepidearen egoera "
                "zuzenean ikusi."),
    "metro": "Estación de metro, suburbano. Metro geltokia.",
    "euskotren": "Estación de tren o tranvía de Euskotren. Euskotren geltokia.",
    "cercanias": "Estación de tren de Cercanías Renfe. Aldiriko trena, aldiriak, tren geltokia.",
    "bilbobus": "Parada de autobús urbano Bilbobus. Bilbobus autobus geltokia.",
    "bizkaibus": "Parada de autobús Bizkaibus. Bizkaibus autobus geltokia.",
}

# tokens de la cláusula locativa que acompaña al nombre del anchor
LOCATIVE = {"cerca", "de", "del", "de la", "la", "el", "en", "junto", "al",
            "lado", "a", "estacion", "parada", "puerto", "inguruan", "ondoan",
            "gertu", "geltokitik", "geltokia", "portutik", "hurbilena",
            "hurbilen", "dagoen", "-tik"}


def strip_location(query: str, anchor_names: list[str]) -> str:
    """Quita del texto la cláusula de ubicación ("cerca de la estación de
    Abando") para que la intención no se contamine. Solo se usa cuando el
    caso trae anchor: en producción este papel lo hace el parser de
    ubicación del buscador."""
    tokens = norm(query).split()
    parts = {norm(seg) for n in anchor_names for seg in n.split("/") if seg}
    out = []
    i = 0
    while i < len(tokens):
        if any(tokens[i] in p.split() or p.startswith(tokens[i]) and len(tokens[i]) >= 4
               for p in parts):
            # borra también los tokens locativos que preceden al nombre
            while out and out[-1] in LOCATIVE:
                out.pop()
            i += 1
            continue
        out.append(tokens[i])
        i += 1
    return " ".join(out) or norm(query)


class SemanticRetriever(BaselineRetriever):
    name = "semantic-minilm-2stage"

    def __init__(self, datasets: dict[str, list[dict]]):
        super().__init__(datasets)
        self.model = TextEmbedding(MODEL)
        self.cats = [c for c in CATEGORY_TEXT if c in datasets]
        vecs = np.array(list(self.model.embed([CATEGORY_TEXT[c] for c in self.cats])))
        self.cat_vecs = vecs / np.linalg.norm(vecs, axis=1, keepdims=True)
        self._anchor_names: list[str] = []

    def set_anchor_names(self, names: list[str]) -> None:
        """El runner informa del texto del anchor del caso (nunca del expected)."""
        self._anchor_names = [n for n in names if n]

    def detect_layers(self, query: str) -> list[str]:
        q = strip_location(query, self._anchor_names)
        v = np.array(list(self.model.embed([q])))[0]
        v /= np.linalg.norm(v)
        sims = self.cat_vecs @ v
        best = float(sims.max())
        if best < SIM_THRESHOLD:
            return []  # nada se parece lo bastante: no sé
        return [c for c, s in zip(self.cats, sims) if s >= best - TIE_WINDOW]


class HybridRetriever(SemanticRetriever):
    """Producción-candidato: keywords primero (precisión alta, gratis),
    embeddings solo cuando las keywords no reconocen la consulta. Es la
    composición natural: el baseline nunca inventa categoría (se abstiene)
    y ahí entra la semántica."""

    name = "hybrid-keywords-then-semantic"

    def detect_layers(self, query: str) -> list[str]:
        layers = BaselineRetriever.detect_layers(self, query)
        if layers:
            return layers
        return SemanticRetriever.detect_layers(self, query)
