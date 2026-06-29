# WildfireRAG Phase 3 Design — Mapbox 3D Globe Dashboard

**Date:** 2026-06-29
**Status:** Approved

## Overview

Phase 3 adds a visual frontend: a Mapbox GL JS 3D globe that plots all active fires from `fires_realtime`, color-coded by the risk score from `fires_predictions`. A Python export script bridges the SQLite database to the React app via a static JSON file.

## Architecture

Two independent pieces:

1. **`export_data.py`** (repo root) — reads `firerag.db`, joins `fires_realtime` with `fires_predictions` on binned lat/lon, writes `app/public/fires.json`.
2. **`app/`** — Vite + React single-page app. One `GlobeMap` component handles all Mapbox GL JS logic. No backend server required at runtime.

Workflow: `python3 export_data.py` → `npm run dev` (in `app/`).

## File Structure

```
export_data.py               # Python: firerag.db → app/public/fires.json
app/
├── public/
│   └── fires.json           # generated output (gitignored)
├── src/
│   ├── main.jsx             # React entry point
│   ├── App.jsx              # layout shell, reads VITE_MAPBOX_TOKEN
│   └── GlobeMap.jsx         # all Mapbox GL JS logic
├── .env                     # VITE_MAPBOX_TOKEN=pk.xxx (gitignored)
├── .env.example             # committed, shows required var name
├── index.html
├── package.json
└── vite.config.js
```

## export_data.py

Reads `firerag.db` (default path, overridable via `--db` CLI arg). Joins every row in `fires_realtime` to its matching cell in `fires_predictions` using the same 0.5° binning formula used in Phase 2:

```
cell_lat = round(latitude * 2) / 2
cell_lon = round(longitude * 2) / 2
```

Join logic: for each fire, look up `fires_predictions` where `round(pred.latitude*2)/2 = cell_lat AND round(pred.longitude*2)/2 = cell_lon` and `prediction_date` is the most recent available. Fires with no matching prediction get `fire_probability: null`.

Output written to `app/public/fires.json`:

```json
{
  "generated_at": "2026-06-29T12:00:00+00:00",
  "count": 5698,
  "fires": [
    {
      "id": 1,
      "latitude": 37.12,
      "longitude": -120.34,
      "brightness": 310.5,
      "acq_date": "2026-06-29",
      "acq_time": "0145",
      "confidence": "nominal",
      "satellite": "N",
      "fire_probability": 0.72
    }
  ]
}
```

Script exits with code 0 and prints `Wrote N fires to app/public/fires.json`.

## React App

### Dependencies

```json
{
  "mapbox-gl": "^3.x",
  "react": "^18.x",
  "react-dom": "^18.x"
}
```

Dev: `vite`, `@vitejs/plugin-react`

### App.jsx

Layout shell. Reads `import.meta.env.VITE_MAPBOX_TOKEN` and passes it as a prop to `GlobeMap`. Renders a full-viewport container (`width: 100vw, height: 100vh`). If the token is missing, renders an error banner instead of the map.

### GlobeMap.jsx

Receives `mapboxToken: string` as a prop. Uses a `useRef` for the map container div and a `useEffect` to initialize the Mapbox map once on mount.

**Map initialization:**
```js
mapboxgl.accessToken = mapboxToken;
const map = new mapboxgl.Map({
  container: containerRef.current,
  style: 'mapbox://styles/mapbox/light-v11',
  projection: 'globe',
  center: [-98, 38],          // center of CONUS
  zoom: 3,
  pitch: 30,
  bearing: 0,
});
```

**On `map.on('load')`:**

1. Add terrain:
```js
map.addSource('mapbox-dem', {
  type: 'raster-dem',
  url: 'mapbox://mapbox.mapbox-terrain-dem-v1',
  tileSize: 512,
});
map.setTerrain({ source: 'mapbox-dem', exaggeration: 1.5 });
```

2. Add atmosphere (globe glow):
```js
map.setFog({});
```

3. Fetch `/fires.json`, convert to GeoJSON FeatureCollection, add as source:
```js
map.addSource('fires', {
  type: 'geojson',
  data: {
    type: 'FeatureCollection',
    features: fires.map(f => ({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [f.longitude, f.latitude] },
      properties: f,
    })),
  },
});
```

4. Add circle layer with color expression:
```js
map.addLayer({
  id: 'fires-layer',
  type: 'circle',
  source: 'fires',
  paint: {
    'circle-radius': ['interpolate', ['linear'], ['zoom'], 2, 4, 8, 8],
    'circle-color': [
      'case',
      ['==', ['get', 'fire_probability'], null],
      '#94a3b8',
      ['interpolate', ['linear'], ['get', 'fire_probability'],
        0,   '#22c55e',
        0.5, '#eab308',
        1,   '#ef4444',
      ],
    ],
    'circle-opacity': 0.85,
    'circle-stroke-width': 1,
    'circle-stroke-color': '#ffffff',
  },
});
```

5. Add popup on click:
```js
map.on('click', 'fires-layer', (e) => {
  const props = e.features[0].properties;
  const riskStr = props.fire_probability != null
    ? `${(props.fire_probability * 100).toFixed(1)}%`
    : 'Unknown';
  new mapboxgl.Popup()
    .setLngLat(e.lngLat)
    .setHTML(`
      <div style="font-family: system-ui; font-size: 13px; line-height: 1.6">
        <strong>Active Fire</strong><br/>
        Lat: ${props.latitude.toFixed(4)}<br/>
        Lon: ${props.longitude.toFixed(4)}<br/>
        Brightness: ${props.brightness}<br/>
        Detected: ${props.acq_date} ${props.acq_time}<br/>
        Confidence: ${props.confidence}<br/>
        Risk Score: <strong>${riskStr}</strong>
      </div>
    `)
    .addTo(map);
});
map.on('mouseenter', 'fires-layer', () => { map.getCanvas().style.cursor = 'pointer'; });
map.on('mouseleave', 'fires-layer', () => { map.getCanvas().style.cursor = ''; });
```

6. Add controls:
```js
map.addControl(new mapboxgl.NavigationControl(), 'top-right');
map.addControl(new mapboxgl.FullscreenControl(), 'top-right');
```

Cleanup: `map.remove()` in the `useEffect` return function.

## Token Handling

`app/.env` (gitignored):
```
VITE_MAPBOX_TOKEN=pk.eyJ...
```

`app/.env.example` (committed):
```
VITE_MAPBOX_TOKEN=your_mapbox_token_here
```

## .gitignore additions

```
app/public/fires.json
app/.env
app/node_modules/
app/dist/
```

## Out of Scope for Phase 3

- FastAPI backend / live data refresh
- Legend UI component
- Filter controls (by date, confidence, risk threshold)
- Heatmap or cluster layer
- Streamlit embedding (Phase 5)
- Mobile layout
