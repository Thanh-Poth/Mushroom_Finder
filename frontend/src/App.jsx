import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import MapView from './MapView.jsx'
import { DetailsPanel, Filters, Legend, SearchBox, SpeciesPicker, TopPanel } from './Panels.jsx'
import { fetchMeta, fetchTop, fetchZones } from './api.js'

const MIN_ZOOM = 11
const INITIAL = { center: [6.86, 48.08], zoom: 12 }   // zone test : Gérardmer (Vosges)
const ALL_TYPES = ['domaniale', 'communale', 'autre']
const ONF_RULES =
  'https://www.onf.fr/vivre-la-foret/que-faire-en-foret/regles-et-bonnes-pratiques-en-foret/+/2891::conseils-precautions-comment-bien-cueillir-champignons-et-chataignes-en-foret.html'
const DEFAULT_META = {
  classes: [
    { min: 60, label: 'Très probable', color: '#1a9850' },
    { min: 40, label: 'Probable', color: '#91cf60' },
    { min: 20, label: 'Possible', color: '#fdae61' },
    { min: 0, label: 'Peu probable', color: '#9e9e9e' },
  ],
  groups: [],
  species: [],
  essence_ok_threshold: 0.6,
}

function loadSpecies() {
  try { return localStorage.getItem('species') || 'cepe' } catch { return 'cepe' }
}

function snapshot(data, key) {
  const f = data?.zones.features.find((z) => z.properties.forest_id === key.forest_id &&
    z.properties.lon === key.lon && z.properties.lat === key.lat)
  if (!f) return null
  const zone = f.properties
  return { zone, forest: data.forests[zone.forest_id], weather: data.weather[zone.cell] }
}

function getPosition() {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) return reject(new Error('Géolocalisation non disponible'))
    // le timeout natif ne couvre pas une demande d'autorisation restée sans réponse
    const t = setTimeout(() => reject(new Error('Géolocalisation sans réponse')), 12000)
    navigator.geolocation.getCurrentPosition(
      (p) => { clearTimeout(t); resolve({ lat: p.coords.latitude, lon: p.coords.longitude }) },
      () => { clearTimeout(t); reject(new Error('Géolocalisation refusée')) }, { timeout: 10000 })
  })
}

