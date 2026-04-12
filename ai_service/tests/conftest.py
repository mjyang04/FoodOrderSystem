"""Shared fixtures for fos_ai tests."""

from __future__ import annotations

import pytest

from fos_ai.schemas import FoodMeta


@pytest.fixture
def sample_menu() -> list[FoodMeta]:
    """A small menu mirroring the seed data for testing."""
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
            description="Crispy roast duck",
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
