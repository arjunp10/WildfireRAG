# WildfireRAG Phase 2 — Forecasting Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Train a Ridge + Random Forest ensemble on 2.3M historical fire records to produce a 0–1 fire risk score for every 0.5° CONUS grid cell, stored in `fires_predictions`.

**Architecture:** A `model/` package owns feature engineering, training, and inference. A root-level `train.py` CLI runs them in sequence. Models are saved to `models/` (gitignored) and loaded at inference time via joblib.

**Tech Stack:** Python 3.11+, pandas, numpy, scikit-learn, joblib, sqlite3 (stdlib)

## Global Constraints

- Python 3.11+
- Grid resolution: exactly 0.5° — binning formula: `round(coord * 2) / 2`
- Train set: `acq_date < 2019-01-01` (27 years, 1992–2018)
- Test set: `acq_date >= 2019-01-01` (2 years, 2019–2020)
- Feature list (exact order): `["hist_fire_count", "hist_avg_size_acres", "hist_fire_density", "temperature", "humidity", "wind_speed", "wind_dir", "month_sin", "month_cos", "heat_drought_index"]`
- Ensemble: `fire_probability = 0.5 * ridge_score + 0.5 * rf_score`, clipped to [0, 1]
- `model_version = "ensemble-v1"` in all `fires_predictions` rows
- `models/` directory is gitignored
- All logging via `logging.getLogger(__name__)`, no bare `print()` except evaluation table
- DB path default: `"firerag.db"`

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `requirements.txt` | Modify | Add pandas, scikit-learn, joblib, numpy |
| `.gitignore` | Modify | Add `models/` |
| `model/__init__.py` | Create | Empty package marker |
| `model/features.py` | Create | Load DB, bin to grid, aggregate, join weather, engineer features, return train/test arrays |
| `model/train.py` | Create | Fit Ridge + RF, evaluate, print metrics table, save to `models/` |
| `model/predict.py` | Create | Load models, score all cells for today, write `fires_predictions` |
| `train.py` | Create | CLI: features → train → predict in sequence |
| `tests/test_features.py` | Create | Feature engineering tests with in-memory SQLite |
| `tests/test_predict.py` | Create | Prediction tests with tiny synthetic models |

---

## Task 1: Scaffold — dependencies and package marker

**Files:**
- Modify: `requirements.txt`
- Modify: `.gitignore`
- Create: `model/__init__.py`
- Create: `models/.gitkeep`

**Interfaces:**
- Produces: nothing consumed by other tasks — pure scaffolding

- [ ] **Step 1: Update `requirements.txt`**

Replace contents:

```
requests==2.32.3
python-dotenv==1.0.1
tabulate==0.9.0
pytest==8.3.2
pandas==2.2.2
numpy==1.26.4
scikit-learn==1.5.1
joblib==1.4.2
```

- [ ] **Step 2: Update `.gitignore`**

Add two lines at the end:

```
models/*.pkl
models/*.joblib
```

- [ ] **Step 3: Create package marker and models placeholder**

```bash
mkdir -p model models
touch model/__init__.py models/.gitkeep
```

- [ ] **Step 4: Install new dependencies**

```bash
pip3 install pandas==2.2.2 numpy==1.26.4 scikit-learn==1.5.1 joblib==1.4.2
```

Expected: installs without error.

- [ ] **Step 5: Commit**

```bash
git add requirements.txt .gitignore model/__init__.py models/.gitkeep
git commit -m "chore: add ml dependencies and model package scaffold"
```

---

## Task 2: Feature Engineering (`model/features.py`)

**Files:**
- Create: `model/features.py`
- Create: `tests/test_features.py`

**Interfaces:**
- Consumes: `firerag.db` (sqlite) — tables `fires_historical`, `weather`
- Produces:
  - `build_features(db_path: str = "firerag.db", split_date: str = "2019-01-01") -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, list[str]]`
    - Returns `(X_train, y_train, X_test, y_test, feature_names)`
    - `X_*` shape: `(n_samples, 10)` — 10 features in Global Constraints order
    - `y_*` shape: `(n_samples,)` — `fire_risk` normalized to [0, 1]
  - `FEATURE_NAMES: list[str]` — module-level constant, exact order from Global Constraints

