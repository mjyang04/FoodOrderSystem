"""Eval metrics — retrieval + generation + judge.

Public API is re-exported here so callers can ``from eval.metrics import ...``
without knowing which submodule a metric lives in.
"""

from __future__ import annotations

from eval.metrics.retrieval import (
    hit_at_k,
    mean,
    ndcg_at_k,
    reciprocal_rank,
)
from eval.metrics.generation import exact_match, field_f1
from eval.metrics.judge import llm_as_judge

__all__ = [
    "hit_at_k",
    "mean",
    "ndcg_at_k",
    "reciprocal_rank",
    "exact_match",
    "field_f1",
    "llm_as_judge",
]
