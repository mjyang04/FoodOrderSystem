"""TTL + LRU business-layer cache decorator.

Wraps pure read-only helpers — ``parser.parse_order`` (applied at the router
layer, small-menu deterministic inputs) and ``search.search`` (router layer,
query + limit + corpus signature). LLM calls themselves are NEVER cached by
this decorator; they are side-effectful network calls.

Thread-safe via a single ``threading.Lock``; mutation-safe via SHA-256 over a
``repr()`` of the args. If a key cannot be hashed (for example if an argument
is unhashable *and* also escapes ``repr``), the decorator falls through to
the underlying callable and logs a single WARNING so the caller notices.
"""

from __future__ import annotations

import functools
import hashlib
import logging
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Callable

from fos_ai.obs.metrics import metrics

logger = logging.getLogger(__name__)

# Swappable clock — tests inject a fake so TTL expiry is deterministic.
_clock: Callable[[], float] = time.monotonic


def _now() -> float:
    return _clock()


@dataclass(frozen=True)
class CacheInfo:
    hits: int
    misses: int
    maxsize: int
    currsize: int
    ttl_seconds: float


def cached(
    ttl_seconds: float,
    maxsize: int = 256,
    namespace: str = "",
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator factory producing a TTL + LRU cached version of a callable.

    Args:
        ttl_seconds: Time-to-live for each cached entry.
        maxsize: Maximum number of entries before LRU eviction kicks in.
        namespace: Label passed to :func:`metrics.record_cache` so the
            ``/ai/stats`` endpoint can report per-namespace hit rates.

    The wrapped callable gains ``cache_info()`` and ``cache_clear()`` helpers,
    mirroring :func:`functools.lru_cache`.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        store: "OrderedDict[str, tuple[float, Any]]" = OrderedDict()
        lock = threading.Lock()
        stats = {"hits": 0, "misses": 0}

        def _key(args: tuple[Any, ...], kwargs: dict[str, Any]) -> str | None:
            try:
                raw = repr(args) + repr(sorted(kwargs.items()))
            except Exception:  # noqa: BLE001
                return None
            return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            key = _key(args, kwargs)
            if key is None:
                logger.warning(
                    "cached(%s): unhashable args — bypassing cache", namespace
                )
                return func(*args, **kwargs)

            now = _now()
            with lock:
                entry = store.get(key)
                if entry is not None:
                    expires_at, value = entry
                    if expires_at > now:
                        store.move_to_end(key)
                        stats["hits"] += 1
                        metrics.record_cache(namespace, hit=True)
                        return value
                    # Expired — fall through to recompute
                    del store[key]

            # Miss — compute outside the lock so we don't hold it during I/O.
            value = func(*args, **kwargs)
            expires_at = _now() + ttl_seconds
            with lock:
                store[key] = (expires_at, value)
                store.move_to_end(key)
                while len(store) > maxsize:
                    store.popitem(last=False)
                stats["misses"] += 1
            metrics.record_cache(namespace, hit=False)
            return value

        def cache_clear() -> None:
            with lock:
                store.clear()
                stats["hits"] = 0
                stats["misses"] = 0

        def cache_info() -> CacheInfo:
            with lock:
                return CacheInfo(
                    hits=stats["hits"],
                    misses=stats["misses"],
                    maxsize=maxsize,
                    currsize=len(store),
                    ttl_seconds=ttl_seconds,
                )

        wrapper.cache_clear = cache_clear  # type: ignore[attr-defined]
        wrapper.cache_info = cache_info  # type: ignore[attr-defined]
        return wrapper

    return decorator


def _set_clock(fn: Callable[[], float]) -> None:
    """Test hook — replace the monotonic clock with a deterministic fake."""
    global _clock
    _clock = fn


def _reset_clock() -> None:
    """Test hook — restore the default monotonic clock."""
    global _clock
    _clock = time.monotonic
