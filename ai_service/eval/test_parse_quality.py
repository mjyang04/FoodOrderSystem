"""Parse quality — stubbed LLM so we measure OUR resolver, not LLM variance."""

from __future__ import annotations

import pytest

from eval.runners.parse_runner import run as run_parse

pytestmark = pytest.mark.eval

MIN_RESTAURANT_MATCH = 1.0
MIN_CONFIDENCE_PASS = 0.9


def test_parse_quality(eval_menu, parse_cases):
    ctx = {"menu": eval_menu}
    result = run_parse(parse_cases, ctx)

    print(
        f"\n[eval:parse] {result.n_cases} cases, "
        f"{len(result.failures)} failures, "
        f"restaurant_match={result.metrics['restaurant_match']:.3f} "
        f"confidence_pass={result.metrics['confidence_pass_rate']:.3f}"
    )
    for f in result.failures:
        print(f"  {f['id']}: {'; '.join(f['reasons'])}")

    assert result.metrics["restaurant_match"] >= MIN_RESTAURANT_MATCH, (
        f"restaurant match {result.metrics['restaurant_match']:.3f} "
        f"below {MIN_RESTAURANT_MATCH}"
    )
    assert result.metrics["confidence_pass_rate"] >= MIN_CONFIDENCE_PASS, (
        f"confidence pass rate {result.metrics['confidence_pass_rate']:.3f} "
        f"below {MIN_CONFIDENCE_PASS}"
    )
