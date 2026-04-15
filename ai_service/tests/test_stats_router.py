"""Integration tests for GET /ai/stats."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from fos_ai.obs.metrics import metrics


@pytest.fixture
def client():
    from fos_ai import deps
    from fos_ai.config import Settings
    from fos_ai.main import app

    deps.init_settings(Settings(llm_provider="anthropic", anthropic_api_key="fake"))
    metrics.reset()
    yield TestClient(app, raise_server_exceptions=False)
    metrics.reset()


def test_admin_happy_path(client):
    # Seed one call so totals aren't zero.
    metrics.record_llm_call(
        provider="anthropic",
        model="claude-haiku-4-5-20251001",
        input_tokens=10,
        output_tokens=20,
        latency_ms=12.5,
        cost_usd=0.0001,
    )
    metrics.record_cache("parser.parse_order", hit=True)
    metrics.record_cache("parser.parse_order", hit=False)

    resp = client.get(
        "/ai/stats",
        headers={"X-User-Id": "1", "X-User-Role": "admin"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    data = body["data"]
    assert "llm" in data
    assert "cache" in data
    assert data["window_seconds"] == 86_400
    assert data["llm"]["total_calls"] == 1
    assert data["llm"]["total_input_tokens"] == 10
    assert data["llm"]["by_provider"]["anthropic"]["total_calls"] == 1
    assert data["cache"]["namespaces"]["parser.parse_order"]["hits"] == 1


def test_non_admin_forbidden(client):
    resp = client.get(
        "/ai/stats",
        headers={"X-User-Id": "7", "X-User-Role": "customer"},
    )
    assert resp.status_code == 403
    assert "admin" in resp.json()["detail"].lower()


def test_missing_user_id_returns_422(client):
    resp = client.get(
        "/ai/stats",
        headers={"X-User-Role": "admin"},
    )
    assert resp.status_code == 422


def test_window_seconds_query_param(client):
    resp = client.get(
        "/ai/stats?window_seconds=3600",
        headers={"X-User-Id": "1", "X-User-Role": "admin"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["window_seconds"] == 3600


def test_admin_case_insensitive(client):
    resp = client.get(
        "/ai/stats",
        headers={"X-User-Id": "1", "X-User-Role": "ADMIN"},
    )
    assert resp.status_code == 200
