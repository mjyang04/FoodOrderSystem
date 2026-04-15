"""Retrieval quality — Hit@5 and MRR against labelled search cases."""

from __future__ import annotations

import pytest

from fos_ai.services.search import search

from eval.metrics import hit_at_k, mean, reciprocal_rank

pytestmark = pytest.mark.eval

# Quality gates — tune with eval runs.
MIN_HIT_AT_5 = 0.80
MIN_MRR = 0.60


def _rank(query: str, corpus, embedder) -> list[int]:
    """Run real search, return list of food_ids in rank order."""
    results = search(query=query, corpus=corpus, embedder=embedder, limit=10)
    return [r.food_id for r in results]


def test_search_hit_at_5(eval_corpus, eval_embedder, search_cases):
    hits: list[float] = []
    misses: list[str] = []
    for case in search_cases:
        ranked = _rank(case["query"], eval_corpus, eval_embedder)
        score = hit_at_k(ranked, case["relevant_food_ids"], k=5)
        hits.append(score)
        if score == 0.0:
            misses.append(f"{case['id']} '{case['query']}' -> {ranked[:5]}")

    aggregate = mean(hits)
    print(f"\n[eval:search] Hit@5 = {aggregate:.3f} ({len(hits)} cases)")
    if misses:
        print("  misses:\n    " + "\n    ".join(misses))
    assert aggregate >= MIN_HIT_AT_5, (
        f"Hit@5 {aggregate:.3f} below gate {MIN_HIT_AT_5}"
    )


def test_search_mrr(eval_corpus, eval_embedder, search_cases):
    rrs: list[float] = []
    for case in search_cases:
        ranked = _rank(case["query"], eval_corpus, eval_embedder)
        rrs.append(reciprocal_rank(ranked, case["relevant_food_ids"]))

    mrr = mean(rrs)
    print(f"\n[eval:search] MRR = {mrr:.3f} ({len(rrs)} cases)")
    assert mrr >= MIN_MRR, f"MRR {mrr:.3f} below gate {MIN_MRR}"
