"""Chat agent quality — scripted LLM + ChatEngine tool loop."""

from __future__ import annotations

import pytest

from eval.runners.chat_runner import run as run_chat

pytestmark = pytest.mark.eval

MIN_TOOL_PLAN_MATCH = 0.80
MIN_TEXT_CONTAINS_RATE = 0.80


def test_chat_quality(chat_cases):
    ctx: dict = {}
    result = run_chat(chat_cases, ctx)

    plan = result.metrics["tool_plan_match"]
    text = result.metrics["text_contains_rate"]
    print(
        f"\n[eval:chat] {result.n_cases} cases, {len(result.failures)} failures "
        f"tool_plan={plan:.3f} text_contains={text:.3f}"
    )
    for f in result.failures[:10]:
        print(f"  {f}")

    assert plan >= MIN_TOOL_PLAN_MATCH, (
        f"tool_plan_match {plan:.3f} below gate {MIN_TOOL_PLAN_MATCH}"
    )
    assert text >= MIN_TEXT_CONTAINS_RATE, (
        f"text_contains_rate {text:.3f} below gate {MIN_TEXT_CONTAINS_RATE}"
    )
