"""Unit tests for the Metrics aggregator."""

from __future__ import annotations

import time

import pytest

from fos_ai.obs.metrics import Metrics


@pytest.fixture
def m() -> Metrics:
    return Metrics(max_records=1000)


def _emit_calls(agg: Metrics, n: int, *, provider: str = "anthropic") -> None:
    base = time.time()
    for i in range(n):
        agg.record_llm_call(
            provider=provider,
            model="claude-haiku-4-5-20251001",
            input_tokens=10,
            output_tokens=20,
            latency_ms=float(i + 1),
            cost_usd=0.001,
            ts=base - i * 0.001,  # all within 1 second
        )


def test_totals(m: Metrics):
    _emit_calls(m, 50)
    s = m.summary(60)
    assert s["llm"]["total_calls"] == 50
    assert s["llm"]["total_input_tokens"] == 500
    assert s["llm"]["total_output_tokens"] == 1000
    assert s["llm"]["total_cost_usd"] == pytest.approx(0.05, rel=1e-6)


def test_p95_and_avg(m: Metrics):
    _emit_calls(m, 50)
    s = m.summary(60)
    # latencies are 1..50ms → mean 25.5, p95 = nearest-rank ceil(0.95*50)=48 → 48ms
    assert s["llm"]["avg_latency_ms"] == pytest.approx(25.5, rel=1e-3)
    assert s["llm"]["p95_latency_ms"] == pytest.approx(48.0, rel=1e-3)


def test_by_provider_breakdown(m: Metrics):
    _emit_calls(m, 10, provider="anthropic")
    _emit_calls(m, 5, provider="openai")
    s = m.summary(60)
    assert s["llm"]["by_provider"]["anthropic"]["total_calls"] == 10
    assert s["llm"]["by_provider"]["openai"]["total_calls"] == 5


def test_error_rate(m: Metrics):
    _emit_calls(m, 8)
    m.record_llm_call(
        provider="anthropic",
        model="claude-haiku-4-5-20251001",
        input_tokens=1,
        output_tokens=1,
        latency_ms=5.0,
        cost_usd=0.0,
        error="RuntimeError: boom",
    )
    m.record_llm_call(
        provider="anthropic",
        model="claude-haiku-4-5-20251001",
        input_tokens=1,
        output_tokens=1,
        latency_ms=5.0,
        cost_usd=0.0,
        error="RuntimeError: boom",
    )
    s = m.summary(60)
    assert s["llm"]["total_calls"] == 10
    assert s["llm"]["error_rate"] == pytest.approx(0.2, rel=1e-3)


def test_cache_counters(m: Metrics):
    m.record_cache("parser.parse_order", hit=True)
    m.record_cache("parser.parse_order", hit=True)
    m.record_cache("parser.parse_order", hit=False)
    m.record_cache("search.search", hit=False)

    s = m.summary(60)
    ns = s["cache"]["namespaces"]
    assert ns["parser.parse_order"]["hits"] == 2
    assert ns["parser.parse_order"]["misses"] == 1
    assert ns["parser.parse_order"]["hit_rate"] == pytest.approx(2 / 3, rel=1e-3)
    assert ns["search.search"]["hits"] == 0
    assert ns["search.search"]["misses"] == 1
    assert s["cache"]["overall_hit_rate"] == pytest.approx(2 / 4, rel=1e-3)


def test_window_filters_old_records(m: Metrics):
    old = time.time() - 1000
    m.record_llm_call(
        provider="anthropic",
        model="claude-haiku-4-5-20251001",
        input_tokens=5,
        output_tokens=5,
        latency_ms=1.0,
        cost_usd=0.0,
        ts=old,
    )
    m.record_llm_call(
        provider="anthropic",
        model="claude-haiku-4-5-20251001",
        input_tokens=5,
        output_tokens=5,
        latency_ms=1.0,
        cost_usd=0.0,
    )
    s = m.summary(window_seconds=60)
    assert s["llm"]["total_calls"] == 1  # the older one is excluded


def test_reset_clears_state(m: Metrics):
    _emit_calls(m, 3)
    m.record_cache("x", hit=True)
    m.reset()
    s = m.summary(60)
    assert s["llm"]["total_calls"] == 0
    assert s["cache"]["namespaces"] == {}


def test_bounded_ring_buffer():
    agg = Metrics(max_records=10)
    _emit_calls(agg, 25)
    s = agg.summary(60)
    # Only the last 10 records survive — older ones were evicted.
    assert s["llm"]["total_calls"] == 10


def test_empty_summary_has_zeros():
    agg = Metrics()
    s = agg.summary(60)
    assert s["llm"]["total_calls"] == 0
    assert s["llm"]["avg_latency_ms"] == 0.0
    assert s["llm"]["p95_latency_ms"] == 0.0
    assert s["llm"]["error_rate"] == 0.0
    assert s["cache"]["overall_hit_rate"] == 0.0
