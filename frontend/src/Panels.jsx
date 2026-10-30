import { useEffect, useRef, useState } from 'react'
import { geocode } from './api.js'
import WeatherChart from './WeatherChart.jsx'
import { NO_DATA_COLOR } from './MapView.jsx'

const MARK = { ok: '✓', warn: '⚠', bad: '✗', na: '' }
const TYPE_LABEL = { domaniale: 'Domaniale', communale: 'Communale', autre: 'Autre forêt publique' }
const MONTHS = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.']
const DANGER_LABEL = { mortel: 'Mortel', toxique: 'Toxique', faible: 'À vérifier' }

export function scoreClass(score, classes) {
  if (score == null) return { label: 'Météo indisponible', color: NO_DATA_COLOR }
  return [...classes].sort((a, b) => b.min - a.min).find((c) => score >= c.min) || classes.at(-1)
}

export function ScoreBadge({ score, classes, large }) {
  const c = scoreClass(score, classes)
  return (
    <span className={large ? 'badge badge-lg' : 'badge'} style={{ background: c.color }} title={c.label}>
      {score ?? '–'}
    </span>
  )
}

const seasonText = (months) =>
  months?.length ? `${MONTHS[months[0] - 1]} – ${MONTHS[months.at(-1) - 1]}` : ''

export function SpeciesPicker({ list, value, onChange }) {
  if (!list.length) return null
  return (
    <section>
      <h3>Champignon recherché</h3>
      <div className="species">
        {list.map((s) => (
          <button key={s.id} className={value === s.id ? 'sp on' : 'sp'} onClick={() => onChange(s.id)}
                  aria-pressed={value === s.id} title={s.latin}>
            <i className="dot" style={{ background: s.color }} />
            <span className="sp-txt"><strong>{s.label}</strong>
              <span className="muted">{seasonText(s.season_ok_months)}</span></span>
          </button>
        ))}
        <button className={value === 'best' ? 'sp sp-all on' : 'sp sp-all'} onClick={() => onChange('best')}
                aria-pressed={value === 'best'}>
          <i className="dot dot-all" />
          <span className="sp-txt"><strong>Toutes les espèces</strong>
            <span className="muted">la plus probable par zone</span></span>
        </button>
      </div>
    </section>
  )
}

