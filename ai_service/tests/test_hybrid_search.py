"""Tests for BM25 + dense + RRF hybrid search.

These tests use a fake in-memory vector store that returns a canned
ranking. The BM25 side is exercised for real against the sample menu
corpus.
"""

from __future__ import annotations

import pytest

from fos_ai.ml.corpus import MenuCorpus, build_corpus
from fos_ai.ml.embedding import Embedder
from fos_ai.schemas import FoodMeta
from fos_ai.services.hybrid_search import _rrf_fuse, hybrid_search, tokenize


class FakeVectorStore:
    """Test double with deterministic canned rankings."""

    def __init__(
        self,
        ranking: list[tuple[int, float, dict]] | None = None,
        collection_count: int = 6,
        raise_on_search: bool = False,
    ) -> None:
        self._ranking = ranking or []
        self._count = collection_count
        self._raise = raise_on_search

    def count(self, name: str) -> int:
        return self._count

    def search(
        self,
        name: str,
        query_vec: list[float],
        limit: int,
        filters: dict | None = None,
    ) -> list[tuple[int, float, dict]]:
        if self._raise:
            raise RuntimeError("qdrant boom")
        return self._ranking[:limit]


@pytest.fixture(scope="module")
def embedder() -> Embedder:
    return Embedder()


@pytest.fixture(scope="module")
def corpus(sample_menu: list[FoodMeta], embedder: Embedder) -> MenuCorpus:
    return build_corpus(sample_menu, embedder)


class TestTokenize:

    def test_lowercases_and_splits(self):
        assert tokenize("Kung Pao Chicken") == ["kung", "pao", "chicken"]

    def test_drops_punctuation_and_empties(self):
        assert tokenize("spicy, tofu!") == ["spicy", "tofu"]

    def test_empty_input(self):
        assert tokenize("   !!!  ") == []


class TestRRFFusion:

    def test_single_ranking_returns_sorted_by_rrf(self):
        ranking = [(1, 5.0), (2, 3.0), (3, 1.0)]
        fused = _rrf_fuse([ranking], k=60)
        assert [doc_id for doc_id, _ in fused] == [1, 2, 3]
        # rank=1 → 1/61, rank=2 → 1/62, rank=3 → 1/63
        assert fused[0][1] == pytest.approx(1 / 61)
        assert fused[1][1] == pytest.approx(1 / 62)
        assert fused[2][1] == pytest.approx(1 / 63)

    def test_two_rankings_combine_scores(self):
        # Doc 1 is rank 1 in A and rank 3 in B → 1/61 + 1/63
        # Doc 2 is rank 2 in A and rank 1 in B → 1/62 + 1/61
        ranking_a = [(1, 5.0), (2, 4.0), (3, 3.0)]
        ranking_b = [(2, 5.0), (3, 4.0), (1, 3.0)]
        fused = _rrf_fuse([ranking_a, ranking_b], k=60)
        fused_map = dict(fused)
        assert fused_map[1] == pytest.approx(1 / 61 + 1 / 63)
        assert fused_map[2] == pytest.approx(1 / 62 + 1 / 61)
        assert fused_map[3] == pytest.approx(1 / 63 + 1 / 62)
        # Doc 2 should rank first (appears at #1 in B and #2 in A).
        assert fused[0][0] == 2

    def test_empty_rankings(self):
        assert _rrf_fuse([], k=60) == []


class TestHybridSearch:

    def test_bm25_only_fallback_when_store_is_none(
        self, corpus: MenuCorpus, embedder: Embedder
    ):
        """vector_store=None → BM25-only results. 'duck' hits Roast Duck."""
        results = hybrid_search("roast duck", corpus, embedder, None, limit=3)
        assert len(results) > 0
        assert results[0].food_name == "Roast Duck"

    def test_fallback_when_vector_store_raises(
        self, corpus: MenuCorpus, embedder: Embedder
    ):
        """If the dense call raises, we degrade to BM25-only, not crash."""
        store = FakeVectorStore(raise_on_search=True)
        results = hybrid_search("roast duck", corpus, embedder, store, limit=3)
        assert len(results) > 0
        assert results[0].food_name == "Roast Duck"

    def test_empty_collection_falls_back_to_bm25(
        self, corpus: MenuCorpus, embedder: Embedder
    ):
        """If the Qdrant collection is empty, we skip dense and use BM25."""
        store = FakeVectorStore(ranking=[], collection_count=0)
        results = hybrid_search("spicy chicken", corpus, embedder, store, limit=3)
        assert len(results) > 0
        assert results[0].food_name == "Kung Pao Chicken"

    def test_empty_corpus_returns_empty(self, embedder: Embedder):
        empty = MenuCorpus()
        results = hybrid_search("anything", empty, embedder, None, limit=5)
        assert results == []

    def test_limit_clamped_to_max(self, corpus: MenuCorpus, embedder: Embedder):
        results = hybrid_search("food", corpus, embedder, None, limit=100)
        assert len(results) <= 20

    def test_limit_clamped_to_min(self, corpus: MenuCorpus, embedder: Embedder):
        results = hybrid_search("food", corpus, embedder, None, limit=0)
        assert len(results) == 1

    def test_dense_ranking_influences_order(
        self, corpus: MenuCorpus, embedder: Embedder
    ):
        """If dense ranks Pasta #1 for a pasta-ish query while BM25 also
        favours it, the fused result should still put pasta on top."""
        dense = [
            (21, 0.90, {"food_id": 21}),  # Pasta
            (11, 0.40, {"food_id": 11}),  # Dim Sum
            (12, 0.30, {"food_id": 12}),  # Roast Duck
        ]
        store = FakeVectorStore(ranking=dense, collection_count=6)
        results = hybrid_search("italian pasta tomato", corpus, embedder, store, limit=3)
        top_names = [r.food_name for r in results[:2]]
        assert "Pasta" in top_names

    def test_result_fields_populated(
        self, corpus: MenuCorpus, embedder: Embedder
    ):
        results = hybrid_search("pasta", corpus, embedder, None, limit=3)
        for r in results:
            assert r.food_id > 0
            assert r.food_name
            assert r.restaurant_id > 0
            assert r.restaurant_name
            assert r.unit_price > 0
            assert isinstance(r.score, float)

    def test_unknown_dense_ids_ignored(
        self, corpus: MenuCorpus, embedder: Embedder
    ):
        """Dense hits referring to ids not in the corpus are filtered out."""
        dense = [
            (9999, 0.99, {"food_id": 9999}),  # not in corpus
            (12, 0.50, {"food_id": 12}),
        ]
        store = FakeVectorStore(ranking=dense, collection_count=6)
        results = hybrid_search("duck", corpus, embedder, store, limit=3)
        assert all(r.food_id != 9999 for r in results)
