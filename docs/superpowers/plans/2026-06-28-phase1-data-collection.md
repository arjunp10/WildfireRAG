# FireRAG Phase 1 — Data Collection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a Python data package that pulls live fire hotspots (NASA FIRMS), current weather (NOAA), and one year of historical fire data (NASA FIRMS archive) into a local SQLite database.

**Architecture:** A `data/` package with one module per source, each exporting `fetch() -> list[dict]` and `save(records, conn) -> int`. A shared `db.py` owns the SQLite connection and all DDL. A top-level `ingest.py` CLI script orchestrates the three sources sequentially, logging timing and a 3-row sample per source.

**Tech Stack:** Python 3.11+, sqlite3 (stdlib), requests, python-dotenv, tabulate, pytest, unittest.mock

## Global Constraints

- Python 3.11+
- All `data/` modules use `logging.getLogger(__name__)` — no bare `print()`
- API keys loaded exclusively from `.env` via `python-dotenv` — never hardcoded
- Each source independently try/caught in `ingest.py` — one failure must not block the others
- `ingested_at` on every row = ISO 8601 UTC timestamp of when the row was pulled (not detected)
- NOAA calls limited to ~25 fire-prone locations for Phase 1 (full 1.0° CONUS grid deferred — NOAA requires 2 API calls per point, making 1,600 points impractical without a rate limiter)
- No retries in Phase 1
- `firerag.db` and `.env` are gitignored

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `requirements.txt` | Create | Pinned dependencies |
| `.gitignore` | Create | Exclude db, env, cache |
| `.env.example` | Create | Document required keys |
| `data/__init__.py` | Create | Empty package marker |
| `data/db.py` | Create | SQLite connection + DDL for all 4 tables |
| `data/firms.py` | Create | NASA FIRMS real-time fetch + save |
| `data/noaa.py` | Create | NOAA weather fetch + save |
| `data/historical.py` | Create | NASA FIRMS historical fetch + save |
| `ingest.py` | Create | CLI entrypoint: orchestrate, log, sample |
| `tests/test_db.py` | Create | Schema creation tests |
| `tests/test_firms.py` | Create | FIRMS fetch/save tests (mocked HTTP) |
| `tests/test_noaa.py` | Create | NOAA fetch/save tests (mocked HTTP) |
| `tests/test_historical.py` | Create | Historical fetch/save tests (mocked HTTP) |

---

## Task 1: Project Scaffold

**Files:**
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `data/__init__.py`
- Create: `tests/__init__.py`

**Interfaces:**
- Produces: nothing consumed by other tasks — pure scaffolding

- [ ] **Step 1: Create `requirements.txt`**

```
requests==2.32.3
python-dotenv==1.0.1
tabulate==0.9.0
pytest==8.3.2
```

- [ ] **Step 2: Create `.gitignore`**

```
firerag.db
.env
__pycache__/
*.pyc
.pytest_cache/
*.egg-info/
dist/
```

- [ ] **Step 3: Create `.env.example`**

```
# Get your free key at: https://firms.modaps.eosdis.nasa.gov/api/
FIRMS_MAP_KEY=your_key_here
```

- [ ] **Step 4: Create empty package markers**

```bash
mkdir -p data tests
touch data/__init__.py tests/__init__.py
```

- [ ] **Step 5: Install dependencies**

```bash
pip install -r requirements.txt
```

Expected: all packages install without error.

- [ ] **Step 6: Commit**

```bash
git init
git add requirements.txt .gitignore .env.example data/__init__.py tests/__init__.py
git commit -m "chore: project scaffold for phase 1"
```

---

## Task 2: Database Schema (`data/db.py`)

**Files:**
- Create: `data/db.py`
- Create: `tests/test_db.py`

**Interfaces:**
- Produces:
  - `get_connection(db_path: str = "firerag.db") -> sqlite3.Connection` — returns an open connection with `row_factory = sqlite3.Row`
  - `init_db(conn: sqlite3.Connection) -> None` — creates all 4 tables if not exists

- [ ] **Step 1: Write the failing test**