- [ ] **Step 1: Write failing tests**

Create `tests/test_features.py`:

```python
import sqlite3
import numpy as np
import pytest
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_features.py -v
```

Expected: `ImportError` — `model.features` doesn't exist yet.

- [ ] **Step 3: Implement `model/features.py`**

```python
import logging
import sqlite3

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

FEATURE_NAMES: list[str] = [
    "hist_fire_count",
    "hist_avg_size_acres",
    "hist_fire_density",
    "temperature",
    "humidity",
    "wind_speed",
    "wind_dir",
    "month_sin",
    "month_cos",
    "heat_drought_index",
]

_TRAIN_YEARS = 27  # 1992–2018
_TEST_YEARS = 2    # 2019–2020


def _bin(val: float) -> float:
    return round(val * 2) / 2


def _load_fires(conn: sqlite3.Connection) -> pd.DataFrame:
    df = pd.read_sql(
        "SELECT latitude, longitude, frp, acq_date FROM fires_historical", conn
    )
    df["cell_lat"] = df["latitude"].apply(_bin)
    df["cell_lon"] = df["longitude"].apply(_bin)
    df["acq_date"] = pd.to_datetime(df["acq_date"])
    df["month"] = df["acq_date"].dt.month
    return df


def _load_weather(conn: sqlite3.Connection) -> pd.DataFrame:
    df = pd.read_sql(
        "SELECT latitude, longitude, temperature, humidity, wind_speed, wind_dir FROM weather",
        conn,
    )
    df["cell_lat"] = df["latitude"].apply(_bin)
    df["cell_lon"] = df["longitude"].apply(_bin)
    return (
        df.groupby(["cell_lat", "cell_lon"])
        .agg(
            temperature=("temperature", "mean"),
            humidity=("humidity", "mean"),
            wind_speed=("wind_speed", "mean"),
            wind_dir=("wind_dir", "mean"),
        )
        .reset_index()
    )


def _aggregate(df: pd.DataFrame, n_years: int) -> pd.DataFrame:
    agg = (
        df.groupby(["cell_lat", "cell_lon", "month"])
        .agg(hist_fire_count=("frp", "count"), hist_avg_size_acres=("frp", "mean"))
        .reset_index()
    )
    agg["hist_fire_density"] = agg["hist_fire_count"] / n_years
    return agg


def _engineer(df: pd.DataFrame, weather: pd.DataFrame) -> pd.DataFrame:
    df = df.merge(weather, on=["cell_lat", "cell_lon"], how="left")
    for col, fill in [
        ("temperature", df["temperature"].median()),
        ("humidity", df["humidity"].median()),
        ("wind_speed", 0.0),
        ("wind_dir", 0.0),
    ]:
        df[col] = df[col].fillna(fill)
    df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12)
    df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12)
    df["heat_drought_index"] = df["temperature"] * (100 - df["humidity"]) / 100
    return df


def build_features(
    db_path: str = "firerag.db",
    split_date: str = "2019-01-01",
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, list[str]]:
    conn = sqlite3.connect(db_path)
    fires = _load_fires(conn)
    weather = _load_weather(conn)
    conn.close()

    split = pd.Timestamp(split_date)
    train_agg = _aggregate(fires[fires["acq_date"] < split], _TRAIN_YEARS)
    test_agg = _aggregate(fires[fires["acq_date"] >= split], _TEST_YEARS)

    train_df = _engineer(train_agg, weather)
    test_df = _engineer(test_agg, weather)

    density_min = train_df["hist_fire_density"].min()
    density_max = train_df["hist_fire_density"].max()
    denom = density_max - density_min + 1e-9

    train_df["fire_risk"] = (train_df["hist_fire_density"] - density_min) / denom
    test_df["fire_risk"] = (test_df["hist_fire_density"] - density_min) / denom

    logger.info(
        "Features built: %d train rows, %d test rows", len(train_df), len(test_df)
    )

    X_train = train_df[FEATURE_NAMES].to_numpy(dtype=float)
    y_train = train_df["fire_risk"].to_numpy(dtype=float)
    X_test = test_df[FEATURE_NAMES].to_numpy(dtype=float)
    y_test = test_df["fire_risk"].to_numpy(dtype=float)

    return X_train, y_train, X_test, y_test, FEATURE_NAMES
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_features.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add model/features.py tests/test_features.py
git commit -m "feat: feature engineering — grid aggregation and weather join"
```

