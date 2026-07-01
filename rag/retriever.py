import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from rag.config import COLLECTION_NAME, EMBED_MODEL, FIRMS_COLLECTION, NEWS_COLLECTION

_ef = SentenceTransformerEmbeddingFunction(model_name=EMBED_MODEL)
_clients: dict[str, chromadb.PersistentClient] = {}


def _get_client(chroma_dir: str) -> chromadb.PersistentClient:
    if chroma_dir not in _clients:
        _clients[chroma_dir] = chromadb.PersistentClient(path=chroma_dir)
    return _clients[chroma_dir]


def query_similar(question: str, chroma_dir: str, k: int = 5) -> list[str]:
    collection = _get_client(chroma_dir).get_collection(COLLECTION_NAME, embedding_function=_ef)
    results = collection.query(query_texts=[question], n_results=k)
    return results["documents"][0]


def query_news(question: str, chroma_dir: str, k: int = 2) -> list[str]:
    collection = _get_client(chroma_dir).get_collection(NEWS_COLLECTION, embedding_function=_ef)
    results = collection.query(query_texts=[question], n_results=k)
    return results["documents"][0]


def query_firms(question: str, chroma_dir: str, k: int = 3) -> list[str]:
    collection = _get_client(chroma_dir).get_collection(FIRMS_COLLECTION, embedding_function=_ef)
    results = collection.query(query_texts=[question], n_results=k)
    return results["documents"][0]
