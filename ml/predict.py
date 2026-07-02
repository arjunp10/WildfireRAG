"""
Generate ML fire risk predictions for the current month.

Loads the trained RandomForest model, runs inference on all weather grid
cells for the current calendar month, blends the ML probability with the
7-day FWI score, then writes results to the ml_predictions table.

Blending formula:
  ml_risk = 0.55 * ml_prob + 0.45 * fwi_score

Usage:
    python3 -m ml.predict
"""
import logging
import math
import pickle
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")
log = logging.getLogger(__name__)

DB_PATH = "firerag.db"
MODEL_PATH = Path(__file__).parent / "model.pkl"
FWI_CAP = 30.0
ML_WEIGHT = 0.55
FWI_WEIGHT = 0.45


def run(db_path: str = DB_PATH) -> int:
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model not found at {MODEL_PATH}. Run: python3 -m ml.train")

    with open(MODEL_PATH, "rb") as f:
        clf = pickle.load(f)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    conn.execute("""
        CREATE TABLE IF NOT EXISTS ml_predictions (
            lat         REAL,
            lon         REAL,
            ml_prob     REAL,
            fwi_score   REAL,
            ml_risk     REAL,
            month       INTEGER,
            computed_at TEXT,
            PRIMARY KEY (lat, lon)
        )
    """)

    grid = conn.execute("""
        SELECT lat, lon,
               COALESCE(forecast_fwi, fosberg_index) AS fwi
        FROM weather_grid
        WHERE fetched_at IS NOT NULL
    """).fetchall()

    now = datetime.now(timezone.utc)
    month = now.month
    sin_m = math.sin(2 * math.pi * month / 12)
    cos_m = math.cos(2 * math.pi * month / 12)

    lats  = np.array([r["lat"] for r in grid], dtype=np.float32)
    lons  = np.array([r["lon"] for r in grid], dtype=np.float32)
    fwis  = np.array([r["fwi"] or 0.0 for r in grid], dtype=np.float32)

    X = np.column_stack([
        lats, lons,
        np.full(len(grid), sin_m, dtype=np.float32),
        np.full(len(grid), cos_m, dtype=np.float32),
    ])

    ml_probs  = clf.predict_proba(X)[:, 1]
    fwi_scores = np.clip(fwis / FWI_CAP, 0, 1)
    ml_risks   = ML_WEIGHT * ml_probs + FWI_WEIGHT * fwi_scores

    now_str = now.isoformat()
    for i, r in enumerate(grid):
        conn.execute("""
            INSERT OR REPLACE INTO ml_predictions
                (lat, lon, ml_prob, fwi_score, ml_risk, month, computed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (r["lat"], r["lon"],
              round(float(ml_probs[i]),  4),
              round(float(fwi_scores[i]), 4),
              round(float(ml_risks[i]),  4),
              month, now_str))

    conn.commit()
    conn.close()
    log.info("ML predictions written: %d cells, month=%d | avg=%.3f max=%.3f",
             len(grid), month, ml_risks.mean(), ml_risks.max())
    return len(grid)


if __name__ == "__main__":
    run()
