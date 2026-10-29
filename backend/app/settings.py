"""Paramètres techniques (surchargeables par variables d'environnement)."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = Path(os.environ.get("CEPES_CONFIG_DIR", ROOT / "config"))
CACHE_DB = Path(os.environ.get("CEPES_CACHE_DB", ROOT / "backend" / "data" / "cache.sqlite"))

ALLOWED_HOSTS = os.environ.get("CEPES_ALLOWED_HOSTS", "localhost,127.0.0.1,backend").split(",")

WFS_URL ="https://data.geopf.fr/wfs/ows"
LAYER_FORESTS = "ONF.FORETS_PUBLIQUES:ONF_FORETS_PUBLIQUES"
LAYER_BDFORET = "LANDCOVER.FORESTINVENTORY.V2:formation_vegetale"
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
GEOCODE_URL = "https://data.geopf.fr/geocodage/search"

TILE_DEG = 0.2              # taille des tuiles de cache WFS (degrés)
MAX_TILES = 48              # au-delà, on demande de zoomer
WFS_PAGE_SIZE = 5000        # CountDefault de la Géoplateforme
WFS_CONCURRENCY = 8         # limite Géoplateforme : 30 req/s par IP
WFS_TTL = 30 * 24 * 3600    # géométries : 30 jours

WEATHER_GRID_DEG = 0.1      # ~10 km
WEATHER_TTL = 3 * 3600      # 3 h
WEATHER_BATCH = 50          # points par requête Open-Meteo
PAST_DAYS = 14
FORECAST_DAYS = 4           # aujourd'hui + 3 jours

MIN_PIECE_HA = 0.3          # zones plus petites ignorées
TOP_MAX_RADIUS_KM = 25