Create `tests/test_db.py`:

```python
import sqlite3
import pytest
from data.db import get_connection, init_db


@pytest.fixture
def conn():
    c = get_connection(":memory:")
    init_db(c)
    yield c
    c.close()


def test_fires_realtime_table_exists(conn):
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='fires_realtime'"
    )
    assert cursor.fetchone() is not None


def test_weather_table_exists(conn):
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='weather'"
    )
    assert cursor.fetchone() is not None


def test_fires_historical_table_exists(conn):
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='fires_historical'"
    )
    assert cursor.fetchone() is not None


def test_fires_predictions_table_exists(conn):
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='fires_predictions'"
    )
    assert cursor.fetchone() is not None


def test_fires_realtime_columns(conn):
    cursor = conn.execute("PRAGMA table_info(fires_realtime)")
    cols = {row[1] for row in cursor.fetchall()}
    assert cols == {
        "id", "latitude", "longitude", "brightness",
        "acq_date", "acq_time", "confidence", "satellite", "ingested_at"
    }


def test_init_db_is_idempotent(conn):
    init_db(conn)  # second call must not raise
    cursor = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
    )
    assert cursor.fetchone()[0] == 4
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_db.py -v
```

Expected: `ImportError` or `ModuleNotFoundError` — `data.db` doesn't exist yet.

- [ ] **Step 3: Implement `data/db.py`**

```python
import sqlite3
import logging

logger = logging.getLogger(__name__)

_DDL = """
CREATE TABLE IF NOT EXISTS fires_realtime (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    latitude    REAL,
    longitude   REAL,
    brightness  REAL,
    acq_date    TEXT,
    acq_time    TEXT,
    confidence  TEXT,
    satellite   TEXT,
    ingested_at TEXT
);

CREATE TABLE IF NOT EXISTS weather (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    latitude    REAL,
    longitude   REAL,
    temperature REAL,
    humidity    REAL,
    wind_speed  REAL,
    wind_dir    REAL,
    timestamp   TEXT,
    ingested_at TEXT
);

CREATE TABLE IF NOT EXISTS fires_historical (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    latitude    REAL,
    longitude   REAL,
    brightness  REAL,
    frp         REAL,
    acq_date    TEXT,
    acq_time    TEXT,
    confidence  TEXT,
    satellite   TEXT,
    ingested_at TEXT
);

CREATE TABLE IF NOT EXISTS fires_predictions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    latitude         REAL,
    longitude        REAL,
    fire_probability REAL,
    prediction_date  TEXT,
    model_version    TEXT,
    ingested_at      TEXT
);
"""


def get_connection(db_path: str = "firerag.db") -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(_DDL)
    conn.commit()
    logger.info("Database schema initialized")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_db.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add data/db.py tests/test_db.py
git commit -m "feat: sqlite schema with 4 tables"
```

---

## Task 3: NASA FIRMS Real-Time (`data/firms.py`)

**Files:**
- Create: `data/firms.py`
- Create: `tests/test_firms.py`

**Interfaces:**
- Consumes: `FIRMS_MAP_KEY` from environment
- Produces:
  - `fetch(map_key: str, area: str = "-130,24,-65,50", day_range: int = 1) -> list[dict]`
    - Returns list of dicts with keys: `latitude`, `longitude`, `brightness`, `acq_date`, `acq_time`, `confidence`, `satellite`
  - `save(records: list[dict], conn: sqlite3.Connection) -> int`
    - Inserts into `fires_realtime`, returns number of rows inserted

**API details:**
- URL: `https://firms.modaps.eosdis.nasa.gov/api/area/csv/{map_key}/VIIRS_SNPP_NRT/{area}/{day_range}`
- Response: CSV with header row. Relevant columns: `latitude`, `longitude`, `bright_ti4` (use as brightness), `acq_date`, `acq_time`, `confidence`, `satellite`
- On error: raises `requests.HTTPError`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_firms.py`:

```python
import sqlite3
import pytest
from unittest.mock import patch, MagicMock
from data.db import init_db
from data.firms import fetch, save