---

## Task 3: Model Training (`model/train.py`)

**Files:**
- Create: `model/train.py`
- Create: `tests/test_train.py`

**Interfaces:**
- Consumes:
  - `X_train: np.ndarray`, `y_train: np.ndarray`, `X_test: np.ndarray`, `y_test: np.ndarray` from `model.features.build_features()`
- Produces:
  - `train_and_save(X_train, y_train, X_test, y_test, models_dir: str = "models") -> dict[str, dict[str, float]]`
    - Returns `{"LR": {"r2": float, "mae": float, "rmse": float}, "RF": {...}, "Ensemble": {...}}`
    - Side effect: writes `models/lr_model.pkl`, `models/lr_scaler.pkl`, `models/rf_model.pkl`

- [ ] **Step 1: Write failing tests**

Create `tests/test_train.py`:

```python
import numpy as np
import pytest
from pathlib import Path
from model.train import train_and_save


@pytest.fixture
def synthetic_data():
    rng = np.random.default_rng(42)
    X_train = rng.random((200, 10))
    y_train = rng.random(200)
    X_test = rng.random((50, 10))
    y_test = rng.random(50)
    return X_train, y_train, X_test, y_test


def test_train_returns_metrics_for_all_models(synthetic_data, tmp_path):
    X_train, y_train, X_test, y_test = synthetic_data
    results = train_and_save(X_train, y_train, X_test, y_test, models_dir=str(tmp_path))
    assert set(results.keys()) == {"LR", "RF", "Ensemble"}
    for model_name in results:
        assert set(results[model_name].keys()) == {"r2", "mae", "rmse"}


def test_train_saves_model_files(synthetic_data, tmp_path):
    X_train, y_train, X_test, y_test = synthetic_data
    train_and_save(X_train, y_train, X_test, y_test, models_dir=str(tmp_path))
    assert (tmp_path / "lr_model.pkl").exists()
    assert (tmp_path / "lr_scaler.pkl").exists()
    assert (tmp_path / "rf_model.pkl").exists()


def test_metrics_are_floats(synthetic_data, tmp_path):
    X_train, y_train, X_test, y_test = synthetic_data
    results = train_and_save(X_train, y_train, X_test, y_test, models_dir=str(tmp_path))
    for model_name, metrics in results.items():
        for metric_name, value in metrics.items():
            assert isinstance(value, float), f"{model_name}.{metric_name} is not float"


def test_rmse_is_non_negative(synthetic_data, tmp_path):
    X_train, y_train, X_test, y_test = synthetic_data
    results = train_and_save(X_train, y_train, X_test, y_test, models_dir=str(tmp_path))
    for model_name in results:
        assert results[model_name]["rmse"] >= 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_train.py -v
```

Expected: `ImportError` — `model.train` doesn't exist yet.

- [ ] **Step 3: Implement `model/train.py`**

