"""Tests for ChatEngine — tool loop, max iterations, session continuity."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from fos_ai.schemas_chat import ChatSession
from fos_ai.services.chat_engine import ChatEngine, ChatMaxIterations
from fos_ai.services.chat_tools import ToolExecutor
from fos_ai.services.llm_client import MessagesResult


# ---------- fakes ----------

@dataclass
class _ScriptedLlm:
    """Returns a queued MessagesResult on each `.messages()` call."""

    queue: list[MessagesResult]
    calls: list[dict[str, Any]] = field(default_factory=list)

    def messages(self, *, system, messages, tools, max_tokens=1024):
        self.calls.append({
            "system": system, "messages": messages,
            "tools": tools, "max_tokens": max_tokens,
        })
        if not self.queue:
            raise AssertionError("scripted LLM ran out of responses")
        return self.queue.pop(0)

    # parser.py compatibility (not used here)
    def tool_call(self, **_):  # pragma: no cover
        raise NotImplementedError


class _StubExecutor:
    """Mimics ToolExecutor without the ctx machinery."""

    def __init__(self, responses: dict[str, Any]):
        self._responses = responses
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def execute(self, name, tool_input):
        self.calls.append((name, tool_input))
        if name not in self._responses:
            raise RuntimeError(f"no stub for tool {name}")
        val = self._responses[name]
        if isinstance(val, Exception):
            raise val
        return val


def _text(text: str) -> MessagesResult:
    return MessagesResult(
        content=[{"type": "text", "text": text}],
        stop_reason="end_turn",
    )


def _tool_use(tid: str, name: str, tool_input: dict) -> MessagesResult:
    return MessagesResult(
        content=[{"type": "tool_use", "id": tid, "name": name, "input": tool_input}],
        stop_reason="tool_use",
    )


# ---------- tests ----------

def test_single_turn_plain_text():
    llm = _ScriptedLlm(queue=[_text("Hello, what would you like?")])
    engine = ChatEngine(llm=llm, executor=_StubExecutor({}))
    session = ChatSession.new(user_id=7)

    result = engine.run(session, "hi")

    assert result.reply == "Hello, what would you like?"
    assert result.tool_calls == []
    assert result.iterations == 1
    assert len(session.messages) == 2  # user + assistant


def test_single_tool_then_text():
    llm = _ScriptedLlm(queue=[
        _tool_use("tu_1", "search_menu", {"query": "spicy", "limit": 3}),
        _text("I found spicy chicken at Sichuan Delight."),
    ])
    executor = _StubExecutor({
        "search_menu": {"count": 1, "results": [
            {"food_id": 1, "food_name": "Kung Pao Chicken", "score": 0.9}
        ]},
    })
    engine = ChatEngine(llm=llm, executor=executor)
    session = ChatSession.new(user_id=7)

    result = engine.run(session, "show me spicy stuff")

    assert result.iterations == 2
    assert result.reply.startswith("I found spicy")
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].tool == "search_menu"
    assert result.tool_calls[0].input == {"query": "spicy", "limit": 3}
    assert result.tool_calls[0].error is None

    # executor saw the call
    assert executor.calls == [("search_menu", {"query": "spicy", "limit": 3})]

    # session has: user, assistant(tool_use), user(tool_result), assistant(text)
    assert len(session.messages) == 4
    assert session.messages[0].role == "user"
    assert session.messages[1].content[0]["type"] == "tool_use"
    assert session.messages[2].content[0]["type"] == "tool_result"
    assert session.messages[2].content[0]["tool_use_id"] == "tu_1"
    assert session.messages[3].content[0]["type"] == "text"


def test_tool_error_surfaces_to_llm_and_continues():
    llm = _ScriptedLlm(queue=[
        _tool_use("tu_1", "check_order_status", {"order_id": 999}),
        _text("Sorry, that order doesn't exist."),
    ])
    executor = _StubExecutor({
        "check_order_status": RuntimeError("order 999 not found"),
    })
    engine = ChatEngine(llm=llm, executor=executor)
    session = ChatSession.new(user_id=7)

    result = engine.run(session, "status of order 999?")

    assert result.iterations == 2
    assert result.tool_calls[0].error == "order 999 not found"
    assert result.tool_calls[0].output == {}
    # tool_result block must be marked as error
    tool_result_block = session.messages[2].content[0]
    assert tool_result_block["is_error"] is True


def test_multi_tool_chain():
    llm = _ScriptedLlm(queue=[
        _tool_use("tu_1", "search_menu", {"query": "noodles"}),
        _tool_use("tu_2", "get_recommendations", {"limit": 3}),
        _text("Here are options + recs."),
    ])
    executor = _StubExecutor({
        "search_menu": {"count": 0, "results": []},
        "get_recommendations": {"strategy": "popularity_fallback", "items": []},
    })
    engine = ChatEngine(llm=llm, executor=executor)
    session = ChatSession.new(user_id=7)

    result = engine.run(session, "help me decide")

    assert result.iterations == 3
    assert [tc.tool for tc in result.tool_calls] == ["search_menu", "get_recommendations"]


def test_max_iterations_raises():
    # LLM keeps asking for tool calls forever
    queue = [_tool_use(f"tu_{i}", "search_menu", {"query": "x"}) for i in range(10)]
    llm = _ScriptedLlm(queue=queue)
    executor = _StubExecutor({"search_menu": {"count": 0, "results": []}})
    engine = ChatEngine(llm=llm, executor=executor, max_iterations=3)
    session = ChatSession.new(user_id=7)

    with pytest.raises(ChatMaxIterations):
        engine.run(session, "loop forever")


def test_session_continuity_across_turns():
    llm = _ScriptedLlm(queue=[
        _text("Got it, anything else?"),
        _text("Bye."),
    ])
    engine = ChatEngine(llm=llm, executor=_StubExecutor({}))
    session = ChatSession.new(user_id=7)

    engine.run(session, "hello")
    engine.run(session, "thanks")

    # LLM should have seen the growing history on turn 2
    second_call_messages = llm.calls[1]["messages"]
    roles = [m["role"] for m in second_call_messages]
    assert roles == ["user", "assistant", "user"]
    assert second_call_messages[0]["content"][0]["text"] == "hello"
    assert second_call_messages[2]["content"][0]["text"] == "thanks"


def test_system_prompt_and_tools_passed():
    llm = _ScriptedLlm(queue=[_text("ok")])
    engine = ChatEngine(llm=llm, executor=_StubExecutor({}))
    session = ChatSession.new(user_id=7)

    engine.run(session, "hi")

    call = llm.calls[0]
    assert "food ordering" in call["system"].lower()
    tool_names = {t["name"] for t in call["tools"]}
    assert tool_names == {
        "search_menu", "create_order_draft",
        "check_order_status", "get_recommendations",
    }