SAMPLE_CSV = (
    "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,"
    "satellite,instrument,confidence,version,bright_ti5,frp,daynight\n"
    "37.123,-120.456,320.1,0.4,0.4,2026-06-28,0130,N,VIIRS,nominal,2.0NRT,290.5,5.2,D\n"
    "36.789,-119.123,310.5,0.4,0.4,2026-06-28,0130,N,VIIRS,high,2.0NRT,285.0,3.1,D\n"
)


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    init_db(c)
    yield c
    c.close()


@patch("data.firms.requests.get")
def test_fetch_returns_list_of_dicts(mock_get):
    mock_resp = MagicMock()
    mock_resp.text = SAMPLE_CSV
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp

    records = fetch("fake_key")

    assert len(records) == 2
    assert records[0]["latitude"] == pytest.approx(37.123)
    assert records[0]["longitude"] == pytest.approx(-120.456)
    assert records[0]["brightness"] == pytest.approx(320.1)
    assert records[0]["acq_date"] == "2026-06-28"
    assert records[0]["acq_time"] == "0130"
    assert records[0]["confidence"] == "nominal"
    assert records[0]["satellite"] == "N"


@patch("data.firms.requests.get")
def test_fetch_raises_on_http_error(mock_get):
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = Exception("404")
    mock_get.return_value = mock_resp

    with pytest.raises(Exception):
        fetch("bad_key")


def test_save_returns_row_count(conn):
    records = [
        {
            "latitude": 37.1, "longitude": -120.5,
            "brightness": 320.0, "acq_date": "2026-06-28",
            "acq_time": "0130", "confidence": "nominal", "satellite": "N",
        }
    ]
    count = save(records, conn)
    assert count == 1


def test_save_persists_to_db(conn):
    records = [
        {
            "latitude": 37.1, "longitude": -120.5,
            "brightness": 320.0, "acq_date": "2026-06-28",
            "acq_time": "0130", "confidence": "nominal", "satellite": "N",
        }
    ]
    save(records, conn)
    row = conn.execute("SELECT * FROM fires_realtime").fetchone()
    assert row["latitude"] == pytest.approx(37.1)
    assert row["ingested_at"] is not None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_firms.py -v
```

Expected: `ImportError` — `data.firms` doesn't exist yet.

- [ ] **Step 3: Implement `data/firms.py`**

```python
import csv
import io
import logging
import sqlite3
from datetime import datetime, timezone

import requests

logger = logging.getLogger(__name__)

_BASE_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"


def fetch(
    map_key: str,
    area: str = "-130,24,-65,50",
    day_range: int = 1,
) -> list[dict]:
    url = f"{_BASE_URL}/{map_key}/VIIRS_SNPP_NRT/{area}/{day_range}"
    logger.info("FIRMS: fetching from %s", url)
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()

    reader = csv.DictReader(io.StringIO(resp.text))
    records = []
    for row in reader:
        records.append({
            "latitude": float(row["latitude"]),
            "longitude": float(row["longitude"]),
            "brightness": float(row["bright_ti4"]),
            "acq_date": row["acq_date"],
            "acq_time": row["acq_time"],
            "confidence": row["confidence"],
            "satellite": row["satellite"],
        })
    return records


def save(records: list[dict], conn: sqlite3.Connection) -> int:
    ingested_at = datetime.now(timezone.utc).isoformat()
    conn.executemany(
        """
        INSERT INTO fires_realtime
            (latitude, longitude, brightness, acq_date, acq_time, confidence, satellite, ingested_at)
        VALUES
            (:latitude, :longitude, :brightness, :acq_date, :acq_time, :confidence, :satellite, :ingested_at)
        """,
        [{**r, "ingested_at": ingested_at} for r in records],
    )
    conn.commit()
    return len(records)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_firms.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add data/firms.py tests/test_firms.py
