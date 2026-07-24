from functools import lru_cache
from dotenv import load_dotenv

load_dotenv()

_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

@lru_cache(maxsize=1)
def _model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(_MODEL_NAME)

def embed(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    return _model().encode(texts, normalize_embeddings=True).tolist()

def embed_one(text: str) -> list[float]:
    return embed([text])[0]