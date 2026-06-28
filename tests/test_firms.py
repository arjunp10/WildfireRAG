import sqlite3
import pytest
from unittest.mock import patch, MagicMock
from data.db import init_db
from data.firms import fetch, save

SAMPLE_CSV = (
    "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,"
    "satellite,instrument,confidence,version,bright_ti5,frp,daynight\n"
    "37.123,-120.456,320.1,0.4,0.4,2026-06-28,0130,N,VIIRS,nominal,2.0NRT,290.5,5.2,D\n"
    "36.789,-119.123,310.5,0.4,0.4,2026-06-28,0130,N,VIIRS,high,2.0NRT,285.0,3.1,D\n"
)


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    init_db(c)
    yield c
    c.close()


@patch("data.firms.requests.get")
def test_fetch_returns_list_of_dicts(mock_get):
    mock_resp = MagicMock()
    mock_resp.text = SAMPLE_CSV
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp

    records = fetch("fake_key")

    assert len(records) == 2
    assert records[0]["latitude"] == pytest.approx(37.123)
    assert records[0]["longitude"] == pytest.approx(-120.456)
    assert records[0]["brightness"] == pytest.approx(320.1)
    assert records[0]["acq_date"] == "2026-06-28"
    assert records[0]["acq_time"] == "0130"
    assert records[0]["confidence"] == "nominal"
    assert records[0]["satellite"] == "N"


@patch("data.firms.requests.get")
def test_fetch_raises_on_http_error(mock_get):
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = Exception("404")
    mock_get.return_value = mock_resp

    with pytest.raises(Exception):
        fetch("bad_key")


def test_save_returns_row_count(conn):
    records = [
        {
            "latitude": 37.1, "longitude": -120.5,
            "brightness": 320.0, "acq_date": "2026-06-28",
            "acq_time": "0130", "confidence": "nominal", "satellite": "N",
        }
    ]
    count = save(records, conn)
    assert count == 1


def test_save_persists_to_db(conn):
    records = [
        {
            "latitude": 37.1, "longitude": -120.5,
            "brightness": 320.0, "acq_date": "2026-06-28",
            "acq_time": "0130", "confidence": "nominal", "satellite": "N",
        }
    ]
    save(records, conn)
    row = conn.execute("SELECT * FROM fires_realtime").fetchone()
    assert row["latitude"] == pytest.approx(37.1)
    assert row["ingested_at"] is not None
