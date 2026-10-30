# 🍄 Mushroom Finder

[Français](README.md) · **English**

Mushroom Finder is an interactive map. It estimates the chance of finding **six of the most popular
edible mushrooms** in every area of the **public forests** of mainland France. To do this, it combines
three sources:

1. the **public forests** managed by the ONF, the French National Forests Office (state forests, town forests…),
2. the **tree species** from BD Forêt® V2, a forest map made by IGN, the French national mapping agency,
3. the **weather of the last 14 days**, plus a 3-day forecast (Open-Meteo).

Each area (a public forest cut by the BD Forêt tree stands) gets a score from 0 to 100 **for each species**.
Click on an area to see how the score was calculated.

| Species | Latin name | Main season | Trees it likes most | Dangerous look-alikes shown |
|---|---|---|---|---|
| **Porcini** (cèpes) | *Boletus edulis, aereus, pinophilus, reticulatus* | Sept. – Nov. | oak, beech, sweet chestnut, fir/spruce, pines | Satan's bolete (toxic) |
| **Chanterelles** (girolles) | *Cantharellus cibarius* | July – Oct. | oak, beech, sweet chestnut, fir/spruce | Jack-o'-lantern mushroom (toxic) |
| **Black trumpets** (trompettes de la mort) | *Craterellus cornucopioides* | Sept. – Nov. | beech, oak | few dangerous look-alikes |
| **Hedgehog mushrooms** (pieds-de-mouton) | *Hydnum repandum* | Oct. – Dec. | beech, oak, fir/spruce, mixed stands | no major toxic look-alike |
| **Morels** (morilles) | *Morchella esculenta, M. elata* | March – May | poplar plantations, ash and elm, cleared areas | **False morel (deadly)**, thimble morel (toxic); toxic when raw |
| **Saffron milk caps** (lactaires délicieux / sanguins) | *Lactarius deliciosus, L. sanguifluus* | Oct. – Nov. | pines (including Aleppo pine) | Woolly milk cap (toxic) |

Caesar's mushroom was left out on purpose, because it can be confused with deadly amanitas.
Truffles were also left out: they grow underground, often in private truffle orchards.

> **This is only an estimate, not a promise.** Only eat mushrooms that a pharmacist or a
> mycological society has identified with certainty.

The app interface is in French. The main button labels are translated in the "How to use it" section below.

## Getting started

### Option A: Docker

```bash
docker compose up --build
```

Then open http://localhost:5173.

### Option B: two terminals (without Docker)

You need Python 3.11 or newer and Node 20.19 or newer.

```bash
# Terminal 1: API (http://localhost:8000)
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt     # Linux/macOS: .venv/bin/pip
.venv/Scripts/uvicorn app.main:app --port 8000     # Linux/macOS: .venv/bin/uvicorn

# Terminal 2: user interface (http://localhost:5173)
cd frontend
npm install
npm run dev
```

The map opens on the test area of Gérardmer, in the Vosges mountains. It works everywhere in mainland France.

## How to use it

- **Choose the mushroom** you are looking for ("Champignon recherché"), or **Toutes les espèces** (all species) to colour each area with its most likely species.
- **Zoom in** (level 11 or more) to show the forests. The app only loads data for the area you can see.
  - The first time you open an area, it takes 5 to 30 seconds, because the app downloads data from IGN.
  - After that, it takes about 1 second, thanks to the cache.
- **Search for a town** with "Rechercher une ville…", or use **📍 Me localiser** (locate me).
- **Click on an area** to see:
  - the forest name and its type;
  - the tree species of the area and the main tree species of the whole forest;
  - the score and the factors behind it (✓ good / ⚠ average / ✗ bad) for the chosen species;
  - the score of all six species in this area (click one to switch species);
  - the dangerous look-alikes of the species and safety advice (for example, morels must be well cooked);
  - a chart of rain and temperature for the last 14 days, plus the forecast.
