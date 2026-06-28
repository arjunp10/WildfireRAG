import logging
import sqlite3
from datetime import datetime, timezone

import requests

logger = logging.getLogger(__name__)

_WIND_DIR_MAP = {
    "N": 0.0, "NNE": 22.0, "NE": 45.0, "ENE": 67.0,
    "E": 90.0, "ESE": 112.0, "SE": 135.0, "SSE": 157.0,
    "S": 180.0, "SSW": 202.0, "SW": 225.0, "WSW": 247.0,
    "W": 270.0, "WNW": 292.0, "NW": 315.0, "NNW": 337.0,
}

# 25 fire-prone locations across CONUS (lat, lon)
FIRE_PRONE_LOCATIONS: list[tuple[float, float]] = [
    (34.0, -118.0),  # Los Angeles Basin, CA
    (37.5, -122.0),  # San Francisco Bay Area, CA
    (38.5, -121.5),  # Sacramento Valley, CA
    (40.5, -122.5),  # Northern CA (Shasta)
    (36.5, -119.0),  # San Joaquin Valley, CA
    (34.5, -117.0),  # Inland Empire, CA
    (33.5, -116.5),  # San Diego foothills, CA
    (45.5, -116.0),  # Northern ID
    (47.0, -114.0),  # Western MT
    (46.0, -120.0),  # Eastern WA
    (44.0, -121.0),  # Central OR
    (42.5, -122.5),  # Southern OR
    (39.5, -119.5),  # Northern NV
    (36.0, -115.0),  # Southern NV
    (35.0, -111.5),  # Northern AZ (Flagstaff)
    (33.5, -112.0),  # Phoenix area, AZ
    (35.5, -106.0),  # Northern NM
    (32.5, -107.0),  # Southern NM
    (39.0, -108.5),  # Western CO
    (37.0, -107.0),  # Southern CO
    (40.5, -111.5),  # Northern UT
    (37.5, -113.0),  # Southern UT
    (43.5, -110.5),  # Western WY
    (46.5, -108.5),  # Eastern MT
    (30.5, -98.5),   # Central TX (Hill Country)
]


def _parse_wind_speed(wind_speed_str: str) -> float:
    return float(wind_speed_str.split()[0])


def _parse_wind_dir(wind_dir_str: str) -> float:
    return _WIND_DIR_MAP.get(wind_dir_str, 0.0)


def fetch(locations: list[tuple[float, float]] | None = None) -> list[dict]:
    if locations is None:
        locations = FIRE_PRONE_LOCATIONS

    records = []
    for lat, lon in locations:
        try:
            points_url = f"https://api.weather.gov/points/{lat},{lon}"
            points_resp = requests.get(
                points_url,
                headers={"User-Agent": "FireRAG/1.0 arjunpol101@gmail.com"},
                timeout=15,
            )
            points_resp.raise_for_status()
            hourly_url = points_resp.json()["properties"]["forecastHourly"]

            hourly_resp = requests.get(
                hourly_url,
                headers={"User-Agent": "FireRAG/1.0 arjunpol101@gmail.com"},
                timeout=15,
            )
            hourly_resp.raise_for_status()
            period = hourly_resp.json()["properties"]["periods"][0]

            records.append({
                "latitude": lat,
                "longitude": lon,
                "temperature": float(period["temperature"]),
                "humidity": float(period["relativeHumidity"]["value"]),
                "wind_speed": _parse_wind_speed(period["windSpeed"]),
                "wind_dir": _parse_wind_dir(period["windDirection"]),
                "timestamp": period["startTime"],
            })
        except Exception as exc:
            logger.warning("NOAA: skipping (%.1f, %.1f) — %s", lat, lon, exc)

    return records


def save(records: list[dict], conn: sqlite3.Connection) -> int:
    ingested_at = datetime.now(timezone.utc).isoformat()
    conn.executemany(
        """
        INSERT INTO weather
            (latitude, longitude, temperature, humidity, wind_speed, wind_dir, timestamp, ingested_at)
        VALUES
            (:latitude, :longitude, :temperature, :humidity, :wind_speed, :wind_dir, :timestamp, :ingested_at)
        """,
        [{**r, "ingested_at": ingested_at} for r in records],
    )
    conn.commit()
    return len(records)
