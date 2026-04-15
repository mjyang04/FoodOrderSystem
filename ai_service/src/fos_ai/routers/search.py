"""GET /ai/search — semantic menu search."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from fos_ai.schemas import SearchResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/search", response_model=SearchResponse)
def search_menu(
    q: str = Query(..., min_length=1, max_length=200),
    limit: int = Query(10, ge=1, le=20),
) -> SearchResponse:
    """Semantic search over the menu corpus."""
    from fos_ai.deps import get_corpus, get_embedder, get_reranker, get_vector_store

    corpus = get_corpus()
    if not corpus.ready:
        raise HTTPException(status_code=503, detail="Menu corpus not loaded yet")

    embedder = get_embedder()
    vector_store = get_vector_store()
    reranker = get_reranker()

    from fos_ai.services.search import search

    results = search(
        query=q,
        corpus=corpus,
        embedder=embedder,
        limit=limit,
        vector_store=vector_store,
        reranker=reranker,
    )

    return SearchResponse(query=q, results=results, count=len(results))