git commit -m "feat: nasa firms real-time ingest"
```

---

## Task 4: NOAA Weather (`data/noaa.py`)

**Files:**
- Create: `data/noaa.py`
- Create: `tests/test_noaa.py`

**Interfaces:**
- Consumes: nothing from environment (NOAA API is keyless)
- Produces:
  - `fetch(locations: list[tuple[float, float]] | None = None) -> list[dict]`
    - `locations` defaults to `FIRE_PRONE_LOCATIONS` (25 lat/lon pairs). Each location requires 2 API calls: `/points/{lat},{lon}` then the `forecastHourly` URL it returns.
    - Returns list of dicts with keys: `latitude`, `longitude`, `temperature`, `humidity`, `wind_speed`, `wind_dir`, `timestamp`
    - Skips a location silently if either API call fails (logs a warning)
  - `save(records: list[dict], conn: sqlite3.Connection) -> int`
    - Inserts into `weather`, returns number of rows inserted

**API details (two-step per location):**
1. `GET https://api.weather.gov/points/{lat},{lon}` → JSON with `properties.forecastHourly` URL
2. `GET {forecastHourly}` → JSON with `properties.periods[0]` containing: `temperature` (°F), `relativeHumidity.value` (%), `windSpeed` (e.g. `"10 mph"`), `windDirection` (e.g. `"SW"`), `startTime` (ISO 8601)

**Wind direction mapping** (cardinal to degrees):
`N=0, NNE=22, NE=45, ENE=67, E=90, ESE=112, SE=135, SSE=157, S=180, SSW=202, SW=225, WSW=247, W=270, WNW=292, NW=315, NNW=337`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_noaa.py`:

```python
import sqlite3
import pytest
from unittest.mock import patch, MagicMock
from data.db import init_db
from data.noaa import fetch, save, _parse_wind_speed, _parse_wind_dir

POINTS_RESPONSE = {
    "properties": {
        "forecastHourly": "https://api.weather.gov/gridpoints/MTR/90,105/forecast/hourly"
    }
}

HOURLY_RESPONSE = {
    "properties": {
        "periods": [
            {
                "startTime": "2026-06-28T01:00:00-07:00",
                "temperature": 85,
                "relativeHumidity": {"value": 20},
                "windSpeed": "15 mph",
                "windDirection": "SW",
            }
        ]
    }
}


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    init_db(c)
    yield c
    c.close()


def test_parse_wind_speed():
    assert _parse_wind_speed("15 mph") == pytest.approx(15.0)
    assert _parse_wind_speed("0 mph") == pytest.approx(0.0)


def test_parse_wind_dir():
    assert _parse_wind_dir("N") == pytest.approx(0.0)
    assert _parse_wind_dir("SW") == pytest.approx(225.0)
    assert _parse_wind_dir("E") == pytest.approx(90.0)


@patch("data.noaa.requests.get")
def test_fetch_returns_records(mock_get):
    def side_effect(url, **kwargs):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        if "points" in url:
            resp.json.return_value = POINTS_RESPONSE
        else:
            resp.json.return_value = HOURLY_RESPONSE
        return resp

    mock_get.side_effect = side_effect

    records = fetch(locations=[(37.5, -122.0)])

    assert len(records) == 1
    assert records[0]["latitude"] == pytest.approx(37.5)
    assert records[0]["longitude"] == pytest.approx(-122.0)
    assert records[0]["temperature"] == pytest.approx(85.0)
    assert records[0]["humidity"] == pytest.approx(20.0)
    assert records[0]["wind_speed"] == pytest.approx(15.0)
    assert records[0]["wind_dir"] == pytest.approx(225.0)


@patch("data.noaa.requests.get")
def test_fetch_skips_failed_location(mock_get):
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = Exception("500")
    mock_get.return_value = mock_resp

    records = fetch(locations=[(37.5, -122.0), (36.0, -120.0)])
    assert records == []


def test_save_returns_row_count(conn):
    records = [{
        "latitude": 37.5, "longitude": -122.0,
        "temperature": 85.0, "humidity": 20.0,
        "wind_speed": 15.0, "wind_dir": 225.0,
        "timestamp": "2026-06-28T01:00:00-07:00",
    }]
    count = save(records, conn)
    assert count == 1