```python
import logging
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)


def train_and_save(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
    models_dir: str = "models",
) -> dict[str, dict[str, float]]:
    Path(models_dir).mkdir(exist_ok=True)

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    logger.info("Training Ridge regression...")
    ridge = Ridge(alpha=1.0)
    ridge.fit(X_train_scaled, y_train)

    logger.info("Training Random Forest (100 trees)...")
    rf = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
    rf.fit(X_train, y_train)

    lr_pred = ridge.predict(X_test_scaled)
    rf_pred = rf.predict(X_test)
    ens_pred = np.clip(0.5 * lr_pred + 0.5 * rf_pred, 0.0, 1.0)

    results: dict[str, dict[str, float]] = {}
    for name, pred in [("LR", lr_pred), ("RF", rf_pred), ("Ensemble", ens_pred)]:
        results[name] = {
            "r2": float(r2_score(y_test, pred)),
            "mae": float(mean_absolute_error(y_test, pred)),
            "rmse": float(mean_squared_error(y_test, pred) ** 0.5),
        }

    joblib.dump(ridge, Path(models_dir) / "lr_model.pkl")
    joblib.dump(scaler, Path(models_dir) / "lr_scaler.pkl")
    joblib.dump(rf, Path(models_dir) / "rf_model.pkl")
    logger.info("Models saved to %s/", models_dir)

    return results
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_train.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add model/train.py tests/test_train.py
git commit -m "feat: ridge + random forest training with evaluation and joblib save"
```

---

## Task 4: Inference (`model/predict.py`)

**Files:**
- Create: `model/predict.py`
- Create: `tests/test_predict.py`

**Interfaces:**
- Consumes:
  - `models/lr_model.pkl`, `models/lr_scaler.pkl`, `models/rf_model.pkl` saved by `model.train.train_and_save()`
  - `firerag.db` — tables `fires_historical`, `weather`
- Produces:
  - `predict_and_save(db_path: str = "firerag.db", models_dir: str = "models", prediction_date: str | None = None) -> int`
    - Scores all CONUS cells with historical fire records for current month
    - Writes rows to `fires_predictions`
    - Returns number of rows written

- [ ] **Step 1: Write failing tests**

Create `tests/test_predict.py`:

```python
import sqlite3
import numpy as np
import joblib
import pytest
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
            (37.1, -120.3, 0.0, 10.0, "2010-07-04", "0000", "high", "Natural", "2026-01-01"),
            (37.2, -120.4, 0.0, 20.0, "2015-07-15", "0000", "high", "Natural", "2026-01-01"),
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_predict.py -v
```

Expected: `ImportError` — `model.predict` doesn't exist yet.

- [ ] **Step 3: Implement `model/predict.py`**

```python
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
    for col, fill in [
        ("temperature", df.get("temperature", pd.Series([70.0])).median()),
        ("humidity", df.get("humidity", pd.Series([50.0])).median()),
        ("wind_speed", 0.0),
        ("wind_dir", 0.0),
    ]:
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_predict.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add model/predict.py tests/test_predict.py
git commit -m "feat: inference — score conus grid and write fires_predictions"
```

---

## Task 5: CLI Entrypoint (`train.py`)

**Files:**
- Create: `train.py`

**Interfaces:**
- Consumes:
  - `model.features.build_features(db_path) -> (X_train, y_train, X_test, y_test, feature_names)`
  - `model.train.train_and_save(X_train, y_train, X_test, y_test, models_dir) -> dict`
  - `model.predict.predict_and_save(db_path, models_dir) -> int`

- [ ] **Step 1: Run full test suite to confirm baseline**

```bash
python3 -m pytest tests/ -v
```

Expected: all existing tests PASS before adding the CLI.

- [ ] **Step 2: Implement `train.py`**

