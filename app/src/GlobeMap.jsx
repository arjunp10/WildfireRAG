import { useEffect, useRef } from 'react'
import mapboxgl from 'mapbox-gl'
import 'mapbox-gl/dist/mapbox-gl.css'
import { idxToLabel } from './utils.js'

export default function GlobeMap({ mapboxToken, monthIdx, confidenceFilter }) {
  const containerRef = useRef(null)
  const mapRef = useRef(null)

  useEffect(() => {
    mapboxgl.accessToken = mapboxToken

    const map = new mapboxgl.Map({
      container: containerRef.current,
      style: 'mapbox://styles/mapbox/dark-v11',
      projection: 'globe',
      center: [-98, 38],
      zoom: 3,
      pitch: 25,
      bearing: 0,
    })
    mapRef.current = map

    map.addControl(new mapboxgl.NavigationControl(), 'bottom-right')

    let cancelled = false
    let activePopup = null

    map.on('load', () => {
      if (cancelled) return
      map.addSource('mapbox-dem', {
        type: 'raster-dem',
        url: 'mapbox://mapbox.mapbox-terrain-dem-v1',
        tileSize: 512,
      })
      map.setTerrain({ source: 'mapbox-dem', exaggeration: 1.5 })
      map.setFog({})

      // --- Active FIRMS fires ---
      fetch('/fires.json')
        .then(r => r.json())
        .then(data => {
          if (cancelled) return
          const geojson = {
            type: 'FeatureCollection',
            features: data.fires.map(f => ({
              type: 'Feature',
              geometry: { type: 'Point', coordinates: [f.longitude, f.latitude] },
              properties: f,
            })),
          }
          map.addSource('fires', { type: 'geojson', data: geojson })
          map.addLayer({
            id: 'fires-layer',
            type: 'circle',
            source: 'fires',
            paint: {
              'circle-radius': ['interpolate', ['linear'], ['zoom'], 2, 4, 8, 8],
              'circle-color': [
                'case',
                ['==', ['get', 'fire_probability'], null], '#94a3b8',
                ['interpolate', ['linear'], ['get', 'fire_probability'],
                  0, '#22c55e', 0.065, '#eab308', 0.13, '#ef4444'],
              ],
              'circle-opacity': 0.85,
              'circle-stroke-width': 1,
              'circle-stroke-color': 'rgba(0,0,0,0.3)',
            },
          })
          map.on('click', 'fires-layer', e => {
            activePopup?.remove()
            const p = e.features[0].properties
            const risk = p.fire_probability != null
              ? `${(Number(p.fire_probability) * 100).toFixed(1)}%`
              : 'Unknown'
            activePopup = new mapboxgl.Popup({ className: 'fire-popup' })
              .setLngLat(e.lngLat)
              .setHTML(`
                <div class="popup-inner">
                  <div class="popup-title">Active Detection</div>
                  <div class="popup-row"><span>Detected</span><span>${p.acq_date} ${p.acq_time}</span></div>
                  <div class="popup-row"><span>Confidence</span><span>${p.confidence?.toUpperCase()}</span></div>
                  <div class="popup-row"><span>Brightness</span><span>${Number(p.brightness).toFixed(0)} K</span></div>
                  <div class="popup-row popup-risk"><span>Risk Score</span><span>${risk}</span></div>
                </div>
              `)
              .addTo(map)
          })
          map.on('mouseenter', 'fires-layer', () => { map.getCanvas().style.cursor = 'pointer' })
          map.on('mouseleave', 'fires-layer', () => { map.getCanvas().style.cursor = '' })
        })
        .catch(err => console.error('Failed to load fires.json:', err))

      // --- Historical fire outlines (large fires) ---
      fetch('/perimeter_outlines.json')
        .then(r => r.json())
        .then(data => {
          if (cancelled) return
          map.addSource('perimeter-outlines', { type: 'geojson', data })
          map.addLayer({
            id: 'fire-outlines-fill',
            type: 'fill',
            source: 'perimeter-outlines',
            paint: {
              'fill-color': [
                'interpolate', ['linear'], ['get', 'acres'],
                50000,  '#fde68a',
                200000, '#f97316',
                500000, '#dc2626',
              ],
              'fill-opacity': 0.3,
            },
            filter: ['==', ['get', 'month_idx'], 240],
          }, 'fires-layer')
          map.addLayer({
            id: 'fire-outlines-stroke',
            type: 'line',
            source: 'perimeter-outlines',
            paint: {
              'line-color': '#92400e',
              'line-width': 1,
              'line-opacity': 0.55,
            },
            filter: ['==', ['get', 'month_idx'], 240],
          }, 'fires-layer')
          map.on('click', 'fire-outlines-fill', e => {
            activePopup?.remove()
            const p = e.features[0].properties
            const dateLabel = p.month_idx != null ? idxToLabel(p.month_idx) : String(p.year)
            activePopup = new mapboxgl.Popup({ className: 'fire-popup' })
              .setLngLat(e.lngLat)
              .setHTML(`
                <div class="popup-inner">
                  <div class="popup-title">${p.name || 'Unknown Fire'}</div>
                  <div class="popup-row"><span>Date</span><span>${dateLabel}</span></div>
                  <div class="popup-row"><span>State</span><span>${p.state || '—'}</span></div>
                  <div class="popup-row popup-risk"><span>Size</span><span>${Number(p.acres).toLocaleString()} acres</span></div>
                </div>
              `)
              .addTo(map)
          })
          map.on('mouseenter', 'fire-outlines-fill', () => { map.getCanvas().style.cursor = 'pointer' })
          map.on('mouseleave', 'fire-outlines-fill', () => { map.getCanvas().style.cursor = '' })
        })
        .catch(err => console.error('Failed to load perimeter_outlines.json:', err))

      // --- Historical confirmed fire dots ---
      fetch('/perimeter_dots.json')
        .then(r => r.json())
        .then(data => {
          if (cancelled) return
          map.addSource('perimeter-dots', { type: 'geojson', data })
          map.addLayer({
            id: 'historical-dots',
            type: 'circle',
            source: 'perimeter-dots',
            paint: {
              'circle-radius': ['interpolate', ['linear'], ['zoom'], 2, 2, 8, 5],
              'circle-color': [
                'interpolate', ['linear'],
                ['log2', ['max', ['get', 'acres'], 1]],
                7,  '#fbbf24',
                13, '#f97316',
                17, '#dc2626',
              ],
              'circle-opacity': 0.45,
              'circle-stroke-width': 0,
            },
            filter: ['<=', ['get', 'month_idx'], 240],
          }, 'fires-layer')
          map.on('click', 'historical-dots', e => {
            activePopup?.remove()
            const p = e.features[0].properties
            const dateLabel = p.month_idx != null ? idxToLabel(p.month_idx) : String(p.year)
            activePopup = new mapboxgl.Popup({ className: 'fire-popup' })
              .setLngLat(e.lngLat)
              .setHTML(`
                <div class="popup-inner">
                  <div class="popup-title">${p.name || 'Unknown Fire'}</div>
                  <div class="popup-row"><span>Date</span><span>${dateLabel}</span></div>
                  <div class="popup-row"><span>State</span><span>${p.state || '—'}</span></div>
                  <div class="popup-row popup-risk"><span>Size</span><span>${Number(p.acres).toLocaleString()} acres</span></div>
                </div>
              `)
              .addTo(map)
          })
          map.on('mouseenter', 'historical-dots', () => { map.getCanvas().style.cursor = 'pointer' })
          map.on('mouseleave', 'historical-dots', () => { map.getCanvas().style.cursor = '' })
        })
        .catch(err => console.error('Failed to load perimeter_dots.json:', err))
    })

    return () => {
      cancelled = true
      map.remove()
      mapRef.current = null
    }
  }, [mapboxToken])

  // Apply confidence filter
  useEffect(() => {
    const map = mapRef.current
    if (!map || !map.getLayer('fires-layer')) return
    map.setFilter('fires-layer',
      confidenceFilter === 'all' ? null : ['==', ['get', 'confidence'], confidenceFilter])
  }, [confidenceFilter])

  // Apply month filter
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    if (map.getLayer('historical-dots')) {
      map.setFilter('historical-dots', ['<=', ['get', 'month_idx'], monthIdx])
    }
    if (map.getLayer('fire-outlines-fill')) {
      map.setFilter('fire-outlines-fill', ['==', ['get', 'month_idx'], monthIdx])
      map.setFilter('fire-outlines-stroke', ['==', ['get', 'month_idx'], monthIdx])
    }
  }, [monthIdx])

  return <div ref={containerRef} style={{ width: '100vw', height: '100vh' }} />
}