def test_save_persists_to_db(conn):
    records = [{
        "latitude": 37.5, "longitude": -122.0,
        "temperature": 85.0, "humidity": 20.0,
        "wind_speed": 15.0, "wind_dir": 225.0,
        "timestamp": "2026-06-28T01:00:00-07:00",
    }]
    save(records, conn)
    row = conn.execute("SELECT * FROM weather").fetchone()
    assert row["temperature"] == pytest.approx(85.0)
    assert row["ingested_at"] is not None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_noaa.py -v
```

Expected: `ImportError` — `data.noaa` doesn't exist yet.

- [ ] **Step 3: Implement `data/noaa.py`**

```python
import logging
import sqlite3
from datetime import datetime, timezone

import requests

logger = logging.getLogger(__name__)

_WIND_DIR_MAP = {
    "N": 0.0, "NNE": 22.0, "NE": 45.0, "ENE": 67.0,
    "E": 90.0, "ESE": 112.0, "SE": 135.0, "SSE": 157.0,
    "S": 180.0, "SSW": 202.0, "SW": 225.0, "WSW": 247.0,
    "W": 270.0, "WNW": 292.0, "NW": 315.0, "NNW": 337.0,
}

# 25 fire-prone locations across CONUS (lat, lon)
FIRE_PRONE_LOCATIONS: list[tuple[float, float]] = [
    (34.0, -118.0),  # Los Angeles Basin, CA
    (37.5, -122.0),  # San Francisco Bay Area, CA
    (38.5, -121.5),  # Sacramento Valley, CA
    (40.5, -122.5),  # Northern CA (Shasta)
    (36.5, -119.0),  # San Joaquin Valley, CA
    (34.5, -117.0),  # Inland Empire, CA
    (33.5, -116.5),  # San Diego foothills, CA
    (45.5, -116.0),  # Northern ID
    (47.0, -114.0),  # Western MT
    (46.0, -120.0),  # Eastern WA
    (44.0, -121.0),  # Central OR
    (42.5, -122.5),  # Southern OR
    (39.5, -119.5),  # Northern NV
    (36.0, -115.0),  # Southern NV
    (35.0, -111.5),  # Northern AZ (Flagstaff)
    (33.5, -112.0),  # Phoenix area, AZ
    (35.5, -106.0),  # Northern NM
    (32.5, -107.0),  # Southern NM
    (39.0, -108.5),  # Western CO
    (37.0, -107.0),  # Southern CO
    (40.5, -111.5),  # Northern UT
    (37.5, -113.0),  # Southern UT
    (43.5, -110.5),  # Western WY
    (46.5, -108.5),  # Eastern MT
    (30.5, -98.5),   # Central TX (Hill Country)
]


def _parse_wind_speed(wind_speed_str: str) -> float:
    return float(wind_speed_str.split()[0])


def _parse_wind_dir(wind_dir_str: str) -> float:
    return _WIND_DIR_MAP.get(wind_dir_str, 0.0)


def fetch(locations: list[tuple[float, float]] | None = None) -> list[dict]:
    if locations is None:
        locations = FIRE_PRONE_LOCATIONS

    records = []
    for lat, lon in locations:
        try:
            points_url = f"https://api.weather.gov/points/{lat},{lon}"
            points_resp = requests.get(
                points_url,
                headers={"User-Agent": "FireRAG/1.0 arjunpol101@gmail.com"},
                timeout=15,
            )
            points_resp.raise_for_status()
            hourly_url = points_resp.json()["properties"]["forecastHourly"]

            hourly_resp = requests.get(
                hourly_url,
                headers={"User-Agent": "FireRAG/1.0 arjunpol101@gmail.com"},
                timeout=15,
            )
            hourly_resp.raise_for_status()
            period = hourly_resp.json()["properties"]["periods"][0]

            records.append({
                "latitude": lat,
                "longitude": lon,
                "temperature": float(period["temperature"]),
                "humidity": float(period["relativeHumidity"]["value"]),
                "wind_speed": _parse_wind_speed(period["windSpeed"]),
                "wind_dir": _parse_wind_dir(period["windDirection"]),
                "timestamp": period["startTime"],
            })
        except Exception as exc:
            logger.warning("NOAA: skipping (%.1f, %.1f) — %s", lat, lon, exc)

    return records


