"""Météo Open-Meteo sur une grille ~10 km, appels regroupés, cache 3 h."""
from __future__ import annotations

import logging
import math
from datetime import date

import httpx

from . import cache
from .scoring import load_config, species_ids, weather_score
from .settings import (FORECAST_DAYS, OPEN_METEO_URL, PAST_DAYS, WEATHER_BATCH,
                       WEATHER_GRID_DEG, WEATHER_TTL)

log = logging.getLogger(__name__)

DAILY = {
    "precipitation_sum": "rain",
    "temperature_2m_min": "tmin",
    "temperature_2m_max": "tmax",
    "temperature_2m_mean": "tmean",
    "soil_temperature_0_to_7cm_mean": "soil_t",
    "soil_moisture_0_to_7cm_mean": "soil_m",
}


def cell_of(lon: float, lat: float) -> str:
    return f"{math.floor(lon / WEATHER_GRID_DEG)}_{math.floor(lat / WEATHER_GRID_DEG)}"


def cell_center(cell: str) -> tuple[float, float]:
    i, j = (int(v) for v in cell.split("_"))
    return (round((i + 0.5) * WEATHER_GRID_DEG, 4), round((j + 0.5) * WEATHER_GRID_DEG, 4))


def _parse(payload: dict) -> dict:
    d = payload["daily"]
    days = [{v: d[k][n] for k, v in DAILY.items()} | {"date": t} for n, t in enumerate(d["time"])]
    # Open-Meteo renvoie PAST_DAYS jours passés puis aujourd'hui (fuseau Europe/Paris)
    return {"today": d["time"][PAST_DAYS], "days": days}


async def _fetch_batch(client: httpx.AsyncClient, cells: list[str]) -> dict[str, dict]:
    centers = [cell_center(c) for c in cells]
    params = {
        "latitude": ",".join(str(lat) for _, lat in centers),
        "longitude": ",".join(str(lon) for lon, _ in centers),
        "daily": ",".join(DAILY),
        "past_days": PAST_DAYS, "forecast_days": FORECAST_DAYS,
        "timezone": "Europe/Paris",
    }
    r = await client.get(OPEN_METEO_URL, params=params, timeout=60)
    r.raise_for_status()
    data = r.json()
    data = data if isinstance(data, list) else [data]
    return {c: _parse(p) for c, p in zip(cells, data)}


async def get_cells(client, cells: set[str], warnings: list) -> dict[str, dict]:
    """Météo + score météo de chaque espèce par cellule (score None si indisponible)."""
    cfg = load_config()
    raw, missing = {}, []
    for c in cells:
        hit = cache.get(f"meteo:{c}", WEATHER_TTL)
        if hit:
            raw[c] = hit[0] | {"stale": False}
        else:
            missing.append(c)
    failed = False
    for k in range(0, len(missing), WEATHER_BATCH):
        batch = missing[k:k + WEATHER_BATCH]
        try:
            for c, v in (await _fetch_batch(client, batch)).items():
                cache.put(f"meteo:{c}", v)
                raw[c] = v | {"stale": False}
        except (httpx.HTTPError, ValueError, KeyError, IndexError) as e:
            log.warning("Open-Meteo : %s", e)
            failed = True
            for c in batch:
                stale = cache.get(f"meteo:{c}", WEATHER_TTL, allow_stale=True)
                raw[c] = stale[0] | {"stale": True} if stale else None
    if failed:
        warnings.append("API météo Open-Meteo indisponible : météo en cache (ou absente) utilisée.")

    out = {}
    for c, v in raw.items():
        lon, lat = cell_center(c)
        if v is None:
            unavailable = {"score": None, "factors": [], "summary": {}, "error": "météo indisponible"}
            out[c] = {"lon": lon, "lat": lat, "days": [],
                      "species": {sid: unavailable for sid in species_ids(cfg)}}
            continue
        today = date.fromisoformat(v["today"])
        out[c] = {"lon": lon, "lat": lat, "today": v["today"], "days": v["days"],
                  "stale": v["stale"],
                  "species": {sid: weather_score(v["days"], today, cfg, sid) for sid in species_ids(cfg)}}
    return out
