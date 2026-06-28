import logging
import os
import sys
import time

from dotenv import load_dotenv
from tabulate import tabulate

from data import firms, historical, noaa
from data.db import get_connection, init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)-20s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ingest")

load_dotenv()


def _require_env(key: str, signup_url: str) -> str:
    value = os.getenv(key)
    if not value:
        logger.error(
            "Missing required env var %s. Get your free key at: %s",
            key,
            signup_url,
        )
        sys.exit(1)
    return value


def _print_sample(records: list[dict], label: str) -> None:
    if not records:
        logger.info("%s: no records to display", label)
        return
    sample = records[:3]
    print(f"\n--- {label} sample (first 3 rows) ---")
    print(tabulate(sample, headers="keys", tablefmt="rounded_outline"))
    print()


def _run_source(label: str, fetch_fn, save_fn) -> None:
    try:
        logger.info("%s: starting fetch", label)
        t0 = time.time()
        records = fetch_fn()
        elapsed = time.time() - t0
        logger.info("%s: fetched %d records in %.2fs", label, len(records), elapsed)

        count = save_fn(records)
        logger.info("%s: saved %d rows to database", label, count)
        _print_sample(records, label)
    except Exception as exc:
        logger.error("%s: failed — %s", label, exc)


def main() -> None:
    firms_key = _require_env(
        "FIRMS_MAP_KEY",
        "https://firms.modaps.eosdis.nasa.gov/api/",
    )

    conn = get_connection()
    init_db(conn)

    _run_source(
        "FIRMS real-time",
        lambda: firms.fetch(firms_key),
        lambda records: firms.save(records, conn),
    )

    _run_source(
        "NOAA weather",
        lambda: noaa.fetch(),
        lambda records: noaa.save(records, conn),
    )

    _run_source(
        "Kaggle historical",
        lambda: historical.fetch(),
        lambda records: historical.save(records, conn),
    )

    conn.close()
    logger.info("Ingest complete.")


if __name__ == "__main__":
    main()