export default function App() {
  const [meta, setMeta] = useState(DEFAULT_META)
  const [data, setData] = useState(null)
  const [status, setStatus] = useState({ loading: false, error: null, zoom: INITIAL.zoom })
  const [filters, setFilters] = useState({ groups: new Set(), types: new Set(ALL_TYPES), minScore: 0 })
  const [selected, setSelected] = useState(null)
  const [flyTarget, setFlyTarget] = useState(null)
  const [userPos, setUserPos] = useState(null)
  const [basemap, setBasemap] = useState('plan')
  const [radius, setRadius] = useState(10)
  const [top, setTop] = useState({})
  const [menuOpen, setMenuOpen] = useState(false)
  const [species, setSpecies] = useState(loadSpecies)
  const pending = useRef(null)
  const ctrl = useRef(null)
  const timer = useRef(null)
  const center = useRef({ lng: INITIAL.center[0], lat: INITIAL.center[1] })

  useEffect(() => {
    fetchMeta().then((m) => {
      setMeta({ ...DEFAULT_META, ...m })
      setFilters((f) => ({ ...f, groups: new Set(m.groups) }))
    }).catch((e) => setStatus((s) => ({ ...s, error: e.message })))
  }, [])

  const onMove = useCallback((bbox, zoom, c) => {
    center.current = c
    clearTimeout(timer.current)
    if (zoom < MIN_ZOOM) {
      ctrl.current?.abort()
      setStatus({ loading: false, error: null, zoom })
      return
    }
    setStatus((s) => ({ ...s, zoom }))
    timer.current = setTimeout(async () => {
      ctrl.current?.abort()
      ctrl.current = new AbortController()
      setStatus((s) => ({ ...s, loading: true, error: null }))
      try {
        const d = await fetchZones(bbox, ctrl.current.signal)
        setData(d)
        if (pending.current) {
          const snap = snapshot(d, pending.current)
          if (snap) setSelected(snap)
          pending.current = null
        }
        setStatus((s) => ({ ...s, loading: false }))
      } catch (e) {
        if (e.name !== 'AbortError') setStatus((s) => ({ ...s, loading: false, error: e.message }))
      }
    }, 350)
  }, [])

  const dataRef = useRef(null)
  dataRef.current = data
  const onSelect = useCallback((key) => setSelected(snapshot(dataRef.current, key)), [])

  const chooseSpecies = (id) => {
    setSpecies(id)
    setTop({})
    try { localStorage.setItem('species', id) } catch { /* stockage indisponible */ }
  }
  const scoreKey = `s_${species}`
  const speciesLabel = species === 'best'
    ? 'meilleure espèce'
    : meta.species.find((s) => s.id === species)?.label ?? species

  const mapFilter = useMemo(() => {
    const f = ['all', ['in', ['get', 'forest_type'], ['literal', [...filters.types]]]]
    if (meta.groups.length) f.push(['in', ['get', 'group'], ['literal', [...filters.groups]]])
    if (filters.minScore > 0) f.push(['>=', ['coalesce', ['get', scoreKey], -1], filters.minScore])
    return f
  }, [filters, meta.groups, scoreKey])

  const locate = async () => {
    try {
      const p = await getPosition()
      setUserPos(p)
      setFlyTarget({ center: [p.lon, p.lat], zoom: 13 })
    } catch (e) {
      setStatus((s) => ({ ...s, error: e.message }))
    }
  }

  const runTop = async () => {
    setTop({ loading: true })
    let pos = userPos, note = null
    if (!pos) {
      try {
        pos = await getPosition()
        setUserPos(pos)
      } catch {
        pos = { lat: center.current.lat, lon: center.current.lng }
        note = 'Position non disponible : recherche autour du centre de la carte.'
      }
    }
    try {
      const r = await fetchTop({ ...pos, radius, groups: [...filters.groups], types: [...filters.types],
                                 minScore: filters.minScore, species })
      setTop({ results: r.results, note: note || (r.warnings.length ? r.warnings.join(' ') : null) })
    } catch (e) {
      setTop({ error: e.message, note })
    }
  }

  const pickTop = (r) => {
    pending.current = { forest_id: r.forest_id, lon: r.lon, lat: r.lat }
    setFlyTarget({ center: [r.lon, r.lat], zoom: 14 })
    setMenuOpen(false)
  }

  const nZones = data?.zones.features.length ?? 0
  const nForests = data ? Object.keys(data.forests).length : 0

  return (
    <div className="app">
      <header className="topbar">
        <button className="menu-btn" onClick={() => setMenuOpen((o) => !o)} aria-label="Menu">☰</button>
        <h1>🍄 Mushroom Finder</h1>
      </header>

      <div className={menuOpen ? 'sidebar open' : 'sidebar'}>
        <h1 className="brand">🍄 Mushroom Finder</h1>
        <p className="muted small">Probabilité de pousse des champignons comestibles dans les forêts publiques, d'après les essences et la météo des 7 derniers jours.</p>

        <div className="callout">
          <strong>Estimation indicative, pas une garantie.</strong> Ne consommez que des champignons
          identifiés avec certitude par un pharmacien ou une association mycologique.
        </div>

        <SpeciesPicker list={meta.species} value={species} onChange={chooseSpecies} />

        <SearchBox onPick={(r) => { setFlyTarget({ center: [r.lon, r.lat], zoom: 13 }); setMenuOpen(false) }} />
        <div className="row">
          <button onClick={locate}>📍 Me localiser</button>
          <button onClick={() => setBasemap((b) => (b === 'plan' ? 'ortho' : 'plan'))}>
            {basemap === 'plan' ? '🛰 Photo aérienne' : '🗺 Plan IGN'}
          </button>
        </div>

        <Filters groups={meta.groups} filters={filters} setFilters={setFilters} />
        <TopPanel state={top} radius={radius} setRadius={setRadius} onRun={runTop} onPick={pickTop}
                  classes={meta.classes} species={species} speciesList={meta.species} />
        <Legend classes={meta.classes} title={speciesLabel} />

        <section className="legal small">
          <h3>Réglementation</h3>
          Cueillette autorisée uniquement dans le respect de la réglementation locale : quotas par
          personne et par jour variables selon les arrêtés préfectoraux (souvent 5 L en forêt domaniale),
          interdite en forêt privée sans accord du propriétaire, interdite dans certaines réserves.{' '}
          <a href={ONF_RULES} target="_blank" rel="noreferrer">Règles de cueillette de l'ONF</a>.
        </section>
      </div>

      <main className="map-wrap">
        <MapView initial={INITIAL} data={data} classes={meta.classes} scoreKey={scoreKey} filter={mapFilter}
                 selected={selected} onSelect={onSelect} onMove={onMove} flyTarget={flyTarget}
                 userPos={userPos} basemap={basemap} />
        <div className="status" role="status">
          {status.zoom < MIN_ZOOM
            ? 'Zoomez pour afficher les forêts publiques'
            : status.loading
              ? 'Chargement des forêts et de la météo… (1er passage sur une zone : jusqu\'à 30 s)'
              : status.error
                ? <span className="err">⚠ {status.error}</span>
                : data && `${speciesLabel} · ${nForests} forêts publiques · ${nZones} zones`}
          {data?.warnings?.length > 0 && !status.loading && (
            <div className="warn-txt">{data.warnings.join(' ')}</div>
          )}
        </div>
        <DetailsPanel selected={selected} classes={meta.classes} essenceOk={meta.essence_ok_threshold}
                      species={species} speciesList={meta.species} onSpecies={chooseSpecies}
                      onClose={() => setSelected(null)} />
      </main>
    </div>
  )
}
