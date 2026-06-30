import argparse
import sqlite3

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from rag.config import EMBED_MODEL, NEWS_COLLECTION

_BATCH_SIZE = 100


def build_news_index(db_path: str = "firerag.db", chroma_dir: str = "rag/chroma_db") -> int:
    ef = SentenceTransformerEmbeddingFunction(model_name=EMBED_MODEL)
    client = chromadb.PersistentClient(path=chroma_dir)

    try:
        client.delete_collection(NEWS_COLLECTION)
    except Exception:
        pass
    collection = client.create_collection(NEWS_COLLECTION, embedding_function=ef)

    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT title, description, url, source, published_at FROM articles"
    ).fetchall()
    conn.close()

    docs, ids = [], []
    for i, (title, description, url, source, published_at) in enumerate(rows):
        source_label = source or "Unknown"
        desc_part = f" {description}" if description else ""
        date_part = f" Published: {published_at}." if published_at else ""
        doc = f"[{source_label}] {title}.{desc_part}{date_part}"
        docs.append(doc)
        ids.append(f"news-{i}")

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
    n = build_news_index(db_path=args.db, chroma_dir=args.chroma_dir)
    print(f"Indexed {n} news articles.")


if __name__ == "__main__":
    main()
