# Sources de données — Mushroom Finder

Toutes les sources ci-dessous ont été **testées le 29/10/2026** avec les requêtes indiquées (réponses HTTP 200, données réelles).

## Synthèse

| Besoin | Source retenue | Accès | Licence | Clé |
|---|---|---|---|---|
| Forêts publiques | ONF via Géoplateforme : `ONF.FORETS_PUBLIQUES:ONF_FORETS_PUBLIQUES` | WFS 2.0 bbox | Licence Ouverte Etalab 2.0 | non |
| Essences | IGN BD Forêt V2 : `LANDCOVER.FORESTINVENTORY.V2:formation_vegetale` | WFS 2.0 bbox | Licence Ouverte Etalab 2.0 | non |
| Fond de carte | Plan IGN v2 / Ortho (WMTS Géoplateforme) | WMTS tuiles XYZ | Licence Ouverte Etalab 2.0 | non |
| Météo 14 j + prévisions | **Open-Meteo** Forecast API | REST JSON, multi-points | CC BY 4.0 (usage non commercial gratuit) | non |
| Recherche de ville | Géoplateforme géocodage (`data.geopf.fr/geocodage/search`) | REST | Etalab 2.0 | non |

---

## 1. Géoplateforme IGN — service WFS

- Endpoint : `https://data.geopf.fr/wfs/ows` (WFS 2.0.0)
- Sortie GeoJSON : `OUTPUTFORMAT=application/json`, reprojection : `SRSNAME=EPSG:4326`
- **Limites** :
  - `CountDefault` = **5 000 objets max par requête**. Au-delà, paginer avec `STARTINDEX` (testé : 0/100/200 → pages disjointes, `numberMatched` renvoyé).
  - Débit : en-tête `ratelimit-limit: 30` → **30 requêtes/s par IP**. Prévoir un sémaphore côté backend.
  - Depuis le 15/06/2026 : **2 couches maximum par URL**. On fait une requête par couche.
- ⚠️ Avec `urn:ogc:def:crs:EPSG::4326`, l'ordre de la BBOX est **lat,lon** (`minLat,minLon,maxLat,maxLon`).

### 1a. Forêts publiques (ONF)

- Couche : `ONF.FORETS_PUBLIQUES:ONF_FORETS_PUBLIQUES` (CRS natif EPSG:3857)
- Contenu : forêts domaniales et non domaniales (communales, sectionales, départementales, établissements publics) relevant du régime forestier.
- Champs :

| Champ | Signification | Exemple |
|---|---|---|
| `iidtn_frt` | identifiant national de la forêt | `F23163W` |
| `llib_frt` | nom de la forêt | `Forêt domaniale de Vologne` |
| `cdom_frt` | domaniale ? `OUI` / `NON` | `OUI` |
| `cinse_dep` | département | `88` |
| `geom` | MultiPolygon | |