- **Filters** ("Filtres"): tree species, forest type (state / town / other), minimum score.
- **🎯 Top 10 autour de moi** (top 10 near me): the best area (1 ha or more) of each forest for the chosen species, within a radius you can set from 2 to 25 km.
  - The active filters also apply to this ranking.
  - If your location is not available, the app searches around the centre of the map.
- **🛰 Photo aérienne** (aerial photo): switches between the IGN map and aerial photos.

## How the score works

```
score(species) = 100 × tree_score(species) × weather_score(species)        (limited to 0–100)
weather_score  = rain × temperature × frost × soil_moisture × earlier_rain × season   (limited to 0–1)
```

All the thresholds are in [config/scoring.yaml](config/scoring.yaml). If you change them, restart the backend.
Each species has its own `species` section in this file: a score for each tree type, weather factors that
replace the default ones (`weather_defaults`), a value for each month of the year, and look-alikes.
To add a species, copy one section and change it. The "all species" mode keeps the best score of each area.

Values for **porcini** (the other species mainly change the temperature range and the season):

| Factor | Data | Values (porcini) |
|---|---|---|
| **Tree type** | BD Forêt TFV code → category ([config/tfv_mapping.yaml](config/tfv_mapping.yaml)) | oak, beech, sweet chestnut 1.0 · fir/spruce 0.9 · pines 0.85 · mixed stands 0.4–0.75 · Douglas fir 0.15 · poplar, black locust, heathland 0 |
| **Rain over 7 days** | total from day -7 to day -1 | 20–60 mm = 1; under 10 mm ≤ 0.25; over 100 mm ≤ 0.55 |
| **Temperature over 7 days** | soil at 0–7 cm (or air if soil data is missing) | 10–18 °C = 1; under 5 °C ≤ 0.15; over 22 °C ≤ 0.4 |
| **Frost** | lowest air temperature over 7 days | 0.5 °C or more = 1; under 0 °C → ×0.45; -5 °C or less → ×0.1 |
| **Soil moisture** | average at 0–7 cm | 0.10 m³/m³ → ×0.8; 0.30 or more → ×1.15 to 1.2 |
| **Earlier rain** | total from day -12 to day -8 is 20 mm or more **and** the 7-day temperature is between 10 and 18 °C | ×1.2 (mushrooms grow 7 to 12 days after rain) |
| **Season** | current month | Sept.–Oct. 1.0 · Nov. 0.9 · summer 0.6–0.7 · Dec.–March 0.1–0.3 |

Main differences between species: chanterelles 12–20 °C (summer), black trumpets 9–16 °C and very wet soil,
hedgehog mushrooms 6–15 °C and they accept light frost, morels 8–14 °C in spring, saffron milk caps only under pines.

Map legend: 60 or more = very likely (dark green), 40 or more = likely, 20 or more = possible (orange), under 20 = unlikely (grey).
A light grey area means "weather data not available".

## Architecture

```
backend/   FastAPI: WFS requests by 0.2° tiles, shapely intersection, score, SQLite cache
frontend/  React + Vite + MapLibre GL: IGN WMTS base map, coloured GeoJSON polygons
config/    scoring.yaml (thresholds), tfv_mapping.yaml (32 TFV codes → categories)
docs/      DATA_SOURCES.md (layers, fields, licences, tested requests; in French)
```

- **Geometries**:
  - the app queries the Géoplateforme WFS service with fixed 0.2° tiles, pages of 5,000 features, and at most 8 requests at the same time;
  - tiles are stored as WKB in SQLite for 30 days;
  - forest × tree-stand intersections are kept in memory.
- **Weather**:
  - grid of 0.1° (about 10 km);
  - up to 50 points per Open-Meteo request;
  - 3-hour cache.
- **When a service is down**:
  - the app uses cached data, even if it is old, and shows a warning;
  - with no cache, the area is missing or its weather is shown in grey;
  - if the ONF service is down and nothing is cached, the API returns a 503 error with a clear message.

### API

