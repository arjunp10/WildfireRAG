# Dev Log

## 2026-06-28 — Phase 1: Data Collection Pipeline

### Goals
Stand up the data collection foundation: three sources flowing into SQLite.

### Completed

**Project scaffold**
- Initialized git repo
- `requirements.txt`: requests, python-dotenv, tabulate, pytest
- `data/` and `tests/` package structure
- `.gitignore` excluding `firerag.db`, `.env`, large data files

**Database schema (`data/db.py`)**
- 4 tables: `fires_realtime`, `weather`, `fires_historical`, `fires_predictions`
- `fires_predictions` created now for forward compatibility with Phase 2
- `ingested_at` on all tables = pull timestamp (not detection time)
- `get_connection()` + `init_db()` — idempotent DDL

**NASA FIRMS real-time (`data/firms.py`)**
- VIIRS SNPP NRT product, last 24h, CONUS bounding box (-130,24,-65,50)
- Pulled 2,717 active fire hotspots on first live run
- Fields: latitude, longitude, brightness, acq_date, acq_time, confidence, satellite

**NOAA weather (`data/noaa.py`)**
- Two-step API: `/points/{lat},{lon}` → hourly forecast URL
- 25 hand-picked fire-prone locations across CONUS (CA, OR, WA, ID, MT, NV, AZ, NM, CO, UT, WY, TX)
- Wind direction mapped from cardinal strings to degrees
- Graceful per-location failure (one bad location doesn't block the rest)

**Historical fire data (`data/historical.py`)**
- Switched from NASA FIRMS archive (hit API rate limits + MODIS decommissioned in 2024) to Kaggle dataset
- Dataset: [2.3 Million US Wildfires (6th Edition)](https://www.kaggle.com/datasets/rtatman/188-million-us-wildfires) — USFS FPA-FOD, 1992–2020
- Reads local SQLite file (`data/data.sqlite`) — no API calls, no rate limits
- Loaded **2,303,566 records** in ~7 seconds
- `frp` column stores fire size in acres (useful proxy for fire intensity in Phase 2)
- `satellite` column repurposed to store fire cause (NWCG_GENERAL_CAUSE)

**Ingest CLI (`ingest.py`)**
- Sequential orchestration: FIRMS → NOAA → Kaggle historical
- Per-source: fetch timing, row count, 3-row tabulate sample
- Graceful degradation: one source failure doesn't block others
- Missing API key exits early with signup URL

**Tests**
- 21 tests, all HTTP-mocked (no live API needed)
- `test_db.py` (6), `test_firms.py` (4), `test_noaa.py` (6), `test_historical.py` (5)
- All passing

### Issues Encountered
- NASA FIRMS archive (`VIIRS_SNPP_SP`) returned 400 — free map key doesn't support archive tier
- `MODIS_SP` caps at 5-day chunks and was decommissioned before 2024 — chunks beyond 2024 returned 400
- Switched to Kaggle dataset to avoid API rate limits entirely
- FIRMS API hit transaction rate limit during testing — real-time fetch returned 0 records on evening run (resets in 24h)
- `executescript` with `AUTOINCREMENT` creates internal `sqlite_sequence` table — fixed idempotency test to exclude `sqlite_%` tables
- NOAA mock test: `"points" in url` also matched `"gridpoints"` URL — fixed to `"/points/" in url and "gridpoints" not in url`
- `_run_source` called `save_fn(records, conn)` but lambdas already captured `conn` in closure — fixed to `save_fn(records)`

### Design Decisions
- Weather grid at 25 representative locations vs full 1.0° CONUS grid (~1,600 points) — NOAA requires 2 API calls per point, making full grid impractical without async/rate limiting
- `fires_predictions` table created in Phase 1 for forward compatibility
- `frp` (fire radiative power) repurposed to store fire size in acres from Kaggle — more useful for Phase 2 regression features than satellite brightness

### Next Up (Phase 2)
- Feature engineering from `fires_historical`: lat/lon grid, month/season, fire size distribution
- Join weather data to historical fire locations
- Train logistic regression + random forest
- Populate `fires_predictions` table with outputs
