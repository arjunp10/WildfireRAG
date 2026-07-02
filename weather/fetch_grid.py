#!/usr/bin/env python3
"""
Fetch NWS weather data for a grid covering current active fire detections.
Stores results (including Fosberg FWI) in the weather_grid SQLite table.

Usage:
    python3 -m weather.fetch_grid [--db firerag.db] [--spacing 1.0] [--workers 5]
"""
import argparse
import logging
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import requests

from weather.fosberg import fosberg_fwi

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

NWS_BASE = "https://api.weather.gov"
HEADERS = {
    "User-Agent": "FireRAG/1.0 (arjunpol101@gmail.com)",
    "Accept": "application/geo+json",
}

# Grid defaults
DEFAULT_SPACING = 1.0   # degrees
DEFAULT_PADDING = 1.0   # degrees of padding around fires bbox
DEFAULT_WORKERS = 5

# NWS retry config
MAX_RETRIES = 3
BASE_RETRY_DELAY = 2.0  # seconds, doubled each attempt


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

_DDL = """
CREATE TABLE IF NOT EXISTS weather_grid (
    lat            REAL NOT NULL,
    lon            REAL NOT NULL,
    temp_f         REAL,
    humidity_pct   REAL,
    wind_speed_mph REAL,
    wind_dir_deg   REAL,
    fosberg_index  REAL,
    fetched_at     TEXT,
    PRIMARY KEY (lat, lon)
);
"""


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(_DDL)
    conn.commit()


