import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from rag.config import COLLECTION_NAME, EMBED_MODEL

_ef = SentenceTransformerEmbeddingFunction(model_name=EMBED_MODEL)
_clients: dict[str, chromadb.PersistentClient] = {}


def _get_collection(chroma_dir: str):
    if chroma_dir not in _clients:
        _clients[chroma_dir] = chromadb.PersistentClient(path=chroma_dir)
    return _clients[chroma_dir].get_collection(COLLECTION_NAME, embedding_function=_ef)


def query_similar(question: str, chroma_dir: str, k: int = 5) -> list[str]:
    collection = _get_collection(chroma_dir)
    results = collection.query(query_texts=[question], n_results=k)
    return results["documents"][0]