def save(records: list[dict], conn: sqlite3.Connection) -> int:
    ingested_at = datetime.now(timezone.utc).isoformat()
    conn.executemany(
        """
        INSERT INTO weather
            (latitude, longitude, temperature, humidity, wind_speed, wind_dir, timestamp, ingested_at)
        VALUES
            (:latitude, :longitude, :temperature, :humidity, :wind_speed, :wind_dir, :timestamp, :ingested_at)
        """,
        [{**r, "ingested_at": ingested_at} for r in records],
    )
    conn.commit()
    return len(records)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_noaa.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add data/noaa.py tests/test_noaa.py
git commit -m "feat: noaa weather ingest (25 fire-prone locations)"
```

---

## Task 5: NASA FIRMS Historical (`data/historical.py`)

**Files:**
- Create: `data/historical.py`
- Create: `tests/test_historical.py`

**Interfaces:**
- Consumes: `FIRMS_MAP_KEY` from environment; same FIRMS CSV format as Task 3
- Produces:
  - `fetch(map_key: str, area: str = "-130,24,-65,50", date_range_days: int = 365) -> list[dict]`
    - Returns list of dicts with keys: `latitude`, `longitude`, `brightness`, `frp`, `acq_date`, `acq_time`, `confidence`, `satellite`
    - Note: FIRMS caps single CSV requests at 10 days. This function fetches in 10-day chunks and concatenates.
  - `save(records: list[dict], conn: sqlite3.Connection) -> int`
    - Inserts into `fires_historical`, returns number of rows inserted

**API details:**
- URL template: `https://firms.modaps.eosdis.nasa.gov/api/area/csv/{map_key}/VIIRS_SNPP_SP/{area}/10/{start_date}`
- `start_date` format: `YYYY-MM-DD`
- `VIIRS_SNPP_SP` is the standard processing (archive) product vs `VIIRS_SNPP_NRT` (near real-time)
- Relevant CSV columns: `latitude`, `longitude`, `bright_ti4` (brightness), `frp`, `acq_date`, `acq_time`, `confidence`, `satellite`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_historical.py`:

```python
import sqlite3
import pytest
from unittest.mock import patch, MagicMock, call
from data.db import init_db
from data.historical import fetch, save

SAMPLE_CSV = (
    "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,"
    "satellite,instrument,confidence,version,bright_ti5,frp,daynight\n"
    "37.123,-120.456,325.0,0.4,0.4,2025-07-04,0200,N,VIIRS,nominal,2.0,295.0,10.5,D\n"
)


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    init_db(c)
    yield c
    c.close()


@patch("data.historical.requests.get")
def test_fetch_returns_records(mock_get):
    mock_resp = MagicMock()
    mock_resp.text = SAMPLE_CSV
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp

    records = fetch("fake_key", date_range_days=10)

    assert len(records) == 1
    assert records[0]["latitude"] == pytest.approx(37.123)
    assert records[0]["frp"] == pytest.approx(10.5)
    assert records[0]["acq_date"] == "2025-07-04"


@patch("data.historical.requests.get")
def test_fetch_chunks_into_10_day_windows(mock_get):
    mock_resp = MagicMock()
    mock_resp.text = "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,instrument,confidence,version,bright_ti5,frp,daynight\n"
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp

    fetch("fake_key", date_range_days=25)

    # 25 days / 10 days per chunk = 3 calls (10 + 10 + 5, but API takes fixed 10-day window)
    assert mock_get.call_count == 3


def test_save_returns_row_count(conn):
    records = [{
        "latitude": 37.1, "longitude": -120.5,
        "brightness": 325.0, "frp": 10.5,
        "acq_date": "2025-07-04", "acq_time": "0200",
        "confidence": "nominal", "satellite": "N",
    }]
    count = save(records, conn)
    assert count == 1


