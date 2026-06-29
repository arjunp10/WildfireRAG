import logging
import sqlite3 as _sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_PATH = Path(__file__).parent / "data.sqlite"
_QUERY = """
    SELECT
        LATITUDE,
        LONGITUDE,
        FIRE_SIZE,
        FIRE_YEAR,
        DISCOVERY_DOY,
        NWCG_GENERAL_CAUSE
    FROM Fires
    WHERE LATITUDE IS NOT NULL
      AND LONGITUDE IS NOT NULL
"""


def _doy_to_date(year: int, doy: int) -> str:
    dt = datetime(int(year), 1, 1) + timedelta(days=int(doy) - 1)
    return dt.strftime("%Y-%m-%d")


def fetch(file_path: str | Path | None = None) -> list[dict]:
    path = Path(file_path) if file_path else _DEFAULT_PATH
    if not path.exists():
        raise FileNotFoundError(
            f"Kaggle wildfire dataset not found at {path}. "
            "Download it from https://www.kaggle.com/datasets/rtatman/188-million-us-wildfires "
            "and save as data/data.sqlite"
        )

    logger.info("Historical: reading from %s", path)
    src = _sqlite3.connect(path)
    src.row_factory = _sqlite3.Row
    rows = src.execute(_QUERY).fetchall()
    src.close()
    logger.info("Historical: loaded %d raw records", len(rows))

    records = []
    for row in rows:
        try:
            records.append({
                "latitude": float(row["LATITUDE"]),
                "longitude": float(row["LONGITUDE"]),
                "brightness": 0.0,
                "frp": float(row["FIRE_SIZE"]) if row["FIRE_SIZE"] else 0.0,
                "acq_date": _doy_to_date(row["FIRE_YEAR"], row["DISCOVERY_DOY"]),
                "acq_time": "0000",
                "confidence": "high",
                "satellite": row["NWCG_GENERAL_CAUSE"] or "Unknown",
            })
        except Exception as exc:
            logger.warning("Historical: skipping malformed row — %s", exc)

    return records


def save(records: list[dict], conn: _sqlite3.Connection) -> int:
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
