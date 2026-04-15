"""Unit tests for eval.metrics — retrieval (nDCG), generation (F1), judge.

These exercise the pure math / parsing; the suite-level runs live in
``ai_service/eval/`` under the ``eval`` pytest marker.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any

import pytest

# Make the test-side ``eval`` package importable from tests/
_AI_SERVICE_DIR = Path(__file__).resolve().parents[1]
if str(_AI_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(_AI_SERVICE_DIR))

from eval.metrics.generation import exact_match, field_f1  # noqa: E402
from eval.metrics.judge import llm_as_judge  # noqa: E402
from eval.metrics.retrieval import (  # noqa: E402
    hit_at_k,
    mean,
    ndcg_at_k,
    reciprocal_rank,
)
from fos_ai.services.llm_client import TextOnlyResult  # noqa: E402


# ---------- retrieval ----------

def test_hit_at_k_basic():
    assert hit_at_k([1, 2, 3], {1}, 3) == 1.0
    assert hit_at_k([1, 2, 3], {9}, 3) == 0.0


def test_reciprocal_rank_positions():
    assert reciprocal_rank([1, 2, 3], {2}) == pytest.approx(0.5)
    assert reciprocal_rank([1, 2, 3], {9}) == 0.0


def test_ndcg_identity_permutation_is_1():
    # Ranked list perfectly matches labelled relevance order.
    ranked = [1, 2, 3]
    relevance = {1: 3.0, 2: 2.0, 3: 1.0}
    assert ndcg_at_k(ranked, relevance, 3) == pytest.approx(1.0)


def test_ndcg_empty_ranked_is_0():
    assert ndcg_at_k([], {1: 1.0}, 5) == 0.0


def test_ndcg_empty_relevance_is_0():
    assert ndcg_at_k([1, 2], {}, 5) == 0.0


def test_ndcg_k_zero_returns_0():
    assert ndcg_at_k([1, 2], {1: 1.0}, 0) == 0.0


def test_ndcg_partial_ordering_between_zero_and_one():
    ranked = [2, 1]  # swap top-2
    relevance = {1: 3.0, 2: 1.0}
    score = ndcg_at_k(ranked, relevance, 2)
    assert 0.0 < score < 1.0


def test_ndcg_uniform_binary_labels():
    ranked = [1, 2, 9]
    relevance = {1: 1.0, 2: 1.0}
    # ideal DCG with 2 gains at ranks 1,2: 1 + 1/log2(3)
    ideal = 1.0 + 1.0 / math.log2(3)
    assert ndcg_at_k(ranked, relevance, 3) == pytest.approx(ideal / ideal)


def test_mean_empty_and_nonempty():
    assert mean([]) == 0.0
    assert mean([1.0, 0.0]) == 0.5


# ---------- generation ----------

def test_exact_match_all_fields_match():
    pred = {"a": 1, "b": "x"}
    expected = {"a": 1, "b": "x"}
    assert exact_match(pred, expected, ["a", "b"]) == 1.0


def test_exact_match_partial():
    pred = {"a": 1, "b": "x"}
    expected = {"a": 1, "b": "y"}
    assert exact_match(pred, expected, ["a", "b"]) == 0.5


def test_field_f1_all_match_mean_one():
    out = field_f1({"a": 1}, {"a": 1}, ["a"])
    assert out["a"] == 1.0
    assert out["_mean"] == 1.0


def test_field_f1_missing_field_counts_as_miss():
    out = field_f1({"a": 1}, {"b": 2}, ["a", "b"])
    assert out["a"] == 0.0
    assert out["b"] == 0.0
    assert out["_mean"] == 0.0


def test_field_f1_empty_fields():
    assert field_f1({}, {}, []) == {"_mean": 1.0}


# ---------- judge ----------

class _StubJudgeLlm:
    """Replay a fixed list of raw text outputs as TextOnlyResult."""

    def __init__(self, outputs: list[str]) -> None:
        self._outputs = list(outputs)
        self._idx = 0

    def tool_call(self, **_: Any):
        raw = self._outputs[self._idx] if self._idx < len(self._outputs) else ""
        self._idx += 1
        return TextOnlyResult(text=raw, stop_reason="end_turn")

    def messages(self, **_: Any):  # pragma: no cover
        raise NotImplementedError

    def messages_stream(self, **_: Any):  # pragma: no cover
        raise NotImplementedError


def test_llm_as_judge_majority_vote():
    outputs = [
        '{"score": 4, "rationale": "good"}',
        '{"score": 4, "rationale": "good"}',
        '{"score": 2, "rationale": "meh"}',
    ]
    llm = _StubJudgeLlm(outputs)
    result = llm_as_judge([], "criteria", llm, samples=3)
    assert result["score"] == 4
    assert result["votes"] == [4, 4, 2]
    assert result["parse_failures"] == 0


def test_llm_as_judge_tie_break_picks_higher_score():
    outputs = [
        '{"score": 5, "rationale": "excellent"}',
        '{"score": 3, "rationale": "ok"}',
    ]
    llm = _StubJudgeLlm(outputs)
    result = llm_as_judge([], "criteria", llm, samples=2)
    # Tie 1-1; tie-break favors the higher score (5 > 3).
    assert result["score"] == 5


def test_llm_as_judge_parse_failures_counted():
    outputs = [
        "unparseable garbage",
        '{"score": 7, "rationale": "out of range"}',  # >5 invalid
        '{"score": 3}',
    ]
    llm = _StubJudgeLlm(outputs)
    result = llm_as_judge([], "criteria", llm, samples=3)
    assert result["parse_failures"] == 2
    assert result["votes"] == [3]
    assert result["score"] == 3


def test_llm_as_judge_zero_samples_raises():
    with pytest.raises(ValueError):
        llm_as_judge([], "criteria", _StubJudgeLlm([]), samples=0)


def test_llm_as_judge_all_parse_failures_returns_zero():
    llm = _StubJudgeLlm(["", "nope", "bad"])
    result = llm_as_judge([], "criteria", llm, samples=3)
    assert result["score"] == 0
    assert result["votes"] == []
    assert result["parse_failures"] == 3
