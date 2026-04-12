"""Semantic menu search — encode query, cosine top-k against corpus."""

from __future__ import annotations

import logging

import torch

from fos_ai.ml.corpus import MenuCorpus
from fos_ai.ml.embedding import Embedder
from fos_ai.schemas import SearchResult

logger = logging.getLogger(__name__)

_MAX_LIMIT = 20
_DEFAULT_LIMIT = 10


def search(
    query: str,
    corpus: MenuCorpus,
    embedder: Embedder,
    limit: int = _DEFAULT_LIMIT,
) -> list[SearchResult]:
    """Encode *query*, compute cosine similarity against the corpus, return top-k.

    Args:
        query: Free-text search string.
        corpus: Pre-encoded menu corpus.
        embedder: The Embedder instance for encoding the query.
        limit: Maximum number of results (clamped to [1, 20]).

    Returns:
        Sorted list of ``SearchResult`` (descending by score).
    """
    if not corpus.ready:
        return []

    limit = max(1, min(limit, _MAX_LIMIT))

    # Encode the query into a (1, dim) vector
    query_vec = embedder.encode([query])  # (1, 384)

    # Cosine similarity — both sides are L2-normalised, so dot product = cosine
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
