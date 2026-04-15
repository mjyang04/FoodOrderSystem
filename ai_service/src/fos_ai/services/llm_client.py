"""Unified LLM client abstraction supporting Anthropic and OpenAI SDKs.

Both providers expose tool-calling; this module normalises the interface so
``parser.py`` never imports either SDK directly.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Iterator, Protocol

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


@dataclass(frozen=True)
class MessagesResult:
    """Multi-turn response — content blocks kept in Anthropic-native shape.

    Content blocks are one of:
      - {"type": "text", "text": "..."}
      - {"type": "tool_use", "id": "...", "name": "...", "input": {...}}
    """

    content: list[dict[str, Any]]
    stop_reason: str = ""

    @property
    def text(self) -> str:
        return "\n".join(
            b.get("text", "") for b in self.content if b.get("type") == "text"
        )

    @property
    def tool_uses(self) -> list[dict[str, Any]]:
        return [b for b in self.content if b.get("type") == "tool_use"]


@dataclass(frozen=True)
class StreamEvent:
    """Provider-agnostic streaming chunk.

    Types:
      - "text_delta": partial assistant text — payload = {"delta": "..."}
      - "message_stop": streaming finished — payload = {"stop_reason": "...", "content": [...]}
    """

    type: str
    payload: dict[str, Any] = field(default_factory=dict)


# ---- protocol ----

class LlmClient(Protocol):
    """Minimal contract that parser.py and chat_engine.py programme against."""

    def tool_call(
        self,
        *,
        system: str,
        user: str,
        tools: list[dict[str, Any]],
        max_tokens: int = 1024,
    ) -> ToolCallResult | TextOnlyResult: ...

    def messages(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        max_tokens: int = 1024,
    ) -> MessagesResult: ...

    def messages_stream(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        max_tokens: int = 1024,
    ) -> Iterator[StreamEvent]: ...


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

    def messages(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        max_tokens: int = 1024,
    ) -> MessagesResult:
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
            tools=tools,
        )
        content: list[dict[str, Any]] = []
        for block in resp.content:
            if block.type == "text":
                content.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                content.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": dict(block.input) if block.input else {},
                })
        return MessagesResult(content=content, stop_reason=resp.stop_reason or "")

    def messages_stream(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        max_tokens: int = 1024,
    ) -> Iterator[StreamEvent]:
        with self._client.messages.stream(
            model=self._model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
            tools=tools,
        ) as stream:
            for event in stream:
                etype = getattr(event, "type", "")
                if etype == "content_block_delta":
                    delta = getattr(event, "delta", None)
                    if delta is not None and getattr(delta, "type", "") == "text_delta":
                        yield StreamEvent(
                            type="text_delta",
                            payload={"delta": delta.text or ""},
                        )
            final = stream.get_final_message()
            content: list[dict[str, Any]] = []
            for block in final.content:
                if block.type == "text":
                    content.append({"type": "text", "text": block.text})
                elif block.type == "tool_use":
                    content.append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": dict(block.input) if block.input else {},
                    })
            yield StreamEvent(
                type="message_stop",
                payload={
                    "stop_reason": final.stop_reason or "",
                    "content": content,
                },
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

    def messages(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        max_tokens: int = 1024,
    ) -> MessagesResult:
        oai_tools = _anthropic_tools_to_openai(tools)
        oai_messages = _anthropic_messages_to_openai(system, messages)

        resp = self._client.chat.completions.create(
            model=self._model,
            max_tokens=max_tokens,
            messages=oai_messages,
            tools=oai_tools,
        )
        choice = resp.choices[0]
        msg = choice.message
        content: list[dict[str, Any]] = []

        if msg.content:
            content.append({"type": "text", "text": msg.content})
        for tc in msg.tool_calls or []:
            try:
                tool_input = json.loads(tc.function.arguments or "{}")
            except (json.JSONDecodeError, TypeError):
                tool_input = {}
            content.append({
                "type": "tool_use",
                "id": tc.id,
                "name": tc.function.name,
                "input": tool_input,
            })

        stop_reason = _openai_finish_reason_to_anthropic(choice.finish_reason or "")
        return MessagesResult(content=content, stop_reason=stop_reason)

    def messages_stream(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        max_tokens: int = 1024,
    ) -> Iterator[StreamEvent]:
        oai_tools = _anthropic_tools_to_openai(tools)
        oai_messages = _anthropic_messages_to_openai(system, messages)

        stream = self._client.chat.completions.create(
            model=self._model,
            max_tokens=max_tokens,
            messages=oai_messages,
            tools=oai_tools,
            stream=True,
        )

        text_buf: list[str] = []
        # tool call fragments keyed by index: {"id": str, "name": str, "args": str}
        tool_frags: dict[int, dict[str, str]] = {}
        finish_reason = ""

        for chunk in stream:
            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            delta = choice.delta

            if getattr(delta, "content", None):
                text_buf.append(delta.content)
                yield StreamEvent(
                    type="text_delta",
                    payload={"delta": delta.content},
                )

            for tc in getattr(delta, "tool_calls", None) or []:
                idx = getattr(tc, "index", 0)
                frag = tool_frags.setdefault(idx, {"id": "", "name": "", "args": ""})
                if getattr(tc, "id", None):
                    frag["id"] = tc.id
                fn = getattr(tc, "function", None)
                if fn is not None:
                    if getattr(fn, "name", None):
                        frag["name"] = fn.name
                    if getattr(fn, "arguments", None):
                        frag["args"] += fn.arguments

            if getattr(choice, "finish_reason", None):
                finish_reason = choice.finish_reason

        content: list[dict[str, Any]] = []
        if text_buf:
            content.append({"type": "text", "text": "".join(text_buf)})
        for idx in sorted(tool_frags):
            frag = tool_frags[idx]
            try:
                tool_input = json.loads(frag["args"] or "{}")
            except (json.JSONDecodeError, TypeError):
                tool_input = {}
            content.append({
                "type": "tool_use",
                "id": frag["id"],
                "name": frag["name"],
                "input": tool_input,
            })

        yield StreamEvent(
            type="message_stop",
            payload={
                "stop_reason": _openai_finish_reason_to_anthropic(finish_reason),
                "content": content,
            },
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


def _anthropic_messages_to_openai(
    system: str,
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Convert Anthropic-native message history to OpenAI chat-completions format.

    Anthropic assistant tool use block → OpenAI assistant.tool_calls
    Anthropic user tool_result block  → OpenAI role=tool message
    """
    out: list[dict[str, Any]] = []
    if system:
        out.append({"role": "system", "content": system})

    for msg in messages:
        role = msg.get("role")
        content = msg.get("content")

        # Plain user/assistant text (already a string)
        if isinstance(content, str):
            out.append({"role": role, "content": content})
            continue

        if not isinstance(content, list):
            continue

        if role == "user":
            # A user turn may contain plain text AND/OR tool_result blocks.
            text_parts: list[str] = []
            for block in content:
                btype = block.get("type")
                if btype == "text":
                    text_parts.append(block.get("text", ""))
                elif btype == "tool_result":
                    # Emit a separate role=tool message per tool_result
                    result_content = block.get("content")
                    if isinstance(result_content, list):
                        result_text = "\n".join(
                            c.get("text", "") for c in result_content
                            if c.get("type") == "text"
                        )
                    else:
                        result_text = str(result_content) if result_content is not None else ""
                    out.append({
                        "role": "tool",
                        "tool_call_id": block.get("tool_use_id", ""),
                        "content": result_text,
                    })
            if text_parts:
                out.append({"role": "user", "content": "\n".join(text_parts)})

        elif role == "assistant":
            text_parts = []
            tool_calls: list[dict[str, Any]] = []
            for block in content:
                btype = block.get("type")
                if btype == "text":
                    text_parts.append(block.get("text", ""))
                elif btype == "tool_use":
                    tool_calls.append({
                        "id": block.get("id", ""),
                        "type": "function",
                        "function": {
                            "name": block.get("name", ""),
                            "arguments": json.dumps(block.get("input", {})),
                        },
                    })
            assistant_msg: dict[str, Any] = {"role": "assistant"}
            if text_parts:
                assistant_msg["content"] = "\n".join(text_parts)
            if tool_calls:
                assistant_msg["tool_calls"] = tool_calls
            if "content" in assistant_msg or tool_calls:
                out.append(assistant_msg)

    return out


def _openai_finish_reason_to_anthropic(reason: str) -> str:
    """Map OpenAI finish_reason values to Anthropic-compatible stop_reason."""
    mapping = {
        "stop": "end_turn",
        "tool_calls": "tool_use",
        "length": "max_tokens",
        "content_filter": "stop_sequence",
    }
    return mapping.get(reason, reason)


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