```python
import logging
import sys
from tabulate import tabulate
from model.features import build_features
from model.train import train_and_save
from model.predict import predict_and_save

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)-25s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("train")

DB_PATH = "firerag.db"
MODELS_DIR = "models"


def main() -> None:
    logger.info("Phase 2: building features from %s", DB_PATH)
    X_train, y_train, X_test, y_test, feature_names = build_features(db_path=DB_PATH)
    logger.info(
        "Feature matrix: train=%s  test=%s", X_train.shape, X_test.shape
    )

    logger.info("Training models...")
    results = train_and_save(X_train, y_train, X_test, y_test, models_dir=MODELS_DIR)

    rows = [
        [name, f"{m['r2']:.4f}", f"{m['mae']:.4f}", f"{m['rmse']:.4f}"]
        for name, m in results.items()
    ]
    print("\n" + tabulate(rows, headers=["Model", "R²", "MAE", "RMSE"], tablefmt="rounded_outline"))

    logger.info("Generating predictions for today...")
    n = predict_and_save(db_path=DB_PATH, models_dir=MODELS_DIR)
    logger.info("Done — %d predictions written to fires_predictions", n)


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run full test suite**

```bash
python3 -m pytest tests/ -v
```

Expected: all tests PASS (no changes to tested modules).

- [ ] **Step 4: Run live training**

```bash
python3 train.py
```

Expected output (values will vary):
```
HH:MM:SS  model.features  INFO  Features built: NNNNN train rows, NNN test rows
HH:MM:SS  model.train     INFO  Training Ridge regression...
HH:MM:SS  model.train     INFO  Training Random Forest (100 trees)...
HH:MM:SS  model.train     INFO  Models saved to models/

╭───────────┬────────┬────────┬────────╮
│ Model     │ R²     │ MAE    │ RMSE   │
├───────────┼────────┼────────┼────────┤
│ LR        │ x.xxxx │ x.xxxx │ x.xxxx │
│ RF        │ x.xxxx │ x.xxxx │ x.xxxx │
│ Ensemble  │ x.xxxx │ x.xxxx │ x.xxxx │
╰───────────┴────────┴────────┴────────╯

HH:MM:SS  model.predict   INFO  Predictions written: NNNN rows for YYYY-MM-DD
HH:MM:SS  train           INFO  Done — NNNN predictions written to fires_predictions
```

- [ ] **Step 5: Verify predictions in DB**

```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('firerag.db')
count = conn.execute('SELECT COUNT(*) FROM fires_predictions').fetchone()[0]
sample = conn.execute('SELECT latitude, longitude, fire_probability, model_version FROM fires_predictions ORDER BY fire_probability DESC LIMIT 5').fetchall()
print(f'Total predictions: {count}')
print('Top 5 highest-risk cells:')
for row in sample:
    print(f'  lat={row[0]:.1f} lon={row[1]:.1f} prob={row[2]:.4f} version={row[3]}')
"
```

- [ ] **Step 6: Commit**

```bash
git add train.py
git commit -m "feat: train.py cli — features, train, evaluate, predict in sequence"
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] Feature engineering (grid binning, hist aggregation, weather join, cyclical encoding, heat_drought_index) → Task 2
- [x] Ridge regression + StandardScaler → Task 3
- [x] Random Forest (100 trees, random_state=42) → Task 3
- [x] Ensemble (0.5 × LR + 0.5 × RF, clipped to [0,1]) → Tasks 3 + 4
- [x] Train/test split: `< 2019-01-01` / `>= 2019-01-01` → Task 2
- [x] Evaluation metrics (R², MAE, RMSE) for all 3 models → Task 3
- [x] Models saved via joblib → Task 3
- [x] Score all CONUS cells with fire history → Task 4
- [x] Write `fires_predictions` with `model_version = "ensemble-v1"` → Task 4
- [x] CLI entrypoint `train.py` → Task 5
- [x] `models/` gitignored → Task 1
- [x] New deps in `requirements.txt` → Task 1

**Placeholder scan:** None found.

**Type consistency:**
- `build_features()` returns `(np.ndarray, np.ndarray, np.ndarray, np.ndarray, list[str])` — consumed correctly in Tasks 3 and 5 ✓
- `train_and_save()` returns `dict[str, dict[str, float]]` — consumed correctly in Task 5 ✓
- `predict_and_save()` returns `int` — consumed correctly in Task 5 ✓
- `FEATURE_NAMES` imported in `model/predict.py` from `model.features` ✓
- `_bin` and `_load_weather` imported in `model/predict.py` from `model.features` ✓
