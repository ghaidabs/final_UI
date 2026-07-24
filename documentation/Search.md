# Semantic Search & Entity Resolution

## 1. Where Semantic Search Lives in the Pipeline

Semantic search is **not** part of the NLU or Dispatcher directly. It is a **fallback tier** inside the entity resolution cascade, invoked by `MockSaasClient.lookup_client()` and `MockSaasClient.lookup_product()` when faster methods fail.


```
User says "Ahmed"
        │
        ▼
┌──────────────────────────────────────────────────────────────────────┐
│  MockSaasClient.lookup_client("Ahmed")                               │
│                                                                      │
│  ① Exact substring match   (mock/db.py → search_clients_by_name)     │
│         │ found? → return immediately                                │
│         │ empty? ▼                                                   │
│  ② Fuzzy match             (search/fuzzy.py → find_fuzzy)            │
│         │ found? → return with _fuzzy_score                          │
│         │ empty? ▼                                                   │
│  ③ Semantic search         (search/ → ensure_index + find_similar)   │
│         │ found? → return with _fuzzy_score (from cosine score)      │
│         │ empty? → return []                                         │
└──────────────────────────────────────────────────────────────────────┘
```

The same three-tier cascade applies to **both clients and products**. The dispatcher then decides what to do based on the number and type of matches returned (see section 5).

---

## 2. Indexing — How Entities Get Into Qdrant

### 2.1 Files Involved

| File | Role |
|------|------|
| `search/embeddings.py` | Loads the sentence-transformer model and produces dense vectors |
| `search/indexer.py` | Creates Qdrant collections and upserts entity points |

### 2.2 Embedding Model

The system uses **`sentence-transformers/all-MiniLM-L6-v2`** — a lightweight model that produces 384-dimensional normalized vectors. The model is loaded lazily on first use and cached via `@lru_cache(maxsize=1)`.

Key points:
- Vectors are **L2-normalized** (`normalize_embeddings=True`), which means cosine similarity is equivalent to dot product.
- `embed_one(text)` is a convenience wrapper that embeds a single string.

### 2.3 Collection Naming

Each entity type + company combination gets its own Qdrant collection:

```
clients_{company_id}     e.g. clients_1, clients_2
products_{company_id}    e.g. products_1, products_2
```

This enforces **tenant isolation** — a search against `clients_1` can never return results from company 2.

### 2.4 Collection Provisioning (`_ensure_collection`)

Before upserting points, the indexer checks if the collection already exists in Qdrant:

1. Maintains an in-memory set `_ensured_collections` to avoid redundant API calls within the same process.
2. On first access, fetches the full list of remote collections via `client.get_collections()`.
3. If the collection doesn't exist, creates it with `VectorParams(size=384, distance=Distance.COSINE)`.
4. Adds the collection name to `_ensured_collections` so subsequent calls are no-ops.

### 2.5 Upserting Entities (`index_entities`)

- **Point ID** = the entity's database `id` (integer). This allows direct lookup via `get_client_by_id()` / `get_product_by_id()` after retrieval.
- **Payload** = `{"text": "Ahmed Ben Ali"}` — stored for debugging/inspection but not used during search.
- **`text_fn`** controls what text is embedded:
  - Clients: `lambda c: f"{c['first_name']} {c['last_name']}"` (full name)
  - Products: `lambda p: p["designation"]` (product name/designation)

### 2.6 Lazy Indexing Strategy (`_ensure_index`)

Indexing is **lazy** — it only happens when semantic search is actually needed, not at startup. The logic has three guards to avoid redundant work:

```
_ensure_index(entity_type, company_id, fetch_fn, text_fn, force)
        │
        ├─ Guard 1: (entity_type, company_id) in _indexed_once?
        │           → yes and not force → skip (already indexed this process)
        │
        ├─ Guard 2: thread lock (_index_lock)
        │           → double-check _indexed_once after acquiring lock
        │
        └─ Guard 3: remote point count == local entity count?
                    → yes and not force → mark as indexed, skip
                    → no → upsert all entities
```

**Detailed walkthrough:**

1. **In-memory flag (`_indexed_once`)**: A set of `(entity_type, company_id)` tuples. If the key is already present and `force=False`, the function returns immediately — no network calls at all.

2. **Thread lock (`_index_lock`)**: A `threading.Lock` protects against concurrent threads (e.g., the search warm-up thread and a request thread) both trying to index the same collection simultaneously. After acquiring the lock, it re-checks `_indexed_once` (double-checked locking pattern).

