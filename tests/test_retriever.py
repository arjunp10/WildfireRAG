import pytest
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from rag.retriever import query_similar


@pytest.fixture
def chroma_dir(tmp_path):
    ef = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    client = chromadb.PersistentClient(path=str(tmp_path / "chroma"))
    col = client.create_collection("wildfire-regions", embedding_function=ef)
    col.add(
        documents=[
            "Grid cell (lat=37.0, lon=-120.0), Month=July (month 7): 100 fires (2005-2020). Avg brightness: 320.0. Avg FRP: 35.0 MW.",
            "Grid cell (lat=35.0, lon=-119.0), Month=August (month 8): 50 fires (2005-2020). Avg brightness: 310.0. Avg FRP: 25.0 MW.",
            "Grid cell (lat=34.0, lon=-118.0), Month=September (month 9): 75 fires (2005-2020). Avg brightness: 315.0. Avg FRP: 30.0 MW.",
            "Grid cell (lat=36.0, lon=-121.0), Month=October (month 10): 30 fires (2005-2020). Avg brightness: 305.0. Avg FRP: 20.0 MW.",
            "Grid cell (lat=38.0, lon=-122.0), Month=November (month 11): 20 fires (2005-2020). Avg brightness: 300.0. Avg FRP: 15.0 MW.",
            "Grid cell (lat=39.0, lon=-123.0), Month=December (month 12): 10 fires (2005-2020). Avg brightness: 295.0. Avg FRP: 10.0 MW.",
        ],
        ids=["r0", "r1", "r2", "r3", "r4", "r5"],
    )
    return str(tmp_path / "chroma")


def test_returns_list(chroma_dir):
    result = query_similar("fire risk in California", chroma_dir, k=3)
    assert isinstance(result, list)


def test_returns_k_results(chroma_dir):
    result = query_similar("fire patterns in summer", chroma_dir, k=3)
    assert len(result) == 3


def test_results_are_strings(chroma_dir):
    result = query_similar("wildfire history", chroma_dir, k=2)
    assert all(isinstance(r, str) and len(r) > 0 for r in result)
