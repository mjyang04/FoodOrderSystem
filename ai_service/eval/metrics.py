"""Retrieval and generation quality metrics used by the eval suite."""

from __future__ import annotations

from typing import Iterable


def hit_at_k(ranked: list[int], relevant: Iterable[int], k: int) -> float:
    """Return 1.0 if any relevant id appears in the top-k, else 0.0."""
    rel = set(relevant)
    top = ranked[:k]
    return 1.0 if any(x in rel for x in top) else 0.0


def reciprocal_rank(ranked: list[int], relevant: Iterable[int]) -> float:
    """1 / rank of the first relevant result; 0 if none found.

    Used as per-query MRR contribution — average across queries to get MRR.
    """
    rel = set(relevant)
    for idx, item in enumerate(ranked, start=1):
        if item in rel:
            return 1.0 / idx
    return 0.0


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def exact_match(pred: dict, expected: dict, fields: list[str]) -> float:
    """Return fraction of listed fields where pred == expected (stringified)."""
    if not fields:
        return 1.0
    hits = 0
    for f in fields:
        if str(pred.get(f)) == str(expected.get(f)):
            hits += 1
    return hits / len(fields)
