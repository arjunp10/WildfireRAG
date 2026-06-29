import sqlite3
import numpy as np
import joblib
from pathlib import Path
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestRegressor
from model.predict import predict_and_save
from data.db import init_db


def _make_db(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    init_db(conn)
    conn.executemany(
        "INSERT INTO fires_historical (latitude, longitude, brightness, frp, acq_date, acq_time, confidence, satellite, ingested_at) VALUES (?,?,?,?,?,?,?,?,?)",
        [
            (37.1, -120.3, 0.0, 10.0, "2010-06-04", "0000", "high", "Natural", "2026-01-01"),
            (37.2, -120.4, 0.0, 20.0, "2015-06-15", "0000", "high", "Natural", "2026-01-01"),
        ]
    )
    conn.execute(
        "INSERT INTO weather (latitude, longitude, temperature, humidity, wind_speed, wind_dir, timestamp, ingested_at) VALUES (?,?,?,?,?,?,?,?)",
        (37.0, -120.0, 85.0, 20.0, 15.0, 225.0, "2026-06-29T00:00:00", "2026-01-01")
    )
    conn.commit()
    conn.close()


def _make_models(models_dir: Path):
    models_dir.mkdir(exist_ok=True)
    X = np.random.default_rng(42).random((50, 10))
    y = np.random.default_rng(42).random(50)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    ridge = Ridge(alpha=1.0)
    ridge.fit(X_scaled, y)

    rf = RandomForestRegressor(n_estimators=5, random_state=42)
    rf.fit(X, y)

    joblib.dump(ridge, models_dir / "lr_model.pkl")
    joblib.dump(scaler, models_dir / "lr_scaler.pkl")
    joblib.dump(rf, models_dir / "rf_model.pkl")


def test_predict_returns_row_count(tmp_path):
    db = str(tmp_path / "test.db")
    _make_db(db)
    _make_models(tmp_path / "models")
    count = predict_and_save(
        db_path=db,
        models_dir=str(tmp_path / "models"),
        prediction_date="2026-06-29",
    )
    assert count > 0


def test_predict_writes_to_db(tmp_path):
    db = str(tmp_path / "test.db")
    _make_db(db)
    _make_models(tmp_path / "models")
    predict_and_save(
        db_path=db,
        models_dir=str(tmp_path / "models"),
        prediction_date="2026-06-29",
    )
    conn = sqlite3.connect(db)
    rows = conn.execute("SELECT * FROM fires_predictions").fetchall()
    conn.close()
    assert len(rows) > 0


def test_predict_fire_probability_in_range(tmp_path):
    db = str(tmp_path / "test.db")
    _make_db(db)
    _make_models(tmp_path / "models")
    predict_and_save(
        db_path=db,
        models_dir=str(tmp_path / "models"),
        prediction_date="2026-06-29",
    )
    conn = sqlite3.connect(db)
    rows = conn.execute("SELECT fire_probability FROM fires_predictions").fetchall()
    conn.close()
    for (prob,) in rows:
        assert 0.0 <= prob <= 1.0


def test_predict_sets_model_version(tmp_path):
    db = str(tmp_path / "test.db")
    _make_db(db)
    _make_models(tmp_path / "models")
    predict_and_save(
        db_path=db,
        models_dir=str(tmp_path / "models"),
        prediction_date="2026-06-29",
    )
    conn = sqlite3.connect(db)
    row = conn.execute("SELECT model_version FROM fires_predictions LIMIT 1").fetchone()
    conn.close()
    assert row[0] == "ensemble-v1"
