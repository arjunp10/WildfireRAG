# WildfireRAG

A wildfire monitoring, forecasting, and retrieval-augmented generation (RAG) system built in Python.

## What It Does

1. **Real-time monitoring** — pulls active fire hotspots from NASA FIRMS and current weather from NOAA
2. **Predictive forecasting** — trains a model on historical fire data to predict fire probability by location and date
3. **RAG query layer** — answers natural language questions like "Why are fires concentrated in California?" by retrieving historical fire data and current conditions

## Tech Stack

- **Data**: NASA FIRMS API, NOAA Weather API, USFS Wildfire Dataset (Kaggle)
- **Storage**: SQLite
- **Models**: scikit-learn (logistic regression / random forest)
- **RAG**: LangChain + ChromaDB
- **Backend**: FastAPI
- **Frontend**: Streamlit

## Project Structure

```
WildfireRAG/
├── data/
│   ├── db.py          # SQLite schema and connection
│   ├── firms.py       # NASA FIRMS real-time hotspot ingest
│   ├── noaa.py        # NOAA weather ingest (25 fire-prone locations)
│   └── historical.py  # Kaggle USFS historical fire data ingest
├── ingest.py          # CLI: runs all data sources, logs samples
├── tests/             # pytest test suite (21 tests)
├── docs/
│   └── superpowers/
│       ├── specs/     # Design documents
│       └── plans/     # Implementation plans
└── requirements.txt
```

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Get a NASA FIRMS API key

Sign up at https://firms.modaps.eosdis.nasa.gov/api/ (free).

```bash
echo "FIRMS_MAP_KEY=your_key_here" > .env
```

### 3. Download historical fire data

Download the [2.3 Million US Wildfires (6th Edition)](https://www.kaggle.com/datasets/rtatman/188-million-us-wildfires) dataset from Kaggle and save the `.sqlite` file as:

```
data/data.sqlite
```

### 4. Run the ingest pipeline

```bash
python3 ingest.py
```

This pulls:
- Live fire hotspots (NASA FIRMS VIIRS, last 24h, CONUS)
- Current weather at 25 fire-prone locations (NOAA)
- 2.3M historical fire records from 1992–2020 (Kaggle/USFS)

All data lands in `firerag.db` (SQLite).

## Database Schema

| Table | Description |
|---|---|
| `fires_realtime` | Active fire hotspots from NASA FIRMS |
| `weather` | Current weather at fire-prone locations |
| `fires_historical` | 2.3M historical US fire records (1992–2020) |
| `fires_predictions` | Model predictions (populated in Phase 2) |

## Development Phases

- [x] **Phase 1** — Data collection pipeline (NASA FIRMS + NOAA + Kaggle)
- [ ] **Phase 2** — Forecasting model (logistic regression / random forest)
- [ ] **Phase 3** — Monitoring dashboard (Streamlit + FastAPI)
- [ ] **Phase 4** — RAG query layer (LangChain + ChromaDB)
- [ ] **Phase 5** — Polish and deploy (Hugging Face Spaces / Railway)

## Running Tests

```bash
pytest tests/ -v
```

21 tests, all mocked (no API keys required for testing).
