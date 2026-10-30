"""Intersection forêts publiques ∩ BD Forêt, puis score par zone."""
from __future__ import annotations

import asyncio
import json
import math
import threading
from collections import OrderedDict, defaultdict

import httpx
import numpy as np
import shapely
from shapely.geometry import box
from shapely.strtree import STRtree

from . import weather, wfs
from .scoring import essence_category, essence_score, load_config, species_ids, total_score
from .settings import MIN_PIECE_HA

M_PER_DEG = 111_320.0
MAX_PIECES = 300_000
# (id forêt, id polygone BD Forêt) -> (géométrie GeoJSON, ha, lon, lat) ou None
_pieces: OrderedDict[tuple[str, str], tuple | None] = OrderedDict()
_pieces_lock = threading.Lock()


def forest_type(props: dict) -> str:
    if props.get("cdom_frt") == "OUI":
        return "domaniale"
    name = (props.get("llib_frt") or "").lower()
    if "communale" in name or "sectionale" in name or "intercommunale" in name:
        return "communale"
    return "autre"


def _areas_ha(geoms) -> np.ndarray:
    """Surfaces approchées (projection équirectangulaire locale), suffisantes pour pondérer."""
    lat = shapely.get_y(shapely.centroid(geoms))
    return shapely.area(geoms) * M_PER_DEG ** 2 * np.cos(np.radians(lat)) / 1e4


def _polygonal(geom):
    if geom.geom_type in ("Polygon", "MultiPolygon"):
        return geom
    polys = [g for g in getattr(geom, "geoms", []) if g.geom_type in ("Polygon", "MultiPolygon")]
    return shapely.union_all(polys) if polys else None


def _out_geoms(geoms, tol: float) -> list:
    g = shapely.set_precision(shapely.simplify(geoms, tol, preserve_topology=True), 1e-5)
    return [None if s is None else json.loads(s) for s in
            shapely.to_geojson(np.where(shapely.is_empty(g), None, g))]


def _compute(forests_raw: list, bd_raw: list, view: tuple) -> tuple[list, dict, list]:
    """Partie CPU (exécutée dans un thread). Renvoie (zones, forêts, contours)."""
    with _pieces_lock:
        return _compute_unlocked(forests_raw, bd_raw, view)


def _compute_unlocked(forests_raw: list, bd_raw: list, view: tuple) -> tuple[list, dict, list]:
    cfg = load_config()
    view_box = box(*view)
    fgeoms = np.array([f["geom"] for f in forests_raw], dtype=object)
    keep = shapely.intersects(fgeoms, view_box) if len(fgeoms) else np.array([], bool)
    forests_raw = [f for f, k in zip(forests_raw, keep) if k]
    fgeoms = fgeoms[keep]
    bgeoms = np.array([f["geom"] for f in bd_raw], dtype=object)

    forests, outlines = {}, []
    for f, og in zip(forests_raw, _out_geoms(fgeoms, 0.0001)):
        p = f["properties"]
        forests[f["id"]] = {"id": f["id"], "name": p.get("llib_frt") or "Forêt publique",
                            "type": forest_type(p), "dep": p.get("cinse_dep"),
                            "partial": not view_box.contains(f["geom"])}
        if og:
            outlines.append({"type": "Feature", "geometry": og,
                             "properties": {"forest_id": f["id"], "name": forests[f["id"]]["name"],
                                            "forest_type": forests[f["id"]]["type"]}})
    if not len(fgeoms) or not len(bgeoms):
        return [], forests, outlines

    fi, bi = STRtree(bgeoms).query(fgeoms, predicate="intersects")
    keys = [(forests_raw[a]["id"], bd_raw[b]["id"]) for a, b in zip(fi, bi)]
    todo = [n for n, k in enumerate(keys) if k not in _pieces]
    if todo:
        _cut_pieces([keys[n] for n in todo], fgeoms[fi[todo]], bgeoms[bi[todo]])

    zones = []
    for (fid, bid), n_bd in zip(keys, bi):
        piece = _pieces.get((fid, bid))
        if piece is None:
            continue
        _pieces.move_to_end((fid, bid))
        geom, ha, x, y = piece
        code = bd_raw[n_bd]["properties"].get("code_tfv")
        category = essence_category(code, cfg)
        cat = cfg["essence_categories"][category]
        props = {
            "forest_id": fid, "forest_name": forests[fid]["name"],
            "forest_type": forests[fid]["type"],
            "code_tfv": code, "tfv": cfg["tfv"].get(code, {}).get("label", code),
            "essence": category, "essence_label": cat["label"], "group": cat["group"],
            "area_ha": ha, "cell": weather.cell_of(x, y), "lon": x, "lat": y,
        }
        # Propriétés à plat (e_<espèce>) : MapLibre ne lit pas les objets imbriqués
        for sid in species_ids(cfg):
            props[f"e_{sid}"] = essence_score(category, cfg, sid)["score"]
        zones.append({"type": "Feature", "geometry": geom, "properties": props})
    while len(_pieces) > MAX_PIECES:
        _pieces.popitem(last=False)
    return zones, forests, outlines


