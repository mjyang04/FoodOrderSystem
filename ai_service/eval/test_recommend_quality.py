"""Recommender quality — strategy routing, history exclusion, result shape."""

from __future__ import annotations

import pytest

from eval.runners.recommend_runner import run as run_recommend

pytestmark = pytest.mark.eval


def test_recommend_quality(eval_corpus, recommend_cases):
    ctx = {"corpus": eval_corpus}
    result = run_recommend(recommend_cases, ctx)

    print(
        f"\n[eval:recommend] {result.n_cases} cases, "
        f"{len(result.failures)} failures, "
        f"strategy_accuracy={result.metrics['strategy_accuracy']:.3f}"
    )
    for f in result.failures:
        print(f"  {f['id']}: {'; '.join(f['reasons'])}")

    assert not result.failures, f"{len(result.failures)} recommender failures"