def test_save_persists_frp(conn):
    records = [{
        "latitude": 37.1, "longitude": -120.5,
        "brightness": 325.0, "frp": 10.5,
        "acq_date": "2025-07-04", "acq_time": "0200",
        "confidence": "nominal", "satellite": "N",
    }]
    save(records, conn)
    row = conn.execute("SELECT frp FROM fires_historical").fetchone()
    assert row["frp"] == pytest.approx(10.5)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_historical.py -v
```

Expected: `ImportError` — `data.historical` doesn't exist yet.

- [ ] **Step 3: Implement `data/historical.py`**

```python
import csv
import io
import logging
import math
import sqlite3
from datetime import datetime, timedelta, timezone

import requests

logger = logging.getLogger(__name__)

_BASE_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
_CHUNK_DAYS = 10


def fetch(
    map_key: str,
    area: str = "-130,24,-65,50",
    date_range_days: int = 365,
) -> list[dict]:
    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=date_range_days)

    num_chunks = math.ceil(date_range_days / _CHUNK_DAYS)
    all_records: list[dict] = []

    for i in range(num_chunks):
        chunk_start = start_date + timedelta(days=i * _CHUNK_DAYS)
        url = f"{_BASE_URL}/{map_key}/VIIRS_SNPP_SP/{area}/{_CHUNK_DAYS}/{chunk_start}"
        logger.info("FIRMS historical: fetching chunk %d/%d (%s)", i + 1, num_chunks, chunk_start)

        resp = requests.get(url, timeout=60)
        resp.raise_for_status()

        reader = csv.DictReader(io.StringIO(resp.text))
        for row in reader:
            all_records.append({
                "latitude": float(row["latitude"]),
                "longitude": float(row["longitude"]),
                "brightness": float(row["bright_ti4"]),
                "frp": float(row["frp"]) if row["frp"] else 0.0,
                "acq_date": row["acq_date"],
                "acq_time": row["acq_time"],
                "confidence": row["confidence"],
                "satellite": row["satellite"],
            })

    return all_records


def save(records: list[dict], conn: sqlite3.Connection) -> int:
    ingested_at = datetime.now(timezone.utc).isoformat()
    conn.executemany(
        """
        INSERT INTO fires_historical
            (latitude, longitude, brightness, frp, acq_date, acq_time, confidence, satellite, ingested_at)
        VALUES
            (:latitude, :longitude, :brightness, :frp, :acq_date, :acq_time, :confidence, :satellite, :ingested_at)
        """,
        [{**r, "ingested_at": ingested_at} for r in records],
    )
    conn.commit()
    return len(records)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_historical.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add data/historical.py tests/test_historical.py
git commit -m "feat: nasa firms historical ingest (365-day chunked fetch)"
```

---

## Task 6: Ingest CLI (`ingest.py`)

**Files:**
- Create: `ingest.py`

**Interfaces:**
- Consumes:
  - `FIRMS_MAP_KEY` from `.env`
  - `data.db.get_connection`, `data.db.init_db`
  - `data.firms.fetch(map_key)`, `data.firms.save(records, conn)`
  - `data.noaa.fetch()`, `data.noaa.save(records, conn)`
  - `data.historical.fetch(map_key)`, `data.historical.save(records, conn)`
- Produces: nothing (side effects: writes to `firerag.db`, logs to stdout)

**Behavior:**
- If `FIRMS_MAP_KEY` missing from env: print a message with signup URL and exit with code 1
- Each source: log fetch start → time the fetch → log count + elapsed → print 3-row sample via `tabulate`
- If a source raises: log the error and continue to the next source

- [ ] **Step 1: Implement `ingest.py`**

(No test for the CLI entrypoint — its dependencies are all tested. Manual verification in Step 2.)

```python
import logging
import os
import sys
import time

from dotenv import load_dotenv
from tabulate import tabulate

from data import firms, historical, noaa
from data.db import get_connection, init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)-20s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ingest")

load_dotenv()


def _require_env(key: str, signup_url: str) -> str:
    value = os.getenv(key)
    if not value:
        logger.error(
            "Missing required env var %s. Get your free key at: %s",
            key,
            signup_url,
        )
        sys.exit(1)
    return value


