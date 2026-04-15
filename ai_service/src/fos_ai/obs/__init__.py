"""Observability package — OpenTelemetry tracing + metrics + business cache.

Public surface:
    - ``init_tracing``: wire TracerProvider + exporters during app startup.
    - ``trace_llm_call``: decorator for LLM client methods.
    - ``metrics``: module-level singleton aggregator consumed by /ai/stats.
    - ``cached``: TTL + LRU cache decorator used by parse/search routers.
"""

from __future__ import annotations

from fos_ai.obs.cache import cached
from fos_ai.obs.metrics import LlmCallRecord, Metrics, metrics
from fos_ai.obs.tracing import COST_TABLE, init_tracing, trace_llm_call

__all__ = [
    "cached",
    "init_tracing",
    "trace_llm_call",
    "metrics",
    "Metrics",
    "LlmCallRecord",
    "COST_TABLE",
]
