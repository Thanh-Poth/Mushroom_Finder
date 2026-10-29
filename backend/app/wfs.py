"""Client WFS Géoplateforme : requêtes par tuiles fixes, pagination, cache disque."""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import math
from collections import OrderedDict

import httpx
import numpy as np
import shapely

from . import cache
from .settings import (LAYER_BDFORET, LAYER_FORESTS, MAX_TILES, TILE_DEG, WFS_CONCURRENCY,
                       WFS_PAGE_SIZE, WFS_TTL, WFS_URL)

log = logging.getLogger(__name__)
_sem = asyncio.Semaphore(WFS_CONCURRENCY)
_mem: OrderedDict[str, list] = OrderedDict()   # tuiles décodées en mémoire
MEM_TILES = 300

LAYERS = {
    "forests": {"name": LAYER_FORESTS, "props": None, "id": "iidtn_frt",
                "label": "ONF – forêts publiques"},
    "bdforet": {"name": LAYER_BDFORET, "props": "code_tfv,essence,geom", "id": None,
                "label": "IGN – BD Forêt V2"},
}


class TooLarge(Exception):
    pass


class ServiceUnavailable(Exception):
    pass


def tiles_for_bbox(min_lon, min_lat, max_lon, max_lat) -> list[tuple[int, int]]:
    i0, i1 = math.floor(min_lon / TILE_DEG), math.floor(max_lon / TILE_DEG)
    j0, j1 = math.floor(min_lat / TILE_DEG), math.floor(max_lat / TILE_DEG)
    tiles = [(i, j) for i in range(i0, i1 + 1) for j in range(j0, j1 + 1)]
    if len(tiles) > MAX_TILES:
        raise TooLarge(f"Zone trop grande ({len(tiles)} tuiles) : zoomez davantage.")
    return tiles


def tile_bounds(tile: tuple[int, int]) -> tuple[float, float, float, float]:
    i, j = tile
    return (round(i * TILE_DEG, 6), round(j * TILE_DEG, 6),
            round((i + 1) * TILE_DEG, 6), round((j + 1) * TILE_DEG, 6))


async def _fetch_tile_remote(client: httpx.AsyncClient, layer: dict, tile) -> list:
    min_lon, min_lat, max_lon, max_lat = tile_bounds(tile)
    params = {
        "SERVICE": "WFS", "VERSION": "2.0.0", "REQUEST": "GetFeature",
        "TYPENAMES": layer["name"], "OUTPUTFORMAT": "application/json",
        "SRSNAME": "EPSG:4326", "COUNT": WFS_PAGE_SIZE,
        # urn EPSG:4326 => ordre lat,lon
        "BBOX": f"{min_lat},{min_lon},{max_lat},{max_lon},urn:ogc:def:crs:EPSG::4326",
    }
    if layer["props"]:
        params["PROPERTYNAME"] = layer["props"]
    out, start = [], 0
    while True:
        async with _sem:
            r = await client.get(WFS_URL, params={**params, "STARTINDEX": start}, timeout=90)
        r.raise_for_status()
        feats = r.json().get("features", [])
        for f in feats:
            p = f.get("properties") or {}
            fid = p.get(layer["id"]) if layer["id"] else f.get("id")
            p = {k: (v.replace("\x92", "'") if isinstance(v, str) else v) for k, v in p.items()}
            if f.get("geometry"):
                out.append({"id": fid, "properties": p, "geometry": f["geometry"]})
        if len(feats) < WFS_PAGE_SIZE:
            return _encode(out)
        start += WFS_PAGE_SIZE


def _encode(feats: list) -> list:
    """GeoJSON -> WKB base64 (géométries rendues valides), bien plus rapide à relire."""
    if not feats:
        return []
    geoms = shapely.from_geojson([json.dumps(f.pop("geometry")) for f in feats])
    bad = ~shapely.is_valid(geoms)
    geoms[bad] = shapely.make_valid(geoms[bad])
    for f, wkb in zip(feats, shapely.to_wkb(geoms)):
        f["wkb"] = base64.b64encode(wkb).decode()
    return feats


def _decode(feats: list) -> list:
    if feats:
        geoms = shapely.from_wkb(np.array([base64.b64decode(f["wkb"]) for f in feats], dtype=object))
        for f, g in zip(feats, geoms):
            f["geom"] = g
            del f["wkb"]
    return feats


def _remember(key: str, feats: list) -> list:
    _mem[key] = feats
    _mem.move_to_end(key)
    while len(_mem) > MEM_TILES:
        _mem.popitem(last=False)
    return feats


async def fetch_tile(client, layer_key: str, tile, warnings: list) -> list:
    layer = LAYERS[layer_key]
    key = f"wfs2:{layer_key}:{tile[0]}:{tile[1]}"
    if key in _mem:
        _mem.move_to_end(key)
        return _mem[key]
    hit = cache.get(key, WFS_TTL)
    if hit:
        return _remember(key, _decode(hit[0]))
    try:
        feats = await _fetch_tile_remote(client, layer, tile)
        cache.put(key, feats)
        return _remember(key, _decode(feats))
    except (httpx.HTTPError, ValueError) as e:
        log.warning("WFS %s tuile %s : %s", layer_key, tile, e)
        stale = cache.get(key, WFS_TTL, allow_stale=True)
        msg = f"Service {layer['label']} indisponible"
        if stale:
            warnings.append(f"{msg} : données en cache utilisées.")
            return _decode(stale[0])
        warnings.append(f"{msg} : une partie de la zone n'a pas pu être chargée.")
        return []


async def fetch_layer(client, layer_key: str, tiles, warnings: list) -> list:
    """Toutes les entités des tuiles, dédoublonnées par identifiant."""
    results = await asyncio.gather(*(fetch_tile(client, layer_key, t, warnings) for t in tiles))
    seen, out = set(), []
    for feats in results:
        for f in feats:
            if f["id"] in seen:
                continue
            seen.add(f["id"])
            out.append(f)
    return out