| Route | Description |
|---|---|
| `GET /api/zones?bbox=minLon,minLat,maxLon,maxLat` | scored areas for all species (properties `s_<species>`, `s_best`, `best_species`), forest outlines, summary per forest, weather per grid cell, warnings |
| `GET /api/top?lat=&lon=&radius_km=10&species=girolle&forest_types=domaniale&min_score=0` | top N areas around a point. `species`: `cepe`, `girolle`, `trompette`, `pied_de_mouton`, `morille`, `lactaire` or `best`; `groups` filters tree types (for example `Chênes`, several values separated by a vertical bar) |
| `GET /api/geocode?q=` | town search (IGN geocoding) |
| `GET /api/meta` | legend classes, tree type groups, species (season, look-alikes) |

Values sent to and returned by the API are in French (for example `domaniale` = state forest, `communale` = town forest, `Chênes` = oaks).

## Tests

```bash
cd backend
.venv/Scripts/python -m pytest
```

- **Score**: dry summer, mild and wet autumn, frost, waterlogged soil, poplar stand, missing soil temperature.
- **Species**: chanterelles in summer, morels in spring under poplars (and not in autumn), black trumpets under beech rather than pine, hedgehog mushrooms in early winter, saffron milk caps only under pines, consistent configuration.
- **Mapping**: all 32 TFV codes are recognised.
- **Resilience**: WFS outage with and without cache, weather API outage.
- **Security**: cross-site requests and unknown hosts are refused, no CORS header, limited parameters.

## Sources and licences

More details (in French) in [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md).

| Data | Producer | Licence |
|---|---|---|
| BD Forêt® V2, IGN map, aerial photos, geocoding | IGN – Géoplateforme | Licence Ouverte Etalab 2.0 (open licence) |
| Public forests | ONF (through Géoplateforme) | Licence Ouverte 2.0 (open licence) |
| Weather | Open-Meteo.com | CC BY 4.0; the free API is for **non-commercial** use only |

The credits are shown at the bottom of the map.

## Rules for picking mushrooms

You may only pick mushrooms if you follow the local rules:
- the amount allowed per person and per day depends on local orders from the prefecture (often 5 litres in state forests);
- selling the mushrooms is forbidden;
- picking is forbidden in private forests without the owner's permission, and in some nature reserves.

See the [ONF picking rules](https://www.onf.fr/vivre-la-foret/que-faire-en-foret/regles-et-bonnes-pratiques-en-foret/+/2891::conseils-precautions-comment-bien-cueillir-champignons-et-chataignes-en-foret.html) (in French).

## Known limits

- **Species profiles are approximate**: they are based on the general ecology of each species. Morels depend a lot on things that are not in the data (single ash trees, burnt areas, chalky soil, orchards), and the bloody milk cap of southern France is not separated from the saffron milk cap.
- **Simple model, not calibrated**: the thresholds are starting values. They should be adjusted with real harvest data. The model does not use soil type (pH), altitude, slope direction, tree age or how many people pick in the area.
- **BD Forêt V2 dates from 2006 to 2019, depending on the department**: recent tree felling, storms and tree diseases (such as bark beetles on spruce) are not included.
- **Mixed stands** ("mixed broadleaves", "mostly broadleaves with conifers"…) do not say which species they contain. They get a middle score, even though they often contain oak or beech.
- **The weather comes from a model**, not from weather stations, with a resolution of about 10 km. A local storm can be missed, and the terrain is only partly taken into account.
- **Forest type**: the ONF only says whether a forest is a state forest or not. The "town forest" type is guessed from the forest name.
- **Forests larger than the screen**: the main species and the average score only use the part of the forest that is loaded (the app shows "partie affichée", meaning "visible part").
- **Only public forests are covered**: private forests (about 75% of French forests) are not shown. This is on purpose, because picking there is forbidden without permission.
- **Usage limits**: the free Open-Meteo API allows 10,000 calls per day, and the Géoplateforme allows 30 requests per second.
