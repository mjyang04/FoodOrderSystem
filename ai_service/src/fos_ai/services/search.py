"""Menu search — delegates to ``hybrid_search`` when a VectorStore is
available, otherwise falls back to the original cosine top-k over the
in-memory corpus. Public signature is kept stable so the FastAPI router
does not need to change.
"""

from __future__ import annotations

import logging

import torch

from fos_ai.ml.corpus import MenuCorpus
from fos_ai.ml.embedding import Embedder
from fos_ai.ml.reranker import Reranker
from fos_ai.ml.vector_store import VectorStore
from fos_ai.schemas import SearchResult

logger = logging.getLogger(__name__)

_MAX_LIMIT = 20
_DEFAULT_LIMIT = 10


def search(
    query: str,
    corpus: MenuCorpus,
    embedder: Embedder,
    limit: int = _DEFAULT_LIMIT,
    vector_store: VectorStore | None = None,
    reranker: Reranker | None = None,
) -> list[SearchResult]:
    """Search the menu corpus and return top-``limit`` ``SearchResult``.

    Args:
        query: Free-text search string.
        corpus: Pre-encoded menu corpus.
        embedder: The Embedder instance for encoding the query.
        limit: Maximum number of results (clamped to [1, 20]).
        vector_store: Optional Qdrant-backed vector store. When supplied
            (and the collection is populated) the call is routed through
            ``hybrid_search`` for BM25 + dense + RRF fusion. When ``None``
            we use the cosine-only fallback.
        reranker: Optional cross-encoder reranker. Only used when
            ``vector_store`` is also provided (two-stage retrieval).

    Returns:
        Sorted list of ``SearchResult`` (descending by score).
    """
    if not corpus.ready:
        return []

    if vector_store is not None:
        from fos_ai.services.hybrid_search import hybrid_search

        return hybrid_search(
            query=query,
            corpus=corpus,
            embedder=embedder,
            vector_store=vector_store,
            limit=limit,
            reranker=reranker,
        )

    return _cosine_search(query, corpus, embedder, limit)


def _cosine_search(
    query: str,
    corpus: MenuCorpus,
    embedder: Embedder,
    limit: int,
) -> list[SearchResult]:
    """Original cosine top-k implementation — kept as a fallback."""
    limit = max(1, min(limit, _MAX_LIMIT))

    query_vec = embedder.encode([query])  # (1, dim)
    scores = (corpus.tensor @ query_vec.T).squeeze(dim=1)  # (N,)

    k = min(limit, corpus.size)
    topk = torch.topk(scores, k)

    results: list[SearchResult] = []
    for idx, score in zip(topk.indices.tolist(), topk.values.tolist()):
        meta = corpus.items[idx]
        results.append(
            SearchResult(
                food_id=meta.food_id,
                food_name=meta.food_name,
                restaurant_id=meta.restaurant_id,
                restaurant_name=meta.restaurant_name,
                unit_price=meta.unit_price,
                score=round(score, 4),
            )
        )

    return results
