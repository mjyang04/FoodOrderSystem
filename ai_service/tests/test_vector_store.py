"""Unit tests for the Qdrant VectorStore wrapper (in-memory backend)."""

from __future__ import annotations

import pytest

from fos_ai.ml.vector_store import VectorStore


@pytest.fixture
def store() -> VectorStore:
    """Fresh in-memory Qdrant store for each test."""
    return VectorStore(in_memory=True)


def _vec(*xs: float) -> list[float]:
    return list(xs)


class TestVectorStore:

    def test_ensure_collection_creates(self, store: VectorStore):
        store.ensure_collection("items", dim=3)
        names = {c.name for c in store.client.get_collections().collections}
        assert "items" in names

    def test_ensure_collection_idempotent(self, store: VectorStore):
        store.ensure_collection("items", dim=3)
        store.ensure_collection("items", dim=3)  # should not raise
        names = {c.name for c in store.client.get_collections().collections}
        assert "items" in names

    def test_upsert_and_search_round_trip(self, store: VectorStore):
        store.ensure_collection("items", dim=3)
        store.upsert(
            "items",
            [
                (1, _vec(1.0, 0.0, 0.0), {"food_id": 1, "food_name": "A"}),
                (2, _vec(0.0, 1.0, 0.0), {"food_id": 2, "food_name": "B"}),
                (3, _vec(0.0, 0.0, 1.0), {"food_id": 3, "food_name": "C"}),
            ],
        )
        hits = store.search("items", _vec(1.0, 0.0, 0.0), limit=2)
        assert len(hits) == 2
        top_id, top_score, top_payload = hits[0]
        assert top_id == 1
        assert top_score > 0.99
        assert top_payload["food_name"] == "A"

    def test_upsert_empty_is_noop(self, store: VectorStore):
        store.ensure_collection("items", dim=3)
        store.upsert("items", [])  # should not raise
        assert store.count("items") == 0

    def test_count_reflects_upserts(self, store: VectorStore):
        store.ensure_collection("items", dim=2)
        store.upsert(
            "items",
            [
                (10, _vec(1.0, 0.0), {"food_id": 10}),
                (11, _vec(0.0, 1.0), {"food_id": 11}),
            ],
        )
        assert store.count("items") == 2

    def test_filter_matches_payload_field(self, store: VectorStore):
        store.ensure_collection("items", dim=3)
        store.upsert(
            "items",
            [
                (1, _vec(1.0, 0.0, 0.0), {"food_id": 1, "restaurant_id": 1}),
                (2, _vec(0.99, 0.01, 0.0), {"food_id": 2, "restaurant_id": 2}),
                (3, _vec(0.98, 0.02, 0.0), {"food_id": 3, "restaurant_id": 1}),
            ],
        )
        hits = store.search(
            "items",
            _vec(1.0, 0.0, 0.0),
            limit=5,
            filters={"restaurant_id": 2},
        )
        # Only the restaurant_id=2 row is eligible.
        assert len(hits) == 1
        assert hits[0][0] == 2

    def test_search_on_missing_collection_raises(self, store: VectorStore):
        with pytest.raises(Exception):
            store.search("does_not_exist", _vec(1.0, 0.0, 0.0), limit=1)
