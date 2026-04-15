"""Search suite runner — Hit@5, MRR, nDCG@5 over labelled queries.

Context (``ctx``) must contain:

    - ``corpus``    : ``MenuCorpus``
    - ``embedder``  : ``Embedder``
    - ``vector_store`` (optional): ``VectorStore`` for hybrid mode
    - ``reranker``  (optional): ``Reranker`` for two-stage retrieval
"""

from __future__ import annotations

from typing import Any

from fos_ai.services.search import search

from eval.metrics.retrieval import hit_at_k, mean, ndcg_at_k, reciprocal_rank
from eval.runners.base import RunResult

_SUITE = "search"
_TOP_K = 5


def _rank(query: str, ctx: dict[str, Any]) -> list[int]:
    results = search(
        query=query,
        corpus=ctx["corpus"],
        embedder=ctx["embedder"],
        limit=10,
        vector_store=ctx.get("vector_store"),
        reranker=ctx.get("reranker"),
    )
    return [r.food_id for r in results]


def _relevance_map(rel_ids: list[int]) -> dict[int, float]:
    """Uniform-weight labels: every labelled id has gain 1.0."""
    return {int(i): 1.0 for i in rel_ids}


def run(cases: list[dict[str, Any]], ctx: dict[str, Any]) -> RunResult:
    hits: list[float] = []
    rrs: list[float] = []
    ndcgs: list[float] = []
    failures: list[dict[str, Any]] = []

    for case in cases:
        rel_ids = case["relevant_food_ids"]
        ranked = _rank(case["query"], ctx)
        h = hit_at_k(ranked, rel_ids, k=_TOP_K)
        rr = reciprocal_rank(ranked, rel_ids)
        nd = ndcg_at_k(ranked, _relevance_map(rel_ids), k=_TOP_K)
        hits.append(h)
        rrs.append(rr)
        ndcgs.append(nd)
        if h == 0.0:
            failures.append({
                "id": case["id"],
                "query": case["query"],
                "expected": rel_ids,
                "top5": ranked[:5],
            })

    return RunResult(
        suite=_SUITE,
        n_cases=len(cases),
        metrics={
            "hit_at_5": mean(hits),
            "mrr": mean(rrs),
            "ndcg_at_5": mean(ndcgs),
        },
        failures=failures,
    )
