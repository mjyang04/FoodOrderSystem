"""Shared fixtures for the eval/ suite — isolated from unit tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fos_ai.schemas import FoodMeta
from fos_ai.ml.corpus import MenuCorpus, build_corpus
from fos_ai.ml.embedding import Embedder

_DATA_DIR = Path(__file__).parent / "data"


def _eval_menu() -> list[FoodMeta]:
    """Larger, labelled-query-aligned menu for evaluation."""
    return [
        FoodMeta(
            food_id=1, food_name="Kung Pao Chicken", unit_price=12.0,
            description="Spicy stir-fried chicken with peanuts",
            preferences="Mild|Medium|Extra Spicy",
            restaurant_id=1, restaurant_name="Sichuan Delight",
        ),
        FoodMeta(
            food_id=2, food_name="Mapo Tofu", unit_price=8.0,
            description="Spicy tofu with minced meat",
            preferences="Mild|Medium|Extra Spicy",
            restaurant_id=1, restaurant_name="Sichuan Delight",
        ),
        FoodMeta(
            food_id=3, food_name="Dan Dan Noodles", unit_price=8.0,
            description="Spicy noodles with minced meat",
            preferences="Mild|Medium|Extra Spicy",
            restaurant_id=1, restaurant_name="Sichuan Delight",
        ),
        FoodMeta(
            food_id=11, food_name="Dim Sum", unit_price=10.0,
            description="Variety of small Cantonese dishes",
            preferences="",
            restaurant_id=3, restaurant_name="Cantonese Kitchen",
        ),
        FoodMeta(
            food_id=12, food_name="Roast Duck", unit_price=20.0,
            description="Crispy roast duck, Cantonese style",
            preferences="Half|Whole",
            restaurant_id=3, restaurant_name="Cantonese Kitchen",
        ),
        FoodMeta(
            food_id=21, food_name="Pasta", unit_price=10.0,
            description="Italian pasta with tomato sauce",
            preferences="Spaghetti|Penne|Fusilli",
            restaurant_id=5, restaurant_name="La Dolce Vita",
        ),
    ]


@pytest.fixture(scope="session")
def eval_menu() -> list[FoodMeta]:
    return _eval_menu()


@pytest.fixture(scope="session")
def eval_embedder() -> Embedder:
    return Embedder()


@pytest.fixture(scope="session")
def eval_corpus(eval_menu, eval_embedder) -> MenuCorpus:
    return build_corpus(eval_menu, eval_embedder)


def _load(name: str) -> list[dict]:
    return json.loads((_DATA_DIR / name).read_text())


@pytest.fixture(scope="session")
def search_cases() -> list[dict]:
    return _load("search_cases.json")


@pytest.fixture(scope="session")
def recommend_cases() -> list[dict]:
    return _load("recommend_cases.json")


@pytest.fixture(scope="session")
def parse_cases() -> list[dict]:
    return _load("parse_cases.json")
