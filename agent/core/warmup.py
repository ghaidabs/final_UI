import logging
import threading
from search.embeddings import _model
from search.indexer import ensure_client_index, ensure_product_index
from mock.db import _companies

logger = logging.getLogger(__name__)

def warm_up_search() -> None:
    try:
        _model()
        for company in _companies.values():
            ensure_client_index(company["id"])
            ensure_product_index(company["id"])
    except Exception:
        logger.exception("Search warm-up failed; first semantic search fallback will be slower.")

def start_warmup_thread() -> None:
    threading.Thread(target=warm_up_search, daemon=True, name="search-warmup").start()