"""Services indisponibles : on doit retomber sur le cache ou renvoyer un message clair."""
import asyncio

import httpx

from app import cache, weather, wfs


class DownClient:
    async def get(self, *args, **kwargs):
        raise httpx.ConnectError("service coupé")


def test_wfs_outage_uses_stale_cache():
    key = "wfs2:forests:999:999"
    feats = [{"id": "F1", "properties": {"llib_frt": "Test"},
              "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]}}]
    cache.put(key, wfs._encode(feats))
    cache._conn.execute("UPDATE kv SET ts = 0 WHERE key = ?", (key,))   # entrée périmée
    warnings = []
    out = asyncio.run(wfs.fetch_tile(DownClient(), "forests", (999, 999), warnings))
    assert out[0]["id"] == "F1" and out[0]["geom"].area == 0.5
    assert "en cache" in warnings[0]


def test_wfs_outage_without_cache_warns():
    warnings = []
    out = asyncio.run(wfs.fetch_tile(DownClient(), "bdforet", (998, 998), warnings))
    assert out == []
    assert "indisponible" in warnings[0]


def test_weather_outage_gives_null_score_and_warning():
    warnings = []
    out = asyncio.run(weather.get_cells(DownClient(), {"9999_9999"}, warnings))
    assert out["9999_9999"]["score"] is None
    assert "Open-Meteo" in warnings[0]
