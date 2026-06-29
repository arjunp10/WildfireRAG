import argparse
import sqlite3

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from rag.config import COLLECTION_NAME, EMBED_MODEL

_MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

_BATCH_SIZE = 100


def build_index(db_path: str = "firerag.db", chroma_dir: str = "rag/chroma_db") -> int:
    ef = SentenceTransformerEmbeddingFunction(model_name=EMBED_MODEL)
    client = chromadb.PersistentClient(path=chroma_dir)

    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    collection = client.create_collection(COLLECTION_NAME, embedding_function=ef)

    conn = sqlite3.connect(db_path)
    rows = conn.execute("""
        SELECT
            round(latitude  * 2) / 2 AS cell_lat,
            round(longitude * 2) / 2 AS cell_lon,
            CAST(strftime('%m', acq_date) AS INTEGER) AS month,
            COUNT(*)                  AS fire_count,
            AVG(brightness)           AS avg_brightness,
            AVG(frp)                  AS avg_frp,
            MIN(strftime('%Y', acq_date)) AS min_year,
            MAX(strftime('%Y', acq_date)) AS max_year
        FROM fires_historical
        GROUP BY cell_lat, cell_lon, month
    """).fetchall()
    conn.close()

    docs, ids = [], []
    for i, (cell_lat, cell_lon, month, fire_count, avg_b, avg_frp, min_yr, max_yr) in enumerate(rows):
        month_name = _MONTHS[int(month) - 1]
        doc = (
            f"Grid cell (lat={cell_lat}, lon={cell_lon}), "
            f"Month={month_name} (month {int(month)}): {fire_count} fires ({min_yr}-{max_yr}). "
            f"Avg brightness: {avg_b:.1f}. Avg FRP: {avg_frp:.1f} MW."
        )
        docs.append(doc)
        ids.append(f"region-{i}")

    for start in range(0, len(docs), _BATCH_SIZE):
        collection.add(
            documents=docs[start:start + _BATCH_SIZE],
            ids=ids[start:start + _BATCH_SIZE],
        )

    return len(docs)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="firerag.db")
    parser.add_argument("--chroma-dir", default="rag/chroma_db")
    args = parser.parse_args()
    n = build_index(db_path=args.db, chroma_dir=args.chroma_dir)
    print(f"Indexed {n} region-month documents.")


if __name__ == "__main__":
    main()
