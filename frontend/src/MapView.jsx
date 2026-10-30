import { useEffect, useRef, useState } from 'react'
import * as maplibregl from 'maplibre-gl'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'

// MapLibre 6 résout son worker en relatif, ce que le pré-bundling Vite casse
maplibregl.setWorkerUrl(workerUrl)

const wmts = (layer, format) =>
  'https://data.geopf.fr/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0' +
  `&LAYER=${layer}&STYLE=normal&TILEMATRIXSET=PM&FORMAT=${format}` +
  '&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}'

const ATTRIBUTION =
  '© <a href="https://cartes.gouv.fr" target="_blank">IGN – Géoplateforme</a> (Plan IGN, BD Forêt® V2) · ' +
  '© <a href="https://www.onf.fr" target="_blank">ONF</a> – Forêts publiques (Licence Ouverte 2.0) · ' +
  'Météo : <a href="https://open-meteo.com/" target="_blank">Open-Meteo.com</a> (CC BY 4.0)'

const EMPTY = { type: 'FeatureCollection', features: [] }

export const NO_DATA_COLOR = '#d9d9d9'

export function scoreColorExpr(classes, key) {
  const asc = [...classes].sort((a, b) => a.min - b.min)
  const step = ['step', ['get', key], asc[0].color]
  asc.slice(1).forEach((c) => step.push(c.min, c.color))
  return ['case', ['==', ['typeof', ['get', key]], 'number'], step, NO_DATA_COLOR]
}

export default function MapView({ initial, data, classes, scoreKey, filter, selected, onSelect, onMove,
                                  flyTarget, userPos, basemap }) {
  const container = useRef(null)
  const mapRef = useRef(null)
  const markerRef = useRef(null)
  const handlers = useRef({})
  const [ready, setReady] = useState(false)
  handlers.current = { onSelect, onMove }

  useEffect(() => {
    const map = new maplibregl.Map({
      container: container.current,
      center: initial.center,
      zoom: initial.zoom,
      maxBounds: [[-10, 40], [13, 52]],
      attributionControl: false,
      style: {
        version: 8,
        sources: {
          plan: { type: 'raster', tiles: [wmts('GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2', 'image/png')],
                  tileSize: 256, maxzoom: 19 },
          ortho: { type: 'raster', tiles: [wmts('ORTHOIMAGERY.ORTHOPHOTOS', 'image/jpeg')],
                   tileSize: 256, maxzoom: 19 },
          zones: { type: 'geojson', data: EMPTY },
          outlines: { type: 'geojson', data: EMPTY },
        },
        layers: [
          { id: 'plan', type: 'raster', source: 'plan' },
          { id: 'ortho', type: 'raster', source: 'ortho', layout: { visibility: 'none' } },
          { id: 'zones-fill', type: 'fill', source: 'zones',
            paint: { 'fill-color': NO_DATA_COLOR, 'fill-opacity': 0.6 } },
          { id: 'zones-line', type: 'line', source: 'zones',
            paint: { 'line-color': '#ffffff', 'line-width': 0.4, 'line-opacity': 0.7 } },
          { id: 'outlines', type: 'line', source: 'outlines',
            paint: { 'line-color': '#1b4d2b', 'line-width': 1.2, 'line-dasharray': [3, 2] } },
          { id: 'forest-selected', type: 'line', source: 'outlines', filter: ['==', 'forest_id', ''],
            paint: { 'line-color': '#0b2a16', 'line-width': 3 } },
          { id: 'zone-selected', type: 'line', source: 'zones', filter: ['==', 'forest_id', ''],
            paint: { 'line-color': '#6a1b9a', 'line-width': 3 } },
        ],
      },
    })
    map.addControl(new maplibregl.AttributionControl({ compact: false, customAttribution: ATTRIBUTION }))
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right')
    map.addControl(new maplibregl.ScaleControl({ unit: 'metric' }), 'bottom-right')

    const emitMove = () => {
      const b = map.getBounds()
      handlers.current.onMove([b.getWest(), b.getSouth(), b.getEast(), b.getNorth()], map.getZoom(),
                              map.getCenter())
    }
    map.on('load', () => { setReady(true); emitMove() })
    map.on('moveend', emitMove)
    map.on('click', 'zones-fill', (e) => {
      const p = e.features[0]?.properties
      if (p) handlers.current.onSelect({ forest_id: p.forest_id, lon: p.lon, lat: p.lat })
    })
    map.on('mouseenter', 'zones-fill', () => { map.getCanvas().style.cursor = 'pointer' })
    map.on('mouseleave', 'zones-fill', () => { map.getCanvas().style.cursor = '' })
    mapRef.current = map
    return () => map.remove()
  }, [])

  useEffect(() => {
    if (!ready) return
    mapRef.current.getSource('zones').setData(data?.zones || EMPTY)
    mapRef.current.getSource('outlines').setData(data?.outlines || EMPTY)
  }, [data, ready])

  useEffect(() => {
    if (ready && classes?.length) {
      mapRef.current.setPaintProperty('zones-fill', 'fill-color', scoreColorExpr(classes, scoreKey))
    }
  }, [classes, scoreKey, ready])

  useEffect(() => {
    if (!ready) return
    mapRef.current.setFilter('zones-fill', filter)
    mapRef.current.setFilter('zones-line', filter)
  }, [filter, ready])

  useEffect(() => {
    if (!ready) return
    const z = selected?.zone
    mapRef.current.setFilter('forest-selected', ['==', ['get', 'forest_id'], z?.forest_id ?? ''])
    mapRef.current.setFilter('zone-selected', z
      ? ['all', ['==', ['get', 'forest_id'], z.forest_id], ['==', ['get', 'lon'], z.lon], ['==', ['get', 'lat'], z.lat]]
      : ['==', ['get', 'forest_id'], ''])
  }, [selected, ready])

  useEffect(() => {
    if (ready && flyTarget) mapRef.current.flyTo({ center: flyTarget.center, zoom: flyTarget.zoom, speed: 1.6 })
  }, [flyTarget, ready])

  useEffect(() => {
    if (!ready) return
    markerRef.current?.remove()
    if (userPos) {
      markerRef.current = new maplibregl.Marker({ color: '#1565c0' }).setLngLat([userPos.lon, userPos.lat])
        .addTo(mapRef.current)
    }
  }, [userPos, ready])

  useEffect(() => {
    if (!ready) return
    mapRef.current.setLayoutProperty('plan', 'visibility', basemap === 'plan' ? 'visible' : 'none')
    mapRef.current.setLayoutProperty('ortho', 'visibility', basemap === 'ortho' ? 'visible' : 'none')
  }, [basemap, ready])

  return <div ref={container} className="map" />
}
