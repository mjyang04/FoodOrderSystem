"""Thread-safe, in-memory LLM + cache metrics aggregator.

Backs the ``GET /ai/stats`` endpoint. Keeps a bounded ring buffer of recent
LLM calls so memory usage stays flat even under sustained traffic.

All public methods are safe to call from multiple threads (FastAPI runs
handlers in a threadpool when the handler is synchronous).
"""

from __future__ import annotations

import logging
import math
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict

logger = logging.getLogger(__name__)

_MAX_RECORDS = 10_000


@dataclass(frozen=True)
class LlmCallRecord:
    """One immutable row in the aggregator's ring buffer."""

    ts: float
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    cost_usd: float
    cache_read_tokens: int = 0
    cache_hit: bool = False
    error: str | None = None


@dataclass
class _CacheCounter:
    hits: int = 0
    misses: int = 0


class Metrics:
    """In-memory aggregator feeding ``GET /ai/stats``.

    Bounded ring buffer of ``LlmCallRecord`` plus namespace-keyed cache
    counters. Reset-able for tests.
    """

    def __init__(self, max_records: int = _MAX_RECORDS) -> None:
        self._lock = threading.Lock()
        self._records: Deque[LlmCallRecord] = deque(maxlen=max_records)
        self._cache_counters: Dict[str, _CacheCounter] = {}

    # ---- LLM calls ----

    def record_llm_call(
        self,
        *,
        provider: str,
        model: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        latency_ms: float = 0.0,
        cost_usd: float = 0.0,
        cache_read_tokens: int = 0,
        cache_hit: bool = False,
        error: str | None = None,
        ts: float | None = None,
    ) -> None:
        record = LlmCallRecord(
            ts=ts if ts is not None else time.time(),
            provider=provider,
            model=model,
            input_tokens=int(input_tokens or 0),
            output_tokens=int(output_tokens or 0),
            latency_ms=float(latency_ms or 0.0),
            cost_usd=float(cost_usd or 0.0),
            cache_read_tokens=int(cache_read_tokens or 0),
            cache_hit=bool(cache_hit),
            error=error,
        )
        with self._lock:
            self._records.append(record)

    # ---- Cache counters ----

    def record_cache(self, namespace: str, hit: bool) -> None:
        with self._lock:
            counter = self._cache_counters.setdefault(namespace, _CacheCounter())
            if hit:
                counter.hits += 1
            else:
                counter.misses += 1

    # ---- Summary ----

    def summary(self, window_seconds: int = 86_400) -> dict:
        """Aggregate the last ``window_seconds`` of traffic.

        Returns a dict shaped for the ``/ai/stats`` response envelope.
        """
        now = time.time()
        cutoff = now - max(1, window_seconds)

        with self._lock:
            records = [r for r in self._records if r.ts >= cutoff]
            cache_snapshot = {
                ns: (c.hits, c.misses) for ns, c in self._cache_counters.items()
            }

        total_calls = len(records)
        total_input = sum(r.input_tokens for r in records)
        total_output = sum(r.output_tokens for r in records)
        total_cost = sum(r.cost_usd for r in records)
        latencies = [r.latency_ms for r in records]
        avg_latency = _mean(latencies)
        p95_latency = _percentile(latencies, 95.0)
        error_count = sum(1 for r in records if r.error)
        error_rate = error_count / total_calls if total_calls else 0.0

        by_provider: Dict[str, Dict[str, float | int]] = {}
        for r in records:
            bucket = by_provider.setdefault(
                r.provider,
                {"total_calls": 0, "total_cost_usd": 0.0, "_lat_sum": 0.0},
            )
            bucket["total_calls"] = int(bucket["total_calls"]) + 1
            bucket["total_cost_usd"] = float(bucket["total_cost_usd"]) + r.cost_usd
            bucket["_lat_sum"] = float(bucket["_lat_sum"]) + r.latency_ms

        provider_out: Dict[str, Dict[str, float | int]] = {}
        for provider, bucket in by_provider.items():
            n = int(bucket["total_calls"]) or 1
            provider_out[provider] = {
                "total_calls": int(bucket["total_calls"]),
                "total_cost_usd": round(float(bucket["total_cost_usd"]), 6),
                "avg_latency_ms": round(float(bucket["_lat_sum"]) / n, 3),
            }

        namespaces_out: Dict[str, Dict[str, float | int]] = {}
        total_hits = 0
        total_misses = 0
        for ns, (hits, misses) in cache_snapshot.items():
            total_hits += hits
            total_misses += misses
            attempts = hits + misses
            namespaces_out[ns] = {
                "hits": hits,
                "misses": misses,
                "hit_rate": round(hits / attempts, 4) if attempts else 0.0,
            }
        overall_attempts = total_hits + total_misses
        overall_hit_rate = (
            round(total_hits / overall_attempts, 4) if overall_attempts else 0.0
        )

        return {
            "window_seconds": window_seconds,
            "llm": {
                "total_calls": total_calls,
                "total_input_tokens": total_input,
                "total_output_tokens": total_output,
                "total_cost_usd": round(total_cost, 6),
                "avg_latency_ms": round(avg_latency, 3),
                "p95_latency_ms": round(p95_latency, 3),
                "error_rate": round(error_rate, 4),
                "by_provider": provider_out,
            },
            "cache": {
                "namespaces": namespaces_out,
                "overall_hit_rate": overall_hit_rate,
            },
        }

    def reset(self) -> None:
        """Clear all accumulated state — test helper only."""
        with self._lock:
            self._records.clear()
            self._cache_counters.clear()


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _percentile(values: list[float], pct: float) -> float:
    """Nearest-rank percentile (no interpolation) — matches common SRE tooling."""
    if not values:
        return 0.0
    ordered = sorted(values)
    k = max(1, math.ceil(pct / 100.0 * len(ordered)))
    return ordered[min(k - 1, len(ordered) - 1)]


# Module-level singleton consumed by trace_llm_call and /ai/stats.
metrics = Metrics()
