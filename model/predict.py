import logging
import sqlite3
from datetime import date, datetime, timezone

import joblib
import numpy as np
import pandas as pd

from model.features import FEATURE_NAMES, _bin, _load_weather

logger = logging.getLogger(__name__)

_MODEL_VERSION = "ensemble-v1"


def predict_and_save(
    db_path: str = "firerag.db",
    models_dir: str = "models",
    prediction_date: str | None = None,
) -> int:
    if prediction_date is None:
        prediction_date = date.today().isoformat()
    month = int(prediction_date[5:7])

    ridge = joblib.load(f"{models_dir}/lr_model.pkl")
    scaler = joblib.load(f"{models_dir}/lr_scaler.pkl")
    rf = joblib.load(f"{models_dir}/rf_model.pkl")

    conn = sqlite3.connect(db_path)

    hist = pd.read_sql(
        f"""
        SELECT
            round(latitude * 2) / 2  AS cell_lat,
            round(longitude * 2) / 2 AS cell_lon,
            COUNT(*)                  AS hist_fire_count,
            AVG(frp)                  AS hist_avg_size_acres,
            COUNT(*) / 27.0           AS hist_fire_density
        FROM fires_historical
        WHERE CAST(strftime('%m', acq_date) AS INTEGER) = {month}
        GROUP BY cell_lat, cell_lon
        """,
        conn,
    )

    weather = _load_weather(conn)
    conn.close()

    df = hist.merge(weather, on=["cell_lat", "cell_lon"], how="left")
    _defaults = {"temperature": 70.0, "humidity": 50.0, "wind_speed": 0.0, "wind_dir": 0.0}
    for col, default in _defaults.items():
        series = df.get(col, pd.Series(dtype=float))
        median_val = series.median()
        fill = median_val if pd.notna(median_val) else default
        df[col] = df[col].fillna(fill)

    df["month_sin"] = np.sin(2 * np.pi * month / 12)
    df["month_cos"] = np.cos(2 * np.pi * month / 12)
    df["heat_drought_index"] = df["temperature"] * (100 - df["humidity"]) / 100

    X = df[FEATURE_NAMES].to_numpy(dtype=float)
    lr_pred = ridge.predict(scaler.transform(X))
    rf_pred = rf.predict(X)
    df["fire_probability"] = np.clip(0.5 * lr_pred + 0.5 * rf_pred, 0.0, 1.0)

    ingested_at = datetime.now(timezone.utc).isoformat()
    rows = [
        (
            float(row.cell_lat),
            float(row.cell_lon),
            float(row.fire_probability),
            prediction_date,
            _MODEL_VERSION,
            ingested_at,
        )
        for row in df.itertuples()
    ]

    out_conn = sqlite3.connect(db_path)
    out_conn.executemany(
        """
        INSERT INTO fires_predictions
            (latitude, longitude, fire_probability, prediction_date, model_version, ingested_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    out_conn.commit()
    out_conn.close()

    logger.info("Predictions written: %d rows for %s", len(rows), prediction_date)
    return len(rows)
