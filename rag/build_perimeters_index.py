"""Embed confirmed wildfire perimeter records into ChromaDB."""
import argparse
import sqlite3

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from rag.config import EMBED_MODEL, PERIMETERS_COLLECTION

_BATCH_SIZE = 100


def build_perimeters_index(db_path: str = "firerag.db", chroma_dir: str = "rag/chroma_db") -> int:
    ef = SentenceTransformerEmbeddingFunction(model_name=EMBED_MODEL)
    client = chromadb.PersistentClient(path=chroma_dir)

    try:
        client.delete_collection(PERIMETERS_COLLECTION)
    except Exception:
        pass
    collection = client.create_collection(PERIMETERS_COLLECTION, embedding_function=ef)

    conn = sqlite3.connect(db_path)
    rows = conn.execute("""
        SELECT fire_name,
               COALESCE(fire_year, CAST(substr(discovery_date,1,4) AS INTEGER)) AS yr,
               state, acres, agency, discovery_date, cause, latitude, longitude
        FROM fire_perimeters
        WHERE acres >= 100
        ORDER BY acres DESC
    """).fetchall()
    conn.close()

    docs, ids, metadatas = [], [], []
    for i, (name, year, state, acres, agency, date, cause, lat, lon) in enumerate(rows):
        parts = []
        name_str = name or "Unknown Fire"
        year_str = f" ({year})" if year else ""
        state_str = f", {state}" if state else ""
        parts.append(f"[CONFIRMED WILDFIRE] {name_str}{year_str}{state_str}.")
        parts.append(f"{acres:,.0f} acres burned.")
        if agency:
            parts.append(f"Agency: {agency}.")
        if date:
            parts.append(f"Discovered: {date}.")
        if cause:
            parts.append(f"Cause: {cause}.")
        if lat and lon:
            parts.append(f"Location: lat={lat:.2f}, lon={lon:.2f}.")
        doc = " ".join(parts)
        docs.append(doc)
        ids.append(f"perim-{i}")
        meta: dict = {}
        if state:
            meta["state"] = state
        if year:
            meta["year"] = int(year)
        metadatas.append(meta if meta else None)

    for start in range(0, len(docs), _BATCH_SIZE):
        batch_meta = metadatas[start:start + _BATCH_SIZE]
        collection.add(
            documents=docs[start:start + _BATCH_SIZE],
            ids=ids[start:start + _BATCH_SIZE],
            metadatas=batch_meta,
        )

    return len(docs)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="firerag.db")
    parser.add_argument("--chroma-dir", default="rag/chroma_db")
    args = parser.parse_args()
    n = build_perimeters_index(db_path=args.db, chroma_dir=args.chroma_dir)
    print(f"Indexed {n} confirmed wildfire perimeters.")


if __name__ == "__main__":
    main()
