"""Menu corpus — load foods from DB, encode once, hold in memory.

The corpus is the backbone for semantic search and recommendations.
It is built once at startup and refreshed periodically.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import torch

from fos_ai.ml.embedding import Embedder
from fos_ai.schemas import FoodMeta

logger = logging.getLogger(__name__)


@dataclass
class MenuCorpus:
    """Pre-encoded menu for vector operations.

    Attributes:
        tensor: (N, dim) L2-normalised embeddings, one row per food item.
        items: Parallel metadata list — ``items[i]`` describes ``tensor[i]``.
    """

    tensor: torch.Tensor = field(default_factory=lambda: torch.empty(0))
    items: list[FoodMeta] = field(default_factory=list)

    @property
    def size(self) -> int:
        return len(self.items)

    @property
    def ready(self) -> bool:
        return self.size > 0


def build_corpus(foods: list[FoodMeta], embedder: Embedder) -> MenuCorpus:
    """Encode a list of FoodMeta into a MenuCorpus.

    Each food is represented as a single string combining its name,
    restaurant, description, and preferences for richer semantic matching.

    Args:
        foods: Menu items (typically from ``menu_repo.fetch_all_foods``).
        embedder: The Embedder instance.

    Returns:
        A ready ``MenuCorpus``.
    """
    if not foods:
        logger.warning("build_corpus called with empty food list")
        return MenuCorpus()

    texts = [_food_to_text(f) for f in foods]
    logger.info("Encoding %d menu items…", len(texts))
    tensor = embedder.encode(texts)
    logger.info("Corpus built — shape=%s", tuple(tensor.shape))

    return MenuCorpus(tensor=tensor, items=list(foods))


def _food_to_text(f: FoodMeta) -> str:
    """Build a rich text representation of a food item for embedding."""
    parts = [f.food_name, f.restaurant_name]
    if f.description:
        parts.append(f.description)
    if f.preferences:
        parts.append(f"Options: {f.preferences}")
    return " — ".join(parts)
