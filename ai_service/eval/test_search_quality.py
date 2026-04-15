"""Retrieval quality — Hit@5, MRR, nDCG@5 via the shared runner."""

from __future__ import annotations

import pytest

from eval.runners.search_runner import run as run_search

pytestmark = pytest.mark.eval

# Quality gates — tune with eval runs.
MIN_HIT_AT_5 = 0.80
MIN_MRR = 0.60
MIN_NDCG_AT_5 = 0.65


def test_search_quality(eval_corpus, eval_embedder, search_cases):
    ctx = {"corpus": eval_corpus, "embedder": eval_embedder}
    result = run_search(search_cases, ctx)

    hit = result.metrics["hit_at_5"]
    mrr = result.metrics["mrr"]
    ndcg = result.metrics["ndcg_at_5"]
    print(
        f"\n[eval:search] {result.n_cases} cases "
        f"Hit@5={hit:.3f} MRR={mrr:.3f} nDCG@5={ndcg:.3f}"
    )
    for f in result.failures:
        print(f"  miss {f['id']} '{f['query']}' exp={f['expected']} top5={f['top5']}")

    assert hit >= MIN_HIT_AT_5, f"Hit@5 {hit:.3f} below gate {MIN_HIT_AT_5}"
    assert mrr >= MIN_MRR, f"MRR {mrr:.3f} below gate {MIN_MRR}"
    assert ndcg >= MIN_NDCG_AT_5, f"nDCG@5 {ndcg:.3f} below gate {MIN_NDCG_AT_5}"
