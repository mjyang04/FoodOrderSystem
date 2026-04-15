"""GET /ai/search — semantic menu search.

The business-layer cache lives at the router layer rather than inside
``services.search.search`` because the underlying function takes a corpus
object that changes when the menu is re-ingested. Caching by ``(query,
limit, corpus_signature)`` at the router lets us invalidate automatically
whenever the corpus is rebuilt (its ``size`` flips), while still covering
the hot path of repeated ``/ai/search?q=...`` requests.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from fos_ai.obs import cached
from fos_ai.schemas import SearchResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])


@cached(ttl_seconds=60.0, maxsize=512, namespace="search.search")
def _cached_search(
    q: str,
    limit: int,
    corpus_signature: tuple[int, ...],
) -> list[dict]:
    """Cache key = (query, limit, corpus_signature).

    ``corpus_signature`` is (size, first_id, last_id) — a cheap fingerprint
    that changes whenever the menu is ingested again.
    """
    from fos_ai.deps import get_corpus, get_embedder, get_reranker, get_vector_store
    from fos_ai.services.search import search

    corpus = get_corpus()
    embedder = get_embedder()
    vector_store = get_vector_store()
    reranker = get_reranker()

    results = search(
        query=q,
        corpus=corpus,
        embedder=embedder,
        limit=limit,
        vector_store=vector_store,
        reranker=reranker,
    )
    return [r.model_dump() for r in results]


def _corpus_signature(corpus) -> tuple[int, ...]:
    if not corpus.ready or not corpus.items:
        return (0,)
    first = corpus.items[0].food_id
    last = corpus.items[-1].food_id
    return (corpus.size, first, last)


@router.get("/search", response_model=SearchResponse)
def search_menu(
    q: str = Query(..., min_length=1, max_length=200),
    limit: int = Query(10, ge=1, le=20),
) -> SearchResponse:
    """Semantic search over the menu corpus."""
    from fos_ai.deps import get_corpus
    from fos_ai.schemas import SearchResult

    corpus = get_corpus()
    if not corpus.ready:
        raise HTTPException(status_code=503, detail="Menu corpus not loaded yet")

    sig = _corpus_signature(corpus)
    payload = _cached_search(q, limit, sig)
    results = [SearchResult(**r) for r in payload]
    return SearchResponse(query=q, results=results, count=len(results))
