"""Multi-turn chat agent — ReAct-style tool loop on top of LlmClient.messages()."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from fos_ai.schemas_chat import ChatMessage, ChatSession, ToolCallRecord
from fos_ai.services.chat_tools import ToolExecutor, all_tools
from fos_ai.services.llm_client import LlmClient, MessagesResult

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are the assistant for a food ordering app.

You help users:
- Explore the menu via `search_menu`
- Get personalised recommendations via `get_recommendations`
- Build an order draft from free text via `create_order_draft`
- Check the status of their own past orders via `check_order_status`

Rules:
- Use tools when the user asks about menu, orders, or recommendations. Do not invent menu items.
- Draft orders are NOT placed — always tell the user they still need to confirm separately.
- If a tool fails or returns nothing useful, tell the user plainly; do not retry blindly.
- Keep replies short and direct; no filler phrases.
- Never reveal internal ids unless the user specifically asked for them.
"""

MAX_ITERATIONS = 5


class ChatMaxIterations(RuntimeError):
    """Hit the tool-loop safety cap."""


@dataclass
class ChatTurnResult:
    reply: str
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    finish_reason: str = ""
    iterations: int = 0


class ChatEngine:
    """Drives one user turn: LLM → optional tool loop → final assistant text."""

    def __init__(
        self,
        llm: LlmClient,
        executor: ToolExecutor,
        *,
        max_iterations: int = MAX_ITERATIONS,
        system_prompt: str = SYSTEM_PROMPT,
    ) -> None:
        self._llm = llm
        self._executor = executor
        self._max_iters = max_iterations
        self._system = system_prompt

    def run(self, session: ChatSession, user_text: str) -> ChatTurnResult:
        """Append the user message, loop LLM↔tools, return final text.

        Side effects: mutates `session.messages` with the new user turn,
        assistant turns, and tool_result turns.
        """
        # 1) record the user message
        session.append(ChatMessage(
            role="user",
            content=[{"type": "text", "text": user_text}],
        ))

        tool_records: list[ToolCallRecord] = []
        last_stop_reason = ""

        for iteration in range(1, self._max_iters + 1):
            result = self._llm.messages(
                system=self._system,
                messages=self._messages_for_llm(session),
                tools=all_tools(),
                max_tokens=1024,
            )
            last_stop_reason = result.stop_reason

            # record the assistant turn verbatim so the next LLM call sees it
            session.append(ChatMessage(role="assistant", content=list(result.content)))

            if not result.tool_uses:
                # Terminal: LLM produced plain text, we're done
                return ChatTurnResult(
                    reply=result.text,
                    tool_calls=tool_records,
                    finish_reason=result.stop_reason or "end_turn",
                    iterations=iteration,
                )

            # 2) execute each tool call, append results as one user turn
            tool_result_blocks: list[dict[str, Any]] = []
            for tu in result.tool_uses:
                name = tu.get("name", "")
                tool_input = tu.get("input", {}) or {}
                tu_id = tu.get("id", "")

                output, error = self._exec_single(name, tool_input)
                tool_records.append(ToolCallRecord(
                    tool=name,
                    input=tool_input,
                    output=output,
                    error=error,
                ))

                payload = error if error is not None else json.dumps(output)
                tool_result_blocks.append({
                    "type": "tool_result",
                    "tool_use_id": tu_id,
                    "content": [{"type": "text", "text": payload}],
                    "is_error": error is not None,
                })

            session.append(ChatMessage(role="user", content=tool_result_blocks))

        # safety cap
        raise ChatMaxIterations(
            f"tool loop exceeded {self._max_iters} iterations "
            f"(last stop_reason={last_stop_reason!r})"
        )

    # ---- helpers ----

    def _exec_single(
        self, name: str, tool_input: dict[str, Any]
    ) -> tuple[dict[str, Any], str | None]:
        try:
            return self._executor.execute(name, tool_input), None
        except Exception as exc:  # noqa: BLE001 — propagate to LLM as tool_result
            logger.info("tool %s errored: %s", name, exc)
            return {}, str(exc)

    @staticmethod
    def _messages_for_llm(session: ChatSession) -> list[dict[str, Any]]:
        """Project session into provider-facing message list."""
        return [{"role": m.role, "content": m.content} for m in session.messages]
