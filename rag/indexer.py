import os
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct
from rag.embeddings import embed
from dotenv import load_dotenv

load_dotenv()

QDRANT_ENDPOINT = os.environ.get("QDRANT_ENDPOINT")
QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY")


_qdrant_client: QdrantClient | None = None
_ensured_collections: set[str] = set()


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


def ensure_client_index(company_id: int) -> None:
    from mock.db import get_all_clients
    clients = get_all_clients(company_id, page=1, size=10_000)["items"]
    index_entities("client", company_id, clients, lambda c: f"{c['first_name']} {c['last_name']}")


def ensure_product_index(company_id: int) -> None:
    from mock.db import get_all_products
    products = get_all_products(company_id, page=1, size=10_000)["items"]
    index_entities("product", company_id, products, lambda p: p["designation"])