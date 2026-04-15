"""Tests for two-stage retrieval: hybrid RRF → cross-encoder rerank.

Uses a stub ``Reranker`` that scores candidates by
``-abs(food_id - query_target_id)`` so the expected order is
deterministic and does not require any model downloads.
"""

from __future__ import annotations

import pytest

from fos_ai.ml.corpus import MenuCorpus, build_corpus
from fos_ai.ml.embedding import Embedder
from fos_ai.ml.reranker import Reranker, RerankerUnavailable
from fos_ai.schemas import FoodMeta
from fos_ai.services.hybrid_search import hybrid_search


class StubReranker(Reranker):
    """Reranker double that never loads a real model."""

    def __init__(self, target_id: int, fail: bool = False) -> None:
        # Skip Reranker.__init__ — we don't need model/device bookkeeping.
        self._target = target_id
        self._fail = fail
        self.calls = 0

    def rerank(self, query, candidates, top_k):  # type: ignore[override]
        self.calls += 1
        if self._fail:
            raise RerankerUnavailable("stub failure")
        scored = [
            (doc_id, float(-abs(doc_id - self._target)))
            for doc_id, _text in candidates
        ]
        scored.sort(key=lambda kv: -kv[1])
        return scored[: max(1, min(top_k, len(scored)))]


@pytest.fixture(scope="module")
def embedder() -> Embedder:
    return Embedder()


@pytest.fixture(scope="module")
def corpus(sample_menu: list[FoodMeta], embedder: Embedder) -> MenuCorpus:
    return build_corpus(sample_menu, embedder)


class TestTwoStageRetrieval:

    def test_reranker_reorders_rrf_output(
        self, corpus: MenuCorpus, embedder: Embedder
    ):
        """Target id=11 (Dim Sum). Reranker should pull it to #1 even if BM25
        would otherwise surface Roast Duck for 'duck' — we pick a generic
        query that hits several corpus items."""
        stub = StubReranker(target_id=11)
        results = hybrid_search(
            query="cantonese food",
            corpus=corpus,
            embedder=embedder,
            vector_store=None,
            limit=3,
            reranker=stub,
        )
        assert stub.calls == 1
        assert results, "expected non-empty results"
        assert results[0].food_id == 11

    def test_reranker_score_flows_into_result(
        self, corpus: MenuCorpus, embedder: Embedder
    ):
        stub = StubReranker(target_id=21)
        results = hybrid_search(
            query="italian pasta",
            corpus=corpus,
            embedder=embedder,
            vector_store=None,
            limit=3,
            reranker=stub,
        )
        # Target id=21 has score 0; other ids have negative scores.
        top = results[0]
        assert top.food_id == 21
        assert top.score == 0.0
        for lower in results[1:]:
            assert lower.score <= 0.0

    def test_reranker_failure_falls_back_to_rrf(
        self, corpus: MenuCorpus, embedder: Embedder
    ):
        """When the reranker raises, the call must not crash — we fall back
        to the RRF (here BM25-only since vector_store=None) ranking."""
        stub = StubReranker(target_id=11, fail=True)
        baseline = hybrid_search(
            query="roast duck", corpus=corpus, embedder=embedder,
            vector_store=None, limit=3,
        )
        results = hybrid_search(
            query="roast duck",
            corpus=corpus,
            embedder=embedder,
            vector_store=None,
            limit=3,
            reranker=stub,
        )
        assert stub.calls == 1
        assert [r.food_id for r in results] == [r.food_id for r in baseline]

    def test_reranker_honours_limit(
        self, corpus: MenuCorpus, embedder: Embedder
    ):
        stub = StubReranker(target_id=1)
        results = hybrid_search(
            query="food",
            corpus=corpus,
            embedder=embedder,
            vector_store=None,
            limit=2,
            reranker=stub,
        )
        assert len(results) == 2

    def test_rerank_candidates_controls_pool(
        self, corpus: MenuCorpus, embedder: Embedder
    ):
        """rerank_candidates >= limit should never shrink the returned set."""
        stub = StubReranker(target_id=3)
        results = hybrid_search(
            query="spicy",
            corpus=corpus,
            embedder=embedder,
            vector_store=None,
            limit=3,
            reranker=stub,
            rerank_candidates=1,  # clamped up to limit internally
        )
        assert len(results) == 3
