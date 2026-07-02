#!/usr/bin/env python3
"""
Fetch 7-day peak fire weather forecast per grid point via NWS forecastHourly.

For each (lat, lon) already in weather_grid, this script:
  1. Calls /points/{lat},{lon} to get the forecastHourly URL.
  2. Fetches up to 168 hourly periods (7 days).
  3. Computes Fosberg FWI for each period, keeps the maximum.
  4. Stores it as forecast_fwi in weather_grid.

This value drives the Risk Forecast overlay, making it forward-looking
rather than a snapshot of today's conditions.

Usage:
    python3 -m weather.fetch_forecast [--db firerag.db] [--workers 5]
"""
import argparse
import logging
import re
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

from weather.fetch_grid import HEADERS, NWS_BASE, _get
from weather.fosberg import fosberg_fwi

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

MAX_PERIODS = 168   # 7 days × 24 hours
_WIND_RE = re.compile(r"(\d+)")


def _parse_wind_mph(wind_str: str | None) -> float:
    """Parse '15 mph' or '10 to 15 mph' → first number as float."""
    if not wind_str:
        return 0.0
    m = _WIND_RE.search(wind_str)
    return float(m.group(1)) if m else 0.0


def _parse_rh(rh_field) -> float | None:
    """forecastHourly relativeHumidity can be a dict or None."""
    if rh_field is None:
        return None
    if isinstance(rh_field, dict):
        return rh_field.get("value")
    try:
        return float(rh_field)
    except (TypeError, ValueError):
        return None


def fetch_forecast_fwi(lat: float, lon: float) -> float | None:
    """Return max Fosberg FWI forecast over the next 7 days, or None on failure."""
    meta = _get(f"{NWS_BASE}/points/{lat},{lon}")
    if not meta:
        return None
    try:
        hourly_url = meta["properties"]["forecastHourly"]
    except (KeyError, TypeError):
        return None

    data = _get(hourly_url)
    if not data:
        return None
    try:
        periods = data["properties"]["periods"]
    except (KeyError, TypeError):
        return None

    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(days=7)
    max_fwi = 0.0

    for p in periods[:MAX_PERIODS]:
        try:
            start_str = p.get("startTime", "")
            if start_str:
                start = datetime.fromisoformat(start_str)
                # make timezone-aware if naive
                if start.tzinfo is None:
                    start = start.replace(tzinfo=timezone.utc)
                if start > cutoff:
                    break

            temp_f = float(p["temperature"])   # forecastHourly always returns °F
            rh = _parse_rh(p.get("relativeHumidity"))
            if rh is None:
                rh = 30.0   # conservative default if missing
            wind_mph = _parse_wind_mph(p.get("windSpeed"))

            fwi = fosberg_fwi(temp_f, rh, wind_mph)
            if fwi > max_fwi:
                max_fwi = fwi
        except (KeyError, TypeError, ValueError):
            continue

    return round(max_fwi, 2) if max_fwi > 0 else None


def run(db_path: str = "firerag.db", workers: int = 5) -> int:
    conn = sqlite3.connect(db_path)

    # Add forecast_fwi column if missing
    cols = {r[1] for r in conn.execute("PRAGMA table_info(weather_grid)")}
    if "forecast_fwi" not in cols:
        conn.execute("ALTER TABLE weather_grid ADD COLUMN forecast_fwi REAL")
        conn.commit()
        log.info("Added forecast_fwi column to weather_grid")

    points = conn.execute(
        "SELECT lat, lon FROM weather_grid WHERE fetched_at IS NOT NULL ORDER BY lat, lon"
    ).fetchall()
    conn.close()

    log.info("Fetching 7-day forecast for %d grid points with %d workers", len(points), workers)

    updated = skipped = 0
    t0 = time.time()

    def _task(lat_lon):
        return lat_lon, fetch_forecast_fwi(*lat_lon)

    conn = sqlite3.connect(db_path)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_task, pt): pt for pt in points}
        for i, future in enumerate(as_completed(futures), 1):
            (lat, lon), fwi = future.result()
            if fwi is not None:
                conn.execute(
                    "UPDATE weather_grid SET forecast_fwi = ? WHERE lat = ? AND lon = ?",
                    (fwi, lat, lon),
                )
                updated += 1
            else:
                skipped += 1

            if i % 50 == 0 or i == len(points):
                elapsed = time.time() - t0
                rate = i / elapsed
                log.info("%d/%d  updated=%d  skipped=%d  %.0f pts/min",
                         i, len(points), updated, skipped, rate * 60)

    conn.commit()
    conn.close()
    log.info("Done. forecast_fwi updated for %d cells.", updated)
    return updated


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="firerag.db")
    parser.add_argument("--workers", type=int, default=5)
    args = parser.parse_args()
    run(db_path=args.db, workers=args.workers)
