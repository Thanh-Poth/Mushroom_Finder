from datetime import date, timedelta

import pytest

from app.scoring import (essence_category, essence_score, interp, load_config,
                         total_score, weather_score)

CFG = load_config()


def make_days(today: date, rain: list[float], tmean: float, tmin: float | None = None,
              soil_t: float | None = None, soil_m: float | None = 0.3,
              lag_rain: float = 0.0) -> list[dict]:
    """14 jours d'historique : J-14…J-8 (pluie `lag_rain` répartie), puis J-7…J-1 = `rain`."""
    days = []
    for k in range(14, 0, -1):
        d = today - timedelta(days=k)
        r = rain[7 - k] if k <= 7 else lag_rain / 7
        days.append({"date": d.isoformat(), "rain": r, "tmean": tmean,
                     "tmin": tmean - 4 if tmin is None else tmin, "tmax": tmean + 4,
                     "soil_t": soil_t, "soil_m": soil_m})
    return days


def score_for(category, species="cepe", **kw):
    today = kw.pop("today")
    w = weather_score(make_days(today, **kw), today, CFG, species)
    return total_score(essence_score(category, CFG, species)["score"], w["score"]), w


def test_interp():
    pts = [[0, 0], [10, 1], [20, 1], [30, 0]]
    assert interp(pts, -5) == 0
    assert interp(pts, 5) == pytest.approx(0.5)
    assert interp(pts, 15) == 1
    assert interp(pts, 40) == 0


def test_all_tfv_codes_mapped_to_known_category():
    for code, entry in CFG["tfv"].items():
        assert entry["category"] in CFG["essence_categories"], code
    assert len(CFG["tfv"]) == 32


def test_essence_mapping():
    assert essence_category("FF1G01-01", CFG) == "chene"
    assert essence_category("FF1-09-09", CFG) == "hetre"
    assert essence_category("FP", CFG) == "peupleraie"
    assert essence_category("INCONNU", CFG) == "sans_couvert"
    assert essence_score("peupleraie", CFG)["score"] == 0


def test_dry_summer_is_unlikely():
    s, w = score_for("chene", today=date(2026, 8, 10), rain=[0, 0, 1, 0, 0, 1, 0],
                     tmean=24, soil_t=23, soil_m=0.08)
    assert s < 10
    status = {f["key"]: f["status"] for f in w["factors"]}
    assert status["rain"] == "bad"
    assert status["temp"] != "ok"
    assert status["season"] != "ok"


def test_mild_wet_autumn_is_very_likely():
    s, w = score_for("chene", today=date(2026, 10, 15), rain=[8, 12, 4, 0, 6, 5, 3],
                     tmean=13, soil_t=13, soil_m=0.32, lag_rain=25)
    assert s >= 80
    assert all(f["status"] in ("ok", "na") for f in w["factors"])
    assert w["summary"]["rain_7d"] == 38


def test_frost_strongly_penalises():
    base = dict(today=date(2026, 11, 5), rain=[8, 12, 4, 0, 6, 5, 3], tmean=10,
                soil_t=10, soil_m=0.3)
    s_ok, _ = score_for("hetre", **base)
    s_frost, w = score_for("hetre", tmin=-3, **base)
    assert s_frost < s_ok * 0.3
    frost = next(f for f in w["factors"] if f["key"] == "frost")
    assert frost["value"] == "oui" and frost["status"] == "bad"


def test_waterlogged_is_penalised():
    ok, _ = score_for("pin", today=date(2026, 10, 1), rain=[6] * 7, tmean=14, soil_t=14)
    wet, _ = score_for("pin", today=date(2026, 10, 1), rain=[25] * 7, tmean=14, soil_t=14)
    assert wet < ok


def test_poplar_is_zero_even_in_perfect_weather():
    s, _ = score_for("peupleraie", today=date(2026, 10, 15), rain=[6] * 7, tmean=13, soil_t=13)
    assert s == 0


def test_air_temperature_fallback_and_incomplete_history():
    today = date(2026, 10, 15)
    w = weather_score(make_days(today, rain=[5] * 7, tmean=12, soil_t=None), today, CFG)
    assert w["summary"]["temp_source"] == "air"
    assert weather_score([], today, CFG)["score"] is None
    assert total_score(1.0, None) is None


# --- Espèces -----------------------------------------------------------------

AUTUMN = dict(rain=[8, 12, 4, 0, 6, 5, 3], soil_m=0.32, lag_rain=25)


def test_species_config_is_consistent():
    assert len(CFG["species"]) >= 6
    for sid, sp in CFG["species"].items():
        assert set(sp["essences"]) <= set(CFG["essence_categories"]), sid
        assert sorted(sp["season"]) == list(range(1, 13)), sid
        assert all(0 <= v <= 1 for v in sp["essences"].values()), sid
        assert sp["lookalikes"], sid


def test_chanterelle_peaks_in_warm_wet_summer():
    kw = dict(today=date(2026, 8, 20), tmean=17, soil_t=17, **AUTUMN)
    girolle, _ = score_for("chene", "girolle", **kw)
    cepe, _ = score_for("chene", "cepe", **kw)
    assert girolle >= 80 and girolle > cepe


def test_morel_spring_under_poplar_not_autumn():
    spring, _ = score_for("peupleraie", "morille", today=date(2026, 4, 15),
                          rain=[5, 0, 8, 4, 0, 6, 2], tmean=11, soil_t=11, soil_m=0.3)
    autumn, _ = score_for("peupleraie", "morille", today=date(2026, 10, 15),
                          rain=[5, 0, 8, 4, 0, 6, 2], tmean=11, soil_t=11, soil_m=0.3)
    cepe_poplar, _ = score_for("peupleraie", "cepe", today=date(2026, 10, 15),
                               rain=[5, 0, 8, 4, 0, 6, 2], tmean=11, soil_t=11, soil_m=0.3)
    assert spring >= 70 and autumn < 10 and cepe_poplar == 0


def test_black_trumpet_prefers_beech_over_pine():
    kw = dict(today=date(2026, 10, 20), tmean=12, soil_t=12, rain=[10] * 7, soil_m=0.35)
    beech, _ = score_for("hetre", "trompette", **kw)
    pine, _ = score_for("pin", "trompette", **kw)
    assert beech >= 80 and pine < 15


def test_hedgehog_tolerates_cold_early_winter_better_than_porcini():
    kw = dict(today=date(2026, 12, 5), tmean=5, tmin=-1, soil_t=6, rain=[5] * 7, soil_m=0.33)
    hedgehog, w = score_for("hetre", "pied_de_mouton", **kw)
    cepe, _ = score_for("hetre", "cepe", **kw)
    assert hedgehog > 3 * cepe
    assert next(f for f in w["factors"] if f["key"] == "season")["status"] == "ok"


def test_saffron_milk_cap_only_under_pines():
    kw = dict(today=date(2026, 10, 25), tmean=13, soil_t=13, **AUTUMN)
    pine, _ = score_for("pin", "lactaire", **kw)
    oak, _ = score_for("chene", "lactaire", **kw)
    assert pine >= 80 and oak == 0
