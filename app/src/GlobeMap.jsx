import { useEffect, useRef, useState } from 'react'
import mapboxgl from 'mapbox-gl'
import 'mapbox-gl/dist/mapbox-gl.css'

export default function GlobeMap({ mapboxToken }) {
  const containerRef = useRef(null)
  const mapRef = useRef(null)
  const [confidenceFilter, setConfidenceFilter] = useState('all')

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

      fetch('/fires.json')
        .then(r => r.json())
        .then(data => {
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
              'circle-radius': [
                'interpolate', ['linear'], ['zoom'],
                2, 4,
                8, 8,
              ],
              'circle-color': [
                'case',
                ['==', ['get', 'fire_probability'], null],
                '#94a3b8',
                [
                  'interpolate', ['linear'], ['get', 'fire_probability'],
                  0,    '#22c55e',
                  0.065,'#eab308',
                  0.13, '#ef4444',
                ],
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

          map.on('mouseenter', 'fires-layer', () => {
            map.getCanvas().style.cursor = 'pointer'
          })
          map.on('mouseleave', 'fires-layer', () => {
            map.getCanvas().style.cursor = ''
          })
        })
        .catch(err => console.error('Failed to load fires.json:', err))
    })

    return () => {
      cancelled = true
      map.remove()
      mapRef.current = null
    }
  }, [mapboxToken])

  // Apply confidence filter whenever it changes
  useEffect(() => {
    const map = mapRef.current
    if (!map || !map.getLayer('fires-layer')) return
    if (confidenceFilter === 'all') {
      map.setFilter('fires-layer', null)
    } else {
      map.setFilter('fires-layer', ['==', ['get', 'confidence'], confidenceFilter])
    }
  }, [confidenceFilter])

  const btnStyle = (val) => ({
    padding: '4px 10px',
    borderRadius: 4,
    border: 'none',
    cursor: 'pointer',
    fontSize: 11,
    fontWeight: 600,
    background: confidenceFilter === val ? 'rgba(239,68,68,0.7)' : 'rgba(255,255,255,0.1)',
    color: confidenceFilter === val ? '#fff' : '#94a3b8',
    transition: 'background 0.15s',
  })

  return (
    <>
      <div ref={containerRef} style={{ width: '100vw', height: '100vh' }} />
      <div style={{
        position: 'fixed', bottom: 24, left: '50%', transform: 'translateX(-50%)',
        zIndex: 900,
        background: 'rgba(15,15,25,0.85)',
        backdropFilter: 'blur(8px)',
        border: '1px solid rgba(255,255,255,0.1)',
        borderRadius: 8,
        padding: '6px 10px',
        display: 'flex', alignItems: 'center', gap: 8,
        fontFamily: 'system-ui', fontSize: 11, color: '#94a3b8',
      }}>
        <span style={{ marginRight: 4 }}>Confidence:</span>
        <button style={btnStyle('all')} onClick={() => setConfidenceFilter('all')}>All</button>
        <button style={btnStyle('n')} onClick={() => setConfidenceFilter('n')}>Nominal</button>
        <button style={btnStyle('h')} onClick={() => setConfidenceFilter('h')}>High</button>
      </div>
    </>
  )
}
