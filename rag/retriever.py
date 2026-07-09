import rag.indexer as indexer

SIMILARITY_FLOOR = 0.55


def find_similar(entity_type: str, company_id: int, query_text: str, top_k: int = 3) -> list[dict]:
    from rag.embeddings import embed_one
    query_vec = embed_one(query_text)

    response = indexer.get_qdrant().query_points(
        collection_name=indexer.collection_name(entity_type, company_id),
        query=query_vec,
        limit=top_k,
    )
    hits = response.points 

    results = [{"id": h.id, "text": h.payload.get("text"), "score": h.score} for h in hits]

    return [r for r in results if r["score"] >= SIMILARITY_FLOOR]