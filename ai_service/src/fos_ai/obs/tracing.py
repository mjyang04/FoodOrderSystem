"""OpenTelemetry tracing init + @trace_llm_call decorator.

Wraps the synchronous LLM-client methods with a span whose attributes follow
the OTel ``gen_ai.*`` semantic conventions where practical. On top of the span
we also push the same measurements into :mod:`fos_ai.obs.metrics` so the
``/ai/stats`` aggregator sees every call even when no collector is attached.

The decorator is transparent: it returns the wrapped callable's return value
unchanged (or re-raises the original exception). Generator-returning methods
are wrapped by a helper that iterates the generator inside the span.
"""

from __future__ import annotations

import functools
import inspect
import logging
import time
from typing import Any, Callable, Iterator

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
)

from fos_ai.obs.metrics import metrics

logger = logging.getLogger(__name__)


# USD per 1M tokens (input, output). Unknown models cost nothing and log once.
COST_TABLE: dict[str, tuple[float, float]] = {
    "claude-haiku-4-5-20251001": (0.80, 4.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-opus-4-6": (15.00, 75.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
}

_UNKNOWN_MODELS_LOGGED: set[str] = set()
_TRACING_INITIALIZED: bool = False


def init_tracing(
    service_name: str = "fos_ai",
    otlp_endpoint: str | None = None,
    console: bool = True,
) -> None:
    """Install a ``TracerProvider`` with the requested exporters.

    Safe to call multiple times — subsequent calls are no-ops to avoid
    stacking processors (tests re-import the module repeatedly).
    """
    global _TRACING_INITIALIZED
    if _TRACING_INITIALIZED:
        return

    try:
        from fos_ai import __version__ as _fos_version  # type: ignore[attr-defined]
    except ImportError:
        _fos_version = "0.1.0"

    resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": _fos_version,
        }
    )
    provider = TracerProvider(resource=resource)

    if console:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    if otlp_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter,
            )

            provider.add_span_processor(
                BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint))
            )
            logger.info("OTLP exporter configured at %s", otlp_endpoint)
        except Exception:  # noqa: BLE001
            logger.warning(
                "OTLP exporter init failed at %s — continuing without OTLP",
                otlp_endpoint,
                exc_info=True,
            )

    trace.set_tracer_provider(provider)
    _TRACING_INITIALIZED = True
    logger.info(
        "Tracing initialised — service=%s console=%s otlp=%s",
        service_name,
        console,
        bool(otlp_endpoint),
    )


def _estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    """Look up the model in :data:`COST_TABLE` and price the call.

    Unknown models return 0.0 and emit a single DEBUG log line so tests and
    production aren't spammed with repeated warnings.
    """
    pricing = COST_TABLE.get(model)
    if pricing is None:
        if model and model not in _UNKNOWN_MODELS_LOGGED:
            _UNKNOWN_MODELS_LOGGED.add(model)
            logger.debug("No price entry for model %r — cost_usd=0", model)
        return 0.0
    in_price, out_price = pricing
    return (input_tokens / 1_000_000.0) * in_price + (
        output_tokens / 1_000_000.0
    ) * out_price


def _extract_usage(response: Any) -> dict[str, Any]:
    """Best-effort extraction of token / cache / stop-reason fields.

    Handles:
        * Anthropic ``Message`` (has ``.usage``, ``.stop_reason``)
        * OpenAI ``ChatCompletion`` (has ``.usage`` with different attr names)
        * Our dataclass return types (``MessagesResult``, ``ToolCallResult``,
          ``TextOnlyResult``) — these do not carry usage; we return zeros.
    """
    out = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "stop_reason": "",
        "tool_calls_count": 0,
    }
    if response is None:
        return out

    usage = getattr(response, "usage", None)
    if usage is not None:
        # Anthropic: input_tokens / output_tokens
        it = getattr(usage, "input_tokens", None)
        ot = getattr(usage, "output_tokens", None)
        # OpenAI: prompt_tokens / completion_tokens
        if it is None:
            it = getattr(usage, "prompt_tokens", 0)
        if ot is None:
            ot = getattr(usage, "completion_tokens", 0)
        out["input_tokens"] = int(it or 0)
        out["output_tokens"] = int(ot or 0)
        out["cache_read_tokens"] = int(
            getattr(usage, "cache_read_input_tokens", 0) or 0
        )

    stop = getattr(response, "stop_reason", "")
    if stop:
        out["stop_reason"] = str(stop)

    # MessagesResult-style dataclasses: count tool_use blocks on content list.
    content = getattr(response, "content", None)
    if isinstance(content, list):
        out["tool_calls_count"] = sum(
            1
            for b in content
            if isinstance(b, dict) and b.get("type") == "tool_use"
        )

    return out


