"""LLM-as-judge metric — 0-5 score with majority vote across samples.

The judge never runs in CI with a real provider; pytest wires a stubbed
``LlmClient`` and the CLI runner does the same unless ``EVAL_USE_REAL_LLM=1``
is set. The helper therefore focuses on parsing discipline and vote
aggregation rather than prompt tuning.
"""

from __future__ import annotations

import json
import logging
import re
from collections import Counter
from typing import Any

from fos_ai.services.llm_client import LlmClient, TextOnlyResult, ToolCallResult

logger = logging.getLogger(__name__)

_JUDGE_SYSTEM = (
    "You are a strict evaluator. Given a chat transcript and a criteria "
    "statement, rate how well the assistant's final answer meets the "
    "criteria on an integer scale from 0 (unusable) to 5 (excellent). "
    "Respond ONLY with JSON: {\"score\": <int 0-5>, \"rationale\": \"<1 "
    "short sentence>\"}."
)

_SCORE_RE = re.compile(r'"score"\s*:\s*(\d+)')
_RATIONALE_RE = re.compile(r'"rationale"\s*:\s*"([^"]*)"')


def _format_transcript(conversation: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for turn in conversation:
        role = turn.get("role", "?")
        content = turn.get("content", "")
        if isinstance(content, list):
            parts: list[str] = []
            for b in content:
                if b.get("type") == "text":
                    parts.append(b.get("text", ""))
                elif b.get("type") == "tool_use":
                    parts.append(f"<tool_use name={b.get('name')!r}>")
                elif b.get("type") == "tool_result":
                    parts.append("<tool_result>")
            text = " | ".join(p for p in parts if p)
        else:
            text = str(content)
        lines.append(f"{role.upper()}: {text}")
    return "\n".join(lines)


def _parse_score(raw: str) -> tuple[int | None, str]:
    """Extract score / rationale from JSON-ish LLM output. Lenient by design."""
    raw = (raw or "").strip()
    if not raw:
        return None, ""
    # Try strict JSON first
    try:
        data = json.loads(raw)
        score = int(data.get("score"))
        rationale = str(data.get("rationale", ""))
        if 0 <= score <= 5:
            return score, rationale
    except (ValueError, TypeError, json.JSONDecodeError):
        pass
    # Fall back to regex
    m = _SCORE_RE.search(raw)
    if not m:
        return None, ""
    try:
        score = int(m.group(1))
    except ValueError:
        return None, ""
    if score < 0 or score > 5:
        return None, ""
    rm = _RATIONALE_RE.search(raw)
    rationale = rm.group(1) if rm else ""
    return score, rationale


def _majority(scores: list[int]) -> int:
    """Mode; tie-break by highest score (more optimistic judges win)."""
    if not scores:
        return 0
    counts = Counter(scores)
    top = max(counts.values())
    winners = [s for s, c in counts.items() if c == top]
    return max(winners)


def llm_as_judge(
    conversation: list[dict[str, Any]],
    criteria: str,
    llm: LlmClient,
    samples: int = 3,
) -> dict[str, Any]:
    """Run the judge ``samples`` times and return aggregated result.

    Returns::

        {"score": int, "votes": [int, ...], "rationales": [str, ...],
         "parse_failures": int}

    Any sample whose output cannot be parsed into a 0-5 integer is counted
    in ``parse_failures`` and excluded from the vote. If every sample fails
    to parse, ``score`` is 0 and ``votes`` is empty.
    """
    if samples <= 0:
        raise ValueError("samples must be >= 1")

    transcript = _format_transcript(conversation)
    user_msg = (
        f"CRITERIA:\n{criteria.strip()}\n\n"
        f"TRANSCRIPT:\n{transcript}\n\n"
        "Score the assistant's final answer against the criteria."
    )

    votes: list[int] = []
    rationales: list[str] = []
    parse_failures = 0
    for _ in range(samples):
        try:
            result = llm.tool_call(
                system=_JUDGE_SYSTEM,
                user=user_msg,
                tools=[],
                max_tokens=256,
            )
        except Exception as exc:  # noqa: BLE001 — a bad judge call is not fatal
            logger.warning("judge llm call failed: %s", exc)
            parse_failures += 1
            continue

        if isinstance(result, ToolCallResult):
            raw = result.raw_text
        elif isinstance(result, TextOnlyResult):
            raw = result.text
        else:
            raw = str(result)

        score, rationale = _parse_score(raw)
        if score is None:
            parse_failures += 1
            continue
        votes.append(score)
        rationales.append(rationale)

    return {
        "score": _majority(votes),
        "votes": votes,
        "rationales": rationales,
        "parse_failures": parse_failures,
    }
