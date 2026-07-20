import logging
import threading
from rag.embeddings import _model
from rag.indexer import ensure_client_index, ensure_product_index
from mock.db import _companies

logger = logging.getLogger(__name__)

def warm_up_rag() -> None:
    try:
        _model()
        for company in _companies.values():
            ensure_client_index(company["id"])
            ensure_product_index(company["id"])
    except Exception:
        logger.exception("RAG warm-up failed; first RAG fallback will be slower.")

def start_warmup_thread() -> None:
    threading.Thread(target=warm_up_rag, daemon=True, name="rag-warmup").start()