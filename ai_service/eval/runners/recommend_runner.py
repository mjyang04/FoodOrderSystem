"""Recommender suite runner — strategy / history / exclusion assertions.

Context (``ctx``) must contain:

    - ``corpus``: ``MenuCorpus``
"""

from __future__ import annotations

from typing import Any

from fos_ai.services.recommender import recommend

from eval.runners.base import RunResult

_SUITE = "recommend"


def run(cases: list[dict[str, Any]], ctx: dict[str, Any]) -> RunResult:
    failures: list[dict[str, Any]] = []
    strategy_hits = 0

    for case in cases:
        strategy, has_history, items = recommend(
            user_id=case["user_id"],
            corpus=ctx["corpus"],
            ordered_food_ids=case["history_food_ids"],
            limit=5,
        )

        reasons: list[str] = []
        if strategy != case["expected_strategy"]:
            reasons.append(
                f"strategy={strategy!r} expected={case['expected_strategy']!r}"
            )
        if has_history != case["expected_has_history"]:
            reasons.append(
                f"has_history={has_history} expected={case['expected_has_history']}"
            )
        returned_ids = {i.food_id for i in items}
        for excluded in case["must_exclude_ids"]:
            if excluded in returned_ids:
                reasons.append(f"recommended excluded id {excluded}")
        if len(items) == 0 and case["expected_strategy"] != "popularity_fallback":
            reasons.append("expected >=1 rec, got 0")

        if strategy == case["expected_strategy"]:
            strategy_hits += 1

        if reasons:
            failures.append({"id": case["id"], "reasons": reasons})

    n = len(cases)
    return RunResult(
        suite=_SUITE,
        n_cases=n,
        metrics={
            "strategy_accuracy": strategy_hits / n if n else 1.0,
            "pass_rate": (n - len(failures)) / n if n else 1.0,
        },
        failures=failures,
    )
