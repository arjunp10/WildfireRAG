import sqlite3
import numpy as np
from model.features import build_features, FEATURE_NAMES


def _make_db(path):
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE fires_historical (
            id INTEGER PRIMARY KEY, latitude REAL, longitude REAL,
            brightness REAL, frp REAL, acq_date TEXT,
            acq_time TEXT, confidence TEXT, satellite TEXT, ingested_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE weather (
            id INTEGER PRIMARY KEY, latitude REAL, longitude REAL,
            temperature REAL, humidity REAL, wind_speed REAL,
            wind_dir REAL, timestamp TEXT, ingested_at TEXT
        )
    """)
    # 3 train fires in same cell+month, 1 test fire
    conn.executemany(
        "INSERT INTO fires_historical (latitude, longitude, frp, acq_date, acq_time, confidence, satellite, ingested_at) VALUES (?,?,?,?,?,?,?,?)",
        [
            (37.1, -120.3, 10.0, "2010-07-04", "0000", "high", "Natural", "2026-01-01"),
            (37.2, -120.4, 20.0, "2015-07-15", "0000", "high", "Natural", "2026-01-01"),
            (37.3, -120.2, 15.0, "2018-07-20", "0000", "high", "Natural", "2026-01-01"),
            (37.1, -120.3, 12.0, "2019-07-10", "0000", "high", "Natural", "2026-01-01"),
        ]
    )
    conn.execute(
        "INSERT INTO weather (latitude, longitude, temperature, humidity, wind_speed, wind_dir, timestamp, ingested_at) VALUES (?,?,?,?,?,?,?,?)",
        (37.0, -120.0, 85.0, 20.0, 15.0, 225.0, "2026-06-29T00:00:00", "2026-01-01")
    )
    conn.commit()
    conn.close()


def test_feature_names_order():
    assert FEATURE_NAMES == [
        "hist_fire_count", "hist_avg_size_acres", "hist_fire_density",
        "temperature", "humidity", "wind_speed", "wind_dir",
        "month_sin", "month_cos", "heat_drought_index",
    ]


def test_build_features_returns_correct_shapes(tmp_path):
    db = str(tmp_path / "test.db")
    _make_db(db)
    X_train, y_train, X_test, y_test, names = build_features(db_path=db)
    assert X_train.shape[1] == 10
    assert X_test.shape[1] == 10
    assert len(y_train) == X_train.shape[0]
    assert len(y_test) == X_test.shape[0]
    assert names == FEATURE_NAMES


def test_train_test_split_is_temporal(tmp_path):
    db = str(tmp_path / "test.db")
    _make_db(db)
    X_train, y_train, X_test, y_test, _ = build_features(db_path=db)
    # 3 train fires → 1 cell+month row; 1 test fire → 1 cell+month row
    assert X_train.shape[0] >= 1
    assert X_test.shape[0] >= 1


def test_target_normalized_to_0_1(tmp_path):
    db = str(tmp_path / "test.db")
    _make_db(db)
    _, y_train, _, _, _ = build_features(db_path=db)
    assert y_train.max() <= 1.0 + 1e-6
    assert y_train.min() >= -1e-6


def test_feature_count_correct(tmp_path):
    db = str(tmp_path / "test.db")
    _make_db(db)
    X_train, _, _, _, _ = build_features(db_path=db)
    assert X_train.shape[1] == 10


def test_month_sin_cos_range(tmp_path):
    db = str(tmp_path / "test.db")
    _make_db(db)
    X_train, _, _, _, names = build_features(db_path=db)
    sin_idx = names.index("month_sin")
    cos_idx = names.index("month_cos")
    assert np.all(X_train[:, sin_idx] >= -1.0)
    assert np.all(X_train[:, sin_idx] <= 1.0)
    assert np.all(X_train[:, cos_idx] >= -1.0)
    assert np.all(X_train[:, cos_idx] <= 1.0)
