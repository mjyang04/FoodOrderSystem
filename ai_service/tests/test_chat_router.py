"""Integration tests for POST /ai/chat — JSON and SSE modes."""

from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from fos_ai.schemas import FoodMeta
from fos_ai.services.llm_client import MessagesResult


class _FakeLlm:
    """Mimics LlmClient with a scripted .messages() queue."""

    def __init__(self, queue: list[MessagesResult]) -> None:
        self._queue = queue

    def messages(self, **_: Any) -> MessagesResult:
        if not self._queue:
            raise AssertionError("fake LLM out of responses")
        return self._queue.pop(0)

    def tool_call(self, **_: Any):  # pragma: no cover
        raise NotImplementedError

    def messages_stream(self, **_: Any):  # pragma: no cover
        raise NotImplementedError


class _FakeDb:
    """Enough cursor shape to satisfy order_repo / menu_repo tool paths."""

    def __init__(self) -> None:
        pass

    def cursor(self, dictionary: bool = False):
        class _C:
            def execute(self, *_): pass
            def fetchone(self): return None
            def fetchall(self): return []
            def close(self): pass
        return _C()


def _text(s: str) -> MessagesResult:
    return MessagesResult(
        content=[{"type": "text", "text": s}],
        stop_reason="end_turn",
    )


@pytest.fixture
def _chat_env(sample_menu: list[FoodMeta]):
    from fos_ai import deps
    from fos_ai.config import Settings
    from fos_ai.ml.corpus import MenuCorpus, build_corpus
    from fos_ai.ml.embedding import Embedder
    from fos_ai.services.session_store import SessionStore

    deps.init_menu(sample_menu)
    deps.init_settings(Settings(llm_provider="anthropic", anthropic_api_key="fake"))

    embedder = Embedder()
    deps.init_embedder(embedder)
    deps.init_corpus(build_corpus(sample_menu, embedder))
    deps.init_db_conn(_FakeDb())
    deps.init_session_store(SessionStore())

    yield

    deps.init_menu([])
    deps.init_corpus(MenuCorpus())
    deps.init_session_store(SessionStore())


@pytest.fixture
def client():
    from fos_ai.main import app
    return TestClient(app, raise_server_exceptions=False)


# ---------- JSON mode ----------

def test_chat_json_mode_happy_path(_chat_env, client):
    from fos_ai import deps
    deps.init_llm_client(_FakeLlm(queue=[_text("Hi! What would you like to eat?")]))

    resp = client.post(
        "/ai/chat",
        headers={"X-User-Id": "7"},
        json={"message": "hello", "stream": False},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["reply"].startswith("Hi!")
    assert len(body["data"]["session_id"]) == 36
    assert body["data"]["tool_calls"] == []


def test_chat_json_mode_reuses_session(_chat_env, client):
    from fos_ai import deps
    deps.init_llm_client(_FakeLlm(queue=[_text("A"), _text("B")]))

    r1 = client.post(
        "/ai/chat",
        headers={"X-User-Id": "7"},
        json={"message": "turn 1", "stream": False},
    )
    sid = r1.json()["data"]["session_id"]

    r2 = client.post(
        "/ai/chat",
        headers={"X-User-Id": "7"},
        json={"message": "turn 2", "session_id": sid, "stream": False},
    )
    assert r2.json()["data"]["session_id"] == sid
    assert r2.json()["data"]["reply"] == "B"


def test_chat_json_mode_missing_header(_chat_env, client):
    resp = client.post(
        "/ai/chat",
        json={"message": "hi", "stream": False},
    )
    assert resp.status_code == 422


def test_chat_json_mode_empty_message(_chat_env, client):
    resp = client.post(
        "/ai/chat",
        headers={"X-User-Id": "7"},
        json={"message": "", "stream": False},
    )
    assert resp.status_code == 422


def test_chat_503_when_corpus_not_ready(client):
    from fos_ai import deps
    from fos_ai.config import Settings
    from fos_ai.ml.corpus import MenuCorpus

    deps.init_corpus(MenuCorpus())
    deps.init_settings(Settings(llm_provider="anthropic", anthropic_api_key="fake"))

    resp = client.post(
        "/ai/chat",
        headers={"X-User-Id": "7"},
        json={"message": "hi", "stream": False},
    )
    assert resp.status_code == 503


# ---------- SSE mode ----------

def _parse_sse(body: str) -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = []
    for frame in body.split("\n\n"):
        frame = frame.strip()
        if not frame:
            continue
        event = ""
        data = "{}"
        for line in frame.splitlines():
            if line.startswith("event: "):
                event = line[len("event: "):]
            elif line.startswith("data: "):
                data = line[len("data: "):]
        out.append((event, json.loads(data)))
    return out


def test_chat_sse_mode_emits_session_and_done(_chat_env, client):
    from fos_ai import deps
    deps.init_llm_client(_FakeLlm(queue=[_text("streamed reply")]))

    with client.stream(
        "POST",
        "/ai/chat",
        headers={"X-User-Id": "7"},
        json={"message": "hi", "stream": True},
    ) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        body = "".join(resp.iter_text())

    frames = _parse_sse(body)
    events = [e for e, _ in frames]
    assert events[0] == "session"
    assert "session_id" in frames[0][1]
    assert "text_delta" in events
    assert events[-1] == "done"


def test_chat_sse_includes_tool_events(_chat_env, client):
    from fos_ai import deps
    deps.init_llm_client(_FakeLlm(queue=[
        MessagesResult(
            content=[{"type": "tool_use", "id": "tu_1", "name": "search_menu",
                      "input": {"query": "spicy"}}],
            stop_reason="tool_use",
        ),
        _text("here are results"),
    ]))

    with client.stream(
        "POST",
        "/ai/chat",
        headers={"X-User-Id": "7"},
        json={"message": "find spicy stuff", "stream": True},
    ) as resp:
        assert resp.status_code == 200
        body = "".join(resp.iter_text())

    frames = _parse_sse(body)
    events = [e for e, _ in frames]
    assert "tool_call" in events
    assert "tool_result" in events
    # order: session, tool_call, tool_result, text_delta, done
    assert events.index("tool_call") < events.index("tool_result")
    assert events.index("tool_result") < events.index("text_delta")
