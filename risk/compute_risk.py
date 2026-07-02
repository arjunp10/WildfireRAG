"""
Phase 1 Fire Risk Index
=======================
Combines two signals per 1°×1° grid cell:

  fwi_score   — current Fosberg Fire Weather Index from weather_grid, normalised 0→1
  hist_score  — historical fire ignition frequency for this cell in the current
                calendar month (±1 month window), log-normalised 0→1

  risk_score  = 0.6 * fwi_score + 0.4 * hist_score

FWI cap: 30 (above this is already critical fire weather).
Hist log base: log(count+1) / log(51) so that 50 fires saturates at 1.0.
Window: current month ±1 to capture seasonal shoulder risk.
"""

import logging
import math
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")
log = logging.getLogger(__name__)

DB_PATH = "firerag.db"
FWI_CAP = 30.0       # normalisation ceiling for Fosberg FWI
HIST_LOG_BASE = 51   # log(HIST_LOG_BASE) is denominator; 50 fires → hist_score ≈ 1.0
FWI_WEIGHT = 0.6
HIST_WEIGHT = 0.4


def _month_window(month: int) -> set[int]:
    """Return {month-1, month, month+1} wrapped around 1-12."""
    return {(month - 2) % 12 + 1, month, month % 12 + 1}


def run(db_path: str = DB_PATH) -> int:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    conn.execute("""
        CREATE TABLE IF NOT EXISTS risk_grid (
            lat         REAL,
            lon         REAL,
            fwi_score   REAL,
            hist_score  REAL,
            risk_score  REAL,
            month       INTEGER,
            computed_at TEXT,
            PRIMARY KEY (lat, lon)
        )
    """)

    # ── Historical fire frequency per (cell_lat, cell_lon, month) ──────────────
    # Bin each fire centroid to the nearest integer lat/lon (rounds to nearest 1° cell)
    rows = conn.execute("""
        SELECT
            ROUND(latitude)  AS cell_lat,
            ROUND(longitude) AS cell_lon,
            CAST(substr(discovery_date, 6, 2) AS INTEGER) AS month
        FROM fire_perimeters
        WHERE latitude  IS NOT NULL
          AND longitude IS NOT NULL
          AND discovery_date IS NOT NULL
          AND length(discovery_date) >= 7
          AND CAST(substr(discovery_date, 6, 2) AS INTEGER) BETWEEN 1 AND 12
    """).fetchall()

    hist: dict[tuple, int] = defaultdict(int)
    for r in rows:
        hist[(r["cell_lat"], r["cell_lon"], r["month"])] += 1

    log.info("Loaded %d historical fire records across %d (cell, month) buckets",
             len(rows), len(hist))

    # ── Weather grid ───────────────────────────────────────────────────────────
    # Prefer 7-day peak forecast FWI; fall back to current FWI if not yet fetched.
    weather = conn.execute("""
        SELECT lat, lon,
               COALESCE(forecast_fwi, fosberg_index) AS fwi
        FROM weather_grid
        WHERE fetched_at IS NOT NULL
    """).fetchall()
    log.info("Weather grid: %d cells", len(weather))

    now = datetime.now(timezone.utc)
    cur_month = now.month
    window = _month_window(cur_month)
    now_str = now.isoformat()
    log_denom = math.log(HIST_LOG_BASE)

    upserted = 0
    for w in weather:
        # Bin weather cell to nearest integer (should already be integer, but guard against float drift)
        cell_lat = round(w["lat"])
        cell_lon = round(w["lon"])

        # Sum fire counts across the ±1 month window
        hist_count = sum(hist.get((cell_lat, cell_lon, m), 0) for m in window)
        hist_score = min(1.0, math.log(hist_count + 1) / log_denom)

        fwi = w["fwi"] or 0.0
        fwi_score = min(1.0, fwi / FWI_CAP)

        risk_score = round(FWI_WEIGHT * fwi_score + HIST_WEIGHT * hist_score, 4)

        conn.execute("""
            INSERT OR REPLACE INTO risk_grid
                (lat, lon, fwi_score, hist_score, risk_score, month, computed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (w["lat"], w["lon"],
              round(fwi_score, 4), round(hist_score, 4), risk_score,
              cur_month, now_str))
        upserted += 1

    conn.commit()
    conn.close()
    log.info("Risk grid written: %d cells, month window %s", upserted, sorted(window))
    return upserted


if __name__ == "__main__":
    n = run()
    print(f"Done — {n} risk grid cells computed.")
