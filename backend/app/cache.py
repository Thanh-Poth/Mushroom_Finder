"""Cache clé/valeur SQLite (JSON compressé) avec TTL et lecture « périmée » en secours."""
import json
import sqlite3
import threading
import time
import zlib

from .settings import CACHE_DB

_lock = threading.Lock()
CACHE_DB.parent.mkdir(parents=True, exist_ok=True)
_conn = sqlite3.connect(CACHE_DB, check_same_thread=False)
_conn.execute("PRAGMA journal_mode=WAL")
_conn.execute("CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, ts REAL, value BLOB)")


def get(key: str, ttl: float, allow_stale: bool = False):
    """Renvoie (valeur, frais) ou None. Avec allow_stale, ignore le TTL."""
    with _lock:
        row = _conn.execute("SELECT ts, value FROM kv WHERE key = ?", (key,)).fetchone()
    if row is None:
        return None
    fresh = time.time() - row[0] < ttl
    if not fresh and not allow_stale:
        return None
    return json.loads(zlib.decompress(row[1])), fresh


def put(key: str, value) -> None:
    blob = zlib.compress(json.dumps(value, separators=(",", ":")).encode())
    with _lock:
        _conn.execute("INSERT OR REPLACE INTO kv VALUES (?, ?, ?)", (key, time.time(), blob))
        _conn.commit()
