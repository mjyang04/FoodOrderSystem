"""Tests for the synthetic intent-classifier dataset generator."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fos_ai_training.intent.data import (
    INTENT_LABELS,
    SLOT_VALUES,
    TEMPLATES,
    generate_dataset,
    load_jsonl,
    save_as_jsonl,
    split_dataset,
)


def test_9_canonical_labels():
    assert INTENT_LABELS == [
        "search",
        "recommend",
        "order",
        "status_check",
        "cancel",
        "rating",
        "menu_browse",
        "chitchat",
        "complaint",
    ]
    # Every label has at least 5 templates per the spec
    for label in INTENT_LABELS:
        assert label in TEMPLATES
        assert len(TEMPLATES[label]) >= 5, f"{label} needs >= 5 templates"


def test_each_class_has_chinese_templates():
    """At least 2 templates per class should contain CJK characters."""

    def _has_cjk(s: str) -> bool:
        return any("\u4e00" <= ch <= "\u9fff" for ch in s)

    for label in INTENT_LABELS:
        cjk_count = sum(1 for t in TEMPLATES[label] if _has_cjk(t))
        assert cjk_count >= 2, f"{label} needs >= 2 Chinese templates"


def test_each_class_has_english_templates():
    """And at least 2 pure-ASCII templates per class."""
    for label in INTENT_LABELS:
        ascii_count = sum(1 for t in TEMPLATES[label] if t.isascii())
        assert ascii_count >= 2, f"{label} needs >= 2 English templates"


def test_n_per_class_respected():
    ds = generate_dataset(n_per_class=10, seed=1)
    assert len(ds) == 9 * 10

    counts: dict[str, int] = {label: 0 for label in INTENT_LABELS}
    for row in ds:
        counts[row["label"]] += 1
    assert all(c == 10 for c in counts.values())


def test_default_size_approx_500():
    """Default n_per_class=56 gives ~504 samples, close to the 500 target."""
    ds = generate_dataset()
    assert len(ds) == 9 * 56


def test_determinism_same_seed_same_output():
    a = generate_dataset(n_per_class=20, seed=7)
    b = generate_dataset(n_per_class=20, seed=7)
    assert a == b


def test_different_seed_differs():
    a = generate_dataset(n_per_class=20, seed=1)
    b = generate_dataset(n_per_class=20, seed=2)
    # The lists should differ (order or contents); guaranteed because
    # the per-class loops call ``rng.choice`` off the same RNG.
    assert a != b


def test_no_empty_text_and_no_unfilled_placeholders():
    ds = generate_dataset(n_per_class=40, seed=3)
    for row in ds:
        assert row["text"].strip(), "empty text"
        assert "{" not in row["text"], f"unfilled placeholder in: {row['text']!r}"


def test_all_slot_values_reachable_over_large_sample():
    """Union of slot values seen across many rows ≈ full SLOT_VALUES."""
    ds = generate_dataset(n_per_class=100, seed=99)
    text_blob = " ".join(row["text"] for row in ds)
    # At least half of every slot's values should show up somewhere
    for slot, values in SLOT_VALUES.items():
        seen = sum(1 for v in values if v in text_blob)
        assert seen >= max(1, len(values) // 2), f"slot {slot!r} under-sampled"


def test_save_load_round_trip(tmp_path: Path):
    ds = generate_dataset(n_per_class=5, seed=0)
    path = tmp_path / "data.jsonl"
    save_as_jsonl(ds, path)
    assert path.exists()
    # Sanity: every line is valid JSON
    for line in path.read_text(encoding="utf-8").splitlines():
        assert line and json.loads(line)
    loaded = load_jsonl(path)
    assert loaded == ds


def test_split_dataset_deterministic_and_sized():
    ds = generate_dataset(n_per_class=20, seed=0)  # 180 rows
    train, val = split_dataset(ds, val_frac=0.1, seed=0)
    assert len(val) == 18
    assert len(train) == len(ds) - 18
    # Re-run → same split
    train2, val2 = split_dataset(ds, val_frac=0.1, seed=0)
    assert train == train2 and val == val2
    # Disjoint
    assert {id(r) for r in train}.isdisjoint({id(r) for r in val})


def test_split_dataset_rejects_bad_frac():
    ds = generate_dataset(n_per_class=5, seed=0)
    with pytest.raises(ValueError):
        split_dataset(ds, val_frac=0.0)
    with pytest.raises(ValueError):
        split_dataset(ds, val_frac=1.5)
