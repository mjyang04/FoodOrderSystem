"""Tests for MenuCorpus — build, properties, text representation."""

from __future__ import annotations

import pytest

from fos_ai.ml.corpus import MenuCorpus, build_corpus, _food_to_text
from fos_ai.ml.embedding import Embedder
from fos_ai.schemas import FoodMeta


@pytest.fixture(scope="module")
def embedder() -> Embedder:
    return Embedder()


class TestBuildCorpus:

    def test_build_from_sample_menu(self, sample_menu: list[FoodMeta], embedder: Embedder):
        """Corpus tensor matches the number of menu items."""
        corpus = build_corpus(sample_menu, embedder)
        assert corpus.size == len(sample_menu)
        assert corpus.tensor.shape == (len(sample_menu), 384)
        assert corpus.ready is True

    def test_empty_menu(self, embedder: Embedder):
        """Empty input → empty corpus, not ready."""
        corpus = build_corpus([], embedder)
        assert corpus.size == 0
        assert corpus.ready is False

    def test_items_parallel_to_tensor(self, sample_menu: list[FoodMeta], embedder: Embedder):
        """items[i] corresponds to tensor[i]."""
        corpus = build_corpus(sample_menu, embedder)
        for i, meta in enumerate(corpus.items):
            assert meta.food_id == sample_menu[i].food_id


class TestFoodToText:

    def test_includes_name_and_restaurant(self):
        f = FoodMeta(
            food_id=1, food_name="Kung Pao Chicken", unit_price=12.0,
            description="Spicy chicken", preferences="Mild|Spicy",
            restaurant_id=1, restaurant_name="Sichuan Delight",
        )
        text = _food_to_text(f)
        assert "Kung Pao Chicken" in text
        assert "Sichuan Delight" in text
        assert "Spicy chicken" in text
        assert "Mild|Spicy" in text

    def test_no_description(self):
        f = FoodMeta(
            food_id=1, food_name="Test", unit_price=1.0,
            description="", preferences="",
            restaurant_id=1, restaurant_name="R",
        )
        text = _food_to_text(f)
        assert "Test" in text
        assert "R" in text
