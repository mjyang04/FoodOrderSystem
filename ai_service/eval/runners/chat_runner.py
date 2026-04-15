"""Chat suite runner — scripted LLM drives the real ChatEngine tool loop.

Each case has a list of turns. For a turn:

- If ``expected_tool`` is non-null, the scripted LLM first returns a
  ``tool_use`` block naming that tool, then (after the executor emits a
  ``tool_result``) returns a final text block whose content must contain
  every substring in ``expected_text_contains``.
- If ``expected_tool`` is null, the scripted LLM answers with plain text
  in one shot.

Tool *execution* is also stubbed so the runner can operate without DB.
We measure:

- ``tool_plan_match``: 1.0 for each turn where the engine invoked the
  expected tool (or none, when expected_tool is null).
- ``text_contains_rate``: 1.0 for each turn whose final reply contains
  every expected_text_contains substring.

No real LLM API call ever happens — ``EVAL_USE_REAL_LLM`` is ignored here
because reproducibility of chat scripts trumps provider nondeterminism.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator

from fos_ai.schemas_chat import ChatSession
from fos_ai.services.chat_engine import ChatEngine
from fos_ai.services.chat_tools import ToolExecutor
from fos_ai.services.llm_client import MessagesResult, StreamEvent, TextOnlyResult, ToolCallResult

from eval.metrics.retrieval import mean
from eval.runners.base import RunResult

_SUITE = "chat"


@dataclass
class _ScriptedStep:
    """Assistant response for one LLM round-trip inside a turn."""

    kind: str  # "tool_use" | "text"
    tool_name: str = ""
    tool_input: dict[str, Any] = field(default_factory=dict)
    text: str = ""


class _ScriptedLlm:
    """Deterministic LLM stub that replays a pre-baked response sequence."""

    def __init__(self, steps: list[_ScriptedStep]) -> None:
        self._steps = list(steps)
        self._idx = 0

    # parser / judge path
    def tool_call(self, **_: Any) -> ToolCallResult | TextOnlyResult:
        step = self._next()
        if step.kind == "tool_use":
            return ToolCallResult(
                tool_name=step.tool_name,
                tool_input=step.tool_input,
                raw_text="",
                stop_reason="tool_use",
            )
        return TextOnlyResult(text=step.text, stop_reason="end_turn")

    # chat engine path
    def messages(self, **_: Any) -> MessagesResult:
        step = self._next()
        if step.kind == "tool_use":
            return MessagesResult(
                content=[{
                    "type": "tool_use",
                    "id": f"toolu_{self._idx}",
                    "name": step.tool_name,
                    "input": step.tool_input,
                }],
                stop_reason="tool_use",
            )
        return MessagesResult(
            content=[{"type": "text", "text": step.text}],
            stop_reason="end_turn",
        )

    def messages_stream(self, **_: Any) -> Iterator[StreamEvent]:  # pragma: no cover
        raise NotImplementedError("streaming not used in eval")

    def _next(self) -> _ScriptedStep:
        if self._idx >= len(self._steps):
            # Safety: if engine asks for one more response, emit terminal text.
            return _ScriptedStep(kind="text", text="")
        step = self._steps[self._idx]
        self._idx += 1
        return step


class _StubExecutor(ToolExecutor):
    """Returns a canned dict for every tool so the chat loop can close."""

    def __init__(self) -> None:  # no ctx needed
        pass

    def execute(  # type: ignore[override]
        self, tool_name: str, tool_input: dict[str, Any]
    ) -> dict[str, Any]:
        return {"tool": tool_name, "ok": True}


def _steps_for_turn(turn: dict[str, Any]) -> list[_ScriptedStep]:
    expected_tool = turn.get("expected_tool")
    final_text = " ".join(turn.get("expected_text_contains", []) or ["ok"])
    if expected_tool:
        return [
            _ScriptedStep(kind="tool_use", tool_name=expected_tool, tool_input={}),
            _ScriptedStep(kind="text", text=final_text),
        ]
    return [_ScriptedStep(kind="text", text=final_text)]


def run(cases: list[dict[str, Any]], ctx: dict[str, Any]) -> RunResult:
    plan_hits: list[float] = []
    text_hits: list[float] = []
    failures: list[dict[str, Any]] = []

    for case in cases:
        turns = case.get("turns", [])
        # One scripted LLM per case drives all turns.
        steps: list[_ScriptedStep] = []
        for t in turns:
            steps.extend(_steps_for_turn(t))
        llm = _ScriptedLlm(steps)
        executor = _StubExecutor()
        engine = ChatEngine(llm=llm, executor=executor)
        session = ChatSession.new(user_id=1)

        for turn_idx, turn in enumerate(turns):
            try:
                result = engine.run(session, turn["user"])
            except Exception as exc:  # noqa: BLE001 — one bad turn shouldn't kill suite
                failures.append({
                    "id": case["id"],
                    "turn": turn_idx,
                    "error": str(exc),
                })
                plan_hits.append(0.0)
                text_hits.append(0.0)
                continue

            # tool plan check
            expected_tool = turn.get("expected_tool")
            invoked = {c.tool for c in result.tool_calls}
            if expected_tool is None:
                plan_ok = len(invoked) == 0
            else:
                plan_ok = expected_tool in invoked
            plan_hits.append(1.0 if plan_ok else 0.0)

            # substring check
            expected_contains = turn.get("expected_text_contains", [])
            reply = result.reply or ""
            contains_ok = all(sub in reply for sub in expected_contains)
            text_hits.append(1.0 if contains_ok else 0.0)

            if not (plan_ok and contains_ok):
                failures.append({
                    "id": case["id"],
                    "turn": turn_idx,
                    "plan_ok": plan_ok,
                    "contains_ok": contains_ok,
                    "invoked": list(invoked),
                    "expected_tool": expected_tool,
                    "reply": reply[:160],
                })

    return RunResult(
        suite=_SUITE,
        n_cases=len(cases),
        metrics={
            "tool_plan_match": mean(plan_hits),
            "text_contains_rate": mean(text_hits),
        },
        failures=failures,
    )
