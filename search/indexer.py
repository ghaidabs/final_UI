import os
import threading
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct
from search.embeddings import embed
from dotenv import load_dotenv
from mock.db import get_all_clients, get_all_products

load_dotenv()

QDRANT_ENDPOINT = os.environ.get("QDRANT_ENDPOINT")
QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY")


_qdrant_client: QdrantClient | None = None
_ensured_collections: set[str] = set()
_indexed_once: set[tuple[str, int]] = set()
_index_lock = threading.Lock() 


def get_qdrant() -> QdrantClient:
    global _qdrant_client
    if _qdrant_client is None:
        if not QDRANT_ENDPOINT:
            raise RuntimeError(
                "QDRANT_ENDPOINT is not set. Add it to .env (see .env.example)."
            )
        _qdrant_client = QdrantClient(url=QDRANT_ENDPOINT, api_key=QDRANT_API_KEY)
    return _qdrant_client


def collection_name(entity_type: str, company_id: int) -> str:
    return f"{entity_type}s_{company_id}"


def _remote_point_count(name: str) -> int | None:
    try:
        return get_qdrant().get_collection(name).points_count
    except Exception:
        return None


def _ensure_collection(name: str, vector_size: int) -> None:
    if name in _ensured_collections:
        return
    client = get_qdrant()
    existing = {c.name for c in client.get_collections().collections}
    if name not in existing:
        client.create_collection(
            name, vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE)
        )
    _ensured_collections.add(name)


def index_entities(entity_type: str, company_id: int, entities: list[dict], text_fn) -> None:
    if not entities:
        return

    texts = [text_fn(e) for e in entities]
    vectors = embed(texts)
    name = collection_name(entity_type, company_id)

    _ensure_collection(name, len(vectors[0]))
    get_qdrant().upsert(
        collection_name=name,
        points=[
            PointStruct(id=e["id"], vector=v, payload={"text": t})
            for e, t, v in zip(entities, texts, vectors)
        ],
    )


def _ensure_index(entity_type: str, company_id: int, fetch_entities, text_fn, force: bool) -> None:
    key = (entity_type, company_id)
    if key in _indexed_once and not force:
        return

    with _index_lock:
        if key in _indexed_once and not force:  # another concurrent thread may have just finished
            return

        entities = fetch_entities(company_id, page=1, size=10_000)["items"]
        name = collection_name(entity_type, company_id)

        if not force:
            remote_count = _remote_point_count(name)
            if remote_count is not None and remote_count == len(entities):
                # Already indexed from a previous run
                _ensured_collections.add(name)
                _indexed_once.add(key)
                return

        index_entities(entity_type, company_id, entities, text_fn)
        _indexed_once.add(key)


def ensure_client_index(company_id: int, force: bool = False) -> None:
    _ensure_index(
        "client", company_id, get_all_clients,
        lambda c: f"{c['first_name']} {c['last_name']}", force,
    )


def ensure_product_index(company_id: int, force: bool = False) -> None:
    _ensure_index(
        "product", company_id, get_all_products,
        lambda p: p["designation"], force,
    )