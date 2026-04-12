"""Tests for content-based recommender — happy path, cold start, filter-seen."""

from __future__ import annotations

import pytest

from fos_ai.ml.corpus import MenuCorpus, build_corpus
from fos_ai.ml.embedding import Embedder
from fos_ai.schemas import FoodMeta
from fos_ai.services.recommender import recommend


@pytest.fixture(scope="module")
def embedder() -> Embedder:
    return Embedder()


@pytest.fixture(scope="module")
def corpus(sample_menu: list[FoodMeta], embedder: Embedder) -> MenuCorpus:
    return build_corpus(sample_menu, embedder)


class TestContentBased:

    def test_happy_path(self, corpus: MenuCorpus):
        """User who ordered Kung Pao Chicken gets content-based recommendations."""
        strategy, has_history, items = recommend(
            user_id=1, corpus=corpus, ordered_food_ids=[1], limit=3,
        )
        assert strategy == "content_based"
        assert has_history is True
        assert len(items) > 0
        assert len(items) <= 3

    def test_excludes_already_ordered(self, corpus: MenuCorpus):
        """Recommended items should NOT include foods already ordered."""
        ordered = [1, 2]  # Kung Pao Chicken + Mapo Tofu
        _, _, items = recommend(
            user_id=1, corpus=corpus, ordered_food_ids=ordered, limit=5,
        )
        returned_ids = {item.food_id for item in items}
        assert returned_ids.isdisjoint(set(ordered))

    def test_similar_cuisine_ranked_higher(self, corpus: MenuCorpus):
        """User who ordered Sichuan food should see Sichuan items ranked highly."""
        # Ordered Kung Pao Chicken (Sichuan, id=1)
        _, _, items = recommend(
            user_id=1, corpus=corpus, ordered_food_ids=[1], limit=5,
        )
        if items:
            # Expect other Sichuan items (Mapo Tofu=2, Dan Dan Noodles=3)
            # to appear before non-Sichuan items
            sichuan_ids = {2, 3}
            top_ids = {item.food_id for item in items[:2]}
            assert top_ids & sichuan_ids, f"Expected Sichuan items in top 2, got {top_ids}"

    def test_scores_descending(self, corpus: MenuCorpus):
        """Recommendation scores should be in descending order."""
        _, _, items = recommend(
            user_id=1, corpus=corpus, ordered_food_ids=[1], limit=5,
        )
        scores = [item.score for item in items]
        assert scores == sorted(scores, reverse=True)

    def test_reason_populated(self, corpus: MenuCorpus):
        """Each recommended item should have a reason string."""
        _, _, items = recommend(
            user_id=1, corpus=corpus, ordered_food_ids=[1], limit=3,
        )
        for item in items:
            assert item.reason


class TestColdStart:

    def test_no_history_uses_popularity_fallback(self, corpus: MenuCorpus):
        """User with no order history gets popularity fallback."""
        strategy, has_history, items = recommend(
            user_id=999, corpus=corpus, ordered_food_ids=[], limit=3,
        )
        assert strategy == "popularity_fallback"
        assert has_history is False
        assert len(items) == 3

    def test_fallback_items_have_popular_reason(self, corpus: MenuCorpus):
        """Fallback items should say 'Popular item'."""
        _, _, items = recommend(
            user_id=999, corpus=corpus, ordered_food_ids=[], limit=2,
        )
        for item in items:
            assert item.reason == "Popular item"

    def test_ordered_ids_not_in_corpus_falls_back(self, corpus: MenuCorpus):
        """If ordered food IDs don't exist in corpus, fall back gracefully."""
        strategy, has_history, items = recommend(
            user_id=1, corpus=corpus, ordered_food_ids=[9999, 8888], limit=3,
        )
        assert strategy == "popularity_fallback"
        assert has_history is False


class TestEdgeCases:

    def test_empty_corpus(self):
        """Empty corpus returns empty results."""
        empty = MenuCorpus()
        strategy, has_history, items = recommend(
            user_id=1, corpus=empty, ordered_food_ids=[1], limit=5,
        )
        assert strategy == "popularity_fallback"
        assert items == []

    def test_limit_clamped(self, corpus: MenuCorpus):
        """Limit > 20 is clamped to 20."""
        _, _, items = recommend(
            user_id=1, corpus=corpus, ordered_food_ids=[], limit=100,
        )
        assert len(items) <= 20
