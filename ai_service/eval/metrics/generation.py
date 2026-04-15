"""Generation quality metrics — exact match, per-field F1."""

from __future__ import annotations

from typing import Any, Mapping


def exact_match(
    pred: Mapping[str, Any],
    expected: Mapping[str, Any],
    fields: list[str],
) -> float:
    """Fraction of listed fields where str(pred[f]) == str(expected[f])."""
    if not fields:
        return 1.0
    hits = 0
    for f in fields:
        if str(pred.get(f)) == str(expected.get(f)):
            hits += 1
    return hits / len(fields)


def field_f1(
    pred: Mapping[str, Any],
    expected: Mapping[str, Any],
    fields: list[str],
) -> dict[str, float]:
    """Per-field exact match + aggregate mean.

    Each field is treated as a binary prediction: 1.0 if string-equal, else 0.0.
    The ``"_mean"`` key carries the unweighted mean across the requested fields.

    Returns a dict ``{field_name: 0.0 | 1.0, "_mean": float}``. An empty
    ``fields`` list returns ``{"_mean": 1.0}``.
    """
    if not fields:
        return {"_mean": 1.0}
    out: dict[str, float] = {}
    for f in fields:
        out[f] = 1.0 if str(pred.get(f)) == str(expected.get(f)) else 0.0
    out["_mean"] = sum(out.values()) / len(fields)
    return out
