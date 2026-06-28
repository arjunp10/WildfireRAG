import sqlite3
import pytest
from unittest.mock import patch, MagicMock
from data.db import init_db
from data.historical import fetch, save

SAMPLE_CSV = (
    "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,"
    "satellite,instrument,confidence,version,bright_ti5,frp,daynight\n"
    "37.123,-120.456,325.0,0.4,0.4,2025-07-04,0200,N,VIIRS,nominal,2.0,295.0,10.5,D\n"
)


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    init_db(c)
    yield c
    c.close()


@patch("data.historical.requests.get")
def test_fetch_returns_records(mock_get):
    mock_resp = MagicMock()
    mock_resp.text = SAMPLE_CSV
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp

    records = fetch("fake_key", date_range_days=10)

    assert len(records) == 1
    assert records[0]["latitude"] == pytest.approx(37.123)
    assert records[0]["frp"] == pytest.approx(10.5)
    assert records[0]["acq_date"] == "2025-07-04"


@patch("data.historical.requests.get")
def test_fetch_chunks_into_10_day_windows(mock_get):
    mock_resp = MagicMock()
    mock_resp.text = (
        "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,"
        "satellite,instrument,confidence,version,bright_ti5,frp,daynight\n"
    )
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp

    fetch("fake_key", date_range_days=25)

    assert mock_get.call_count == 3


def test_save_returns_row_count(conn):
    records = [{
        "latitude": 37.1, "longitude": -120.5,
        "brightness": 325.0, "frp": 10.5,
        "acq_date": "2025-07-04", "acq_time": "0200",
        "confidence": "nominal", "satellite": "N",
    }]
    count = save(records, conn)
    assert count == 1


def test_save_persists_frp(conn):
    records = [{
        "latitude": 37.1, "longitude": -120.5,
        "brightness": 325.0, "frp": 10.5,
        "acq_date": "2025-07-04", "acq_time": "0200",
        "confidence": "nominal", "satellite": "N",
    }]
    save(records, conn)
    row = conn.execute("SELECT frp FROM fires_historical").fetchone()
    assert row["frp"] == pytest.approx(10.5)
