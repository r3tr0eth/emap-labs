"""Retriever baseline: keywords ES/EU + filtro geográfico. Sin embeddings.

Es la cifra a batir por el retriever semántico de L1 (pgvector). Recibe
solo la consulta y el anchor — nunca el resultado esperado del corpus.
Si no reconoce ninguna categoría, devuelve [] (abstención): mejor decir
"no sé" que inventar.
"""
from __future__ import annotations

import re
import unicodedata

try:
    from emap_geo.distance import haversine_m
except ImportError:  # CI / entorno sin emap-next: fallback vendorizado
    from _geo import haversine_m


def norm(text: str) -> str:
    """minúsculas y sin diacríticos (moyúa → moyua)."""
    nfd = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn")


# keyword normalizada → capas candidatas. El orden importa: la primera
# regla que casa gana su capa (bici+parking = aparcabicis, no parking).
KEYWORD_LAYERS: list[tuple[tuple[str, ...], tuple[str, ...]]] = [
    (("aparcabici", "bizikleta-aparkaleku", "bizikleta apark", "dejar la bici",
      "utzi bizikleta", "bici", "bizikleta"), ("bikepark",)),
    (("desfibrilador", "desfibriladore", "dea",), ("defib",)),
    (("cargador", "kargagailu", "kargatzeko", "electrolinera", "kargatoki",
      "punto de carga", "puntos de carga", "carga "), ("ev",)),
    (("fuente", "iturria", "iturri", "edateko", "beber agua", "edan",
      "botella", "botila", "agua", "ura"), ("fountains",)),
    (("aseo", "bano", "komun", "wc", "meando"), ("toilets",)),
    (("playa", "hondartza", "banarse", "bainatu"), ("beaches",)),
    (("camara", "kamera"), ("cameras",)),
    (("aparcamiento", "aparcar", "parking", "aparkaleku", "aparkatu"),
     ("parking",)),
    # euskadi-places (2026-07): 8 capas de Open Data Euskadi.
    # Solo sustantivos inequívocos de la categoría — los verbos de necesidad
    # ("comer", "dormir") son ambiguos y le tocan a la etapa semántica.
    (("farmacia", "farmazia", "botika", "botiquin"), ("pharmacy",)),
    (("biblioteca", "liburutegi", "mediateca", "mediateka"), ("library",)),
    (("polideportivo", "kiroldegi", "fronton", "pilotaleku", "piscina",
      "igerileku", "gimnasio", "instalacion deportiva"), ("sports",)),
    (("restaurante", "jatetxe", "sidreria", "sagardotegi", "asador"),
     ("food",)),
    (("albergue", "aterpe", "hostel"), ("hostel",)),
    (("camping", "kanpin"), ("camping",)),
    (("hotel", "pension", "alojamiento", "ostatu"),
     ("lodging", "hostel", "camping")),
    (("parque natural", "espacio natural", "naturgune", "natur parke",
      "biotopo", "marisma"), ("nature",)),
    (("bilbobus",), ("bilbobus",)),
    (("bizkaibus",), ("bizkaibus",)),
    (("cercanias", "aldiriko"), ("cercanias",)),
    (("euskotren",), ("euskotren",)),
    (("metro",), ("metro",)),
    (("tren", "estacion", "geltoki", "parada"),
     ("metro", "euskotren", "cercanias")),
    (("linea", "linea"), ("metro", "euskotren", "cercanias", "bilbobus", "bizkaibus")),
]

# atributo detectado en la consulta → filtro sobre tags del POI
ATTRIBUTE_FILTERS: list[tuple[tuple[str, ...], tuple[str, str, bool]]] = [
    (("silla de ruedas", "gurpil-aulki", "accesible", "irisgarri"),
     ("wheelchair", "yes", True)),
    (("gratis", "gratuito", "doako"), ("fee", "no", True)),
    (("cubierto", "estali", "toki estalia"), ("covered", "yes", True)),
    (("rapido", "azkar"), ("TipoCarga", "Lenta (3-7 kW)", False)),  # != lenta
    # movilidad del cuidado: cambiador de bebé (33 aseos en Euskadi, OSM)
    (("cambiador", "cambiar al bebe", "aldatzeko", "haurra aldatu", "aldalekua"),
     ("changing_table", "yes", True)),
]


class BaselineRetriever:
    name = "baseline-keywords-geo"

    def __init__(self, datasets: dict[str, list[dict]]):
        self.datasets = datasets  # layer → [poi]; poi: {id,name,lat,lon,tags}

    def detect_layers(self, query: str) -> list[str]:
        """Etapa 1: qué categorías pide la consulta (aquí, por keywords)."""
        q = norm(query)
        # frontera izquierda de palabra: "aseo" no debe casar dentro de "paseo";
        # la derecha queda libre para plurales/declinaciones (fuente→fuentes)
        for keywords, layer_ids in KEYWORD_LAYERS:
            if any(re.search(rf"(?<![a-zà-ÿ]){re.escape(kw)}", q) for kw in keywords):
                return [l for l in layer_ids if l in self.datasets]
        return []

    def retrieve(self, query: str, anchor: dict | None, k: int = 5) -> list[dict]:
        q = norm(query)
        hit = lambda kw: re.search(rf"(?<![a-zà-ÿ]){re.escape(kw)}", q)  # noqa: E731

        layers = self.detect_layers(query)
        if not layers:
            return []  # no sé qué me pides: abstención

        candidates = [dict(p, layer=l) for l in layers for p in self.datasets[l]]

        for keywords, (tag, value, must_equal) in ATTRIBUTE_FILTERS:
            if any(hit(kw) for kw in keywords):
                # sin fallback: si nada cumple el atributo, mejor abstenerse
                # que devolver resultados que no cumplen lo pedido
                candidates = [
                    p for p in candidates
                    if (p.get("tags", {}).get(tag) == value) == must_equal
                    and (must_equal or p.get("tags", {}).get(tag) is not None)
                ]

        # con anchor manda la distancia (lo genérico cerca gana a lo
        # homónimo lejos); el nombre citado solo decide sin ubicación
        if anchor:
            candidates.sort(key=lambda p: haversine_m(
                anchor["lat"], anchor["lon"], p["lat"], p["lon"]))
            return candidates[:k]

        def name_match(p: dict) -> int:
            names = [p["name"].get("es", "") or "", p["name"].get("eu", "") or ""]
            for cand in (norm(n) for n in names):
                if len(cand) >= 4 and cand in q:
                    return 2  # nombre completo citado
            # partes de nombres compuestos: "Santimami/San Mamés", "X (nota)"
            parts = [seg.split(" (")[0].strip()
                     for n in names for seg in n.split("/")]
            if any(len(pt) >= 4 and norm(pt) in q for pt in parts):
                return 1
            return 0

        named = sorted(((s, p) for p in candidates if (s := name_match(p))),
                       key=lambda sp: -sp[0])
        if named:
            return [p for _, p in named[:k]]
        return candidates[:k]
