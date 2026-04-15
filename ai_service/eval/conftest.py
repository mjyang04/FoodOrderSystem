"""Shared fixtures for the eval/ suite — isolated from unit tests.

The evaluation menu is a deterministic 21-item subset of ``src/db/schema.sql``
seed data covering 8 cuisines. All case files reference food ids from this
list — if you touch ``_EVAL_MENU`` make sure every labelled id still resolves.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fos_ai.schemas import FoodMeta
from fos_ai.ml.corpus import MenuCorpus, build_corpus
from fos_ai.ml.embedding import Embedder

_DATA_DIR = Path(__file__).parent / "data"


# Hand-crafted, schema-aligned. Ids match seed data in src/db/schema.sql
# so eval labels remain stable even when recompiling the corpus.
_EVAL_MENU_ITEMS: list[tuple[int, str, float, str, str, int, str]] = [
    # (food_id, food_name, unit_price, description, preferences, rid, r_name)
    # --- Sichuan Delight (rid=1) ---
    (1, "Kung Pao Chicken", 12.0,
     "Spicy stir-fried chicken with peanuts",
     "Mild|Medium|Extra Spicy", 1, "Sichuan Delight"),
    (2, "Mapo Tofu", 8.0,
     "Spicy tofu with minced meat",
     "Mild|Medium|Extra Spicy", 1, "Sichuan Delight"),
    (3, "Hot Pot", 15.0,
     "Spicy hot pot with meat and vegetables",
     "Mild|Medium|Extra Spicy", 1, "Sichuan Delight"),
    (4, "Dan Dan Noodles", 8.0,
     "Spicy noodles with minced meat",
     "Mild|Medium|Extra Spicy", 1, "Sichuan Delight"),
    # --- Chengdu Flavors (rid=2) ---
    (8, "Boiled Fish", 16.0,
     "Boiled fish with spicy broth",
     "Mild|Medium|Extra Spicy", 2, "Chengdu Flavors"),
    # --- Cantonese Kitchen (rid=3) ---
    (11, "Dim Sum", 10.0,
     "Variety of small Cantonese dishes",
     "", 3, "Cantonese Kitchen"),
    (12, "Roast Duck", 20.0,
     "Crispy roast duck, Cantonese style",
     "Half|Whole", 3, "Cantonese Kitchen"),
    (14, "BBQ Pork Buns", 3.0,
     "Steamed buns with BBQ pork",
     "", 3, "Cantonese Kitchen"),
    # --- Guangzhou Garden (rid=4) ---
    (17, "Char Siu", 12.0,
     "Barbecue pork Cantonese style",
     "", 4, "Guangzhou Garden"),
    # --- La Dolce Vita (rid=5) ---
    (21, "Pasta", 10.0,
     "Italian pasta with tomato sauce",
     "Spaghetti|Penne|Fusilli", 5, "La Dolce Vita"),
    (22, "Pizza", 15.0,
     "Cheese and tomato pizza",
     "Small|Medium|Large", 5, "La Dolce Vita"),
    (23, "Tiramisu", 5.0,
     "Italian coffee-flavored dessert",
     "", 5, "La Dolce Vita"),
    # --- Roma Ristorante (rid=6) ---
    (27, "Margherita Pizza", 16.0,
     "Pizza with tomatoes, mozzarella, and basil",
     "Small|Medium|Large", 6, "Roma Ristorante"),
    # --- Le Petit Bistro (rid=7) ---
    (31, "Steak", 25.0,
     "Grilled beef steak",
     "Rare|Medium Rare|Medium|Well Done", 7, "Le Petit Bistro"),
    # --- Lebanese Delights (rid=9) ---
    (41, "Shawarma", 10.0,
     "Marinated meat wrapped in pita",
     "Chicken|Beef|Lamb", 9, "Lebanese Delights"),
    # --- Moroccan Feast (rid=10) ---
    (46, "Tagine", 15.0,
     "Slow-cooked meat and vegetable stew",
     "Chicken|Lamb|Vegetable", 10, "Moroccan Feast"),
    # --- Texas Tacos (rid=11) ---
    (51, "Taco", 3.0,
     "Soft corn tortilla with fillings",
     "Beef|Chicken|Fish", 11, "Texas Tacos"),
    # --- Sushi House (rid=13) ---
    (61, "Nigiri", 12.0,
     "Sushi with fish on top of rice",
     "Tuna|Salmon|Shrimp", 13, "Sushi House"),
    (63, "Sashimi", 14.0,
     "Sliced raw fish",
     "Tuna|Salmon|Mixed", 13, "Sushi House"),
    # --- Ramen World (rid=14) ---
    (66, "Tonkotsu Ramen", 12.0,
     "Pork bone broth ramen",
     "Regular|Extra Rich", 14, "Ramen World"),
    (70, "Spicy Ramen", 13.0,
     "Spicy flavored ramen",
     "Mild|Medium|Extreme", 14, "Ramen World"),
]


def _eval_menu() -> list[FoodMeta]:
    """21-item labelled menu covering 8 cuisines / 10 restaurants."""
    return [
        FoodMeta(
            food_id=fid, food_name=name, unit_price=price,
            description=desc, preferences=prefs,
            restaurant_id=rid, restaurant_name=rname,
        )
        for (fid, name, price, desc, prefs, rid, rname) in _EVAL_MENU_ITEMS
    ]


# Exposed for the CLI runner (run.py) to build the same corpus outside pytest.
def build_eval_menu() -> list[FoodMeta]:
    return _eval_menu()


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


@pytest.fixture(scope="session")
def chat_cases() -> list[dict]:
    return _load("chat_cases.json")
