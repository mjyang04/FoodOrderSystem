"""Shared dataclasses for eval runners."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RunResult:
    """One suite's eval outcome.

    ``failures`` carries per-case records explaining why a case did not meet
    its gate — used by the markdown report to surface top regressions.
    """

    suite: str
    n_cases: int
    metrics: dict[str, float] = field(default_factory=dict)
    failures: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "suite": self.suite,
            "n_cases": self.n_cases,
            "metrics": dict(self.metrics),
            "failures": list(self.failures),
        }
