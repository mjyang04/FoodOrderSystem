"""Integration tests for POST /ai/intent."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from fos_ai.services.intent_classifier import IntentClassifier, IntentUnavailable


class _StubClassifier:
    def __init__(self, label: str = "search", conf: float = 0.88):
        self._label = label
        self._conf = conf
        self.calls: list[str] = []

    def classify(self, text: str) -> tuple[str, float]:
        self.calls.append(text)
        return self._label, self._conf


class _ErrorClassifier:
    def __init__(self, exc: Exception):
        self._exc = exc

    def classify(self, text: str) -> tuple[str, float]:
        raise self._exc


@pytest.fixture
def client():
    from fos_ai import deps
    from fos_ai.config import Settings
    from fos_ai.main import app

    deps.init_settings(Settings(llm_provider="anthropic", anthropic_api_key="fake"))
    yield TestClient(app, raise_server_exceptions=False)
    deps.init_intent_classifier(None, source="none")


def test_intent_happy_path_lora_source(client):
    from fos_ai import deps

    stub = _StubClassifier(label="order", conf=0.93)
    deps.init_intent_classifier(stub, source="lora")

    resp = client.post(
        "/ai/intent",
        headers={"X-User-Id": "7"},
        json={"text": "order two pizzas"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"label": "order", "confidence": 0.93, "source": "lora"}
    assert stub.calls == ["order two pizzas"]


def test_intent_fallback_source(client):
    from fos_ai import deps

    deps.init_intent_classifier(
        _StubClassifier(label="chitchat", conf=0.7),
        source="fallback",
    )
    resp = client.post(
        "/ai/intent",
        headers={"X-User-Id": "1"},
        json={"text": "hey"},
    )
    assert resp.status_code == 200
    assert resp.json()["source"] == "fallback"


def test_intent_missing_header_returns_422(client):
    from fos_ai import deps

    deps.init_intent_classifier(_StubClassifier(), source="lora")
    resp = client.post("/ai/intent", json={"text": "hi"})
    assert resp.status_code == 422


def test_intent_empty_text_returns_422(client):
    from fos_ai import deps

    deps.init_intent_classifier(_StubClassifier(), source="lora")
    resp = client.post(
        "/ai/intent",
        headers={"X-User-Id": "1"},
        json={"text": ""},
    )
    assert resp.status_code == 422


def test_intent_503_when_classifier_not_configured(client):
    from fos_ai import deps

    deps.init_intent_classifier(None, source="none")
    resp = client.post(
        "/ai/intent",
        headers={"X-User-Id": "1"},
        json={"text": "hi"},
    )
    assert resp.status_code == 503


def test_intent_502_on_unavailable(client):
    from fos_ai import deps

    deps.init_intent_classifier(
        _ErrorClassifier(IntentUnavailable("adapter corrupt")),
        source="lora",
    )
    resp = client.post(
        "/ai/intent",
        headers={"X-User-Id": "1"},
        json={"text": "hi"},
    )
    assert resp.status_code == 502
    assert "AI_INTENT_UNAVAILABLE" in resp.json()["detail"]


def test_intent_502_on_generic_exception(client):
    from fos_ai import deps

    deps.init_intent_classifier(
        _ErrorClassifier(RuntimeError("numerical nan")),
        source="lora",
    )
    resp = client.post(
        "/ai/intent",
        headers={"X-User-Id": "1"},
        json={"text": "hi"},
    )
    assert resp.status_code == 502
    assert "AI_INTENT_ERROR" in resp.json()["detail"]
