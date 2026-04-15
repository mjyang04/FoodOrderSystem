"""Integration tests for FastAPI routers using TestClient."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from fos_ai.schemas import FoodMeta
from fos_ai.services.llm_client import TextOnlyResult, ToolCallResult


class FakeLlmClient:
    """Configurable fake for router tests."""

    def __init__(self, response: ToolCallResult | TextOnlyResult) -> None:
        self._response = response

    def tool_call(self, **kwargs: Any) -> ToolCallResult | TextOnlyResult:
        return self._response


@pytest.fixture
def _fake_menu(sample_menu: list[FoodMeta]):
    """Patch deps to return sample menu and corpus without DB."""
    from fos_ai import deps
    from fos_ai.config import Settings
    from fos_ai.ml.corpus import MenuCorpus, build_corpus
    from fos_ai.ml.embedding import Embedder

    deps.init_menu(sample_menu)
    deps.init_settings(Settings(llm_provider="anthropic", anthropic_api_key="fake"))

    embedder = Embedder()
    deps.init_embedder(embedder)
    corpus = build_corpus(sample_menu, embedder)
    deps.init_corpus(corpus)

    yield

    deps.init_menu([])
    deps.init_corpus(MenuCorpus())


@pytest.fixture
def client():
    """Raw FastAPI TestClient without lifespan (no DB needed)."""
    from fos_ai.main import app
    return TestClient(app, raise_server_exceptions=False)


class TestHealthRouter:

    def test_health_not_ready_on_cold_start(self, client: TestClient):
        """Before corpus loads, /health returns ready=false."""
        from fos_ai import deps
        from fos_ai.ml.corpus import MenuCorpus

        deps.init_menu([])
        deps.init_corpus(MenuCorpus())
        deps.init_settings(
            __import__("fos_ai.config", fromlist=["Settings"]).Settings(
                llm_provider="anthropic", anthropic_api_key="fake"
            )
        )

        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["ready"] is False
        assert body["corpus_size"] == 0

    def test_health_ready_with_corpus(self, _fake_menu, client: TestClient):
        """After corpus loads, /health returns ready=true with corpus_size."""
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["ready"] is True
        assert body["corpus_size"] == 6  # sample_menu has 6 items


class TestParseOrderRouter:

    def test_parse_order_happy_path(self, _fake_menu, client: TestClient):
        """POST /ai/parse-order with valid LLM tool-call response."""
        fake_llm = FakeLlmClient(ToolCallResult(
            tool_name="create_order_draft",
            tool_input={
                "restaurant_name": "Sichuan Delight",
                "delivery_option": "Standard",
                "items": [
                    {"food_name": "Kung Pao Chicken", "quantity": 2},
                    {"food_name": "Mapo Tofu", "quantity": 1},
                ],
            },
        ))

        from fos_ai import deps
        deps.init_llm_client(fake_llm)

        resp = client.post(
            "/ai/parse-order",
            json={"text": "两份宫保鸡丁一份麻婆豆腐"},
            headers={"X-User-Id": "5"},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["confidence"] == 1.0
        assert body["draft"]["restaurant_name"] == "Sichuan Delight"
        assert len(body["draft"]["items"]) == 2
        assert body["draft"]["estimated_total"] == 32.0

    def test_parse_order_llm_refusal(self, _fake_menu, client: TestClient):
        """LLM refuses → 422."""
        fake_llm = FakeLlmClient(TextOnlyResult(
            text="I don't understand your request",
            stop_reason="end_turn",
        ))

        from fos_ai import deps
        deps.init_llm_client(fake_llm)

        resp = client.post(
            "/ai/parse-order",
            json={"text": "asdfghjkl random noise"},
            headers={"X-User-Id": "5"},
        )

        assert resp.status_code == 422
        assert "LLM_REFUSED" in resp.json()["detail"]

    def test_parse_order_missing_header(self, _fake_menu, client: TestClient):
        """No X-User-Id header → 422 (FastAPI validation)."""
        resp = client.post(
            "/ai/parse-order",
            json={"text": "some order"},
        )
        assert resp.status_code == 422

    def test_parse_order_empty_text(self, _fake_menu, client: TestClient):
        """Empty text → 422 (pydantic min_length=1)."""
        resp = client.post(
            "/ai/parse-order",
            json={"text": ""},
            headers={"X-User-Id": "5"},
        )
        assert resp.status_code == 422

    def test_parse_order_no_menu(self, client: TestClient):
        """No menu loaded → 503."""
        from fos_ai import deps
        deps.init_menu([])
        deps.init_settings(
            __import__("fos_ai.config", fromlist=["Settings"]).Settings(
                llm_provider="anthropic", anthropic_api_key="fake"
            )
        )
        deps.init_llm_client(FakeLlmClient(TextOnlyResult(text="x")))

        resp = client.post(
            "/ai/parse-order",
            json={"text": "order something"},
            headers={"X-User-Id": "5"},
        )
        assert resp.status_code == 503


class TestSearchRouter:

    def test_search_happy_path(self, _fake_menu, client: TestClient):
        """GET /ai/search with valid query returns results."""
        resp = client.get("/ai/search", params={"q": "spicy chicken"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["query"] == "spicy chicken"
        assert body["count"] > 0
        assert len(body["results"]) == body["count"]

    def test_search_empty_query(self, _fake_menu, client: TestClient):
        """Empty q → 422 (FastAPI min_length=1)."""
        resp = client.get("/ai/search", params={"q": ""})
        assert resp.status_code == 422

    def test_search_missing_query(self, _fake_menu, client: TestClient):
        """No q param → 422."""
        resp = client.get("/ai/search")
        assert resp.status_code == 422

    def test_search_limit_respected(self, _fake_menu, client: TestClient):
        """Limit parameter is respected."""
        resp = client.get("/ai/search", params={"q": "food", "limit": 2})
        assert resp.status_code == 200
        assert resp.json()["count"] <= 2

    def test_search_no_corpus(self, client: TestClient):
        """No corpus loaded → 503."""
        from fos_ai import deps
        from fos_ai.ml.corpus import MenuCorpus

        deps.init_corpus(MenuCorpus())
        deps.init_settings(
            __import__("fos_ai.config", fromlist=["Settings"]).Settings(
                llm_provider="anthropic", anthropic_api_key="fake"
            )
        )

        resp = client.get("/ai/search", params={"q": "test"})
        assert resp.status_code == 503


class TestRecommendRouter:

    def test_recommend_cold_start(self, _fake_menu, client: TestClient):
        """User with no DB history gets popularity fallback."""
        with patch("fos_ai.routers.recommend.fetch_user_order_food_ids", return_value=[]), \
             patch("fos_ai.deps.get_db_conn", return_value=None):
            resp = client.get(
                "/ai/recommend",
                headers={"X-User-Id": "999"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["strategy"] == "popularity_fallback"
        assert body["user_has_history"] is False
        assert body["count"] > 0

    def test_recommend_with_history(self, _fake_menu, client: TestClient):
        """User with order history gets content-based recs."""
        with patch("fos_ai.routers.recommend.fetch_user_order_food_ids", return_value=[1]), \
             patch("fos_ai.deps.get_db_conn", return_value=None):
            resp = client.get(
                "/ai/recommend",
                headers={"X-User-Id": "1"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["strategy"] == "content_based"
        assert body["user_has_history"] is True
        # Should not include already-ordered food
        returned_ids = {item["food_id"] for item in body["items"]}
        assert 1 not in returned_ids

    def test_recommend_missing_header(self, _fake_menu, client: TestClient):
        """No X-User-Id header → 422."""
        resp = client.get("/ai/recommend")
        assert resp.status_code == 422

    def test_recommend_no_corpus(self, client: TestClient):
        """No corpus loaded → 503."""
        from fos_ai import deps
        from fos_ai.ml.corpus import MenuCorpus

        deps.init_corpus(MenuCorpus())
        deps.init_settings(
            __import__("fos_ai.config", fromlist=["Settings"]).Settings(
                llm_provider="anthropic", anthropic_api_key="fake"
            )
        )

        resp = client.get(
            "/ai/recommend",
            headers={"X-User-Id": "1"},
        )
        assert resp.status_code == 503
