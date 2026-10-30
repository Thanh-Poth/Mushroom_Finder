"""Modèle de score par espèce : score = 100 × score_essence × score_météo.

Fonctions pures, sans I/O hormis le chargement des YAML, pour être testables.
Tous les seuils viennent de config/scoring.yaml et config/tfv_mapping.yaml.
"""
from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from statistics import mean

import yaml

from .settings import CONFIG_DIR

MONTHS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
             "août", "septembre", "octobre", "novembre", "décembre"]


@lru_cache
def load_config(config_dir: Path = CONFIG_DIR) -> dict:
    with open(config_dir / "scoring.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    with open(config_dir / "tfv_mapping.yaml", encoding="utf-8") as f:
        cfg["tfv"] = yaml.safe_load(f)
    # Météo résolue par espèce : défauts + facteurs surchargés + saison
    cfg["species_weather"] = {
        sid: {**cfg["weather_defaults"], **(sp.get("weather") or {}),
              "season": sp["season"], "season_ok_months": sp["season_ok_months"]}
        for sid, sp in cfg["species"].items()
    }
    return cfg


def species_ids(cfg: dict) -> list[str]:
    return list(cfg["species"])


def interp(points: list[list[float]], x: float) -> float:
    """Interpolation linéaire par morceaux, valeurs constantes hors bornes."""
    if x <= points[0][0]:
        return float(points[0][1])
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return float(points[-1][1])


def _status(multiplier: float, ok: bool | None = None) -> str:
    if ok is True or (ok is None and multiplier >= 0.9):
        return "ok"
    return "warn" if multiplier >= 0.5 else "bad"


# ---------------------------------------------------------------------------
# Essence
# ---------------------------------------------------------------------------

def essence_category(code_tfv: str | None, cfg: dict) -> str:
    entry = cfg["tfv"].get((code_tfv or "").strip())
    return entry["category"] if entry else "sans_couvert"


def essence_score(category: str, cfg: dict, species: str = "cepe") -> dict:
    cat = cfg["essence_categories"][category]
    score = float(cfg["species"][species]["essences"].get(category, 0.0))
    return {
        "category": category,
        "label": cat["label"],
        "group": cat["group"],
        "score": score,
        "status": "ok" if score >= cfg["essence_ok_threshold"]
        else ("warn" if score >= 0.3 else "bad"),
    }


# ---------------------------------------------------------------------------
# Météo
# ---------------------------------------------------------------------------

def _window(days: list[dict], today: date, from_day: int, to_day: int) -> list[dict]:
    """Jours de J-from_day à J-to_day inclus (from_day > to_day)."""
    start, end = today - timedelta(days=from_day), today - timedelta(days=to_day)
    return [d for d in days if start <= date.fromisoformat(d["date"]) <= end]


def _avg(values) -> float | None:
    values = [v for v in values if v is not None]
    return mean(values) if values else None


def weather_score(days: list[dict], today: date, cfg: dict, species: str = "cepe") -> dict:
    """Calcule le score météo (0..1) d'une espèce et les facteurs explicatifs.

    `days` : liste de {date, rain, tmin, tmax, tmean, soil_t, soil_m}
    `today` : date de référence ; la fenêtre principale est J-7 … J-1.
    """
    w = cfg["species_weather"][species]
    main = _window(days, today, w["main_window_days"], 1)
    lag = _window(days, today, w["lag_window"]["from_day"], w["lag_window"]["to_day"])
    if len(main) < w["main_window_days"] - 1:
        return {"score": None, "factors": [], "summary": {}, "error": "historique météo incomplet"}

    rain_7d = sum(d["rain"] or 0 for d in main)
    rain_lag = sum(d["rain"] or 0 for d in lag)
    air_t = _avg(d["tmean"] for d in main)
    soil_t = _avg(d.get("soil_t") for d in main)
    use_soil = w["temperature"]["prefer"] == "soil" and soil_t is not None
    temp_7d = soil_t if use_soil else air_t
    tmin_7d = min((d["tmin"] for d in main if d["tmin"] is not None), default=None)
    soil_m = _avg(d.get("soil_m") for d in main)
    month = today.month

    factors = []

    f_rain = interp(w["rain_7d"]["points"], rain_7d)
    lo, hi = w["rain_7d"]["ok_range"]
    factors.append({
        "key": "rain", "label": "Pluie 7 j", "value": f"{rain_7d:.0f} mm",
        "effect": round(f_rain, 2),
        "status": _status(f_rain, lo <= rain_7d <= hi),
        "hint": None if lo <= rain_7d <= hi else ("trop sec" if rain_7d < lo else "détrempé"),
    })

    if temp_7d is None:
        f_temp = 0.5
        factors.append({"key": "temp", "label": "Température 7 j", "value": "n/d",
                        "effect": f_temp, "status": "warn", "hint": "donnée manquante"})
    else:
        f_temp = interp(w["temperature"]["points"], temp_7d)
        lo, hi = w["temperature"]["ok_range"]
        factors.append({
            "key": "temp", "label": "Sol 7 j" if use_soil else "Air 7 j",
            "value": f"{temp_7d:.1f} °C", "effect": round(f_temp, 2),
            "status": _status(f_temp, lo <= temp_7d <= hi),
            "hint": None if lo <= temp_7d <= hi else ("trop froid" if temp_7d < lo else "trop chaud"),
        })

    f_frost = 1.0 if tmin_7d is None else interp(w["frost"]["points"], tmin_7d)
    factors.append({
        "key": "frost", "label": "Gel",
        "value": "oui" if f_frost < 1 else "non",
        "effect": round(f_frost, 2), "status": "ok" if f_frost >= 1 else "bad",
        "hint": f"min {tmin_7d:.1f} °C" if tmin_7d is not None else None,
    })

    if soil_m is None:
        f_moist = 1.0
        factors.append({"key": "moisture", "label": "Humidité du sol", "value": "n/d",
                        "effect": 1.0, "status": "na", "hint": None})
    else:
        f_moist = interp(w["soil_moisture"]["points"], soil_m)
        factors.append({
            "key": "moisture", "label": "Humidité du sol", "value": f"{soil_m * 100:.0f} %",
            "effect": round(f_moist, 2),
            "status": "ok" if soil_m >= w["soil_moisture"]["ok_min"] else _status(f_moist, False),
            "hint": None,
        })

    lr = w["lagged_rain"]
    mild = temp_7d is not None and lr["mild_temp_range"][0] <= temp_7d <= lr["mild_temp_range"][1]
    f_lag = lr["bonus"] if rain_lag >= lr["min_rain_mm"] and mild else 1.0
    factors.append({
        "key": "lag", "label": "Pluie J-12…J-8", "value": f"{rain_lag:.0f} mm",
        "effect": f_lag, "status": "ok" if f_lag > 1 else "na",
        "hint": "bonus : pluie ancienne + temps doux" if f_lag > 1 else None,
    })

    f_season = float(w["season"][month])
    factors.append({
        "key": "season", "label": "Saison", "value": MONTHS_FR[month - 1],
        "effect": f_season,
        "status": "ok" if month in w["season_ok_months"] else _status(f_season, False),
        "hint": None if month in w["season_ok_months"] else "hors pleine saison",
    })

    score = f_rain * f_temp * f_frost * f_moist * f_lag * f_season
    return {
        "score": round(max(0.0, min(1.0, score)), 3),
        "factors": factors,
        "summary": {
            "rain_7d": round(rain_7d, 1), "rain_lag": round(rain_lag, 1),
            "temp_7d": None if temp_7d is None else round(temp_7d, 1),
            "temp_source": "sol" if use_soil else "air",
            "tmin_7d": tmin_7d, "soil_moisture_7d": None if soil_m is None else round(soil_m, 3),
        },
    }


def total_score(essence: float, weather: float | None) -> int | None:
    if weather is None:
        return None
    return int(round(100 * max(0.0, min(1.0, essence * weather))))
