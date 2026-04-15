"""Tests for the cross-encoder reranker wrapper.

The real ``BAAI/bge-reranker-base`` weights (~280 MB) are never
downloaded here — we monkeypatch ``sentence_transformers.CrossEncoder``
with a stub that returns deterministic scores.
"""

from __future__ import annotations

import pytest

from fos_ai.ml import reranker as reranker_module
from fos_ai.ml.reranker import Reranker, RerankerUnavailable


class FakeCrossEncoder:
    """Deterministic stand-in for ``sentence_transformers.CrossEncoder``.

    ``predict`` scores each ``(query, text)`` pair by the negative
    absolute difference between the doc_id encoded in ``text`` and a
    target id parsed from the query string. A query like ``"id=12"``
    will rank the candidate with ``id=12`` first.
    """

    last_init: dict | None = None
    load_should_fail: bool = False
    predict_should_fail: bool = False

    def __init__(self, model_name: str, device: str | None = None) -> None:
        if FakeCrossEncoder.load_should_fail:
            raise RuntimeError("simulated model load failure")
        FakeCrossEncoder.last_init = {"model_name": model_name, "device": device}
        self.model_name = model_name
        self.device = device

    def predict(self, pairs):  # type: ignore[override]
        if FakeCrossEncoder.predict_should_fail:
            raise RuntimeError("simulated predict failure")
        scores: list[float] = []
        for query, text in pairs:
            target = _parse_target(query)
            doc_id = _parse_id(text)
            if target is None or doc_id is None:
                scores.append(0.0)
            else:
                scores.append(-abs(doc_id - target))
        return scores


def _parse_target(query: str) -> int | None:
    """Parse ``id=<int>`` from a query string."""
    if "id=" not in query:
        return None
    try:
        return int(query.split("id=", 1)[1].split()[0])
    except ValueError:
        return None


def _parse_id(text: str) -> int | None:
    """Parse ``id=<int>`` from a candidate text."""
    if "id=" not in text:
        return None
    try:
        return int(text.split("id=", 1)[1].split()[0])
    except ValueError:
        return None


@pytest.fixture(autouse=True)
def _reset_fake_state():
    """Reset monkeypatched state between tests."""
    FakeCrossEncoder.last_init = None
    FakeCrossEncoder.load_should_fail = False
    FakeCrossEncoder.predict_should_fail = False
    yield
    FakeCrossEncoder.last_init = None
    FakeCrossEncoder.load_should_fail = False
    FakeCrossEncoder.predict_should_fail = False


@pytest.fixture
def patch_cross_encoder(monkeypatch):
    """Replace the lazily-imported CrossEncoder with our fake."""
    import sentence_transformers

    monkeypatch.setattr(sentence_transformers, "CrossEncoder", FakeCrossEncoder)
    return FakeCrossEncoder


class TestRerankerInit:

    def test_model_not_loaded_until_rerank_called(self, patch_cross_encoder):
        r = Reranker(model_name="fake/model", device="cpu")
        assert patch_cross_encoder.last_init is None  # lazy

        r.rerank("id=1", [(1, "id=1")], top_k=1)
        assert patch_cross_encoder.last_init == {"model_name": "fake/model", "device": "cpu"}

    def test_device_auto_detect_populates(self, patch_cross_encoder):
        r = Reranker(model_name="fake/model")
        assert r.device in {"cpu", "cuda", "mps"}
        r.rerank("id=1", [(1, "id=1")], top_k=1)
        assert patch_cross_encoder.last_init is not None


class TestRerankerRerank:

    def test_sorts_by_score_desc(self, patch_cross_encoder):
        r = Reranker(model_name="fake/model", device="cpu")
        # Target id=3 → score(3)=0 > score(1)=-2 > score(10)=-7
        candidates = [(1, "id=1"), (10, "id=10"), (3, "id=3")]
        out = r.rerank("id=3", candidates, top_k=3)
        assert [doc_id for doc_id, _ in out] == [3, 1, 10]
        assert out[0][1] == 0.0
        assert out[1][1] == -2.0
        assert out[2][1] == -7.0

    def test_top_k_trims(self, patch_cross_encoder):
        r = Reranker(model_name="fake/model", device="cpu")
        candidates = [(i, f"id={i}") for i in range(1, 8)]
        out = r.rerank("id=4", candidates, top_k=3)
        assert len(out) == 3
        assert [doc_id for doc_id, _ in out] == [4, 3, 5]

    def test_empty_candidates_returns_empty(self, patch_cross_encoder):
        r = Reranker(model_name="fake/model", device="cpu")
        assert r.rerank("id=1", [], top_k=5) == []

    def test_top_k_clamped_to_candidates_length(self, patch_cross_encoder):
        r = Reranker(model_name="fake/model", device="cpu")
        out = r.rerank("id=1", [(1, "id=1"), (2, "id=2")], top_k=100)
        assert len(out) == 2


class TestRerankerFailure:

    def test_load_failure_raises_unavailable(self, patch_cross_encoder):
        FakeCrossEncoder.load_should_fail = True
        r = Reranker(model_name="fake/model", device="cpu")
        with pytest.raises(RerankerUnavailable):
            r.rerank("id=1", [(1, "id=1")], top_k=1)

    def test_load_failure_is_sticky(self, patch_cross_encoder):
        """A second call after a failed load still raises without retrying."""
        FakeCrossEncoder.load_should_fail = True
        r = Reranker(model_name="fake/model", device="cpu")
        with pytest.raises(RerankerUnavailable):
            r.rerank("id=1", [(1, "id=1")], top_k=1)
        # Even if we flip the flag, the reranker remembers it failed.
        FakeCrossEncoder.load_should_fail = False
        with pytest.raises(RerankerUnavailable):
            r.rerank("id=1", [(1, "id=1")], top_k=1)

    def test_predict_failure_raises_unavailable(self, patch_cross_encoder):
        r = Reranker(model_name="fake/model", device="cpu")
        # Force the loaded-model path, then flip the predict flag.
        r.rerank("id=1", [(1, "id=1")], top_k=1)
        FakeCrossEncoder.predict_should_fail = True
        with pytest.raises(RerankerUnavailable):
            r.rerank("id=1", [(1, "id=1")], top_k=1)


def test_reranker_module_default_name():
    """Sanity: the documented default matches the config default."""
    assert reranker_module._DEFAULT_MODEL == "BAAI/bge-reranker-base"
