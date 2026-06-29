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
    # Keep acq_date as str (YYYY-MM-DD is lexicographically sortable) to avoid
    # pandas/Python-3.13 segfault in strptime. Extract month via string slice.
    df["month"] = df["acq_date"].str[5:7].astype(int)
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

    # Use string comparison — YYYY-MM-DD is lexicographically sortable
    train_agg = _aggregate(fires[fires["acq_date"] < split_date], _TRAIN_YEARS)
    test_agg = _aggregate(fires[fires["acq_date"] >= split_date], _TEST_YEARS)

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
