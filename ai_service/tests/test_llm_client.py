"""Tests for the LLM client abstraction and tool format conversion."""

from __future__ import annotations

from fos_ai.services.llm_client import (
    TextOnlyResult,
    ToolCallResult,
    _anthropic_tools_to_openai,
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
