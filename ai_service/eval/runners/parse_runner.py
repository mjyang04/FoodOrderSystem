"""Parse suite runner — stub LLM returns the labelled tool_call payload.

Context (``ctx``) must contain:

    - ``menu``: ``list[FoodMeta]``

The runner instantiates its own per-case stub LLM so the test exercises
our resolver logic, not the LLM.
"""

from __future__ import annotations

from typing import Any

from fos_ai.services.llm_client import ToolCallResult
from fos_ai.services.parser import parse_order

from eval.runners.base import RunResult

_SUITE = "parse"


class _StubLlm:
    """Fixed tool-call response — ignores any real LLM provider."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def tool_call(self, **_: Any) -> ToolCallResult:  # type: ignore[override]
        return ToolCallResult(
            tool_name="create_order_draft",
            tool_input=self._payload,
            raw_text="",
            stop_reason="tool_use",
        )


def run(cases: list[dict[str, Any]], ctx: dict[str, Any]) -> RunResult:
    failures: list[dict[str, Any]] = []
    restaurant_hits = 0
    confidence_hits = 0

    for case in cases:
        llm = _StubLlm(case["llm_stub"])
        resp = parse_order(
            text=case["text"],
            menu=ctx["menu"],
            llm=llm,
            restaurant_hint_id=None,
        )
        exp = case["expected"]
        reasons: list[str] = []

        if resp.draft.restaurant_id == exp["restaurant_id"]:
            restaurant_hits += 1
        else:
            reasons.append(
                f"restaurant_id={resp.draft.restaurant_id} "
                f"expected={exp['restaurant_id']}"
            )
        if len(resp.draft.items) != exp["item_count"]:
            reasons.append(
                f"item_count={len(resp.draft.items)} "
                f"expected={exp['item_count']}"
            )
        if abs(resp.draft.estimated_total - exp["total"]) > 0.01:
            reasons.append(
                f"total={resp.draft.estimated_total} expected={exp['total']}"
            )
        if resp.confidence < exp["min_confidence"]:
            reasons.append(
                f"confidence={resp.confidence} < {exp['min_confidence']}"
            )
        else:
            confidence_hits += 1

        if reasons:
            failures.append({"id": case["id"], "reasons": reasons})

    n = len(cases)
    return RunResult(
        suite=_SUITE,
        n_cases=n,
        metrics={
            "restaurant_match": restaurant_hits / n if n else 1.0,
            "confidence_pass_rate": confidence_hits / n if n else 1.0,
            "pass_rate": (n - len(failures)) / n if n else 1.0,
        },
        failures=failures,
    )
