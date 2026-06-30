import argparse
import os
import sqlite3
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv

load_dotenv()

_API_URL = "https://newsapi.org/v2/everything"

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS articles (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT NOT NULL,
    description  TEXT,
    url          TEXT NOT NULL UNIQUE,
    source       TEXT,
    published_at TEXT,
    fetched_at   TEXT
)
"""


def fetch_articles(db_path: str, api_key: str, hours: int = 48) -> int:
    from_dt = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    resp = requests.get(
        _API_URL,
        params={
            "qInTitle": 'wildfire OR "forest fire"',
            "language": "en",
            "sortBy": "publishedAt",
            "from": from_dt,
            "pageSize": 100,
        },
        headers={"X-Api-Key": api_key},
        timeout=15,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"News API HTTP {resp.status_code}")
    data = resp.json()
    if data.get("status") == "error":
        raise RuntimeError(f"News API error: {data.get('message', 'unknown')}")

    fetched_at = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(db_path)
    conn.execute(_CREATE_TABLE)

    count = 0
    for article in data.get("articles", []):
        title = (article.get("title") or "").strip()
        if not title or title == "[Removed]":
            continue
        cursor = conn.execute(
            """INSERT OR IGNORE INTO articles
               (title, description, url, source, published_at, fetched_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                title,
                article.get("description"),
                article.get("url", ""),
                (article.get("source") or {}).get("name"),
                article.get("publishedAt"),
                fetched_at,
            ),
        )
        count += cursor.rowcount

    conn.commit()
    conn.close()
    return count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="firerag.db")
    parser.add_argument("--hours", type=int, default=48)
    args = parser.parse_args()
    api_key = os.environ.get("NEWS_API_KEY", "")
    if not api_key:
        raise SystemExit("NEWS_API_KEY not set. Add it to .env.")
    n = fetch_articles(db_path=args.db, api_key=api_key, hours=args.hours)
    print(f"Fetched {n} new articles.")


if __name__ == "__main__":
    main()
