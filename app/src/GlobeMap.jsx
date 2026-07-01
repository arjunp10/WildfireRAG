import { useEffect, useRef, useState, useCallback } from 'react'
import mapboxgl from 'mapbox-gl'
import 'mapbox-gl/dist/mapbox-gl.css'

const MIN_YEAR = 2000
const MAX_YEAR = 2026

export default function GlobeMap({ mapboxToken }) {
  const containerRef = useRef(null)
  const mapRef = useRef(null)
  const [confidenceFilter, setConfidenceFilter] = useState('all')
  const [year, setYear] = useState(2020)
  const [playing, setPlaying] = useState(false)
  const playRef = useRef(false)

  useEffect(() => {
    mapboxgl.accessToken = mapboxToken

    const map = new mapboxgl.Map({
      container: containerRef.current,
      style: 'mapbox://styles/mapbox/light-v11',
      projection: 'globe',
      center: [-98, 38],
      zoom: 3,
      pitch: 30,
      bearing: 0,
    })
    mapRef.current = map

    map.addControl(new mapboxgl.NavigationControl(), 'top-right')
    map.addControl(new mapboxgl.FullscreenControl(), 'top-right')

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
              'circle-stroke-color': '#ffffff',
            },
          })
          map.on('click', 'fires-layer', e => {
            activePopup?.remove()
            const p = e.features[0].properties
            const risk = p.fire_probability != null
              ? `${(Number(p.fire_probability) * 100).toFixed(1)}%`
              : 'Unknown'
            activePopup = new mapboxgl.Popup()
              .setLngLat(e.lngLat)
              .setHTML(`
                <div style="font-family:system-ui;font-size:13px;line-height:1.6">
                  <strong>Active Fire</strong><br/>
                  Lat: ${Number(p.latitude).toFixed(4)}<br/>
                  Lon: ${Number(p.longitude).toFixed(4)}<br/>
                  Brightness: ${p.brightness}<br/>
                  Detected: ${p.acq_date} ${p.acq_time}<br/>
                  Confidence: ${p.confidence}<br/>
                  Risk Score: <strong>${risk}</strong>
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
                'interpolate', ['linear'],
                ['get', 'acres'],
                50000,  '#fde68a',
                200000, '#f97316',
                500000, '#dc2626',
              ],
              'fill-opacity': 0.35,
            },
            filter: ['==', ['get', 'year'], 2020],
          }, 'fires-layer')
          map.addLayer({
            id: 'fire-outlines-stroke',
            type: 'line',
            source: 'perimeter-outlines',
            paint: {
              'line-color': '#92400e',
              'line-width': 1,
              'line-opacity': 0.6,
            },
            filter: ['==', ['get', 'year'], 2020],
          }, 'fires-layer')
          map.on('click', 'fire-outlines-fill', e => {
            activePopup?.remove()
            const p = e.features[0].properties
            activePopup = new mapboxgl.Popup()
              .setLngLat(e.lngLat)
              .setHTML(`
                <div style="font-family:system-ui;font-size:13px;line-height:1.6">
                  <strong>${p.name || 'Unknown Fire'}</strong><br/>
                  Year: ${p.year}<br/>
                  State: ${p.state || 'Unknown'}<br/>
                  Size: <strong>${Number(p.acres).toLocaleString()} acres</strong>
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
              'circle-radius': ['interpolate', ['linear'], ['zoom'], 2, 2.5, 8, 5],
              'circle-color': [
                'interpolate', ['linear'],
                ['log2', ['max', ['get', 'acres'], 1]],
                7,  '#fbbf24',
                13, '#f97316',
                17, '#dc2626',
              ],
              'circle-opacity': 0.5,
              'circle-stroke-width': 0,
            },
            filter: ['<=', ['get', 'year'], 2020],
          }, 'fires-layer')
          map.on('click', 'historical-dots', e => {
            activePopup?.remove()
            const p = e.features[0].properties
            activePopup = new mapboxgl.Popup()
              .setLngLat(e.lngLat)
              .setHTML(`
                <div style="font-family:system-ui;font-size:13px;line-height:1.6">
                  <strong>${p.name || 'Unknown Fire'}</strong><br/>
                  Year: ${p.year}<br/>
                  State: ${p.state || 'Unknown'}<br/>
                  Size: <strong>${Number(p.acres).toLocaleString()} acres</strong>
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

  // Apply confidence filter to active FIRMS layer
  useEffect(() => {
    const map = mapRef.current
    if (!map || !map.getLayer('fires-layer')) return
    map.setFilter('fires-layer', confidenceFilter === 'all'
      ? null
      : ['==', ['get', 'confidence'], confidenceFilter])
  }, [confidenceFilter])

  // Apply year filter to historical layers
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    if (map.getLayer('historical-dots')) {
      map.setFilter('historical-dots', ['<=', ['get', 'year'], year])
    }
    if (map.getLayer('fire-outlines-fill')) {
      map.setFilter('fire-outlines-fill', ['==', ['get', 'year'], year])
      map.setFilter('fire-outlines-stroke', ['==', ['get', 'year'], year])
    }
  }, [year])

  // Play/pause animation
  useEffect(() => {
    playRef.current = playing
    if (!playing) return
    const tick = () => {
      if (!playRef.current) return
      setYear(y => {
        const next = y >= MAX_YEAR ? MIN_YEAR : y + 1
        return next
      })
      setTimeout(tick, 900)
    }
    const t = setTimeout(tick, 900)
    return () => clearTimeout(t)
  }, [playing])

  const btnStyle = (val) => ({
    padding: '4px 10px', borderRadius: 4, border: 'none', cursor: 'pointer',
    fontSize: 11, fontWeight: 600,
    background: confidenceFilter === val ? 'rgba(239,68,68,0.7)' : 'rgba(255,255,255,0.1)',
    color: confidenceFilter === val ? '#fff' : '#94a3b8',
    transition: 'background 0.15s',
  })

  return (
    <>
      <div ref={containerRef} style={{ width: '100vw', height: '100vh' }} />

      {/* Year slider */}
      <div style={{
        position: 'fixed', top: 36, left: 320, right: 20,
        zIndex: 900,
        background: 'rgba(15,15,25,0.82)',
        backdropFilter: 'blur(8px)',
        border: '1px solid rgba(255,255,255,0.1)',
        borderRadius: 8,
        padding: '8px 16px',
        display: 'flex', alignItems: 'center', gap: 12,
        fontFamily: 'system-ui',
      }}>
        <span style={{ fontSize: 11, color: '#64748b', whiteSpace: 'nowrap' }}>History</span>
        <span style={{ fontSize: 20, fontWeight: 700, color: '#ef4444', minWidth: 44 }}>{year}</span>
        <input
          type="range"
          min={MIN_YEAR}
          max={MAX_YEAR}
          value={year}
          onChange={e => { setPlaying(false); setYear(Number(e.target.value)) }}
          style={{ flex: 1, accentColor: '#ef4444', cursor: 'pointer' }}
        />
        <span style={{ fontSize: 11, color: '#64748b', whiteSpace: 'nowrap' }}>{MAX_YEAR}</span>
        <button
          onClick={() => setPlaying(p => !p)}
          style={{
            background: playing ? 'rgba(239,68,68,0.7)' : 'rgba(255,255,255,0.12)',
            border: 'none', borderRadius: 6, cursor: 'pointer',
            color: '#fff', fontSize: 13, padding: '4px 10px', fontWeight: 600,
          }}
        >
          {playing ? '⏸' : '▶'}
        </button>
        <div style={{ width: 1, background: 'rgba(255,255,255,0.1)', alignSelf: 'stretch' }} />
        <span style={{ fontSize: 11, color: '#64748b', whiteSpace: 'nowrap' }}>Active fires:</span>
        <button style={btnStyle('all')} onClick={() => setConfidenceFilter('all')}>All</button>
        <button style={btnStyle('n')} onClick={() => setConfidenceFilter('n')}>Nominal</button>
        <button style={btnStyle('h')} onClick={() => setConfidenceFilter('h')}>High</button>
      </div>

      {/* Legend */}
      <div style={{
        position: 'fixed', bottom: 24, left: '50%', transform: 'translateX(-50%)',
        zIndex: 900,
        background: 'rgba(15,15,25,0.85)',
        backdropFilter: 'blur(8px)',
        border: '1px solid rgba(255,255,255,0.1)',
        borderRadius: 8,
        padding: '6px 14px',
        display: 'flex', alignItems: 'center', gap: 16,
        fontFamily: 'system-ui', fontSize: 11, color: '#94a3b8',
      }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#22c55e', display: 'inline-block' }} />
          Low risk
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#eab308', display: 'inline-block' }} />
          Med risk
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#ef4444', display: 'inline-block' }} />
          High risk (active)
        </span>
        <span style={{ color: 'rgba(255,255,255,0.2)' }}>|</span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#f97316', opacity: 0.6, display: 'inline-block' }} />
          Confirmed (history)
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <span style={{ width: 14, height: 10, background: 'rgba(249,115,22,0.4)', border: '1px solid #92400e', display: 'inline-block', borderRadius: 2 }} />
          Perimeter (≥50k acres)
        </span>
      </div>
    </>
  )
}
