"""Pydantic + dataclass models for the conversational chat agent."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field

ChatRole = Literal["user", "assistant", "tool"]


# ---------- wire-level request / response ----------

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    session_id: str | None = None
    stream: bool = True


class ToolCallRecord(BaseModel):
    tool: str
    input: dict[str, Any]
    output: dict[str, Any]
    error: str | None = None


class ChatData(BaseModel):
    session_id: str
    reply: str
    tool_calls: list[ToolCallRecord] = []
    finish_reason: str = ""


class ChatResponse(BaseModel):
    success: bool = True
    data: ChatData


# ---------- SSE events ----------

class StreamEvent(BaseModel):
    """One SSE frame — serialised as `event: {event}\\ndata: {json}\\n\\n`."""

    event: Literal[
        "session", "tool_call", "tool_result", "text_delta", "done", "error"
    ]
    data: dict[str, Any]


# ---------- in-memory session ----------

@dataclass
class ChatMessage:
    """One turn in the conversation (user / assistant / tool result).

    Stored in provider-native message blocks so we can feed it straight back
    to the LLM without re-serialising. Anthropic expects `content` to be a
    list of blocks (text, tool_use, tool_result).
    """

    role: ChatRole
    content: list[dict[str, Any]]
    created_at: float = field(default_factory=time.time)


@dataclass
class ChatSession:
    """Per-user conversation state held in memory."""

    session_id: str
    user_id: int
    messages: list[ChatMessage] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_active_at: float = field(default_factory=time.time)

    @classmethod
    def new(cls, user_id: int) -> "ChatSession":
        return cls(session_id=str(uuid.uuid4()), user_id=user_id)

    def touch(self) -> None:
        self.last_active_at = time.time()

    def append(self, message: ChatMessage) -> None:
        self.messages.append(message)
        self.touch()
