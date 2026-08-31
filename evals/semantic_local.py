"""Retriever semántico local: clasificación de categoría por embeddings.

Arquitectura en dos etapas (la misma que tendrá /nearby en producción):

  1. SEMÁNTICA — la consulta (con la cláusula de ubicación recortada) se
     compara por coseno contra un texto descriptivo por categoría; bajo el
     umbral se abstiene, y las categorías empatadas entran juntas.
  2. ESTRUCTURADA — heredada del baseline: filtros de atributo, nombre
     citado y orden geográfico. Solo cambia CÓMO se decide la categoría.

El primer intento (embeder cada POI con su nombre) puntuó 13/60: el nombre
ahogaba la señal de categoría. Documentado en results/.

Modelo y calibración: perfil de `retriever-config.json` vía FastEmbed (ONNX,
sin GPU). MiniLM es el default reproducible; producción selecciona e5large.

AVISO de honestidad: las descripciones de categoría y las paráfrasis del
corpus las escribió la misma persona; la validación real llegará con
consultas de usuarios.
"""
from __future__ import annotations

import os
import threading
from typing import Callable, Mapping

import numpy as np
from fastembed import TextEmbedding

from baseline import BaselineRetriever, norm
from retriever_config import resolve_profile

# L3 carril 1: modelo intercambiable por env para el benchmark por-modelo.
# fastembed 0.8 no trae BGE-M3 ni Qwen3 (los objetivos del roadmap sólo tienen
# variantes en/zh de BGE) — ésos esperan la caja de 8GB con sentence-transformers
# nativo. La vía multilingüe viable HOY (cabe en este Mac): MiniLM-L12 (384d,
# actual), mpnet-base (768d) y multilingual-e5-large (1024d, el más fuerte).
PROFILE = resolve_profile(
    profile_name=os.environ.get("EMAP_RETRIEVER_PROFILE"),
    model=os.environ.get("EMAP_EMBED_MODEL"),
)
PROFILE_NAME = PROFILE.name
MODEL = PROFILE.model
MODEL_TAG = PROFILE.name

# Los modelos e5 se entrenaron con prefijos asimétricos: la consulta lleva
# "query:" y los textos indexados "passage:". Sin ellos el coseno se degrada
# (es el error clásico al portar e5). El resto de modelos no llevan prefijo.
_IS_E5 = "e5" in MODEL.lower()
QUERY_PREFIX = "query: " if _IS_E5 else ""
DOC_PREFIX = "passage: " if _IS_E5 else ""
# Recalibrado en dev 2026-07-09 al pasar de 13 → 21 categorías (τ 0.45→0.50,
# tie 0.08→0.03): con más categorías el tie-window ancho dejaba colar capas
# basura que robaban el top-1 por cercanía, y τ alto compensa la subida de
# falsos positivos. Elegido por paridad ES/EU (barrido en dev, commit).
SIM_THRESHOLD = float(os.environ.get("EMAP_SIM_TAU", PROFILE.sim_threshold))
TIE_WINDOW = float(os.environ.get("EMAP_TIE_WIN", PROFILE.tie_window))

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
    # euskadi-places (2026-07): EU pendiente de cotejo con Itzuli.
    # Descripciones ceñidas a lo que el dato ES — sin necesidades genéricas
    # ("tengo hambre", "sitio tranquilo") que absorben conceptos ausentes
    # (pintxos, mercados, cafeterías, parques urbanos) y matan la abstención.
    "pharmacy": ("Farmacia o botiquín de guardia: comprar medicamentos con "
                 "o sin receta. Farmazia edo botika: sendagaiak erosi, "
                 "errezetako botikak."),
    "library": ("Biblioteca o mediateca pública: estudiar, leer, préstamo "
                "de libros, sala de estudio. Liburutegi edo mediateka "
                "publikoa: ikasi, irakurri, liburuak mailegatu, ikasteko "
                "gela."),
    "sports": ("Instalación deportiva: polideportivo, piscina municipal, "
               "frontón, gimnasio, hacer deporte, entrenar. "
               "Kirol-instalazioa: kiroldegia, udal igerilekua, "
               "pilotalekua, kirola egin, entrenatu."),
    "food": ("Restaurante, sidrería, asador o bodega: comida o cena de "
             "restaurante, menú del día. Jatetxea, sagardotegia, "
             "erretegia: jatetxeko bazkaria edo afaria, eguneko menua."),
    "lodging": ("Hotel, pensión o agroturismo: alojarse en habitación con "
                "cama, reservar una habitación, pasar la noche en un hotel. "
                "Hotela, pentsioa, nekazalturismoa: gela erreserbatu, ostatu "
                "hartu, lo egin ohean, gaua pasatu hotelan."),
    "hostel": ("Albergue de peregrinos o juvenil: litera en dormitorio "
               "compartido. Aterpetxea: erromesen aterpea, litera logela "
               "partekatuan."),
    "camping": ("Camping al aire libre: parcela para tienda de campaña o "
                "bungalow. Kanpina: zelaia kanpina, dendarako partzela, "
                "bungalowa."),
    "nature": ("Espacio natural protegido: parque natural, biotopo, marisma, "
               "humedal con aves. Naturgune babestua: natur parkea, "
               "biotopoa, padura, hezegunea."),
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
        if any(tokens[i] in p.split()
               or (p.startswith(tokens[i]) and len(tokens[i]) >= 4)
               # declinación vasca: "Moyuatik", "Sopelako" → anchor "moyua"…
               or any(tokens[i].startswith(pw) and len(pw) >= 4 for pw in p.split())
               for p in parts):
            # borra también los tokens locativos que preceden al nombre
            # (es: "cerca de Moyua") y los que lo siguen (eu: "Moyuatik gertu")
            while out and out[-1] in LOCATIVE:
                out.pop()
            i += 1
            while i < len(tokens) and tokens[i] in LOCATIVE:
                i += 1
            continue
        out.append(tokens[i])
        i += 1
    return " ".join(out) or norm(query)


