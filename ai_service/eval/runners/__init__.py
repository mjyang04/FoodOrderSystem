"""Eval runners — callable functions that execute a suite and return metrics.

Each runner is a pure function over ``(cases, ctx)`` so the same code path
backs both pytest test modules and the CLI report generator.
"""

from __future__ import annotations

from eval.runners.base import RunResult
from eval.runners.search_runner import run as run_search
from eval.runners.recommend_runner import run as run_recommend
from eval.runners.parse_runner import run as run_parse
from eval.runners.chat_runner import run as run_chat

__all__ = [
    "RunResult",
    "run_search",
    "run_recommend",
    "run_parse",
    "run_chat",
]
