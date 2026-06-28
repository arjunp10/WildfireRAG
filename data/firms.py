import csv
import io
import logging
import sqlite3
from datetime import datetime, timezone

import requests

logger = logging.getLogger(__name__)

_BASE_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"


def fetch(
    map_key: str,
    area: str = "-130,24,-65,50",
    day_range: int = 1,
) -> list[dict]:
    url = f"{_BASE_URL}/{map_key}/VIIRS_SNPP_NRT/{area}/{day_range}"
    logger.info("FIRMS: fetching from %s", url)
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()

    reader = csv.DictReader(io.StringIO(resp.text))
    records = []
    for row in reader:
        records.append({
            "latitude": float(row["latitude"]),
            "longitude": float(row["longitude"]),
            "brightness": float(row["bright_ti4"]),
            "acq_date": row["acq_date"],
            "acq_time": row["acq_time"],
            "confidence": row["confidence"],
            "satellite": row["satellite"],
        })
    return records


def save(records: list[dict], conn: sqlite3.Connection) -> int:
    ingested_at = datetime.now(timezone.utc).isoformat()
    conn.executemany(
        """
        INSERT INTO fires_realtime
            (latitude, longitude, brightness, acq_date, acq_time, confidence, satellite, ingested_at)
        VALUES
            (:latitude, :longitude, :brightness, :acq_date, :acq_time, :confidence, :satellite, :ingested_at)
        """,
        [{**r, "ingested_at": ingested_at} for r in records],
    )
    conn.commit()
    return len(records)
