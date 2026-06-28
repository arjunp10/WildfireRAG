import csv
import io
import logging
import math
import sqlite3
from datetime import datetime, timedelta, timezone

import requests

logger = logging.getLogger(__name__)

_BASE_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
_CHUNK_DAYS = 10


def fetch(
    map_key: str,
    area: str = "-130,24,-65,50",
    date_range_days: int = 365,
) -> list[dict]:
    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=date_range_days)

    num_chunks = math.ceil(date_range_days / _CHUNK_DAYS)
    all_records: list[dict] = []

    for i in range(num_chunks):
        chunk_start = start_date + timedelta(days=i * _CHUNK_DAYS)
        url = f"{_BASE_URL}/{map_key}/VIIRS_SNPP_SP/{area}/{_CHUNK_DAYS}/{chunk_start}"
        logger.info("FIRMS historical: fetching chunk %d/%d (%s)", i + 1, num_chunks, chunk_start)

        resp = requests.get(url, timeout=60)
        resp.raise_for_status()

        reader = csv.DictReader(io.StringIO(resp.text))
        for row in reader:
            all_records.append({
                "latitude": float(row["latitude"]),
                "longitude": float(row["longitude"]),
                "brightness": float(row["bright_ti4"]),
                "frp": float(row["frp"]) if row["frp"] else 0.0,
                "acq_date": row["acq_date"],
                "acq_time": row["acq_time"],
                "confidence": row["confidence"],
                "satellite": row["satellite"],
            })

    return all_records


def save(records: list[dict], conn: sqlite3.Connection) -> int:
    ingested_at = datetime.now(timezone.utc).isoformat()
    conn.executemany(
        """
        INSERT INTO fires_historical
            (latitude, longitude, brightness, frp, acq_date, acq_time, confidence, satellite, ingested_at)
        VALUES
            (:latitude, :longitude, :brightness, :frp, :acq_date, :acq_time, :confidence, :satellite, :ingested_at)
        """,
        [{**r, "ingested_at": ingested_at} for r in records],
    )
    conn.commit()
    return len(records)