def _record(
    span: Any,
    *,
    provider: str,
    model: str,
    usage: dict[str, Any],
    latency_ms: float,
    error: str | None = None,
) -> None:
    """Stamp the span and forward the same numbers to :mod:`metrics`."""
    input_tokens = int(usage.get("input_tokens", 0) or 0)
    output_tokens = int(usage.get("output_tokens", 0) or 0)
    cache_read = int(usage.get("cache_read_tokens", 0) or 0)
    cost = _estimate_cost_usd(model, input_tokens, output_tokens)
    cache_hit = cache_read > 0

    if span is not None:
        span.set_attribute("gen_ai.system", provider)
        if model:
            span.set_attribute("gen_ai.request.model", model)
        if input_tokens:
            span.set_attribute("gen_ai.usage.input_tokens", input_tokens)
        if output_tokens:
            span.set_attribute("gen_ai.usage.output_tokens", output_tokens)
        span.set_attribute("gen_ai.usage.cost_usd", round(cost, 6))
        span.set_attribute("gen_ai.latency_ms", round(latency_ms, 3))
        stop_reason = usage.get("stop_reason")
        if stop_reason:
            span.set_attribute("gen_ai.stop_reason", stop_reason)
        tool_calls = int(usage.get("tool_calls_count", 0) or 0)
        if tool_calls:
            span.set_attribute("gen_ai.tool_calls_count", tool_calls)
        span.set_attribute("gen_ai.cache.read_tokens", cache_read)
        span.set_attribute("gen_ai.cache.hit", cache_hit)
        if error:
            span.set_attribute("gen_ai.error", error)

    metrics.record_llm_call(
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        cost_usd=cost,
        cache_read_tokens=cache_read,
        cache_hit=cache_hit,
        error=error,
    )


def trace_llm_call(
    provider: str | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorate an LLM client method so every call produces a span + metric.

    The wrapper covers both regular methods (which return a dataclass) and
    generator methods like ``messages_stream``. For generators we iterate the
    stream inside the span, yield each event downstream, and only close the
    span when the final ``message_stop`` event has been emitted.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        method_name = func.__name__
        is_gen = inspect.isgeneratorfunction(func)
        span_name = f"llm.{provider or 'unknown'}.{method_name}"

        if is_gen:

            @functools.wraps(func)
            def gen_wrapper(self: Any, *args: Any, **kwargs: Any) -> Iterator[Any]:
                resolved_provider = provider or _guess_provider(self)
                model = getattr(self, "_model", "") or ""
                tracer = trace.get_tracer("fos_ai.llm")
                start = time.perf_counter()
                usage: dict[str, Any] = {}
                error_msg: str | None = None
                with tracer.start_as_current_span(span_name) as span:
                    try:
                        for event in func(self, *args, **kwargs):
                            etype = getattr(event, "type", "")
                            payload = getattr(event, "payload", None) or {}
                            if etype == "message_stop" and isinstance(payload, dict):
                                usage = {
                                    "stop_reason": payload.get("stop_reason", ""),
                                    "tool_calls_count": sum(
                                        1
                                        for b in payload.get("content", []) or []
                                        if isinstance(b, dict)
                                        and b.get("type") == "tool_use"
                                    ),
                                }
                            yield event
                    except Exception as exc:  # noqa: BLE001
                        error_msg = f"{type(exc).__name__}: {exc}"
                        if span is not None:
                            span.record_exception(exc)
                        raise
                    finally:
                        latency_ms = (time.perf_counter() - start) * 1000.0
                        _record(
                            span,
                            provider=resolved_provider,
                            model=model,
                            usage=usage,
                            latency_ms=latency_ms,
                            error=error_msg,
                        )

            return gen_wrapper

        @functools.wraps(func)
        def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            resolved_provider = provider or _guess_provider(self)
            model = getattr(self, "_model", "") or ""
            tracer = trace.get_tracer("fos_ai.llm")
            start = time.perf_counter()
            error_msg: str | None = None
            with tracer.start_as_current_span(span_name) as span:
                try:
                    result = func(self, *args, **kwargs)
                except Exception as exc:  # noqa: BLE001
                    error_msg = f"{type(exc).__name__}: {exc}"
                    if span is not None:
                        span.record_exception(exc)
                    latency_ms = (time.perf_counter() - start) * 1000.0
                    _record(
                        span,
                        provider=resolved_provider,
                        model=model,
                        usage={},
                        latency_ms=latency_ms,
                        error=error_msg,
                    )
                    raise

                latency_ms = (time.perf_counter() - start) * 1000.0
                usage = _extract_usage(result)
                _record(
                    span,
                    provider=resolved_provider,
                    model=model,
                    usage=usage,
                    latency_ms=latency_ms,
                    error=None,
                )
                return result

        return wrapper

    return decorator


def _guess_provider(instance: Any) -> str:
    """Infer the provider name from the class when decorator omits it."""
    cls_name = type(instance).__name__.lower()
    if "anthropic" in cls_name:
        return "anthropic"
    if "openai" in cls_name:
        return "openai"
    return "unknown"
