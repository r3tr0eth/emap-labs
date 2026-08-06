"""Planificador de excursiones: monte en transporte público.

Dada una cima y una fecha, calcula:
- ruta de ida (transit hasta parada + walk a cima)
- tiempo estimado de ascenso (basado en desnivel)
- opciones de regreso verificables
- recomendación con margen de seguridad

Fuentes:
- data/processed/mendi/peaks-transit.json: cimas × paradas
- OTP (:8082): routing real transit+walk con horarios
- OSRM (:8085): tiempos de caminata cuando OTP no cubre
"""
from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

DATA_DIR = Path(os.environ.get("EMAP_DATA_DIR", "/opt/emap-labs/data")).resolve()
OTP_BASE = os.environ.get("EMAP_OTP_URL", "http://localhost:8082/otp/routers/default")

# Cache de peaks-transit
_peaks_cache: list[dict] | None = None


def load_peaks() -> list[dict]:
    """Carga peaks-transit.json."""
    global _peaks_cache
    if _peaks_cache is not None:
        return _peaks_cache
    path = DATA_DIR / "processed" / "mendi" / "peaks-transit.json"
    if not path.exists():
        _peaks_cache = []
        return _peaks_cache
    doc = json.loads(path.read_text())
    _peaks_cache = doc.get("items", [])
    return _peaks_cache


def find_peak(query: str) -> dict | None:
    """Busca una cima por nombre (ES o EU), case-insensitive parcial."""
    peaks = load_peaks()
    q = query.lower().strip()
    # Match exacto primero
    for p in peaks:
        for lang in ("es", "eu"):
            if p.get("peak", {}).get(lang, "").lower() == q:
                return p
    # Match parcial
    for p in peaks:
        for lang in ("es", "eu"):
            if q in p.get("peak", {}).get(lang, "").lower():
                return p
    return None


def estimate_hike_time(elevation_m: float | None, dist_to_peak_m: float) -> int:
    """Estima tiempo de ascenso en minutos.

    Regla simplificada basada en ritmo montañero:
    - 300m desnivel/hora en subida
    - 5 km/h en llano
    - +10 min por cada 100m de desnivel
    """
    if not elevation_m:
        # Sin dato de elevación: estimar solo por distancia
        return int(dist_to_peak_m / 83)  # ~5 km/h

    # Tiempo subida por desnivel + distancia horizontal
    ascent_time = (elevation_m / 300) * 60  # minutos por desnivel
    flat_time = (dist_to_peak_m / 83)  # minutos por distancia
    return int(max(ascent_time, flat_time)) + 15  # +15 min margen base


def otp_plan(from_lat: float, from_lon: float,
             to_lat: float, to_lon: float,
             date_str: str, time_str: str,
             mode: str = "TRANSIT,WALK") -> dict | None:
    """Llama al planificador de OTP. Devuelve el plan o None."""
    params = {
        "fromPlace": f"{from_lat},{from_lon}",
        "toPlace": f"{to_lat},{to_lon}",
        "mode": mode,
        "date": date_str,
        "time": time_str,
        "maxWalkDistance": 8000,
        "arriveBy": "false",
    }
    url = f"{OTP_BASE}/plan?{urllib.parse.urlencode(params)}"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        return data.get("plan")
    except Exception:
        return None


def plan_hike(peak_name: str, from_lat: float, from_lon: float,
              hike_date: str | None = None, start_time: str = "08:00") -> dict:
    """Planifica una excursión al monte en transporte público.

    Args:
        peak_name: nombre de la cima (ES o EU)
        from_lat, from_lon: punto de origen (ej: Bilbao centro)
        hike_date: fecha ISO (default: hoy)
        start_time: hora de salida HH:MM

    Returns:
        dict con itinerario o razón por la que no es viable
    """
    if not hike_date:
        hike_date = date.today().isoformat()

    peak = find_peak(peak_name)
    if not peak:
        return {
            "ok": False,
            "reason": "peak_not_found",
            "query": peak_name,
        }

    peak_lat = peak["lat"]
    peak_lon = peak["lon"]
    nearest = peak["nearest_stop"]
    dist_to_peak = nearest["dist_m"]

    # Estimar tiempo de ascenso
    hike_up = estimate_hike_time(peak.get("ele"), dist_to_peak)

    # Buscar ruta de ida con OTP (origen → parada cercana)
    # Usamos las coords de la parada más cercana (aproximadas por la cima)
    plan_out = otp_plan(from_lat, from_lon, peak_lat, peak_lon, hike_date, start_time)

    if not plan_out or not plan_out.get("itineraries"):
        return {
            "ok": False,
            "reason": "no_transit_route",
            "peak": peak["peak"],
            "nearest_stop": nearest,
            "hike_up_min": hike_up,
        }

    # Tomar el itinerario más corto
    itin = min(plan_out["itineraries"], key=lambda i: i["duration"])
    arrival_at_stop = datetime.strptime(f"{hike_date} {start_time}", "%Y-%m-%d %H:%M")
    arrival_at_stop += timedelta(seconds=itin["duration"])

    # Hora estimada de llegada a cima
    summit_time = arrival_at_stop + timedelta(minutes=hike_up)

    # Buscar regreso: desde la cima, tardamos hike_up/2 en bajar
    descent_time = int(hike_up * 0.6)  # bajar es más rápido
    earliest_return = summit_time + timedelta(minutes=descent_time + 15)  # 15 min descanso

    # Buscar ruta de regreso con OTP
    return_time_str = earliest_return.strftime("%H:%M")
    plan_back = otp_plan(peak_lat, peak_lon, from_lat, from_lon,
                          hike_date, return_time_str)

    return_options = []
    if plan_back and plan_back.get("itineraries"):
        for ri in plan_back["itineraries"][:3]:
            return_departure = earliest_return
            return_arrival = return_departure + timedelta(seconds=ri["duration"])
            return_options.append({
                "departure": return_departure.strftime("%H:%M"),
                "arrival": return_arrival.strftime("%H:%M"),
                "duration_min": ri["duration"] // 60,
                "legs": len(ri.get("legs", [])),
            })

    # Evaluar viabilidad
    viable = len(return_options) > 0
    recommendation = ""
    if viable:
        last_return = return_options[-1]
        margin = (datetime.strptime(f"{hike_date} {last_return['arrival']}", "%Y-%m-%d %H:%M")
                  - earliest_return).total_seconds() / 60
        if margin > 60:
            recommendation = "viable_comoda"
        elif margin > 30:
            recommendation = "viable_justa"
        else:
            recommendation = "viable_con_margen_justo"
    else:
        recommendation = "no_viable_sin_regreso"

    return {
        "ok": True,
        "viable": viable,
        "recommendation": recommendation,
        "peak": peak["peak"],
        "elevation_m": peak.get("ele"),
        "nearest_stop": nearest,
        "hike_up_min": hike_up,
        "descent_min": descent_time,
        "outbound": {
            "departure": start_time,
            "arrival_at_stop": arrival_at_stop.strftime("%H:%M"),
            "transit_duration_min": itin["duration"] // 60,
            "legs": len(itin.get("legs", [])),
        },
        "summit_time": summit_time.strftime("%H:%M"),
        "return_options": return_options,
        "date": hike_date,
        "data_sources": ["peaks-transit", "osm", "gtfs-via-otp"],
        "caveats": [
            "Tiempos de ascenso estimados por desnivel, no verificados presencialmente",
            "Horarios de transporte pueden variar (verificar con la operadora)",
            "Condiciones meteorológicas no incluidas",
        ],
    }