- Type de forêt : `cdom_frt=OUI` → domaniale ; `NON` → communale ou autre (le nom `llib_frt` commence généralement par « Forêt communale de… », ce qui permet d'affiner).
- Licence : Licence Ouverte v2.0 (fiche data.gouv « Forêts publiques (diffusion publique) », ONF, mise à jour du 12/09/2026, fréquence non renseignée ; l'ONF annonce une mise à jour semestrielle).
- Secours : `BDTOPO_V3:foret_publique` (champs `toponyme`, `nature`, géométrie `geometrie`).

```
https://data.geopf.fr/wfs/ows?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature
  &TYPENAMES=ONF.FORETS_PUBLIQUES:ONF_FORETS_PUBLIQUES
  &OUTPUTFORMAT=application/json&SRSNAME=EPSG:4326
  &BBOX=48.05,6.80,48.12,6.92,urn:ogc:def:crs:EPSG::4326&COUNT=1000
→ 16 forêts (3 domaniales, 13 communales) autour de Gérardmer (88)
```

### 1b. BD Forêt V2 (essences)

- Couche : `LANDCOVER.FORESTINVENTORY.V2:formation_vegetale`, titre « BD Forêt v2 (2006-2019) » (le millésime varie selon le département). CRS natif EPSG:2154.
- Polygones ≥ 0,5 ha, nomenclature nationale de **32 postes**.
- Champs : `id`, `code_tfv` (code type de formation végétale), `tfv` (libellé), `tfv_g11` (regroupement en 11 classes), `essence` (essence simplifiée), `geom`.
- On peut alléger les réponses avec `PROPERTYNAME=code_tfv,tfv,tfv_g11,essence`.
- ⚠️ Encodage : certains libellés `tfv` contiennent l'apostrophe cp1252 `\x92` → normaliser en `'`. On utilise **`code_tfv`** comme clé, jamais le libellé.

**Les 32 codes TFV**, relevés empiriquement sur 16 zones (Landes, Vosges, Provence, Bretagne, Sologne, Alpes, Massif central, Corse, Tronçais, Jura, Pyrénées, Fontainebleau, Cévennes, Ardennes, Alsace, Limousin ; ~21 000 polygones) :

| code_tfv | Libellé | essence |
|---|---|---|
| FF1G01-01 | Forêt fermée de chênes décidus purs | Chênes décidus |
| FF1G06-06 | Forêt fermée de chênes sempervirents purs | Chênes sempervirents |
| FF1-09-09 | Forêt fermée de hêtre pur | Hêtre |
| FF1-10-10 | Forêt fermée de châtaignier pur | Châtaignier |
| FF1-14-14 | Forêt fermée de robinier pur | Robinier |
| FF1-49-49 | Forêt fermée d'un autre feuillu pur | Feuillus |
| FF1-00-00 | Forêt fermée à mélange de feuillus | Feuillus |
| FF1-00 | Forêt fermée de feuillus purs en îlots | Feuillus |
| FF2G61-61 | Forêt fermée de sapin ou épicéa | Sapin, épicéa |
| FF2-51-51 | Forêt fermée de pin maritime pur | Pin maritime |
| FF2-52-52 | Forêt fermée de pin sylvestre pur | Pin sylvestre |
| FF2G53-53 | Forêt fermée de pin laricio ou pin noir pur | Pin laricio, pin noir |
| FF2-57-57 | Forêt fermée de pin d'Alep pur | Pin d'Alep |
| FF2G58-58 | Forêt fermée de pin à crochets ou pin cembro pur | Pin à crochets, pin cembro |
| FF2-80-80 | Forêt fermée à mélange de pins purs | Pins mélangés |
| FF2-81-81 | Forêt fermée d'un autre pin pur | Pin autre |
| FF2-63-63 | Forêt fermée de mélèze pur | Mélèze |
| FF2-64-64 | Forêt fermée de douglas pur | Douglas |
| FF2-90-90 | Forêt fermée à mélange d'autres conifères | Conifères |
| FF2-91-91 | Forêt fermée d'un autre conifère pur autre que pin | Conifères |
| FF2-00-00 | Forêt fermée à mélange de conifères | Conifères |
| FF2-00 | Forêt fermée de conifères purs en îlots | Conifères |
| FF31 | Forêt fermée à mélange de feuillus prépondérants et conifères | Mixte |
| FF32 | Forêt fermée à mélange de conifères prépondérants et feuillus | Mixte |
| FF0 | Forêt fermée sans couvert arboré | NR |
| FO1 | Forêt ouverte de feuillus purs | Feuillus |
| FO2 | Forêt ouverte de conifères purs | Conifères |
| FO3 | Forêt ouverte à mélange de feuillus et conifères | Mixte |
| FO0 | Forêt ouverte sans couvert arboré | NR |
| FP | Peupleraie | Peuplier |
| LA4 | Lande | NC |
| LA6 | Formation herbacée | NC |

Limite importante : les mélanges (`FF1-00-00`, `FF31`, `FF32`, `FO*`) **ne précisent pas** les essences présentes. Ils contiennent souvent du chêne ou du hêtre, mais BD Forêt ne le dit pas : ils recevront un score intermédiaire.

```
https://data.geopf.fr/wfs/ows?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature
  &TYPENAMES=LANDCOVER.FORESTINVENTORY.V2:formation_vegetale
  &OUTPUTFORMAT=application/json&SRSNAME=EPSG:4326
  &BBOX=48.05,6.80,48.12,6.92,urn:ogc:def:crs:EPSG::4326&COUNT=5000
  &PROPERTYNAME=code_tfv,tfv,tfv_g11,essence
→ 237 polygones (52 sapin/épicéa, 41 FF31, 32 FF32…)
```

## 2. Fond de carte — WMTS Géoplateforme

- Endpoint : `https://data.geopf.fr/wmts`, TileMatrixSet `PM` (Web Mercator), utilisable directement en XYZ dans MapLibre :
  - Plan IGN : `...&LAYER=GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2&STYLE=normal&FORMAT=image/png&TILEMATRIXSET=PM&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}` ✓
  - Ortho : `LAYER=ORTHOIMAGERY.ORTHOPHOTOS`, `FORMAT=image/jpeg` ✓
  - Optionnel, en raster à faible zoom : `LANDCOVER.FORESTINVENTORY.V2` (png) ✓
- Exemple testé : `https://data.geopf.fr/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2&STYLE=normal&TILEMATRIXSET=PM&TILEMATRIX=12&TILEROW=1418&TILECOL=2125&FORMAT=image/png` → PNG 200.
- Attribution : « © IGN – Géoplateforme ».

## 3. Météo

### Choix : Open-Meteo

**Open-Meteo est retenu : il est gratuit et sans clé, interrogeable en multi-points en une seule requête, et fournit en un appel 14 jours d'historique (`past_days` jusqu'à 92), les prévisions, la température et l'humidité du sol. Météo-France impose un compte, un jeton et un abonnement par API, et ne fournit les observations qu'aux stations.**

- Endpoint : `https://api.open-meteo.com/v1/forecast`
- Paramètres utiles :
  - `latitude=48.08,48.5&longitude=6.86,6.9` → plusieurs points par appel (réponse = liste JSON)
  - `past_days=14&forecast_days=3&timezone=Europe/Paris`
  - journalier : `precipitation_sum, temperature_2m_min, temperature_2m_max, temperature_2m_mean`
  - horaire : `soil_temperature_0_to_7cm`, `soil_moisture_0_to_7cm` (testés, valeurs non nulles). Il existe aussi `soil_temperature_0cm/6cm` et `soil_moisture_0_to_1cm/1_to_3cm`.
- **Limites (offre gratuite)** : 600 appels/min, 5 000/h, 10 000/jour, 300 000/mois, **usage non commercial uniquement**. Un appel multi-points compte pour plusieurs appels, proportionnellement au nombre de points.
- Stratégie : grille d'environ 0,1° (~10 km), points dédupliqués, lots d'environ 50 points par requête, cache de 3 h.
- Licence : CC BY 4.0. Attribution : « Weather data by Open-Meteo.com ».
- Exemple testé :

```
https://api.open-meteo.com/v1/forecast?latitude=48.08&longitude=6.86
  &daily=precipitation_sum,temperature_2m_min,temperature_2m_max,temperature_2m_mean
  &hourly=soil_temperature_0_to_7cm,soil_moisture_0_to_7cm
  &past_days=14&forecast_days=3&timezone=Europe/Paris
→ 17 jours (15/10 → 31/10/2026) ; pluie J-14…J-1 : 0, 0, 2.7, 9.7, 0.6, 2, 10.6, 0, 4.4, 4.8, 29.9, 0, 0, 1.4 mm
```

### Alternative non retenue : API Météo-France

`portail-api.meteofrance.fr`, API « Données climatologiques » : compte et jeton obligatoires (abonnement gratuit), données aux stations seulement (pas de grille), pas de variables de sol simples. À garder comme évolution possible pour recaler les cumuls de pluie sur des observations réelles.

## 4. Réglementation (liens affichés dans l'app)

- ONF, bonnes pratiques de cueillette : https://www.onf.fr/vivre-la-foret/que-faire-en-foret/regles-et-bonnes-pratiques-en-foret/+/2891::conseils-precautions-comment-bien-cueillir-champignons-et-chataignes-en-foret.html
- Règle générale en forêt domaniale : usage familial, environ 5 L par personne et par jour, revente interdite (contravention de 4e classe entre 5 et 10 L, délit au-delà). Les arrêtés préfectoraux peuvent restreindre davantage (jours interdits, quotas). En forêt communale ou privée : accord du propriétaire requis.

## 5. Attributions à afficher

`© IGN – Géoplateforme (BD Forêt® V2, Plan IGN) · © ONF – Forêts publiques (Licence Ouverte 2.0) · Météo : Open-Meteo.com (CC BY 4.0)`
