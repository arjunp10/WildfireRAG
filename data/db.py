import sqlite3
import logging

logger = logging.getLogger(__name__)

_DDL = """
CREATE TABLE IF NOT EXISTS fires_realtime (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    latitude    REAL,
    longitude   REAL,
    brightness  REAL,
    acq_date    TEXT,
    acq_time    TEXT,
    confidence  TEXT,
    satellite   TEXT,
    ingested_at TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS fires_realtime_dedup
    ON fires_realtime (latitude, longitude, acq_date, acq_time);

CREATE TABLE IF NOT EXISTS weather (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    latitude    REAL,
    longitude   REAL,
    temperature REAL,
    humidity    REAL,
    wind_speed  REAL,
    wind_dir    REAL,
    timestamp   TEXT,
    ingested_at TEXT
);

CREATE TABLE IF NOT EXISTS fires_historical (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    latitude    REAL,
    longitude   REAL,
    brightness  REAL,
    frp         REAL,
    acq_date    TEXT,
    acq_time    TEXT,
    confidence  TEXT,
    satellite   TEXT,
    ingested_at TEXT
);

CREATE TABLE IF NOT EXISTS fires_predictions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    latitude         REAL,
    longitude        REAL,
    fire_probability REAL,
    prediction_date  TEXT,
    model_version    TEXT,
    ingested_at      TEXT
);

CREATE TABLE IF NOT EXISTS articles (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT NOT NULL,
    description  TEXT,
    url          TEXT NOT NULL UNIQUE,
    source       TEXT,
    published_at TEXT,
    fetched_at   TEXT
);
"""


def get_connection(db_path: str = "firerag.db") -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(_DDL)
    conn.commit()
    logger.info("Database schema initialized")