def _cut_pieces(keys: list, fgeoms, bgeoms) -> None:
    """Intersections forêt × polygone BD Forêt, mémorisées (None = rien d'exploitable)."""
    inter = shapely.intersection(fgeoms, bgeoms)
    types = shapely.get_type_id(inter)
    for k in np.where((types != 3) & (types != 6))[0]:   # ni Polygon ni MultiPolygon
        inter[k] = None if shapely.is_empty(inter[k]) else _polygonal(inter[k])
    ok = ~shapely.is_missing(inter)
    ha = np.zeros(len(inter))
    ha[ok] = _areas_ha(inter[ok])
    ok &= ha >= MIN_PIECE_HA
    for k in np.where(~ok)[0]:
        _pieces[keys[k]] = None
    idx = np.where(ok)[0]
    if not len(idx):
        return
    pts = shapely.point_on_surface(inter[idx])
    xs, ys = shapely.get_x(pts), shapely.get_y(pts)
    for n, k, geom in zip(range(len(idx)), idx, _out_geoms(inter[idx], 0.00004)):
        _pieces[keys[k]] = None if geom is None else (
            geom, round(float(ha[k]), 2), round(float(xs[n]), 5), round(float(ys[n]), 5))


def _summarise_forests(zones: list, forests: dict) -> None:
    by_forest = defaultdict(list)
    for z in zones:
        by_forest[z["properties"]["forest_id"]].append(z["properties"])
    for fid, info in forests.items():
        pieces = by_forest.get(fid, [])
        total = sum(p["area_ha"] for p in pieces)
        shares = defaultdict(float)
        for p in pieces:
            shares[p["essence_label"]] += p["area_ha"]
        info["area_ha"] = round(total, 1)
        info["essences"] = [{"label": k, "share": round(v / total, 3)}
                            for k, v in sorted(shares.items(), key=lambda kv: -kv[1])][:6] if total else []
        info["scores"] = {}
        for sid in [*species_ids(load_config()), "best"]:
            key = f"s_{sid}"
            scored = [p for p in pieces if p[key] is not None]
            sa = sum(p["area_ha"] for p in scored)
            big = [p[key] for p in scored if p["area_ha"] >= 1]
            info["scores"][sid] = {
                "mean": round(sum(p[key] * p["area_ha"] for p in scored) / sa) if sa else None,
                "best": max(big) if big else None,
            }


async def compute_zones(view: tuple[float, float, float, float]) -> dict:
    """view = (min_lon, min_lat, max_lon, max_lat)."""
    tiles = wfs.tiles_for_bbox(*view)
    warnings: list[str] = []
    async with httpx.AsyncClient(headers={"User-Agent": "mushroom-finder/0.2"}) as client:
        forests_raw, bd_raw = await asyncio.gather(
            wfs.fetch_layer(client, "forests", tiles, warnings),
            wfs.fetch_layer(client, "bdforet", tiles, warnings),
        )
        zones, forests, outlines = await asyncio.to_thread(_compute, forests_raw, bd_raw, view)
        cells = {z["properties"]["cell"] for z in zones}
        meteo = await weather.get_cells(client, cells, warnings)

    ids = species_ids(load_config())
    for z in zones:
        p = z["properties"]
        per_species = (meteo.get(p["cell"]) or {}).get("species", {})
        best_sid, best = None, None
        for sid in ids:
            s = total_score(p[f"e_{sid}"], (per_species.get(sid) or {}).get("score"))
            p[f"s_{sid}"] = s
            if s is not None and (best is None or s > best):
                best_sid, best = sid, s
        p["s_best"], p["best_species"] = best, best_sid
    _summarise_forests(zones, forests)
    if not forests_raw and any("ONF" in w for w in warnings):
        raise wfs.ServiceUnavailable(" ".join(dict.fromkeys(warnings)))
    return {
        "zones": {"type": "FeatureCollection", "features": zones},
        "outlines": {"type": "FeatureCollection", "features": outlines},
        "forests": forests,
        "weather": meteo,
        "warnings": list(dict.fromkeys(warnings)),
    }


def haversine_km(lon1, lat1, lon2, lat2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(a))


async def top_zones(lon: float, lat: float, radius_km: float, limit: int = 10,
                    groups: set[str] | None = None, forest_types: set[str] | None = None,
                    min_score: int = 0, species: str = "cepe") -> dict:
    """Meilleure zone de chaque forêt pour `species` (ou "best" : toutes espèces confondues)."""
    key = f"s_{species}"
    dlat = radius_km / 111.32
    dlon = radius_km / (111.32 * math.cos(math.radians(lat)))
    res = await compute_zones((lon - dlon, lat - dlat, lon + dlon, lat + dlat))
    best: dict[str, dict] = {}
    for z in res["zones"]["features"]:
        p = z["properties"]
        score = p[key]
        if score is None or score < min_score or p["area_ha"] < 1:
            continue
        if groups and p["group"] not in groups:
            continue
        if forest_types and p["forest_type"] not in forest_types:
            continue
        d = haversine_km(lon, lat, p["lon"], p["lat"])
        if d > radius_km:
            continue
        cur = best.get(p["forest_id"])
        if cur is None or (score, p["area_ha"]) > (cur["score"], cur["area_ha"]):
            best[p["forest_id"]] = {**p, "score": score, "distance_km": round(d, 1),
                                    "species": p["best_species"] if species == "best" else species}
    ranked = sorted(best.values(), key=lambda p: (-p["score"], p["distance_km"]))[:limit]
    return {"results": ranked, "warnings": res["warnings"]}
