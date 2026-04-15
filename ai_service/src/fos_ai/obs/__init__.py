"""Observability package — OpenTelemetry tracing + metrics aggregator.

Public surface:
    - ``init_tracing``: wire TracerProvider + exporters during app startup.
    - ``trace_llm_call``: decorator for LLM client methods.
    - ``metrics``: module-level singleton aggregator consumed by /ai/stats.
"""

from __future__ import annotations

from fos_ai.obs.metrics import LlmCallRecord, Metrics, metrics
from fos_ai.obs.tracing import COST_TABLE, init_tracing, trace_llm_call

__all__ = [
    "init_tracing",
    "trace_llm_call",
    "metrics",
    "Metrics",
    "LlmCallRecord",
    "COST_TABLE",
]
