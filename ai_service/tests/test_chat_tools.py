"""Tests for chat tool schemas and dispatcher."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from fos_ai.schemas import (
    FoodMeta,
    OrderDraft,
    OrderDraftItem,
    ParseOrderResponse,
    RecommendItem,
    SearchResult,
)
from fos_ai.services import chat_tools
from fos_ai.services.chat_tools import ToolContext, ToolError, ToolExecutor


# ---------- schema sanity ----------

def test_all_tools_have_anthropic_schema_shape():
    for tool in chat_tools.all_tools():
        assert "name" in tool
        assert "description" in tool and tool["description"]
        assert tool["input_schema"]["type"] == "object"
        assert "properties" in tool["input_schema"]


def test_four_tools_registered():
    names = [t["name"] for t in chat_tools.all_tools()]
    assert set(names) == {
        "search_menu",
        "create_order_draft",
        "check_order_status",
        "get_recommendations",
    }


# ---------- fakes ----------

@dataclass
class _FakeCursor:
    rows: list[dict[str, Any]]
    _pos: int = 0
    def execute(self, _sql, _params=None):
        self._pos = 0
    def fetchone(self):
        return self.rows[0] if self.rows else None
    def fetchall(self):
        return list(self.rows)
    def close(self):
        pass


class _FakeConn:
    def __init__(self, rows: list[dict[str, Any]] | None = None,
                 user_history: list[int] | None = None) -> None:
        self._rows = rows or []
        self._history = user_history or []

    def cursor(self, dictionary: bool = False):
        if dictionary:
            return _FakeCursor(rows=self._rows)
        # non-dict cursor for fetch_user_order_food_ids — returns tuples
        class _TupleCursor:
            def __init__(self, ids):
                self._ids = ids
            def execute(self, _sql, _params=None):
                pass
            def fetchall(self):
                return [(i,) for i in self._ids]
            def close(self):
                pass
        return _TupleCursor(self._history)


@pytest.fixture
def ctx(sample_menu):
    # Minimal corpus/embedder/llm stand-ins. Handlers that need them will be
    # tested via monkeypatch of the underlying service calls.
    return ToolContext(
        user_id=7,
        menu=sample_menu,
        corpus=object(),     # search handler will be monkey-patched
        embedder=object(),
        llm=object(),
        db_conn=_FakeConn(),
    )


# ---------- dispatcher ----------

def test_unknown_tool_raises(ctx):
    exe = ToolExecutor(ctx)
    with pytest.raises(ToolError, match="unknown tool"):
        exe.execute("no_such_tool", {})


def test_search_menu_dispatches(monkeypatch, ctx, sample_menu):
    captured = {}

    def fake_search(*, query, corpus, embedder, limit):
        captured["query"] = query
        captured["limit"] = limit
        return [
            SearchResult(
                food_id=1, food_name="Kung Pao Chicken",
                restaurant_id=1, restaurant_name="Sichuan Delight",
                unit_price=12.0, score=0.92,
            )
        ]

    monkeypatch.setattr("fos_ai.services.chat_tools.search.search", fake_search)

    out = ToolExecutor(ctx).execute("search_menu", {"query": "spicy chicken", "limit": 3})
    assert captured == {"query": "spicy chicken", "limit": 3}
    assert out["count"] == 1
    assert out["results"][0]["food_id"] == 1


def test_search_menu_empty_query_raises(ctx):
    with pytest.raises(ToolError, match="non-empty"):
        ToolExecutor(ctx).execute("search_menu", {"query": "  "})


def test_create_order_draft_dispatches(monkeypatch, ctx, sample_menu):
    def fake_parse(*, text, menu, llm, restaurant_hint_id):
        return ParseOrderResponse(
            draft=OrderDraft(
                restaurant_id=1,
                restaurant_name="Sichuan Delight",
                delivery_option="Standard",
                items=[OrderDraftItem(
                    food_id=1, food_name="Kung Pao Chicken",
                    quantity=2, unit_price=12.0,
                )],
                estimated_total=24.0,
            ),
            confidence=1.0,
            issues=[],
        )

    monkeypatch.setattr("fos_ai.services.chat_tools.parser.parse_order", fake_parse)

    out = ToolExecutor(ctx).execute(
        "create_order_draft",
        {"text": "two kung pao chicken", "restaurant_hint_id": 1},
    )
    assert out["draft"]["restaurant_id"] == 1
    assert out["draft"]["items"][0]["quantity"] == 2


def test_create_order_draft_parser_error_becomes_tool_error(monkeypatch, ctx):
    def fake_parse(*, text, menu, llm, restaurant_hint_id):
        raise ValueError("LLM_REFUSED: nothing matches")

    monkeypatch.setattr("fos_ai.services.chat_tools.parser.parse_order", fake_parse)

    with pytest.raises(ToolError, match="LLM_REFUSED"):
        ToolExecutor(ctx).execute(
            "create_order_draft", {"text": "something weird"}
        )


def test_check_order_status_success(sample_menu):
    rows = [{
        "order_id": 42, "user_id": 7, "status": "Preparing",
        "total_amount": 24.5, "rating": None,
        "created_at": "2026-04-15 10:00:00",
        "restaurant_name": "Sichuan Delight",
    }]
    ctx = ToolContext(
        user_id=7, menu=sample_menu, corpus=object(),
        embedder=object(), llm=object(),
        db_conn=_FakeConn(rows=rows),
    )
    out = ToolExecutor(ctx).execute("check_order_status", {"order_id": 42})
    assert out["status"] == "Preparing"
    assert out["restaurant_name"] == "Sichuan Delight"


def test_check_order_status_owner_mismatch(sample_menu):
    rows = [{
        "order_id": 42, "user_id": 99, "status": "Preparing",
        "total_amount": 24.5, "rating": None,
        "created_at": "2026-04-15",
        "restaurant_name": "X",
    }]
    ctx = ToolContext(
        user_id=7, menu=sample_menu, corpus=object(),
        embedder=object(), llm=object(),
        db_conn=_FakeConn(rows=rows),
    )
    with pytest.raises(ToolError, match="not found"):
        ToolExecutor(ctx).execute("check_order_status", {"order_id": 42})


def test_check_order_status_bad_input(ctx):
    with pytest.raises(ToolError, match="positive integer"):
        ToolExecutor(ctx).execute("check_order_status", {"order_id": 0})


def test_get_recommendations_dispatches(monkeypatch, sample_menu):
    ctx = ToolContext(
        user_id=7, menu=sample_menu, corpus=object(),
        embedder=object(), llm=object(),
        db_conn=_FakeConn(user_history=[1, 2]),
    )

    def fake_recommend(*, user_id, corpus, ordered_food_ids, limit):
        assert user_id == 7
        assert ordered_food_ids == [1, 2]
        return (
            "content_based",
            True,
            [RecommendItem(
                food_id=3, food_name="Dan Dan Noodles",
                restaurant_id=1, restaurant_name="Sichuan Delight",
                unit_price=8.0, score=0.85, reason="ok",
            )],
        )

    monkeypatch.setattr(
        "fos_ai.services.chat_tools.recommender.recommend", fake_recommend
    )

    out = ToolExecutor(ctx).execute("get_recommendations", {"limit": 3})
    assert out["strategy"] == "content_based"
    assert out["user_has_history"] is True
    assert out["items"][0]["food_id"] == 3


def test_generic_exception_wraps_to_tool_error(monkeypatch, ctx):
    def boom(**_kwargs):
        raise RuntimeError("underlying service down")

    monkeypatch.setattr("fos_ai.services.chat_tools.search.search", boom)

    with pytest.raises(ToolError, match="search_menu failed"):
        ToolExecutor(ctx).execute("search_menu", {"query": "x"})
