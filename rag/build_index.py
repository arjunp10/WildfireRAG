import argparse
import sqlite3

import chromadb
import reverse_geocoder as rg
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from rag.config import COLLECTION_NAME, EMBED_MODEL
from rag.geo import ADMIN1_TO_ABBREV

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

    coords = [(float(r[0]), float(r[1])) for r in rows]
    geo = rg.search(coords, mode=1, verbose=False)

    docs, ids, metadatas = [], [], []
    for i, (row, loc) in enumerate(zip(rows, geo)):
        cell_lat, cell_lon, month, fire_count, avg_b, avg_frp, min_yr, max_yr = row
        month_name = _MONTHS[int(month) - 1]
        admin1 = loc.get("admin1", "")
        country = loc.get("cc", "")
        location_label = f", {admin1}" if admin1 and country == "US" else (f", {country}" if country else "")
        doc = (
            f"Grid cell (lat={cell_lat}, lon={cell_lon}){location_label}, "
            f"Month={month_name} (month {int(month)}): {fire_count} fires ({min_yr}-{max_yr}). "
            f"Avg brightness: {avg_b:.1f}. Avg FRP: {avg_frp:.1f} MW."
        )
        docs.append(doc)
        ids.append(f"region-{i}")
        abbrev = ADMIN1_TO_ABBREV.get(admin1) if country == "US" else None
        metadatas.append({"state": abbrev} if abbrev else None)

    for start in range(0, len(docs), _BATCH_SIZE):
        collection.add(
            documents=docs[start:start + _BATCH_SIZE],
            ids=ids[start:start + _BATCH_SIZE],
            metadatas=metadatas[start:start + _BATCH_SIZE],
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