3. **Remote count check**: If this is the first time in this process, the indexer fetches the current point count from Qdrant (`_remote_point_count`). If the remote count matches the number of local entities, it assumes the collection is already up-to-date from a previous process run and skips re-indexing. This avoids re-embedding and re-upserting on every server restart.

4. **Full re-index**: If none of the above short-circuits, all entities are fetched via `fetch_entities(company_id, page=1, size=10_000)`, embedded, and upserted in one batch.

### 2.7 Background Warm-Up

At import time, `agent/main.py` spawns a **daemon thread** that pre-indexes all companies:

This means:
- The embedding model is downloaded/loaded in the background while the user is selecting their mock user.
- Qdrant collections are populated before the first voice command arrives.
- If warm-up fails (e.g., Qdrant is unreachable), a warning is logged but the REPL continues — the first semantic search lookup will just be slower (or fail gracefully).

### 2.8 `force` Parameter

Both `ensure_client_index` and `ensure_product_index` accept `force=False`. When `force=True`:
- The in-memory flag is ignored.
- The remote count check is skipped.
- All entities are re-embedded and upserted unconditionally.

This is useful when the underlying data has changed (e.g., a new client was added to the mock DB).

---

## 3. Retrieval — How Similarity Search Works

### 3.1 Files Involved

| File | Role |
|------|------|
| `search/retriever.py` | Embeds the query, searches Qdrant, filters by similarity floor |

### 3.2 Search Flow

**Step by step:**

1. **Embed the query**: The spoken entity name (e.g., `"Ahmet"`) is embedded into a 384-dim vector using the same `all-MiniLM-L6-v2` model.
2. **Search Qdrant**: `query_points()` runs a nearest-neighbor search against the tenant-scoped collection, returning the top-K closest points by cosine distance.
3. **Similarity floor filtering**: Any result with `score < 0.55` is discarded. This prevents low-quality matches from polluting downstream logic.
4. **Return format**: Each hit is returned as `{"id": <entity_db_id>, "text": <indexed_text>, "score": <cosine_similarity>}`.

### 3.3 Result Caching

`find_similar` is decorated with `@lru_cache(maxsize=256)`. This means:
- Repeated queries for the same `(entity_type, company_id, query_text, top_k)` tuple are served from memory instantly.
- The cache is **not invalidated** when new entities are indexed — this is acceptable for the current MVP since the entity catalog doesn't change mid-session.

### 3.4 Similarity Floor: `0.55`

The threshold of `0.55` was chosen empirically to balance recall vs. precision for spoken entity names in French/English. Scores below this are considered noise — the model isn't confident enough that the spoken name corresponds to the indexed entity.

---

## 4. Fuzzy Matching — String-Level Entity Search

### 4.1 Files Involved

| File | Role |
|------|------|
| `search/fuzzy.py` | RapidFuzz-based entity resolution for client names and product names |

### 4.2 How It Works

- Uses `WRatio` scorer from `rapidfuzz` — a weighted combination of multiple string similarity metrics.
- **Threshold**: 75% minimum score (configurable via `FUZZY_FLOOR`).
- Returns top-K matches with their `_fuzzy_score` attached (score / 100), so the dispatcher can decide whether to auto-resolve or ask for confirmation.
- Operates entirely in-memory — no external services or embeddings required.

---

## 5. How MockSaasClient Orchestrates the Cascade

The three-tier cascade is implemented identically for clients and products in `api/mock_saas_client.py`:

### 5.1 Client Lookup

**Important details:**

| Aspect | Tier 1 (Exact) | Tier 2 (Fuzzy) | Tier 3 (Semantic) |
|--------|---------------|----------------|-----------------|
| Method | `str in str` substring | `rapidfuzz.fuzz.WRatio` | `sentence-transformers` + Qdrant cosine |
| Threshold | N/A | 75% | 0.55 |
| Speed | Instant (in-memory) | ~ms (in-memory) | ~100ms+ (embedding + network) |
| Returns `_fuzzy_score`? | No | Yes (score / 100) | Yes (cosine score) |
| Threading | Sync | Sync | `asyncio.to_thread` (non-blocking) |

- **`_fuzzy_score` marker**: Results from tier 2 and tier 3 carry a `_fuzzy_score` key. This is how the dispatcher knows the match is approximate and should trigger a **disambiguation prompt** rather than being silently accepted.
- **`asyncio.to_thread`**: Semantic search calls (embedding + Qdrant search) are CPU/IO-bound, so they're offloaded to a thread to avoid blocking the async event loop.
- **Hydration from DB**: Semantic search returns only `{"id", "text", "score"}`. The client re-fetches the full entity record via `get_client_by_id()` to ensure the returned dict has all fields the dispatcher expects. If the entity was deleted between indexing and retrieval, the walrus operator `(c := get_client_by_id(...))` filters it out.

