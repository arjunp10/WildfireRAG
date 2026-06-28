import sqlite3
import pytest
from data.db import get_connection, init_db


@pytest.fixture
def conn():
    c = get_connection(":memory:")
    init_db(c)
    yield c
    c.close()


def test_fires_realtime_table_exists(conn):
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='fires_realtime'"
    )
    assert cursor.fetchone() is not None


def test_weather_table_exists(conn):
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='weather'"
    )
    assert cursor.fetchone() is not None


def test_fires_historical_table_exists(conn):
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='fires_historical'"
    )
    assert cursor.fetchone() is not None


def test_fires_predictions_table_exists(conn):
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='fires_predictions'"
    )
    assert cursor.fetchone() is not None


def test_fires_realtime_columns(conn):
    cursor = conn.execute("PRAGMA table_info(fires_realtime)")
    cols = {row[1] for row in cursor.fetchall()}
    assert cols == {
        "id", "latitude", "longitude", "brightness",
        "acq_date", "acq_time", "confidence", "satellite", "ingested_at"
    }


def test_init_db_is_idempotent(conn):
    init_db(conn)  # second call must not raise
    cursor = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )
    assert cursor.fetchone()[0] == 4