def _print_sample(records: list[dict], label: str) -> None:
    if not records:
        logger.info("%s: no records to display", label)
        return
    sample = records[:3]
    print(f"\n--- {label} sample (first 3 rows) ---")
    print(tabulate(sample, headers="keys", tablefmt="rounded_outline"))
    print()


def _run_source(label: str, fetch_fn, save_fn, conn) -> None:
    try:
        logger.info("%s: starting fetch", label)
        t0 = time.time()
        records = fetch_fn()
        elapsed = time.time() - t0
        logger.info("%s: fetched %d records in %.2fs", label, len(records), elapsed)

        count = save_fn(records, conn)
        logger.info("%s: saved %d rows to database", label, count)
        _print_sample(records, label)
    except Exception as exc:
        logger.error("%s: failed — %s", label, exc)


def main() -> None:
    firms_key = _require_env(
        "FIRMS_MAP_KEY",
        "https://firms.modaps.eosdis.nasa.gov/api/",
    )

    conn = get_connection()
    init_db(conn)

    _run_source(
        "FIRMS real-time",
        lambda: firms.fetch(firms_key),
        lambda records: firms.save(records, conn),
        conn,
    )

    _run_source(
        "NOAA weather",
        lambda: noaa.fetch(),
        lambda records: noaa.save(records, conn),
        conn,
    )

    _run_source(
        "FIRMS historical",
        lambda: historical.fetch(firms_key),
        lambda records: historical.save(records, conn),
        conn,
    )

    conn.close()
    logger.info("Ingest complete.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run all tests to verify nothing broke**

```bash
pytest tests/ -v
```

Expected: all tests PASS (no changes to tested modules).

- [ ] **Step 3: Verify missing key handling**

```bash
python ingest.py
```

Expected output (if `.env` not yet created):
```
HH:MM:SS  ingest                ERROR  Missing required env var FIRMS_MAP_KEY. Get your free key at: https://firms.modaps.eosdis.nasa.gov/api/
```
Then exits with code 1.

- [ ] **Step 4: Sign up for FIRMS API key and create `.env`**

1. Visit https://firms.modaps.eosdis.nasa.gov/api/
2. Click "Get API Key", register with your email
3. Key arrives by email within minutes
4. Create `.env`:
   ```
   FIRMS_MAP_KEY=your_actual_key_here
   ```

- [ ] **Step 5: Run live ingest**

```bash
python ingest.py
```

Expected: logs show fetch timings, each source logs row counts, 3-row sample tables print to console. Historical fetch will take several minutes (36 chunks × ~2s each).

- [ ] **Step 6: Verify data in SQLite**

```bash
python -c "
from data.db import get_connection
conn = get_connection()
for table in ['fires_realtime', 'weather', 'fires_historical']:
    count = conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
    print(f'{table}: {count} rows')
"
```

Expected: non-zero counts in all three tables.

- [ ] **Step 7: Commit**

```bash
git add ingest.py
git commit -m "feat: ingest cli entrypoint with logging and tabulate samples"
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] NASA FIRMS real-time → Task 3
- [x] NOAA weather → Task 4
- [x] NASA FIRMS historical → Task 5
- [x] SQLite schema (4 tables) → Task 2
- [x] `data/` package structure → Task 1
- [x] `ingest.py` CLI entrypoint → Task 6
- [x] Logging (not print) → all modules + Task 6
- [x] Timing per source → Task 6
- [x] 3-row tabulate sample → Task 6
- [x] Graceful degradation (one source fails, others continue) → Task 6 `_run_source`
- [x] Missing API key exits with helpful message → Task 6 `_require_env`
- [x] `ingested_at` = pull timestamp on all tables → Tasks 3, 4, 5

**Placeholder scan:** None found.

**Type consistency:**
- `fetch()` returns `list[dict]` in Tasks 3, 4, 5 ✓
- `save(records, conn)` returns `int` in Tasks 3, 4, 5 ✓
- `get_connection()` / `init_db()` signatures consistent across all tasks ✓
