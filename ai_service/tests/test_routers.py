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
    """Patch deps to return sample menu without DB."""
    from fos_ai import deps
    deps.init_menu(sample_menu)
    from fos_ai.config import Settings
    deps.init_settings(Settings(llm_provider="anthropic", anthropic_api_key="fake"))
    yield
    deps.init_menu([])


@pytest.fixture
def client():
    """Raw FastAPI TestClient without lifespan (no DB needed)."""
    from fos_ai.main import app
    return TestClient(app, raise_server_exceptions=False)


class TestHealthRouter:

    def test_health_not_ready_on_cold_start(self, client: TestClient):
        """Before menu loads, /health returns ready=false."""
        from fos_ai import deps
        deps.init_menu([])
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

    def test_health_ready_with_menu(self, _fake_menu, client: TestClient):
        """After menu loads, /health returns ready=true with corpus_size."""
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