def save_row(conn: sqlite3.Connection, row: dict) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO weather_grid
            (lat, lon, temp_f, humidity_pct, wind_speed_mph, wind_dir_deg,
             fosberg_index, fetched_at)
        VALUES
            (:lat, :lon, :temp_f, :humidity_pct, :wind_speed_mph, :wind_dir_deg,
             :fosberg_index, :fetched_at)
        """,
        row,
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Grid construction
# ---------------------------------------------------------------------------

def _fire_bbox(db_path: str, padding: float) -> tuple[float, float, float, float]:
    """Bounding box of fires_realtime detections, padded and clamped to NWS coverage."""
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT MIN(latitude), MAX(latitude), MIN(longitude), MAX(longitude) FROM fires_realtime"
    ).fetchone()
    conn.close()

    if not row or row[0] is None:
        # Fallback: western US
        return 32.0, 49.0, -124.0, -100.0

    min_lat = max(24.0,  row[0] - padding)
    max_lat = min(50.0,  row[1] + padding)
    min_lon = max(-125.0, row[2] - padding)
    max_lon = min(-66.0,  row[3] + padding)
    return min_lat, max_lat, min_lon, max_lon


def _build_grid(
    min_lat: float, max_lat: float,
    min_lon: float, max_lon: float,
    spacing: float,
) -> list[tuple[float, float]]:
    points = []
    lat = min_lat
    while lat <= max_lat + 1e-6:
        lon = min_lon
        while lon <= max_lon + 1e-6:
            points.append((round(lat, 4), round(lon, 4)))
            lon = round(lon + spacing, 4)
        lat = round(lat + spacing, 4)
    return points


# ---------------------------------------------------------------------------
# NWS API helpers
# ---------------------------------------------------------------------------

def _get(url: str) -> dict | None:
    """GET with exponential-backoff retry. Returns None on permanent failure."""
    delay = BASE_RETRY_DELAY
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code in (404, 422):
                return None  # point not covered by NWS (offshore / outside US)
            if resp.status_code in (429, 503):
                logger.debug("HTTP %d, retrying in %.1fs …", resp.status_code, delay)
                time.sleep(delay)
                delay *= 2
                continue
            logger.debug("HTTP %d for %s — skipping", resp.status_code, url)
            return None
        except requests.Timeout:
            logger.debug("Timeout (attempt %d) for %s", attempt + 1, url)
            time.sleep(delay)
            delay *= 2
        except requests.RequestException as exc:
            logger.debug("Request error: %s", exc)
            time.sleep(delay)
            delay *= 2
    return None


def _first_value(props: dict, key: str) -> float | None:
    """Pull the first forecast value from a gridData property."""
    try:
        vals = props[key]["values"]
        return float(vals[0]["value"]) if vals else None
    except (KeyError, TypeError, IndexError, ValueError):
        return None


def fetch_point(lat: float, lon: float) -> dict | None:
    """
    Fetch weather for a single (lat, lon) point via NWS API.
    Returns a dict ready for DB insertion, or None on failure.
    """
    # Step 1 — resolve grid location
    meta = _get(f"{NWS_BASE}/points/{lat},{lon}")
    if not meta:
        return None
    try:
        grid_data_url = meta["properties"]["forecastGridData"]
    except (KeyError, TypeError):
        return None

    # Step 2 — fetch gridpoint forecast data
    grid = _get(grid_data_url)
    if not grid:
        return None

    try:
        props = grid["properties"]
    except (KeyError, TypeError):
        return None

    temp_c      = _first_value(props, "temperature")        # °C
    rh          = _first_value(props, "relativeHumidity")   # %
    wind_kmh    = _first_value(props, "windSpeed")          # km h⁻¹
    wind_dir    = _first_value(props, "windDirection")      # degrees

    if temp_c is None or rh is None or wind_kmh is None:
        return None

    temp_f    = temp_c * 9.0 / 5.0 + 32.0
    wind_mph  = wind_kmh * 0.621371

    return {
        "lat":            lat,
        "lon":            lon,
        "temp_f":         round(temp_f, 1),
        "humidity_pct":   round(rh, 1),
        "wind_speed_mph": round(wind_mph, 1),
        "wind_dir_deg":   round(wind_dir, 1) if wind_dir is not None else None,
        "fosberg_index":  fosberg_fwi(temp_f, rh, wind_mph),
        "fetched_at":     datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Main fetch loop
# ---------------------------------------------------------------------------

def fetch_grid(
    db_path: str = "firerag.db",
    spacing: float = DEFAULT_SPACING,
    padding: float = DEFAULT_PADDING,
    workers: int = DEFAULT_WORKERS,
) -> int:
    conn = sqlite3.connect(db_path)
    init_db(conn)

    bbox = _fire_bbox(db_path, padding)
    logger.info(
        "Bbox (fires + %.1f° pad): lat %.1f–%.1f  lon %.1f–%.1f",
        padding, bbox[0], bbox[1], bbox[2], bbox[3],
    )

    points = _build_grid(*bbox, spacing)
    logger.info("Grid: %d points at %.1f° spacing", len(points), spacing)

    saved = failed = 0
    t0 = time.time()

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(fetch_point, lat, lon): (lat, lon) for lat, lon in points}
        for i, future in enumerate(as_completed(futures), 1):
            lat, lon = futures[future]
            try:
                result = future.result()
            except Exception as exc:
                logger.warning("Unhandled error at (%.2f, %.2f): %s", lat, lon, exc)
                result = None

            if result:
                save_row(conn, result)
                saved += 1
            else:
                failed += 1

            if i % 100 == 0 or i == len(points):
                elapsed = time.time() - t0
                rate = i / elapsed
                remaining = (len(points) - i) / rate if rate else 0
                logger.info(
                    "%d/%d  saved=%d  skipped=%d  %.0f pts/min  ~%.0fs left",
                    i, len(points), saved, failed, rate * 60, remaining,
                )

    conn.close()
    logger.info("Finished. Saved %d rows, skipped/failed %d.", saved, failed)
    return saved


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch NWS weather grid for active fire areas")
    parser.add_argument("--db",      default="firerag.db", help="SQLite database path")
    parser.add_argument("--spacing", type=float, default=DEFAULT_SPACING, help="Grid spacing in degrees")
    parser.add_argument("--padding", type=float, default=DEFAULT_PADDING, help="Padding around fires bbox")
    parser.add_argument("--workers", type=int,   default=DEFAULT_WORKERS, help="Concurrent NWS fetchers")
    args = parser.parse_args()

    n = fetch_grid(db_path=args.db, spacing=args.spacing, padding=args.padding, workers=args.workers)
    print(f"Done — {n} grid points saved.")


if __name__ == "__main__":
    main()
