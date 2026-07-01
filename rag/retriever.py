import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from rag.config import COLLECTION_NAME, EMBED_MODEL, FIRMS_COLLECTION, NEWS_COLLECTION, PERIMETERS_COLLECTION

_ef = SentenceTransformerEmbeddingFunction(model_name=EMBED_MODEL)
_clients: dict[str, chromadb.PersistentClient] = {}


def _get_client(chroma_dir: str) -> chromadb.PersistentClient:
    if chroma_dir not in _clients:
        _clients[chroma_dir] = chromadb.PersistentClient(path=chroma_dir)
    return _clients[chroma_dir]


def _query(collection, question: str, k: int, where: dict | None) -> list[str]:
    """Query with optional where filter. Falls back to unfiltered if filter yields no results."""
    if where:
        try:
            results = collection.query(query_texts=[question], n_results=k, where=where)
            docs = results["documents"][0]
            if docs:
                return docs
        except Exception:
            pass
    results = collection.query(query_texts=[question], n_results=k)
    return results["documents"][0]


def query_similar(question: str, chroma_dir: str, k: int = 5, where: dict | None = None) -> list[str]:
    collection = _get_client(chroma_dir).get_collection(COLLECTION_NAME, embedding_function=_ef)
    return _query(collection, question, k, where)


def query_news(question: str, chroma_dir: str, k: int = 2, where: dict | None = None) -> list[str]:
    collection = _get_client(chroma_dir).get_collection(NEWS_COLLECTION, embedding_function=_ef)
    return _query(collection, question, k, where)


def query_firms(question: str, chroma_dir: str, k: int = 3, where: dict | None = None) -> list[str]:
    collection = _get_client(chroma_dir).get_collection(FIRMS_COLLECTION, embedding_function=_ef)
    return _query(collection, question, k, where)


def query_perimeters(question: str, chroma_dir: str, k: int = 3, where: dict | None = None) -> list[str]:
    collection = _get_client(chroma_dir).get_collection(PERIMETERS_COLLECTION, embedding_function=_ef)
    return _query(collection, question, k, where)
