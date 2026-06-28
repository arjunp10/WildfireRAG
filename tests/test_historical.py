import sqlite3
import tempfile
import pytest
from pathlib import Path
from data.db import init_db
from data.historical import fetch, save, _doy_to_date


def _make_kaggle_db(path: Path):
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE Fires (
            LATITUDE REAL, LONGITUDE REAL, FIRE_SIZE REAL,
            FIRE_YEAR INTEGER, DISCOVERY_DOY INTEGER, STAT_CAUSE_DESCR TEXT
        )
    """)
    conn.execute(
        "INSERT INTO Fires VALUES (37.123, -120.456, 150.5, 2020, 185, 'Lightning')"
    )
    conn.execute(
        "INSERT INTO Fires VALUES (NULL, -119.0, 50.0, 2020, 186, 'Debris Burning')"
    )
    conn.commit()
    conn.close()


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    init_db(c)
    yield c
    c.close()


def test_doy_to_date():
    assert _doy_to_date(2020, 1) == "2020-01-01"
    assert _doy_to_date(2020, 185) == "2020-07-03"
    assert _doy_to_date(2021, 365) == "2021-12-31"


def test_fetch_returns_records(tmp_path):
    db_path = tmp_path / "wildfires.sqlite"
    _make_kaggle_db(db_path)

    records = fetch(file_path=db_path)

    assert len(records) == 1  # NULL row skipped
    assert records[0]["latitude"] == pytest.approx(37.123)
    assert records[0]["frp"] == pytest.approx(150.5)
    assert records[0]["acq_date"] == "2020-07-03"
    assert records[0]["satellite"] == "Lightning"
    assert records[0]["confidence"] == "high"


def test_fetch_raises_if_file_missing(tmp_path):
    with pytest.raises(FileNotFoundError, match="wildfires.sqlite"):
        fetch(file_path=tmp_path / "nonexistent.sqlite")


def test_save_returns_row_count(conn, tmp_path):
    db_path = tmp_path / "wildfires.sqlite"
    _make_kaggle_db(db_path)
    records = fetch(file_path=db_path)
    count = save(records, conn)
    assert count == 1


def test_save_persists_frp(conn, tmp_path):
    db_path = tmp_path / "wildfires.sqlite"
    _make_kaggle_db(db_path)
    records = fetch(file_path=db_path)
    save(records, conn)
    row = conn.execute("SELECT frp FROM fires_historical").fetchone()
    assert row["frp"] == pytest.approx(150.5)
