# FireRAG

A wildfire intelligence platform combining a RAG-powered chat interface with real-time and historical fire data visualized on an interactive 3D globe.

## What It Does

- **Natural-language Q&A** — ask questions like *"Why is fire risk high in Northern California?"* and get answers grounded in live weather, satellite detections, and 26 years of fire history via RAG
- **Active fire tracking** — real-time NASA FIRMS satellite hotspots with high/nominal/low confidence filtering
- **Fire Risk Index** — composite score from Fosberg FWI (peak 7-day NWS forecast) × 26-year ignition history, rendered as a choropleth grid
- **Spread prediction** — 24-hour wind-aligned spread ellipses for active fire clusters
- **Historical record** — 41,000+ fire perimeters (2000–2026) with a month slider

## Tech Stack

| Layer | Technologies |
|---|---|
| Frontend | React, Vite, Mapbox GL JS |
| Backend | FastAPI, SQLite |
| Vector DB | ChromaDB |
| Embeddings | sentence-transformers (`all-MiniLM-L6-v2`) |
| LLM | Anthropic Claude API (Haiku) |
| Data | NASA FIRMS, NWS API, GeomAC/WFIGS perimeters |

No LangChain. No LlamaIndex. RAG pipeline, context injection, and embeddings are all built from scratch.

## Architecture

```
NASA FIRMS ──► SQLite (fires_grid)  ──►┐
NWS API    ──► SQLite (weather_grid) ──►├── FastAPI /chat
GeomAC/WFIGS ► ChromaDB (perimeters) ──►│     └── Claude Haiku
News API   ──► ChromaDB (news)  ────────┘
                                         ▲
                              state bbox SQL filtering
                              + ChromaDB semantic search
```

At query time, the `/chat` endpoint:
1. Filters weather/risk/spread/FIRMS data by the states mentioned in the query via bounding-box SQL
2. Runs semantic search over ChromaDB collections (perimeters, news, regions, FIRMS)
3. Injects all context into Claude Haiku's prompt

## Project Structure

```
FireRAG/
├── api/
│   └── main.py          # FastAPI: /chat, /risk/grid, /spread/current, /stats
├── app/
│   └── src/
│       ├── App.jsx
│       ├── GlobeMap.jsx  # Mapbox GL layers (fires, weather, risk, spread, perimeters)
│       ├── Sidebar.jsx   # Layer toggles
│       ├── TimelineBar.jsx
│       └── ChatBox.jsx
├── data/
│   ├── firms.py          # NASA FIRMS ingest
│   └── weather_grid.py   # NWS weather grid builder
├── risk/
│   └── compute_risk.py   # Fosberg FWI + historical ignition → risk score
├── spread/
│   └── compute.py        # DBSCAN clustering + wind-aligned ellipses
├── weather/
│   └── fetch_forecast.py # NWS 7-day hourly forecast → peak FWI
└── refresh_weather.sh    # Daily refresh: FIRMS + weather + forecast + risk
```

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
cd app && npm install
```

### 2. Set environment variables

```bash
export MAPBOX_TOKEN=your_mapbox_token
export ANTHROPIC_API_KEY=your_anthropic_key
export FIRMS_MAP_KEY=your_firms_key
export NEWS_API_KEY=your_newsapi_key
```

### 3. Run the daily refresh

```bash
bash refresh_weather.sh
```

### 4. Start the servers

```bash
# Backend
uvicorn api.main:app --reload

# Frontend
cd app && npm run dev
```

Open `http://localhost:5173`.

## Resume

- Built a RAG pipeline over 41,000+ historical fire perimeters, NASA FIRMS satellite detections, and NWS forecast data using ChromaDB with all-MiniLM-L6-v2 embeddings and Claude Haiku for natural-language Q&A
- Computed Fosberg FWI risk scores via SQLite queries with state bounding-box filtering and rendered wind-aligned 24h spread ellipses as choropleth overlays on a Mapbox GL globe with 3D terrain exaggeration
