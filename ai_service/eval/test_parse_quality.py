"""Parse quality — uses stubbed LLM so we measure OUR resolution logic,
not LLM variance."""

from __future__ import annotations

from typing import Any

import pytest

from fos_ai.services.parser import parse_order
from fos_ai.services.llm_client import ToolCallResult

pytestmark = pytest.mark.eval


class _StubLlm:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def tool_call(self, **_: Any):
        return ToolCallResult(
            tool_name="create_order_draft",
            tool_input=self._payload,
            raw_text="",
            stop_reason="tool_use",
        )


def test_parse_cases(eval_menu, parse_cases):
    failures: list[str] = []
    for case in parse_cases:
        llm = _StubLlm(case["llm_stub"])
        resp = parse_order(
            text=case["text"],
            menu=eval_menu,
            llm=llm,
            restaurant_hint_id=None,
        )
        exp = case["expected"]

        if resp.draft.restaurant_id != exp["restaurant_id"]:
            failures.append(
                f"{case['id']}: restaurant_id={resp.draft.restaurant_id} "
                f"expected={exp['restaurant_id']}"
            )
        if len(resp.draft.items) != exp["item_count"]:
            failures.append(
                f"{case['id']}: item_count={len(resp.draft.items)} "
                f"expected={exp['item_count']}"
            )
        if abs(resp.draft.estimated_total - exp["total"]) > 0.01:
            failures.append(
                f"{case['id']}: total={resp.draft.estimated_total} "
                f"expected={exp['total']}"
            )
        if resp.confidence < exp["min_confidence"]:
            failures.append(
                f"{case['id']}: confidence={resp.confidence} "
                f"< {exp['min_confidence']}"
            )

    print(f"\n[eval:parse] {len(parse_cases)} cases, {len(failures)} failures")
    for f in failures:
        print("  -", f)
    assert not failures, f"{len(failures)} parse failures"