export function SearchBox({ onPick }) {
  const [q, setQ] = useState('')
  const [results, setResults] = useState([])
  const [error, setError] = useState(null)
  const ctrl = useRef(null)

  useEffect(() => {
    if (q.trim().length < 2) { setResults([]); return }
    const t = setTimeout(async () => {
      ctrl.current?.abort()
      ctrl.current = new AbortController()
      try {
        setResults(await geocode(q, ctrl.current.signal)); setError(null)
      } catch (e) {
        if (e.name !== 'AbortError') setError(e.message)
      }
    }, 300)
    return () => clearTimeout(t)
  }, [q])

  return (
    <div className="search">
      <input type="search" placeholder="Rechercher une ville…" value={q}
             onChange={(e) => setQ(e.target.value)} aria-label="Rechercher une ville" />
      {error && <div className="small err">{error}</div>}
      {results.length > 0 && (
        <ul className="search-results">
          {results.map((r, i) => (
            <li key={i}>
              <button onClick={() => { onPick(r); setResults([]); setQ(r.label) }}>
                <strong>{r.label}</strong> <span className="muted">{r.context}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export function Filters({ groups, filters, setFilters }) {
  const toggle = (key, value) => setFilters((f) => {
    const s = new Set(f[key])
    s.has(value) ? s.delete(value) : s.add(value)
    return { ...f, [key]: s }
  })
  return (
    <section>
      <h3>Filtres</h3>
      <div className="label">Essences</div>
      <div className="chips">
        {groups.map((g) => (
          <button key={g} className={filters.groups.has(g) ? 'chip on' : 'chip'}
                  onClick={() => toggle('groups', g)} aria-pressed={filters.groups.has(g)}>{g}</button>
        ))}
      </div>
      <div className="label">Type de forêt</div>
      <div className="chips">
        {Object.entries(TYPE_LABEL).map(([k, v]) => (
          <button key={k} className={filters.types.has(k) ? 'chip on' : 'chip'}
                  onClick={() => toggle('types', k)} aria-pressed={filters.types.has(k)}>{v}</button>
        ))}
      </div>
      <label className="label">
        Score minimum : <strong>{filters.minScore}</strong>
        <input type="range" min="0" max="95" step="5" value={filters.minScore}
               onChange={(e) => setFilters((f) => ({ ...f, minScore: +e.target.value }))} />
      </label>
    </section>
  )
}

export function Legend({ classes, title }) {
  return (
    <section>
      <h3>Légende : {title}</h3>
      <ul className="legend">
        {classes.map((c) => (
          <li key={c.label}><span className="sw" style={{ background: c.color }} />{c.label} ({c.min}+)</li>
        ))}
        <li><span className="sw" style={{ background: NO_DATA_COLOR }} />Météo indisponible</li>
        <li><span className="sw sw-line" />Limite de forêt publique</li>
      </ul>
    </section>
  )
}

export function TopPanel({ state, radius, setRadius, onRun, onPick, classes, species, speciesList }) {
  const label = (id) => speciesList.find((s) => s.id === id)?.label ?? id
  return (
    <section>
      <h3>Top 10 autour de moi</h3>
      <label className="label">
        Rayon : <strong>{radius} km</strong>
        <input type="range" min="2" max="25" step="1" value={radius} onChange={(e) => setRadius(+e.target.value)} />
      </label>
      <button className="primary" onClick={onRun} disabled={state.loading}>
        {state.loading ? 'Recherche… (jusqu\'à 1 min la 1re fois)' : '🎯 Top 10 autour de moi'}
      </button>
      {state.note && <div className="small muted">{state.note}</div>}
      {state.error && <div className="small err">{state.error}</div>}
      {state.results && state.results.length === 0 && <div className="small muted">Aucune zone trouvée.</div>}
      {state.results?.length > 0 && (
        <ol className="top">
          {state.results.map((r) => (
            <li key={r.forest_id}>
              <button onClick={() => onPick(r)}>
                <ScoreBadge score={r.score} classes={classes} />
                <span className="top-txt">
                  <strong>{r.forest_name}</strong>
                  <span className="muted">
                    {species === 'best' ? `${label(r.species)} · ` : ''}
                    {r.essence_label} · {r.area_ha} ha · {r.distance_km} km
                  </span>
                </span>
              </button>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}

function Lookalikes({ sp }) {
  if (!sp?.lookalikes?.length && !sp?.note) return null
  return (
    <>
      <h3>Attention aux confusions</h3>
      {sp.note && <div className="small warn-box">{sp.note}</div>}
      <ul className="lookalikes">
        {sp.lookalikes.map((l) => (
          <li key={l.name}>
            <span className={`danger danger-${l.danger}`}>{DANGER_LABEL[l.danger] ?? l.danger}</span>
            <span><strong>{l.name}</strong><small>{l.hint}</small></span>
          </li>
        ))}
      </ul>
    </>
  )
}

export function DetailsPanel({ selected, classes, essenceOk, species, speciesList, onSpecies, onClose }) {
  if (!selected) return null
  const { zone, forest, weather } = selected
  const sid = species === 'best' ? zone.best_species : species
  const sp = speciesList.find((s) => s.id === sid)
  const score = zone[`s_${sid}`] ?? null
  const essScore = zone[`e_${sid}`] ?? 0
  const w = weather?.species?.[sid]
  const essStatus = essScore >= essenceOk ? 'ok' : essScore >= 0.3 ? 'warn' : 'bad'
  const c = scoreClass(score, classes)
  const others = speciesList
    .map((s) => ({ ...s, score: zone[`s_${s.id}`] }))
    .sort((a, b) => (b.score ?? -1) - (a.score ?? -1))
  const forestScores = forest?.scores?.[sid]

  return (
    <aside className="details" aria-label="Détails de la zone">
      <button className="close" onClick={onClose} aria-label="Fermer">×</button>
      <div className="details-head">
        <ScoreBadge score={score} classes={classes} large />
        <div>
          <h2>{forest?.name || zone.forest_name}</h2>
          <div className="muted">{TYPE_LABEL[zone.forest_type]}{forest?.dep ? ` · dép. ${forest.dep}` : ''}</div>
          <div className="cls" style={{ color: c.color === NO_DATA_COLOR ? '#666' : c.color }}>
            {sp ? `${sp.label} : ` : ''}{c.label}
          </div>
        </div>
      </div>

      <h3>Pourquoi ce score ?{sp ? ` (${sp.label.toLowerCase()})` : ''}</h3>
      <ul className="factors">
        <li className={essStatus}>
          <span>Essence : {zone.essence_label}</span><span>{MARK[essStatus]}</span>
          <small>{zone.tfv} · {zone.area_ha} ha · ×{essScore}</small>
        </li>
        {w?.factors?.map((f) => (
          <li key={f.key} className={f.status}>
            <span>{f.label} : {f.value}</span><span>{MARK[f.status]}</span>
            <small>{[f.hint, `×${f.effect}`].filter(Boolean).join(' · ')}</small>
          </li>
        ))}
        {w?.error && <li className="bad"><span>Météo : {w.error}</span><span>✗</span></li>}
      </ul>
      <p className="formula small muted">
        Score = 100 × essence ({essScore}) × météo ({w?.score ?? '–'})
      </p>

      <h3>Toutes les espèces dans cette zone</h3>
      <ul className="others">
        {others.map((o) => (
          <li key={o.id}>
            <button className={o.id === sid ? 'on' : ''} onClick={() => onSpecies(o.id)}
                    title={`Afficher la carte des ${o.label.toLowerCase()}`}>
              <ScoreBadge score={o.score} classes={classes} />
              <span>{o.label}</span>
            </button>
          </li>
        ))}
      </ul>

      <Lookalikes sp={sp} />

      <h3>Météo (cellule ~10 km)</h3>
      {weather?.stale && <div className="small warn-txt">Données météo en cache (API indisponible).</div>}
      <WeatherChart days={weather?.days} today={weather?.today} />
      <div className="chart-legend small">
        <span><i className="k-bar" />pluie (mm)</span>
        <span><i className="k-air" />air</span>
        <span><i className="k-soil" />sol 0-7 cm</span>
        <span><i className="k-win" />7 derniers jours</span>
      </div>

      {forest?.essences?.length > 0 && (
        <>
          <h3>Essences dominantes de la forêt{forest.partial ? ' (partie affichée)' : ''}</h3>
          <ul className="shares">
            {forest.essences.map((e) => (
              <li key={e.label}>
                <span>{e.label}</span>
                <span className="share-bar"><i style={{ width: `${Math.round(e.share * 100)}%` }} /></span>
                <span>{Math.round(e.share * 100)} %</span>
              </li>
            ))}
          </ul>
          <div className="small muted">
            {forest.area_ha} ha cartographiés · score moyen {forestScores?.mean ?? '–'} · meilleure zone {forestScores?.best ?? '–'}
          </div>
        </>
      )}
    </aside>
  )
}
