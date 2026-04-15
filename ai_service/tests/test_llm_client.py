"""Tests for the LLM client abstraction and tool format conversion."""

from __future__ import annotations

import json

from fos_ai.services.llm_client import (
    MessagesResult,
    StreamEvent,
    TextOnlyResult,
    ToolCallResult,
    _anthropic_messages_to_openai,
    _anthropic_tools_to_openai,
    _openai_finish_reason_to_anthropic,
)


def test_anthropic_to_openai_conversion():
    """Anthropic tool schema converts to OpenAI function-calling format."""
    anthropic_tools = [
        {
            "name": "create_order_draft",
            "description": "Create an order",
            "input_schema": {
                "type": "object",
                "properties": {
                    "restaurant_name": {"type": "string"},
                    "items": {"type": "array", "items": {"type": "object"}},
                },
                "required": ["restaurant_name", "items"],
            },
        }
    ]

    oai = _anthropic_tools_to_openai(anthropic_tools)

    assert len(oai) == 1
    assert oai[0]["type"] == "function"
    fn = oai[0]["function"]
    assert fn["name"] == "create_order_draft"
    assert fn["description"] == "Create an order"
    assert "properties" in fn["parameters"]
    assert "restaurant_name" in fn["parameters"]["properties"]


def test_tool_call_result_is_frozen():
    """ToolCallResult is immutable."""
    r = ToolCallResult(tool_name="test", tool_input={"a": 1})
    assert r.tool_name == "test"
    assert r.tool_input == {"a": 1}
    assert r.raw_text == ""


def test_text_only_result():
    """TextOnlyResult holds refusal text."""
    r = TextOnlyResult(text="I cannot parse this", stop_reason="end_turn")
    assert "cannot" in r.text
    assert r.stop_reason == "end_turn"


# ---------- MessagesResult helpers ----------

def test_messages_result_text_and_tool_uses_accessors():
    r = MessagesResult(
        content=[
            {"type": "text", "text": "Hello"},
            {"type": "tool_use", "id": "tu_1", "name": "search_menu", "input": {"q": "x"}},
            {"type": "text", "text": "world"},
        ],
        stop_reason="tool_use",
    )
    assert r.text == "Hello\nworld"
    assert len(r.tool_uses) == 1
    assert r.tool_uses[0]["name"] == "search_menu"


def test_stream_event_dataclass():
    e = StreamEvent(type="text_delta", payload={"delta": "hi"})
    assert e.type == "text_delta"
    assert e.payload["delta"] == "hi"


# ---------- message conversion ----------

def test_anthropic_messages_to_openai_plain_text():
    msgs = [
        {"role": "user", "content": [{"type": "text", "text": "hi"}]},
        {"role": "assistant", "content": [{"type": "text", "text": "hello"}]},
    ]
    out = _anthropic_messages_to_openai("You are helpful", msgs)
    assert out[0] == {"role": "system", "content": "You are helpful"}
    assert out[1] == {"role": "user", "content": "hi"}
    assert out[2] == {"role": "assistant", "content": "hello"}


def test_anthropic_messages_to_openai_tool_use_flow():
    msgs = [
        {"role": "user", "content": [{"type": "text", "text": "search noodles"}]},
        {"role": "assistant", "content": [
            {"type": "tool_use", "id": "tu_1", "name": "search_menu",
             "input": {"query": "noodles"}}
        ]},
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "tu_1",
             "content": [{"type": "text", "text": '{"count": 3}'}]}
        ]},
    ]
    out = _anthropic_messages_to_openai("", msgs)

    # user → assistant(tool_calls) → tool(role=tool)
    assert out[0]["role"] == "user"
    assert out[1]["role"] == "assistant"
    assert out[1]["tool_calls"][0]["id"] == "tu_1"
    assert out[1]["tool_calls"][0]["function"]["name"] == "search_menu"
    assert json.loads(out[1]["tool_calls"][0]["function"]["arguments"]) == {"query": "noodles"}
    assert out[2] == {
        "role": "tool", "tool_call_id": "tu_1",
        "content": '{"count": 3}',
    }


def test_anthropic_messages_string_content_passthrough():
    msgs = [{"role": "user", "content": "raw string"}]
    out = _anthropic_messages_to_openai("", msgs)
    assert out == [{"role": "user", "content": "raw string"}]


def test_openai_finish_reason_mapping():
    assert _openai_finish_reason_to_anthropic("stop") == "end_turn"
    assert _openai_finish_reason_to_anthropic("tool_calls") == "tool_use"
    assert _openai_finish_reason_to_anthropic("length") == "max_tokens"
    assert _openai_finish_reason_to_anthropic("") == ""
    assert _openai_finish_reason_to_anthropic("unknown") == "unknown"