### 5.2 Product Lookup

Identical cascade structure, using `search_products_by_name`, `find_fuzzy` against `designation`, and `ensure_product_index` / `find_similar("product", ...)`.

---

## 6. How the Dispatcher Uses Resolution Results

The dispatcher doesn't call the search layer directly — it calls `saas.lookup_client()` or `saas.lookup_product()` and reacts to the **shape** of the returned list:

| Result | `_fuzzy_score` present? | Dispatcher action |
|--------|------------------------|-------------------|
| 1 match, no `_fuzzy_score` | No | **Auto-accept** — exact match, proceed silently |
| 1 match, with `_fuzzy_score` | Yes | **Disambiguation prompt** — stash in `session.pending_disambiguation`, ask user *"Did you mean X?"* |
| Multiple matches | Either | **Multiple candidates prompt** — list all names, ask user to pick |
| 0 matches | N/A | **Not found** — return error or ask user to clarify |

### 6.1 Disambiguation Flow (Single Fuzzy/Semantic Match)

When exactly one candidate is returned with a `_fuzzy_score`:

1. The candidate and the original intent are stashed in `session.pending_disambiguation`:
   ```python
   session.pending_disambiguation = {
       "kind": "client",          # or "product"
       "candidate": matches[0],
       "resume_intent": "create_invoice",
       "original_intent": intent,
   }
   ```
2. The user is asked: *"Did you mean Ahmed Ben Ali? Please confirm."*
3. On **confirm** → `_resolve_disambiguation()` accepts the candidate and resumes the original flow (create invoice, add line item, or lookup client).
4. On **cancel** → the session enters `awaiting_field="client_name"` (or `"product_name"`) and asks the user to re-state the name.

### 6.2 Product Disambiguation During `create_invoice`

When creating an invoice with multiple articles, disambiguation can pause **mid-list**:

1. `_build_line_items_or_pause()` iterates through articles in order.
2. On the first ambiguous product, it stashes:
   - Already-resolved line items (`resolved_line_items`)
   - The paused article index (`article_index`)
   - The resolved client (`resolved_client`)
3. After the user confirms/rejects, `_resolve_disambiguation()` resumes from where it left off, continuing to resolve the remaining articles.

---

## 7. Data Flow Summary

```
                    ┌─────────────────────────────────────────────┐
                    │             Startup (daemon thread)         │
                    │                                             │
                    │  1. Load sentence-transformer model         │
                    │  2. For each company:                       │
                    │     a. Fetch all clients from mock DB       │
                    │     b. Check Qdrant point count             │
                    │     c. If mismatch → embed + upsert         │
                    │     d. Repeat for products                  │
                    └─────────────────────────────────────────────┘

                    ┌─────────────────────────────────────────────┐
                    │           Runtime (per user utterance)      │
                    │                                             │
                    │  STT → NLU extracts intent + entity names   │
                    │        ↓                                    │
                    │  Dispatcher calls saas.lookup_client(name)  │
                    │        ↓                                    │
                    │  MockSaasClient runs cascade:               │
                    │    ① Exact → ② Fuzzy → ③ Semantic           │
                    │        ↓                                    │
                    │  Dispatcher inspects matches:               │
                    │    • exact hit → auto-accept                │
                    │    • fuzzy/semantic hit → disambig. prompt   │
                    │    • no hit → error / clarification         │
                    │        ↓                                    │
                    │  Response → Templates → TTS → User          │
                    └─────────────────────────────────────────────┘
```

---

## 8. Configuration Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `QDRANT_ENDPOINT` | *(required)* | Qdrant server URL |
| `QDRANT_API_KEY` | `None` | Qdrant API key (optional for local instances) |
| `HF_TOKEN` | `None` | Hugging Face token (only needed if the embedding model is gated) |

| Constant | File | Value | Description |
|----------|------|-------|-------------|
| `_MODEL_NAME` | `search/embeddings.py` | `sentence-transformers/all-MiniLM-L6-v2` | Embedding model |
| `SIMILARITY_FLOOR` | `search/retriever.py` | `0.55` | Minimum cosine similarity to accept a semantic match |
| `FUZZY_FLOOR` | `search/fuzzy.py` | `75` | Minimum RapidFuzz WRatio score (out of 100) |
| `Distance` | `search/indexer.py` | `COSINE` | Qdrant vector distance metric |
