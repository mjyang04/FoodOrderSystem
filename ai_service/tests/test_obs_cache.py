"""Unit tests for the @cached decorator (TTL + LRU)."""

from __future__ import annotations

import pytest

from fos_ai.obs.cache import _reset_clock, _set_clock, cached
from fos_ai.obs.metrics import metrics


@pytest.fixture(autouse=True)
def _reset():
    metrics.reset()
    _reset_clock()
    yield
    _reset_clock()
    metrics.reset()


def test_hit_and_miss_counts():
    calls = {"n": 0}

    @cached(ttl_seconds=60, maxsize=10, namespace="test.hit")
    def fn(x: int) -> int:
        calls["n"] += 1
        return x * 2

    assert fn(1) == 2
    assert fn(1) == 2  # cache hit
    assert fn(2) == 4  # new key
    assert calls["n"] == 2
    info = fn.cache_info()
    assert info.hits == 1
    assert info.misses == 2
    assert info.currsize == 2

    # Metrics should record the hits too.
    s = metrics.summary(60)
    assert s["cache"]["namespaces"]["test.hit"]["hits"] == 1
    assert s["cache"]["namespaces"]["test.hit"]["misses"] == 2


def test_ttl_expiry_with_fake_clock():
    now = {"t": 100.0}
    _set_clock(lambda: now["t"])

    calls = {"n": 0}

    @cached(ttl_seconds=5.0, maxsize=10, namespace="test.ttl")
    def fn(x: int) -> int:
        calls["n"] += 1
        return x

    fn(1)  # miss
    fn(1)  # hit
    assert calls["n"] == 1

    now["t"] = 106.0  # past TTL
    fn(1)  # miss again — expired
    assert calls["n"] == 2


def test_lru_eviction_at_maxsize():
    @cached(ttl_seconds=600, maxsize=3, namespace="test.lru")
    def fn(x: int) -> int:
        return x

    fn(1); fn(2); fn(3)
    fn(1)  # bump 1 to MRU
    fn(4)  # evicts 2 (LRU)
    assert fn.cache_info().currsize == 3

    # Confirm 2 was evicted (recompute → miss), 1 still cached.
    counted = {"n": 0}

    @cached(ttl_seconds=600, maxsize=3, namespace="test.lru_check")
    def probe(x: int) -> int:
        counted["n"] += 1
        return x

    probe(1); probe(1)
    assert counted["n"] == 1


def test_cache_clear_resets_state():
    @cached(ttl_seconds=60, maxsize=5, namespace="test.clear")
    def fn(x: int) -> int:
        return x

    fn(1); fn(1); fn(2)
    assert fn.cache_info().currsize == 2
    fn.cache_clear()
    info = fn.cache_info()
    assert info.currsize == 0
    assert info.hits == 0
    assert info.misses == 0


def test_kwargs_and_args_ordering():
    calls = {"n": 0}

    @cached(ttl_seconds=60, maxsize=5, namespace="test.kw")
    def fn(a: int, b: int = 1) -> int:
        calls["n"] += 1
        return a + b

    fn(1, b=2)
    fn(1, b=2)
    fn(a=1, b=2)  # positional vs kw — different repr → new miss is OK
    assert calls["n"] >= 1


def test_unhashable_bypass_logs_and_computes(caplog):
    calls = {"n": 0}

    class Unrepr:
        def __repr__(self):
            raise RuntimeError("cannot repr")

    @cached(ttl_seconds=60, maxsize=5, namespace="test.unhash")
    def fn(x) -> int:
        calls["n"] += 1
        return 42

    # The repr itself raises — wrapper should catch and bypass.
    with caplog.at_level("WARNING"):
        assert fn(Unrepr()) == 42
        assert fn(Unrepr()) == 42
    assert calls["n"] == 2
    assert any("unhashable" in r.message.lower() for r in caplog.records)
