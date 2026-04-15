"""Unit tests for the @trace_llm_call decorator and cost estimator."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from fos_ai.obs.metrics import metrics
from fos_ai.obs.tracing import (
    COST_TABLE,
    _estimate_cost_usd,
    _extract_usage,
    trace_llm_call,
)


@dataclass
class _FakeUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0


@dataclass
class _FakeResp:
    usage: _FakeUsage
    stop_reason: str = "end_turn"
    content: list | None = None


class _FakeAnthropic:
    """Stand-in for AnthropicLlmClient — the decorator only reads ``_model``."""

    _model = "claude-haiku-4-5-20251001"

    @trace_llm_call(provider="anthropic")
    def tool_call(self, **kwargs):
        return _FakeResp(
            usage=_FakeUsage(input_tokens=100, output_tokens=200, cache_read_input_tokens=40),
            stop_reason="end_turn",
            content=[
                {"type": "text", "text": "hi"},
                {"type": "tool_use", "name": "foo", "input": {}},
            ],
        )

    @trace_llm_call(provider="anthropic")
    def broken(self):
        raise RuntimeError("boom")


@pytest.fixture(autouse=True)
def _reset_metrics():
    metrics.reset()
    yield
    metrics.reset()


def test_cost_table_known_model():
    # 1M input, 1M output of haiku
    cost = _estimate_cost_usd("claude-haiku-4-5-20251001", 1_000_000, 1_000_000)
    in_price, out_price = COST_TABLE["claude-haiku-4-5-20251001"]
    assert cost == pytest.approx(in_price + out_price)


def test_cost_table_unknown_model_is_zero():
    assert _estimate_cost_usd("no-such-model", 1000, 1000) == 0.0


def test_cost_prorates_correctly():
    # 500 input tokens at $0.80 per 1M = 0.80 * 500/1e6 = 0.0004
    cost = _estimate_cost_usd("claude-haiku-4-5-20251001", 500, 0)
    assert cost == pytest.approx(0.80 * 500 / 1_000_000.0)


def test_extract_usage_anthropic_like():
    resp = _FakeResp(
        usage=_FakeUsage(input_tokens=1, output_tokens=2, cache_read_input_tokens=3),
        stop_reason="tool_use",
        content=[{"type": "tool_use", "name": "x", "input": {}}],
    )
    u = _extract_usage(resp)
    assert u["input_tokens"] == 1
    assert u["output_tokens"] == 2
    assert u["cache_read_tokens"] == 3
    assert u["stop_reason"] == "tool_use"
    assert u["tool_calls_count"] == 1


def test_decorator_records_metric():
    client = _FakeAnthropic()
    result = client.tool_call()
    assert result.stop_reason == "end_turn"
    summary = metrics.summary(window_seconds=60)
    assert summary["llm"]["total_calls"] == 1
    assert summary["llm"]["total_input_tokens"] == 100
    assert summary["llm"]["total_output_tokens"] == 200
    assert summary["llm"]["by_provider"]["anthropic"]["total_calls"] == 1
    # Cost sanity: haiku input 0.80/1M, output 4.00/1M.
    expected = 100 * 0.80 / 1e6 + 200 * 4.0 / 1e6
    assert summary["llm"]["total_cost_usd"] == pytest.approx(expected, rel=1e-6)


def test_decorator_records_cache_hit():
    client = _FakeAnthropic()
    client.tool_call()
    summary = metrics.summary(window_seconds=60)
    # cache_read_input_tokens was 40 → cache_hit True → contributes to counts
    # but cache.record is for business cache only; the LLM call itself records
    # cache_hit on the record, not on the namespace counter. Verify via the
    # underlying record.
    rec = metrics._records[-1]  # noqa: SLF001
    assert rec.cache_read_tokens == 40
    assert rec.cache_hit is True


def test_decorator_records_exception():
    client = _FakeAnthropic()
    with pytest.raises(RuntimeError):
        client.broken()
    summary = metrics.summary(window_seconds=60)
    assert summary["llm"]["total_calls"] == 1
    assert summary["llm"]["error_rate"] == 1.0


def test_span_attributes_set(monkeypatch):
    """Verify the decorator calls set_attribute with the gen_ai.* names."""
    captured: dict[str, object] = {}

    class _FakeSpan:
        def set_attribute(self, k, v):
            captured[k] = v

        def record_exception(self, exc):
            captured["_exc"] = repr(exc)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    class _FakeTracer:
        def start_as_current_span(self, name):
            captured["_name"] = name
            return _FakeSpan()

    from fos_ai.obs import tracing as tracing_mod

    monkeypatch.setattr(tracing_mod.trace, "get_tracer", lambda _name: _FakeTracer())

    client = _FakeAnthropic()
    client.tool_call()

    assert captured["_name"] == "llm.anthropic.tool_call"
    assert captured["gen_ai.system"] == "anthropic"
    assert captured["gen_ai.request.model"] == "claude-haiku-4-5-20251001"
    assert captured["gen_ai.usage.input_tokens"] == 100
    assert captured["gen_ai.usage.output_tokens"] == 200
    assert captured["gen_ai.cache.read_tokens"] == 40
    assert captured["gen_ai.cache.hit"] is True
    assert captured["gen_ai.stop_reason"] == "end_turn"
    assert "gen_ai.latency_ms" in captured
    assert "gen_ai.usage.cost_usd" in captured
    assert captured["gen_ai.tool_calls_count"] == 1
