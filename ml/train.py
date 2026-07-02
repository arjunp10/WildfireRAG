"""
Phase 2 — ML fire ignition model
=================================
Trains a RandomForestClassifier on 26 years of confirmed fire ignitions.

Features per (cell, month) sample:
  lat, lon, sin_month, cos_month

Target: 1 if ≥1 confirmed fire ignition in this 1°×1° cell in this month
        0 otherwise

At inference time the raw ML probability is blended with the current
7-day FWI score (see predict.py).

Usage:
    python3 -m ml.train
Saves model to ml/model.pkl
"""
import logging
import math
import pickle
import sqlite3
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score

logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")
log = logging.getLogger(__name__)

DB_PATH = "firerag.db"
MODEL_PATH = Path(__file__).parent / "model.pkl"


def build_dataset(db_path: str = DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Grid cells we have weather data for (defines our prediction space)
    grid = conn.execute(
        "SELECT lat, lon FROM weather_grid WHERE fetched_at IS NOT NULL"
    ).fetchall()
    grid_cells = [(r["lat"], r["lon"]) for r in grid]

    # Historical fire ignitions: bin to nearest 1° cell, group by (cell, month)
    fires = conn.execute("""
        SELECT
            ROUND(latitude)  AS cell_lat,
            ROUND(longitude) AS cell_lon,
            CAST(substr(discovery_date, 6, 2) AS INTEGER) AS month
        FROM fire_perimeters
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
          AND discovery_date IS NOT NULL AND length(discovery_date) >= 7
          AND CAST(substr(discovery_date, 6, 2) AS INTEGER) BETWEEN 1 AND 12
    """).fetchall()
    conn.close()

    fire_set = defaultdict(int)
    for f in fires:
        fire_set[(f["cell_lat"], f["cell_lon"], f["month"])] += 1

    log.info("Grid cells: %d | fire ignition buckets: %d", len(grid_cells), len(fire_set))

    X, y = [], []
    for lat, lon in grid_cells:
        cell_lat = round(lat)
        cell_lon = round(lon)
        for month in range(1, 13):
            sin_m = math.sin(2 * math.pi * month / 12)
            cos_m = math.cos(2 * math.pi * month / 12)
            X.append([lat, lon, sin_m, cos_m])
            count = fire_set.get((cell_lat, cell_lon, month), 0)
            y.append(1 if count >= 1 else 0)

    X = np.array(X, dtype=np.float32)
    y = np.array(y, dtype=np.int8)
    log.info("Dataset: %d samples | %d positive (%.1f%%)",
             len(y), y.sum(), 100 * y.mean())
    return X, y


def train(db_path: str = DB_PATH) -> RandomForestClassifier:
    X, y = build_dataset(db_path)

    clf = RandomForestClassifier(
        n_estimators=300,
        max_depth=10,
        min_samples_leaf=3,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )

    # Quick cross-val to report accuracy before saving
    scores = cross_val_score(clf, X, y, cv=5, scoring="roc_auc")
    log.info("5-fold ROC-AUC: %.3f ± %.3f", scores.mean(), scores.std())

    clf.fit(X, y)

    with open(MODEL_PATH, "wb") as f:
        pickle.dump(clf, f)
    log.info("Model saved → %s", MODEL_PATH)
    return clf


if __name__ == "__main__":
    train()
