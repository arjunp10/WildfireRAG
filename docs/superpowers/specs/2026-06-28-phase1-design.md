# FireRAG Phase 1 Design — Data Collection Layer

**Date:** 2026-06-28
**Status:** Approved

## Overview

Phase 1 establishes the data collection foundation for FireRAG: a wildfire monitoring, forecasting, and RAG system. The goal is to get three data sources flowing into a local SQLite database with no strict output format requirement — just data moving reliably.

## Project Structure

```
FireRAG/
├── data/
│   ├── __init__.py
│   ├── db.py          # SQLite connection, schema creation, shared session
│   ├── firms.py       # NASA FIRMS real-time hotspot fetch + save
│   ├── noaa.py        # NOAA weather fetch + save
│   └── historical.py  # NASA FIRMS historical archive fetch + save
├── ingest.py          # CLI entrypoint: runs all three sources, prints sample
├── firerag.db         # Created on first run (gitignored)
├── .env               # API keys (gitignored)
├── requirements.txt
└── docs/
    └── superpowers/specs/
```

Each module in `data/` exports two functions:
- `fetch() -> list[dict]` — hits the API, returns normalized records
- `save(records, conn) -> int` — writes to SQLite, returns row count inserted

## Data Sources

### NASA FIRMS (real-time)
- **Auth:** Free API key from firms.modaps.eosdis.nasa.gov
- **Endpoint:** Active fire hotspots from MODIS/VIIRS, last 24–48h, CONUS area
- **Format:** CSV response, parsed to list of dicts

### NOAA (weather)
- **Auth:** None required — api.weather.gov is public
- **Coverage:** 1.0° grid over CONUS (~1,600 points). Coarser than 0.5° to keep queries fast and storage reasonable.
- **Format:** JSON response per grid point

### NASA FIRMS (historical)
- **Auth:** Same API key as real-time
- **Scope:** 1 year of CONUS data via area + date range query
- **Fetch once:** Not re-fetched on subsequent ingest runs (data doesn't change)

## Database Schema (SQLite)

```sql
fires_realtime (
  id INTEGER PRIMARY KEY,
  latitude REAL, longitude REAL,
  brightness REAL, acq_date TEXT, acq_time TEXT,
  confidence TEXT, satellite TEXT,
  ingested_at TEXT  -- ISO timestamp of when this row was pulled, not detected
)

weather (
  id INTEGER PRIMARY KEY,
  latitude REAL, longitude REAL,
  temperature REAL, humidity REAL,
  wind_speed REAL, wind_dir REAL,
  timestamp TEXT, ingested_at TEXT
)

fires_historical (
  id INTEGER PRIMARY KEY,
  latitude REAL, longitude REAL,
  brightness REAL, frp REAL,  -- fire radiative power (intensity proxy)
  acq_date TEXT, acq_time TEXT,
  confidence TEXT, satellite TEXT,
  ingested_at TEXT
)

fires_predictions (
  id INTEGER PRIMARY KEY,
  latitude REAL, longitude REAL,
  fire_probability REAL,
  prediction_date TEXT,
  model_version TEXT,
  ingested_at TEXT
  -- Populated in Phase 2. Schema created in Phase 1 for forward compatibility.
)
```

## Data Flow

`ingest.py` runs sequentially:

1. `db.py` creates all 4 tables if they don't exist (idempotent DDL)
2. For each source: fetch → save → log count + timing + 3-row sample table
3. Each source is independently try/caught — one failure doesn't block the others

### Idempotency
- `fires_realtime` and `weather`: re-running inserts fresh rows (acceptable; these are time-series snapshots)
- `fires_historical`: fetched once; no duplicate concern
- `fires_predictions`: Phase 2 only

## Error Handling

- Missing `.env` key: exit early with message naming the missing key and its signup URL
- HTTP error from any source: log source name, status code, and response snippet; continue to next source
- No retries in Phase 1

## Logging & Observability

Use Python's `logging` module throughout (not `print()`):

```python
import logging
logger = logging.getLogger(__name__)
logger.info(f"FIRMS: ingested {count} records in {elapsed:.2f}s")
```

Each source logs:
- Fetch start
- Fetch duration (`time.time()` wrapping the fetch call)
- Row count saved
- 3-row sample formatted as a readable table (not raw dicts)

## Dependencies

```
requests
python-dotenv
tabulate       # for 3-row sample formatting
```

## Out of Scope for Phase 1

- FastAPI endpoints (Phase 3)
- Streamlit dashboard (Phase 3)
- Model training (Phase 2)
- RAG / ChromaDB (Phase 4)
- Deduplication of real-time fire records across runs
