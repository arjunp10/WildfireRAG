import json
import sqlite3
import pytest
from pathlib import Path
from export_data import export_fires


def _make_db(path: str):
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE fires_realtime (
            id INTEGER PRIMARY KEY, latitude REAL, longitude REAL,
            brightness REAL, acq_date TEXT, acq_time TEXT,
            confidence TEXT, satellite TEXT, ingested_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE fires_predictions (
            id INTEGER PRIMARY KEY, latitude REAL, longitude REAL,
            fire_probability REAL, prediction_date TEXT,
            model_version TEXT, ingested_at TEXT
        )
    """)
    conn.execute("""
        INSERT INTO fires_realtime
            (latitude, longitude, brightness, acq_date, acq_time, confidence, satellite, ingested_at)
        VALUES (37.0, -120.0, 310.5, '2026-06-29', '0145', 'nominal', 'N', '2026-06-29')
    """)
    conn.execute("""
        INSERT INTO fires_predictions
            (latitude, longitude, fire_probability, prediction_date, model_version, ingested_at)
        VALUES (37.0, -120.0, 0.72, '2026-06-29', 'ensemble-v1', '2026-06-29')
    """)
    conn.commit()
    conn.close()


def test_export_fires_returns_count(tmp_path):
    db = str(tmp_path / "test.db")
    out = str(tmp_path / "fires.json")
    _make_db(db)
    count = export_fires(db_path=db, out_path=out)
    assert count == 1


def test_export_fires_writes_json(tmp_path):
    db = str(tmp_path / "test.db")
    out = str(tmp_path / "fires.json")
    _make_db(db)
    export_fires(db_path=db, out_path=out)
    data = json.loads(Path(out).read_text())
    assert "fires" in data
    assert "generated_at" in data
    assert data["count"] == 1


def test_export_fires_joins_probability(tmp_path):
    db = str(tmp_path / "test.db")
    out = str(tmp_path / "fires.json")
    _make_db(db)
    export_fires(db_path=db, out_path=out)
    data = json.loads(Path(out).read_text())
    assert pytest.approx(data["fires"][0]["fire_probability"]) == 0.72


def test_export_fires_null_probability_when_no_predictions(tmp_path):
    db = str(tmp_path / "test.db")
    out = str(tmp_path / "fires.json")
    conn = sqlite3.connect(db)
    conn.execute("""
        CREATE TABLE fires_realtime (
            id INTEGER PRIMARY KEY, latitude REAL, longitude REAL,
            brightness REAL, acq_date TEXT, acq_time TEXT,
            confidence TEXT, satellite TEXT, ingested_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE fires_predictions (
            id INTEGER PRIMARY KEY, latitude REAL, longitude REAL,
            fire_probability REAL, prediction_date TEXT,
            model_version TEXT, ingested_at TEXT
        )
    """)
    conn.execute("""
        INSERT INTO fires_realtime
            (latitude, longitude, brightness, acq_date, acq_time, confidence, satellite, ingested_at)
        VALUES (37.0, -120.0, 310.5, '2026-06-29', '0145', 'nominal', 'N', '2026-06-29')
    """)
    conn.commit()
    conn.close()
    export_fires(db_path=db, out_path=out)
    data = json.loads(Path(out).read_text())
    assert data["fires"][0]["fire_probability"] is None


def test_export_fires_creates_parent_dirs(tmp_path):
    db = str(tmp_path / "test.db")
    out = str(tmp_path / "nested" / "dir" / "fires.json")
    _make_db(db)
    export_fires(db_path=db, out_path=out)
    assert Path(out).exists()


def test_fire_fields_present(tmp_path):
    db = str(tmp_path / "test.db")
    out = str(tmp_path / "fires.json")
    _make_db(db)
    export_fires(db_path=db, out_path=out)
    data = json.loads(Path(out).read_text())
    fire = data["fires"][0]
    for field in ["id", "latitude", "longitude", "brightness", "acq_date",
                  "acq_time", "confidence", "satellite", "fire_probability"]:
        assert field in fire, f"Missing field: {field}"
