import { useEffect, useRef } from 'react'
import mapboxgl from 'mapbox-gl'
import 'mapbox-gl/dist/mapbox-gl.css'

export default function GlobeMap({ mapboxToken }) {
  const containerRef = useRef(null)

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
                  0,   '#22c55e',
                  0.5, '#eab308',
                  1,   '#ef4444',
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
    }
  }, [mapboxToken])

  return <div ref={containerRef} style={{ width: '100vw', height: '100vh' }} />
}
