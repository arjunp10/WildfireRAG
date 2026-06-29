import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

_EMBED_MODEL = "all-MiniLM-L6-v2"
_COLLECTION = "wildfire-regions"


def query_similar(question: str, chroma_dir: str, k: int = 5) -> list[str]:
    ef = SentenceTransformerEmbeddingFunction(model_name=_EMBED_MODEL)
    client = chromadb.PersistentClient(path=chroma_dir)
    collection = client.get_collection(_COLLECTION, embedding_function=ef)
    results = collection.query(query_texts=[question], n_results=k)
    return results["documents"][0]
