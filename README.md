# 🍄 Mushroom Finder

**Français** · [English](README.en.md)

Carte interactive qui estime, pour chaque zone des **forêts publiques** de France métropolitaine,
la probabilité de trouver **six champignons comestibles parmi les plus recherchés** en croisant :

1. les **forêts publiques** de l'ONF (domaniales, communales…),
2. les **essences d'arbres** de la BD Forêt® V2 de l'IGN,
3. la **météo des 14 derniers jours** + 3 jours de prévision (Open-Meteo).

Chaque zone (forêt publique ∩ peuplement BD Forêt) reçoit un score de 0 à 100 **pour chaque espèce**,
avec le détail du calcul au clic.

| Espèce | Nom latin | Pleine saison | Arbres associés (score max) | Sosies dangereux signalés |
|---|---|---|---|---|
| **Cèpes** | *Boletus edulis, aereus, pinophilus, reticulatus* | sept. – nov. | chênes, hêtre, châtaignier, sapin/épicéa, pins | Bolet Satan (toxique) |
| **Girolles** | *Cantharellus cibarius* | juil. – oct. | chênes, hêtre, châtaignier, sapin/épicéa | Clitocybe de l'olivier (toxique) |
| **Trompettes de la mort** | *Craterellus cornucopioides* | sept. – nov. | hêtre, chênes | peu de confusion dangereuse |
| **Pieds-de-mouton** | *Hydnum repandum* | oct. – déc. | hêtre, chênes, sapin/épicéa, mélanges | pas de sosie toxique majeur |
| **Morilles** | *Morchella esculenta, M. elata* | mars – mai | peupleraies, frênes et ormes, coupes | **Gyromitre (mortel)**, Verpe (toxique) ; toxique crue |
| **Lactaires délicieux / sanguins** | *Lactarius deliciosus, L. sanguifluus* | oct. – nov. | pins (y compris pin d'Alep) | Lactaire à toison (toxique) |

Les amanites des Césars (risque de confusion avec des amanites mortelles) et les truffes (souterraines,
souvent en truffières privées) ont été volontairement écartées.

> **Estimation indicative, pas une garantie.** Ne consommez que des champignons identifiés avec
> certitude par un pharmacien ou une association mycologique.

## Démarrage

### Option A : Docker

```bash
docker compose up --build
```

Puis ouvrir http://localhost:5173.

### Option B : deux terminaux (sans Docker)

Prérequis : Python ≥ 3.11 et Node ≥ 20.19.

```bash
# Terminal 1 : API (http://localhost:8000)
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt     # Linux/macOS : .venv/bin/pip
.venv/Scripts/uvicorn app.main:app --port 8000     # Linux/macOS : .venv/bin/uvicorn

# Terminal 2 : interface (http://localhost:5173)
cd frontend
npm install
npm run dev
```

La carte s'ouvre sur la zone test de Gérardmer (Vosges). Elle fonctionne partout en France métropolitaine.

## Utilisation

- **Choisissez le champignon** recherché, ou **Toutes les espèces** pour colorer chaque zone selon l'espèce la plus probable.
- **Zoomez** (niveau ≥ 11) pour afficher les forêts. Les données sont chargées à la demande pour la zone visible.
  - Le premier passage sur une zone prend 5 à 30 s, le temps d'interroger l'IGN.
  - Les passages suivants prennent environ 1 s grâce au cache.
- **Rechercher une ville** ou **📍 Me localiser**.
- **Cliquer une zone** pour voir :
  - le nom de la forêt et son type ;
  - l'essence de la zone et les essences dominantes de la forêt ;
  - le score et les facteurs (✓ / ⚠ / ✗) pour l'espèce choisie ;
  - le score des six espèces dans cette zone (cliquer pour changer d'espèce) ;
  - les sosies dangereux de l'espèce et ses précautions (ex. : morilles à bien cuire) ;
  - le graphique pluie et température sur 14 jours, plus les prévisions.
- **Filtres** : essences, type de forêt (domaniale / communale / autre), score minimum.
- **🎯 Top 10 autour de moi** : meilleure zone (≥ 1 ha) de chaque forêt pour l'espèce choisie, dans un rayon réglable de 2 à 25 km.
  - Les filtres actifs s'appliquent au classement.
  - Sans géolocalisation, la recherche se fait autour du centre de la carte.
- **🛰 Photo aérienne** : bascule entre le Plan IGN et les orthophotos.

## Formule du score

```
score(espèce) = 100 × score_essence(espèce) × score_météo(espèce)        (borné à 0–100)
score_météo   = pluie × température × gel × humidité_sol × pluie_ancienne × saison   (borné à 0–1)
```

Tous les seuils sont dans [config/scoring.yaml](config/scoring.yaml). Après modification, redémarrer le backend.
Chaque espèce y a sa propre section `species` : score par essence, facteurs météo qui remplacent
les valeurs par défaut (`weather_defaults`), saison mois par mois et sosies. Pour ajouter une espèce,
il suffit de copier une section. Le mode « Toutes les espèces » prend, pour chaque zone, le meilleur score.

Valeurs pour les **cèpes** (les autres espèces décalent surtout la température et la saison) :

| Facteur | Données | Valeurs (cèpes) |
|---|---|---|
| **Essence** | code TFV BD Forêt → catégorie ([config/tfv_mapping.yaml](config/tfv_mapping.yaml)) | chêne, hêtre, châtaignier 1,0 · sapin/épicéa 0,9 · pins 0,85 · mélanges 0,4–0,75 · douglas 0,15 · peupleraie, robinier, landes 0 |
| **Pluie 7 j** | cumul J-7…J-1 | 20–60 mm = 1 ; < 10 mm ≤ 0,25 ; > 100 mm ≤ 0,55 |
| **Température 7 j** | sol 0–7 cm (sinon air) | 10–18 °C = 1 ; < 5 °C ≤ 0,15 ; > 22 °C ≤ 0,4 |
| **Gel** | minimum de l'air sur 7 j | ≥ 0,5 °C = 1 ; < 0 °C → ×0,45 ; ≤ -5 °C → ×0,1 |
| **Humidité du sol** | moyenne 0–7 cm | 0,10 m³/m³ → ×0,8 ; ≥ 0,30 → ×1,15 à 1,2 |
| **Pluie ancienne** | cumul J-12…J-8 ≥ 20 mm **et** température 7 j entre 10 et 18 °C | ×1,2 (la pousse suit la pluie de 7 à 12 jours) |
| **Saison** | mois en cours | sept.–oct. 1,0 · nov. 0,9 · été 0,6–0,7 · déc.–mars 0,1–0,3 |

Principaux écarts par espèce : girolles 12–20 °C (été), trompettes 9–16 °C et sol très humide,
pieds-de-mouton 6–15 °C et tolérants au gel léger, morilles 8–14 °C au printemps, lactaires uniquement sous les pins.

Classes de la légende : ≥ 60 très probable (vert foncé), ≥ 40 probable, ≥ 20 possible (orange), < 20 peu probable (gris).
Une zone grise claire signifie « météo indisponible ».

## Architecture

```
backend/   FastAPI : WFS par tuiles de 0,2°, intersection shapely, score, cache SQLite
frontend/  React + Vite + MapLibre GL : fond WMTS IGN, polygones GeoJSON colorés
config/    scoring.yaml (seuils), tfv_mapping.yaml (32 codes TFV → catégories)
docs/      DATA_SOURCES.md (couches, champs, licences, requêtes testées)
```

- **Géométries** :
  - le WFS de la Géoplateforme est interrogé par tuiles fixes de 0,2°, avec pagination à 5 000 objets et 8 requêtes simultanées au maximum ;
  - les tuiles sont stockées en WKB dans SQLite pendant 30 jours ;
  - les intersections forêt × peuplement sont gardées en mémoire.
- **Météo** :
  - grille de 0,1° (~10 km) ;
  - jusqu'à 50 points par appel Open-Meteo ;
  - cache de 3 h.
- **Pannes** :
  - si un service ne répond pas, l'app utilise les données en cache, même périmées, et affiche un avertissement ;
  - sans cache, la zone concernée est absente ou sa météo est grisée ;
  - si le service ONF est en panne sans aucun cache, l'API renvoie une erreur 503 avec un message clair.

### API

| Route | Description |
|---|---|
| `GET /api/zones?bbox=minLon,minLat,maxLon,maxLat` | zones scorées pour toutes les espèces (propriétés `s_<espèce>`, `s_best`, `best_species`), contours, résumé par forêt, météo par cellule, avertissements |
| `GET /api/top?lat=&lon=&radius_km=10&species=girolle&forest_types=domaniale&min_score=0` | Top N des zones autour d'un point. `species` : `cepe`, `girolle`, `trompette`, `pied_de_mouton`, `morille`, `lactaire` ou `best` ; `groups` filtre les essences (ex. `Chênes`, plusieurs valeurs séparées par une barre verticale) |
| `GET /api/geocode?q=` | recherche de commune (géocodage IGN) |
| `GET /api/meta` | classes de la légende, groupes d'essences, espèces (saison, sosies) |

## Tests

```bash
cd backend
.venv/Scripts/python -m pytest
```

- **Score** : été sec, automne doux et humide, gel, sol détrempé, peupleraie, absence de température du sol.
- **Espèces** : girolles en été, morilles au printemps sous peupliers (et pas en automne), trompettes sous hêtre plutôt que sous pin, pieds-de-mouton en début d'hiver, lactaires uniquement sous les pins, cohérence de la configuration.
- **Mapping** : les 32 codes TFV sont reconnus.
- **Résilience** : panne WFS avec et sans cache, panne de l'API météo.
- **Sécurité** : requêtes inter-sites et hôtes inconnus refusés, absence d'en-tête CORS, paramètres bornés.

## Sources et licences

Le détail est dans [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md).

| Donnée | Producteur | Licence |
|---|---|---|
| BD Forêt® V2, Plan IGN, orthophotos, géocodage | IGN – Géoplateforme | Licence Ouverte Etalab 2.0 |
| Forêts publiques | ONF (via Géoplateforme) | Licence Ouverte 2.0 |
| Météo | Open-Meteo.com | CC BY 4.0, API gratuite réservée à un usage **non commercial** |

Les attributions sont affichées en bas de la carte.

## Réglementation

La cueillette n'est autorisée que dans le respect de la réglementation locale :
- les quotas par personne et par jour varient selon les arrêtés préfectoraux (souvent 5 L en forêt domaniale) ;
- la revente est interdite ;
- la cueillette est interdite en forêt privée sans l'accord du propriétaire, et dans certaines réserves.

Voir les [règles de cueillette de l'ONF](https://www.onf.fr/vivre-la-foret/que-faire-en-foret/regles-et-bonnes-pratiques-en-foret/+/2891::conseils-precautions-comment-bien-cueillir-champignons-et-chataignes-en-foret.html).

## Limites connues

- **Profils d'espèces approximatifs** : ils reposent sur l'écologie générale de chaque espèce. Les morilles dépendent beaucoup de facteurs absents des données (frênes isolés, brûlis, sols calcaires, vergers), et les lactaires sanguins du Midi ne sont pas distingués du lactaire délicieux.
- **Modèle heuristique, non calibré** : les seuils sont des valeurs de départ, à ajuster avec de vraies récoltes. Le modèle ignore le sol (pH), l'altitude, l'exposition, l'âge des peuplements et la pression de cueillette.
- **BD Forêt V2 date de 2006 à 2019 selon les départements** : coupes, tempêtes et dépérissements récents (scolytes sur l'épicéa) ne sont pas pris en compte.
- **Les mélanges** (« mélange de feuillus », « feuillus prépondérants et conifères »…) ne précisent pas les essences présentes : ils reçoivent un score intermédiaire alors qu'ils contiennent souvent du chêne ou du hêtre.
- **Météo modélisée** (pas d'observations de stations), avec une résolution d'environ 10 km : un orage local peut manquer, et le relief n'est que partiellement pris en compte.
- **Type de forêt** : l'ONF fournit seulement « domaniale oui/non ». Le type « communale » est déduit du nom de la forêt.
- **Forêts qui débordent de l'écran** : les essences dominantes et le score moyen sont calculés sur la partie chargée (mention « partie affichée »).
- **Couverture limitée aux forêts publiques** : les forêts privées (≈ 75 % de la forêt française) ne sont pas couvertes, ce qui est volontaire puisque la cueillette y est interdite sans accord.
- **Volumes** : l'API gratuite Open-Meteo est limitée à 10 000 appels par jour, et la Géoplateforme à 30 requêtes par seconde.
