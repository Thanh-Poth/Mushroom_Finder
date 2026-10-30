"""API FastAPI « Mushroom Finder »."""
import logging

import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import wfs
from .scoring import load_config, species_ids
from .settings import ALLOWED_HOSTS, GEOCODE_URL, TOP_MAX_RADIUS_KM
from .zones import compute_zones, top_zones

logging.basicConfig(level=logging.INFO)
app = FastAPI(title="Mushroom Finder API", version="0.2.0")
# Pas de CORS : le frontend passe par le proxy Vite (même origine).
# Host contrôlé contre le DNS rebinding.
app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)
app.add_middleware(GZipMiddleware, minimum_size=2000)


@app.middleware("http")
async def reject_cross_site(request: Request, call_next):
    # Empêche un site tiers ouvert dans le navigateur de déclencher des appels (quotas IGN / Open-Meteo)
    if request.headers.get("sec-fetch-site") == "cross-site":
        return JSONResponse({"detail": "Requête inter-sites refusée"}, status_code=403)
    return await call_next(request)


def _parse_bbox(bbox: str) -> tuple[float, float, float, float]:
    try:
        v = tuple(float(x) for x in bbox.split(","))
        assert len(v) == 4 and v[0] < v[2] and v[1] < v[3]
    except (ValueError, AssertionError):
        raise HTTPException(400, "bbox attendu : minLon,minLat,maxLon,maxLat")
    return v


async def _guard(coro):
    try:
        return await coro
    except wfs.TooLarge as e:
        raise HTTPException(400, str(e))
    except wfs.ServiceUnavailable as e:
        raise HTTPException(503, str(e))


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/meta")
def meta():
    cfg = load_config()
    groups = list(dict.fromkeys(e["group"] for e in cfg["essence_categories"].values()))
    species = [{"id": sid, "label": sp["label"], "latin": sp["latin"], "color": sp["color"],
                "season_ok_months": sp["season_ok_months"], "lookalikes": sp.get("lookalikes", []),
                "note": sp.get("note")}
               for sid, sp in cfg["species"].items()]
    return {"classes": cfg["classes"], "groups": groups, "species": species,
            "essence_ok_threshold": cfg["essence_ok_threshold"]}


@app.get("/api/zones")
async def zones(bbox: str):
    return await _guard(compute_zones(_parse_bbox(bbox)))


@app.get("/api/top")
async def top(lat: float, lon: float, radius_km: float = Query(10, gt=0),
              limit: int = Query(10, ge=1, le=50), groups: str = "", forest_types: str = "",
              min_score: int = 0, species: str = "cepe"):
    if species != "best" and species not in species_ids(load_config()):
        raise HTTPException(400, "Espèce inconnue")
    radius = min(radius_km, TOP_MAX_RADIUS_KM)
    g = {x for x in groups.split("|") if x} or None
    t = {x for x in forest_types.split("|") if x} or None
    res = await _guard(top_zones(lon, lat, radius, limit, g, t, min_score, species))
    return res | {"radius_km": radius}


@app.get("/api/geocode")
async def geocode(q: str = Query(..., min_length=2, max_length=200)):
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(GEOCODE_URL, params={"q": q, "limit": 6}, timeout=15)
            r.raise_for_status()
    except httpx.HTTPError:
        raise HTTPException(503, "Service de géocodage IGN indisponible")
    return [{"label": f["properties"]["label"], "context": f["properties"].get("context", ""),
             "type": f["properties"].get("type"),
             "lon": f["geometry"]["coordinates"][0], "lat": f["geometry"]["coordinates"][1]}
            for f in r.json().get("features", [])]
