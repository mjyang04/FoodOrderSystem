"""Content-based recommender with cold-start popularity fallback."""

from __future__ import annotations

import logging
from typing import Any

import torch

from fos_ai.ml.corpus import MenuCorpus
from fos_ai.schemas import RecommendItem

logger = logging.getLogger(__name__)

_MAX_LIMIT = 20
_DEFAULT_LIMIT = 5


def recommend(
    user_id: int,
    corpus: MenuCorpus,
    ordered_food_ids: list[int],
    limit: int = _DEFAULT_LIMIT,
) -> tuple[str, bool, list[RecommendItem]]:
    """Generate recommendations for a user.

    Args:
        user_id: The authenticated user's ID.
        corpus: Pre-encoded menu corpus.
        ordered_food_ids: Food IDs the user has ordered before.
        limit: Maximum results (clamped to [1, 20]).

    Returns:
        Tuple of (strategy, user_has_history, items).
    """
    if not corpus.ready:
        return "popularity_fallback", False, []

    limit = max(1, min(limit, _MAX_LIMIT))

    if ordered_food_ids:
        return _content_based(corpus, ordered_food_ids, limit)
    return _popularity_fallback(corpus, limit)


def _content_based(
    corpus: MenuCorpus,
    ordered_food_ids: list[int],
    limit: int,
) -> tuple[str, bool, list[RecommendItem]]:
    """Average embeddings of ordered foods, find similar unseen items."""
    # Build a set for O(1) lookup
    seen = set(ordered_food_ids)

    # Find corpus indices for ordered foods
    ordered_indices = [
        i for i, meta in enumerate(corpus.items)
        if meta.food_id in seen
    ]

    if not ordered_indices:
        # User ordered foods not in current corpus — fall back
        return _popularity_fallback(corpus, limit)

    # Mean of ordered food embeddings → user profile vector
    ordered_tensor = corpus.tensor[ordered_indices]  # (M, dim)
    user_profile = ordered_tensor.mean(dim=0, keepdim=True)  # (1, dim)
    user_profile = torch.nn.functional.normalize(user_profile, p=2, dim=1)

    # Cosine similarity against full corpus
    scores = (corpus.tensor @ user_profile.T).squeeze(dim=1)  # (N,)

    # Mask already-ordered foods with -inf so they rank last
    for i, meta in enumerate(corpus.items):
        if meta.food_id in seen:
            scores[i] = float("-inf")

    # Top-k from remaining
    k = min(limit, corpus.size)
    topk = torch.topk(scores, k)

    items: list[RecommendItem] = []
    for idx, score in zip(topk.indices.tolist(), topk.values.tolist()):
        if score == float("-inf"):
            break
        meta = corpus.items[idx]
        items.append(
            RecommendItem(
                food_id=meta.food_id,
                food_name=meta.food_name,
                restaurant_id=meta.restaurant_id,
                restaurant_name=meta.restaurant_name,
                unit_price=meta.unit_price,
                score=round(score, 4),
                reason="Similar to items in your past orders",
            )
        )

    return "content_based", True, items


def _popularity_fallback(
    corpus: MenuCorpus,
    limit: int,
) -> tuple[str, bool, list[RecommendItem]]:
    """Cold-start: return first N items (simulates popularity ranking).

    In a production system this would rank by global order count.
    With seed data, item order in the corpus approximates popularity.
    """
    k = min(limit, corpus.size)
    items: list[RecommendItem] = []
    for meta in corpus.items[:k]:
        items.append(
            RecommendItem(
                food_id=meta.food_id,
                food_name=meta.food_name,
                restaurant_id=meta.restaurant_id,
                restaurant_name=meta.restaurant_name,
                unit_price=meta.unit_price,
                score=0.0,
                reason="Popular item",
            )
        )

    return "popularity_fallback", False, items
