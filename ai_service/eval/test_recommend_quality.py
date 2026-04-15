"""Recommender quality — strategy routing, history exclusion, result shape."""

from __future__ import annotations

import pytest

from fos_ai.services.recommender import recommend

pytestmark = pytest.mark.eval


def test_recommend_strategy_and_exclusion(eval_corpus, recommend_cases):
    failures: list[str] = []
    for case in recommend_cases:
        strategy, has_history, items = recommend(
            user_id=case["user_id"],
            corpus=eval_corpus,
            ordered_food_ids=case["history_food_ids"],
            limit=5,
        )

        if strategy != case["expected_strategy"]:
            failures.append(
                f"{case['id']}: strategy={strategy!r} expected={case['expected_strategy']!r}"
            )
        if has_history != case["expected_has_history"]:
            failures.append(
                f"{case['id']}: has_history={has_history} expected={case['expected_has_history']}"
            )
        returned_ids = {i.food_id for i in items}
        for excluded in case["must_exclude_ids"]:
            if excluded in returned_ids:
                failures.append(
                    f"{case['id']}: recommended food_id={excluded} was in history"
                )
        if len(items) == 0 and case["expected_strategy"] != "popularity_fallback":
            failures.append(f"{case['id']}: expected >=1 rec, got 0")

    print(f"\n[eval:recommend] {len(recommend_cases)} cases, "
          f"{len(failures)} failures")
    if failures:
        for f in failures:
            print("  -", f)
    assert not failures, f"{len(failures)} recommender failures"
