"""Tests for semantic menu search — cosine correctness, ordering, limits."""

from __future__ import annotations

import pytest
import torch

from fos_ai.ml.corpus import MenuCorpus, build_corpus
from fos_ai.ml.embedding import Embedder
from fos_ai.schemas import FoodMeta
from fos_ai.services.search import search


@pytest.fixture(scope="module")
def embedder() -> Embedder:
    return Embedder()


@pytest.fixture(scope="module")
def corpus(sample_menu: list[FoodMeta], embedder: Embedder) -> MenuCorpus:
    return build_corpus(sample_menu, embedder)


class TestSearch:

    def test_returns_results_for_relevant_query(self, corpus: MenuCorpus, embedder: Embedder):
        """Search for 'spicy chicken' should return results."""
        results = search("spicy chicken", corpus, embedder, limit=3)
        assert len(results) > 0
        assert len(results) <= 3

    def test_results_sorted_descending(self, corpus: MenuCorpus, embedder: Embedder):
        """Scores should be in descending order."""
        results = search("noodles", corpus, embedder, limit=6)
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_top_result_is_semantically_relevant(self, corpus: MenuCorpus, embedder: Embedder):
        """Searching for 'duck' should rank Roast Duck highly."""
        results = search("roast duck", corpus, embedder, limit=5)
        top_names = [r.food_name for r in results[:2]]
        assert "Roast Duck" in top_names

    def test_limit_clamped_to_max(self, corpus: MenuCorpus, embedder: Embedder):
        """Limit > 20 is clamped to 20."""
        results = search("food", corpus, embedder, limit=100)
        assert len(results) <= 20

    def test_limit_clamped_to_min(self, corpus: MenuCorpus, embedder: Embedder):
        """Limit < 1 is clamped to 1."""
        results = search("food", corpus, embedder, limit=0)
        assert len(results) == 1

    def test_empty_corpus_returns_empty(self, embedder: Embedder):
        """Search on empty corpus returns no results."""
        empty = MenuCorpus()
        results = search("anything", empty, embedder, limit=5)
        assert results == []

    def test_result_fields_populated(self, corpus: MenuCorpus, embedder: Embedder):
        """Each result has all required fields."""
        results = search("pasta", corpus, embedder, limit=3)
        for r in results:
            assert r.food_id > 0
            assert r.food_name
            assert r.restaurant_id > 0
            assert r.restaurant_name
            assert r.unit_price > 0
            assert isinstance(r.score, float)

    def test_scores_are_valid_cosine_range(self, corpus: MenuCorpus, embedder: Embedder):
        """Cosine similarity should be in [-1, 1]."""
        results = search("dim sum", corpus, embedder, limit=6)
        for r in results:
            assert -1.0 <= r.score <= 1.0
