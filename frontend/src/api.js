async function getJSON(url, signal) {
  let r
  try {
    r = await fetch(url, { signal })
  } catch (e) {
    if (e.name === 'AbortError') throw e
    throw new Error('Serveur Mushroom Finder injoignable (le backend est-il lancé ?)')
  }
  if (!r.ok) {
    let detail = `Erreur ${r.status}`
    try { detail = (await r.json()).detail || detail } catch { /* corps non JSON */ }
    throw new Error(detail)
  }
  return r.json()
}

export const fetchMeta = () => getJSON('/api/meta')

export const fetchZones = (b, signal) =>
  getJSON(`/api/zones?bbox=${b.map((v) => v.toFixed(4)).join(',')}`, signal)

export const fetchTop = ({ lat, lon, radius, groups, types, minScore, species }) => {
  const q = new URLSearchParams({
    lat, lon, radius_km: radius, min_score: minScore, species,
    groups: groups.join('|'), forest_types: types.join('|'),
  })
  return getJSON(`/api/top?${q}`)
}

export const geocode = (q, signal) => getJSON(`/api/geocode?q=${encodeURIComponent(q)}`, signal)
