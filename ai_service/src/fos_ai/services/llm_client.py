"""Unified LLM client abstraction supporting Anthropic and OpenAI SDKs.

Both providers expose tool-calling; this module normalises the interface so
``parser.py`` never imports either SDK directly.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

logger = logging.getLogger(__name__)


# ---- normalised result ----

@dataclass(frozen=True)
class ToolCallResult:
    """Provider-agnostic representation of an LLM tool-call response."""

    tool_name: str
    tool_input: dict[str, Any]
    raw_text: str = ""  # any non-tool text the model also emitted
    stop_reason: str = ""


@dataclass(frozen=True)
class TextOnlyResult:
    """The model replied with plain text instead of calling a tool."""

    text: str
    stop_reason: str = ""


# ---- protocol ----

class LlmClient(Protocol):
    """Minimal contract that parser.py programmes against."""

    def tool_call(
        self,
        *,
        system: str,
        user: str,
        tools: list[dict[str, Any]],
        max_tokens: int = 1024,
    ) -> ToolCallResult | TextOnlyResult: ...


# ---- Anthropic implementation ----

class AnthropicLlmClient:
    """Wraps ``anthropic.Anthropic`` for tool-calling."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-haiku-4-5-20251001",
        base_url: str | None = None,
    ) -> None:
        import anthropic

        kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = anthropic.Anthropic(**kwargs)
        self._model = model
        logger.info("AnthropicLlmClient ready — model=%s", model)

    def tool_call(
        self,
        *,
        system: str,
        user: str,
        tools: list[dict[str, Any]],
        max_tokens: int = 1024,
    ) -> ToolCallResult | TextOnlyResult:
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            tools=tools,
        )

        tool_block = None
        text_parts: list[str] = []
        for block in resp.content:
            if block.type == "tool_use":
                tool_block = block
            elif block.type == "text":
                text_parts.append(block.text)

        raw_text = "\n".join(text_parts)

        if tool_block is None:
            return TextOnlyResult(text=raw_text, stop_reason=resp.stop_reason or "")

        return ToolCallResult(
            tool_name=tool_block.name,
            tool_input=dict(tool_block.input) if tool_block.input else {},
            raw_text=raw_text,
            stop_reason=resp.stop_reason or "",
        )


# ---- OpenAI implementation ----

class OpenAILlmClient:
    """Wraps ``openai.OpenAI`` for tool-calling (works with any compatible endpoint)."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str | None = None,
    ) -> None:
        import openai

        kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = openai.OpenAI(**kwargs)
        self._model = model
        logger.info("OpenAILlmClient ready — model=%s", model)

    def tool_call(
        self,
        *,
        system: str,
        user: str,
        tools: list[dict[str, Any]],
        max_tokens: int = 1024,
    ) -> ToolCallResult | TextOnlyResult:
        # Convert Anthropic-style tool defs to OpenAI function-calling format
        oai_tools = _anthropic_tools_to_openai(tools)

        resp = self._client.chat.completions.create(
            model=self._model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            tools=oai_tools,
        )

        choice = resp.choices[0]
        message = choice.message

        # Check for tool calls
        if message.tool_calls:
            tc = message.tool_calls[0]  # take the first tool call
            try:
                tool_input = json.loads(tc.function.arguments)
            except (json.JSONDecodeError, TypeError):
                tool_input = {}
            return ToolCallResult(
                tool_name=tc.function.name,
                tool_input=tool_input,
                raw_text=message.content or "",
                stop_reason=choice.finish_reason or "",
            )

        return TextOnlyResult(
            text=message.content or "",
            stop_reason=choice.finish_reason or "",
        )


def _anthropic_tools_to_openai(
    tools: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Convert Anthropic tool schema to OpenAI function-calling schema.

    Anthropic format::

        {"name": "fn", "description": "...", "input_schema": {json-schema}}

    OpenAI format::

        {"type": "function", "function": {"name": "fn", "description": "...",
         "parameters": {json-schema}}}
    """
    oai: list[dict[str, Any]] = []
    for t in tools:
        oai.append({
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t.get("input_schema", {}),
            },
        })
    return oai


# ---- factory ----

def create_llm_client(
    provider: str,
    *,
    anthropic_api_key: str | None = None,
    anthropic_base_url: str | None = None,
    anthropic_model: str = "claude-haiku-4-5-20251001",
    openai_api_key: str | None = None,
    openai_base_url: str | None = None,
    openai_model: str = "gpt-4o-mini",
) -> LlmClient:
    """Instantiate the right client based on ``provider``."""
    if provider == "openai":
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        return OpenAILlmClient(
            api_key=openai_api_key,
            model=openai_model,
            base_url=openai_base_url,
        )

    if provider == "anthropic":
        if not anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic")
        return AnthropicLlmClient(
            api_key=anthropic_api_key,
            model=anthropic_model,
            base_url=anthropic_base_url,
        )

    raise ValueError(f"Unknown LLM provider: {provider!r}")
