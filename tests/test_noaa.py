import sqlite3
import pytest
from unittest.mock import patch, MagicMock
from data.db import init_db
from data.noaa import fetch, save, _parse_wind_speed, _parse_wind_dir

POINTS_RESPONSE = {
    "properties": {
        "forecastHourly": "https://api.weather.gov/gridpoints/MTR/90,105/forecast/hourly"
    }
}

HOURLY_RESPONSE = {
    "properties": {
        "periods": [
            {
                "startTime": "2026-06-28T01:00:00-07:00",
                "temperature": 85,
                "relativeHumidity": {"value": 20},
                "windSpeed": "15 mph",
                "windDirection": "SW",
            }
        ]
    }
}


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    init_db(c)
    yield c
    c.close()


def test_parse_wind_speed():
    assert _parse_wind_speed("15 mph") == pytest.approx(15.0)
    assert _parse_wind_speed("0 mph") == pytest.approx(0.0)


def test_parse_wind_dir():
    assert _parse_wind_dir("N") == pytest.approx(0.0)
    assert _parse_wind_dir("SW") == pytest.approx(225.0)
    assert _parse_wind_dir("E") == pytest.approx(90.0)


@patch("data.noaa.requests.get")
def test_fetch_returns_records(mock_get):
    def side_effect(url, **kwargs):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        if "/points/" in url and "gridpoints" not in url:
            resp.json.return_value = POINTS_RESPONSE
        else:
            resp.json.return_value = HOURLY_RESPONSE
        return resp

    mock_get.side_effect = side_effect

    records = fetch(locations=[(37.5, -122.0)])

    assert len(records) == 1
    assert records[0]["latitude"] == pytest.approx(37.5)
    assert records[0]["longitude"] == pytest.approx(-122.0)
    assert records[0]["temperature"] == pytest.approx(85.0)
    assert records[0]["humidity"] == pytest.approx(20.0)
    assert records[0]["wind_speed"] == pytest.approx(15.0)
    assert records[0]["wind_dir"] == pytest.approx(225.0)


@patch("data.noaa.requests.get")
def test_fetch_skips_failed_location(mock_get):
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = Exception("500")
    mock_get.return_value = mock_resp

    records = fetch(locations=[(37.5, -122.0), (36.0, -120.0)])
    assert records == []


def test_save_returns_row_count(conn):
    records = [{
        "latitude": 37.5, "longitude": -122.0,
        "temperature": 85.0, "humidity": 20.0,
        "wind_speed": 15.0, "wind_dir": 225.0,
        "timestamp": "2026-06-28T01:00:00-07:00",
    }]
    count = save(records, conn)
    assert count == 1


def test_save_persists_to_db(conn):
    records = [{
        "latitude": 37.5, "longitude": -122.0,
        "temperature": 85.0, "humidity": 20.0,
        "wind_speed": 15.0, "wind_dir": 225.0,
        "timestamp": "2026-06-28T01:00:00-07:00",
    }]
    save(records, conn)
    row = conn.execute("SELECT * FROM weather").fetchone()
    assert row["temperature"] == pytest.approx(85.0)
    assert row["ingested_at"] is not None
