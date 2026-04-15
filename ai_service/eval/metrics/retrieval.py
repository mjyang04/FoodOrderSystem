"""Retrieval quality metrics — Hit@k, MRR, nDCG@k."""

from __future__ import annotations

import math
from typing import Iterable, Mapping


def hit_at_k(ranked: list[int], relevant: Iterable[int], k: int) -> float:
    """Return 1.0 if any relevant id appears in the top-k, else 0.0."""
    rel = set(relevant)
    top = ranked[:k]
    return 1.0 if any(x in rel for x in top) else 0.0


def reciprocal_rank(ranked: list[int], relevant: Iterable[int]) -> float:
    """1 / rank of the first relevant result; 0 if none found.

    Used as the per-query MRR contribution — average across queries to get MRR.
    """
    rel = set(relevant)
    for idx, item in enumerate(ranked, start=1):
        if item in rel:
            return 1.0 / idx
    return 0.0


def ndcg_at_k(
    ranked: list[int],
    relevance: Mapping[int, float],
    k: int,
) -> float:
    """Normalised Discounted Cumulative Gain at rank ``k``.

    Gain is looked up by id via ``relevance.get(id, 0)``. Discount uses
    ``1 / log2(rank + 1)`` with rank starting at 1.

    Returns 0.0 when ``k <= 0``, the ranked list is empty, or no relevance
    mass exists (i.e. ideal DCG == 0).
    """
    if k <= 0 or not ranked:
        return 0.0

    top = ranked[:k]
    dcg = 0.0
    for idx, item in enumerate(top, start=1):
        gain = float(relevance.get(item, 0.0))
        if gain <= 0.0:
            continue
        dcg += gain / math.log2(idx + 1)

    # ideal: sort all positive gains descending, take top-k
    gains_sorted = sorted((g for g in relevance.values() if g > 0), reverse=True)
    if not gains_sorted:
        return 0.0
    ideal_dcg = 0.0
    for idx, gain in enumerate(gains_sorted[:k], start=1):
        ideal_dcg += float(gain) / math.log2(idx + 1)
    if ideal_dcg == 0.0:
        return 0.0
    return dcg / ideal_dcg


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0