class SemanticRetriever(BaselineRetriever):
    def __init__(
        self,
        datasets: Mapping[str, list[dict] | tuple[dict, ...]],
        *,
        encoder: "SemanticEncoder | None" = None,
        profile_name: str | None = None,
    ):
        super().__init__(datasets)
        self.encoder = encoder or SemanticEncoder(profile_name)
        self.name = f"semantic-{self.encoder.profile_name}-2stage"
        self.cats = [c for c in CATEGORY_TEXT if c in datasets]
        docs = [CATEGORY_TEXT[c] for c in self.cats]
        vecs = np.array(self.encoder.embed_documents(docs))
        self.cat_vecs = vecs / np.linalg.norm(vecs, axis=1, keepdims=True)
        self._anchor_names: list[str] = []
        self.sim_threshold = self.encoder.sim_threshold
        self.tie_window = self.encoder.tie_window

    def set_anchor_names(self, names: list[str]) -> None:
        """El runner informa del texto del anchor del caso (nunca del expected)."""
        self._anchor_names = [n for n in names if n]

    def detect_layers(self, query: str) -> list[str]:
        q = strip_location(query, self._anchor_names)
        v = np.array(self.encoder.embed_query(q))
        v /= np.linalg.norm(v)
        sims = self.cat_vecs @ v
        best = float(sims.max())
        if best < self.sim_threshold:
            return []  # nada se parece lo bastante: no sé
        return [c for c, s in zip(self.cats, sims) if s >= best - self.tie_window]


class SemanticEncoder:
    """Modelo semántico compartible; no contiene estado territorial."""

    def __init__(self, profile_name: str | None = None) -> None:
        profile = resolve_profile(profile_name=profile_name)
        self.profile_name = profile.name
        self.sim_threshold = float(
            os.environ.get("EMAP_SIM_TAU", profile.sim_threshold)
        )
        self.tie_window = float(os.environ.get("EMAP_TIE_WIN", profile.tie_window))
        self._is_e5 = "e5" in profile.model.lower()
        self._model = TextEmbedding(profile.model)
        self._lock = threading.RLock()

    def embed_documents(self, texts: list[str]) -> list[np.ndarray]:
        prefix = "passage: " if self._is_e5 else ""
        with self._lock:
            return list(self._model.embed([prefix + text for text in texts]))

    def embed_query(self, text: str) -> np.ndarray:
        prefix = "query: " if self._is_e5 else ""
        with self._lock:
            return list(self._model.embed([prefix + text]))[0]


class HybridRetrieverFactory:
    """Crea retrievers aislados compartiendo un encoder por perfil."""

    def __init__(
        self,
        *,
        encoder_factory: Callable[[str], SemanticEncoder] = SemanticEncoder,
    ) -> None:
        self._encoder_factory = encoder_factory
        self._encoders: dict[str, SemanticEncoder] = {}
        self._lock = threading.Lock()

    def __call__(
        self,
        profile_name: str,
        datasets: Mapping[str, list[dict] | tuple[dict, ...]],
    ) -> "HybridRetriever":
        with self._lock:
            encoder = self._encoders.get(profile_name)
            if encoder is None:
                encoder = self._encoder_factory(profile_name)
                self._encoders[profile_name] = encoder
        return HybridRetriever(datasets, encoder=encoder)


class HybridRetriever(SemanticRetriever):
    """Producción-candidato: keywords primero (precisión alta, gratis),
    embeddings solo cuando las keywords no reconocen la consulta. Es la
    composición natural: el baseline nunca inventa categoría (se abstiene)
    y ahí entra la semántica."""

    def __init__(
        self,
        datasets: Mapping[str, list[dict] | tuple[dict, ...]],
        *,
        encoder: SemanticEncoder | None = None,
        profile_name: str | None = None,
    ) -> None:
        super().__init__(datasets, encoder=encoder, profile_name=profile_name)
        self.name = f"hybrid-keywords-then-{self.encoder.profile_name}"

    def detect_layers(self, query: str) -> list[str]:
        layers = BaselineRetriever.detect_layers(self, query)
        if layers:
            return layers
        return SemanticRetriever.detect_layers(self, query)

    def detect_layers_with_scores(self, query: str) -> tuple[list[str], dict[str, float], str]:
        """Devuelve (capas, scores_por_capa, método). 'method' es 'keywords'
        o 'semantic' según qué etapa detectó la categoría."""
        # Probar keywords primero
        kw_layers = BaselineRetriever.detect_layers(self, query)
        if kw_layers:
            scores = {c: 0.0 for c in self.cats}
            for c in kw_layers:
                scores[c] = 1.0  # keywords: score binario
            return kw_layers, scores, "keywords"

        # Fall back a semántica
        layers = SemanticRetriever.detect_layers(self, query)
        if not layers:
            return [], {}, "semantic"

        # Recuperar scores reales
        q = strip_location(query, self._anchor_names)
        v = np.array(self.encoder.embed_query(q))
        v /= np.linalg.norm(v)
        sims = self.cat_vecs @ v
        scores = {c: float(s) for c, s in zip(self.cats, sims)}
        return layers, scores, "semantic"
