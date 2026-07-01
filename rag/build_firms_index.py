import argparse
import sqlite3

import chromadb
import reverse_geocoder as rg
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from rag.config import EMBED_MODEL, FIRMS_COLLECTION

_BATCH_SIZE = 100


def build_firms_index(db_path: str = "firerag.db", chroma_dir: str = "rag/chroma_db") -> int:
    ef = SentenceTransformerEmbeddingFunction(model_name=EMBED_MODEL)
    client = chromadb.PersistentClient(path=chroma_dir)

    try:
        client.delete_collection(FIRMS_COLLECTION)
    except Exception:
        pass
    collection = client.create_collection(FIRMS_COLLECTION, embedding_function=ef)

    conn = sqlite3.connect(db_path)
    rows = conn.execute("""
        SELECT
            round(latitude  * 2) / 2 AS cell_lat,
            round(longitude * 2) / 2 AS cell_lon,
            COUNT(*)                  AS detection_count,
            AVG(brightness)           AS avg_brightness,
            MAX(acq_date || ' ' || acq_time) AS latest_detection,
            GROUP_CONCAT(DISTINCT confidence) AS confidences
        FROM fires_realtime
        GROUP BY cell_lat, cell_lon
        HAVING detection_count >= 1
    """).fetchall()
    conn.close()

    if not rows:
        return 0

    coords = [(float(r[0]), float(r[1])) for r in rows]
    geo = rg.search(coords, mode=1, verbose=False)

    docs, ids = [], []
    for i, (row, loc) in enumerate(zip(rows, geo)):
        cell_lat, cell_lon, count, avg_b, latest, confidences = row
        state = loc.get("admin1", "")
        city = loc.get("name", "")
        country = loc.get("cc", "")

        if country == "US" and state:
            location = f"{city}, {state}" if city else state
        else:
            location = f"lat={cell_lat}, lon={cell_lon}"

        conf_str = confidences or "unknown"
        doc = (
            f"[ACTIVE FIRE] {count} detection(s) near {location} "
            f"(lat={cell_lat}, lon={cell_lon}). "
            f"Latest detection: {latest} UTC. "
            f"Avg brightness: {avg_b:.1f} K. "
            f"Confidence: {conf_str}."
        )
        docs.append(doc)
        ids.append(f"firms-{i}")

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
    n = build_firms_index(db_path=args.db, chroma_dir=args.chroma_dir)
    print(f"Indexed {n} active fire clusters.")


if __name__ == "__main__":
    main()
