"""CLI entry point for the eval harness — ``python -m fos_ai.eval.run``.

Builds the real corpus / embedder (same as the pytest fixtures) and walks
the requested suites. For suites that would otherwise require a live LLM
(parse, chat) the CLI supplies a stubbed client by default. Set
``EVAL_USE_REAL_LLM=1`` to route parse through a real provider; chat
scripts always run against the scripted stub for reproducibility.

Markdown report is written to ``--out`` (default
``eval/reports/<YYYY-MM-DD>.md``). Exit code is 0 on pass, 1 if any
quality gate fails.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from fos_ai.eval import run_chat, run_parse, run_recommend, run_search

logger = logging.getLogger(__name__)

# Same repo layout assumption as ``fos_ai.eval.__init__``.
_AI_SERVICE_DIR = Path(__file__).resolve().parents[3]
_EVAL_DIR = _AI_SERVICE_DIR / "eval"
_DATA_DIR = _EVAL_DIR / "data"
_REPORTS_DIR = _EVAL_DIR / "reports"

# Gates mirror the pytest thresholds so `python -m fos_ai.eval.run` and
# `pytest -m eval` reject the same regressions.
_GATES: dict[str, dict[str, float]] = {
    "search": {"hit_at_5": 0.80, "mrr": 0.60, "ndcg_at_5": 0.65},
    "recommend": {"pass_rate": 1.0},
    "parse": {"restaurant_match": 1.0, "confidence_pass_rate": 0.9},
    "chat": {"tool_plan_match": 0.80, "text_contains_rate": 0.80},
}


def _load_cases(name: str) -> list[dict[str, Any]]:
    return json.loads((_DATA_DIR / name).read_text())


def _build_ctx() -> dict[str, Any]:
    # Import test-side conftest helpers for the deterministic menu.
    from eval.conftest import build_eval_menu  # type: ignore

    from fos_ai.ml.corpus import build_corpus
    from fos_ai.ml.embedding import Embedder

    menu = build_eval_menu()
    embedder = Embedder()
    corpus = build_corpus(menu, embedder)
    return {"menu": menu, "embedder": embedder, "corpus": corpus}


def _git_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=False, cwd=_AI_SERVICE_DIR,
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except OSError:
        pass
    return "unknown"


def _gate_ok(suite: str, metrics: dict[str, float]) -> tuple[bool, list[str]]:
    gates = _GATES.get(suite, {})
    failed: list[str] = []
    for key, minimum in gates.items():
        val = metrics.get(key, 0.0)
        if val < minimum:
            failed.append(f"{key}={val:.3f} < gate {minimum:.3f}")
    return (not failed), failed


def _render_report(
    results: list[dict[str, Any]],
    *,
    sha: str,
    timestamp: str,
    all_pass: bool,
) -> str:
    lines: list[str] = []
    lines.append(f"# Eval Report — {timestamp}")
    lines.append("")
    lines.append(f"- Git SHA: `{sha}`")
    lines.append(f"- Overall: **{'PASS' if all_pass else 'FAIL'}**")
    lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append("| Suite | Cases | Metrics | Gate |")
    lines.append("|-------|-------|---------|------|")
    for r in results:
        metric_str = ", ".join(f"{k}={v:.3f}" for k, v in r["metrics"].items())
        gate_str = "pass" if r["gate_ok"] else "FAIL"
        lines.append(f"| {r['suite']} | {r['n_cases']} | {metric_str} | {gate_str} |")
    lines.append("")

    for r in results:
        lines.append(f"## {r['suite']}")
        lines.append("")
        if r["gate_failures"]:
            lines.append("Gate violations:")
            for gf in r["gate_failures"]:
                lines.append(f"- {gf}")
            lines.append("")
        failures = r["failures"]
        if failures:
            lines.append(f"Top {min(5, len(failures))} failing cases:")
            for f in failures[:5]:
                lines.append(f"- `{json.dumps(f, ensure_ascii=False)}`")
        else:
            lines.append("_No per-case failures._")
        lines.append("")
    return "\n".join(lines) + "\n"


def _run_suite(suite: str, ctx: dict[str, Any]) -> dict[str, Any]:
    if suite == "search":
        r = run_search(_load_cases("search_cases.json"), ctx)
    elif suite == "recommend":
        r = run_recommend(_load_cases("recommend_cases.json"), ctx)
    elif suite == "parse":
        r = run_parse(_load_cases("parse_cases.json"), ctx)
    elif suite == "chat":
        r = run_chat(_load_cases("chat_cases.json"), ctx)
    else:
        raise ValueError(f"unknown suite: {suite}")
    gate_ok, gate_failures = _gate_ok(suite, r.metrics)
    rec = r.as_dict()
    rec["gate_ok"] = gate_ok
    rec["gate_failures"] = gate_failures
    return rec


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fos_ai.eval.run")
    parser.add_argument(
        "--suite",
        choices=["all", "search", "recommend", "parse", "chat"],
        default="all",
    )
    parser.add_argument(
        "--out", type=Path, default=None,
        help="Report path (default eval/reports/<date>.md)",
    )
    parser.add_argument(
        "--quiet", action="store_true",
        help="Suppress stdout summary (CI sometimes prefers file only).",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s %(name)s %(message)s",
    )

    if args.suite == "all":
        suites = ["search", "recommend", "parse", "chat"]
    else:
        suites = [args.suite]

    ctx = _build_ctx()
    results = [_run_suite(s, ctx) for s in suites]
    all_pass = all(r["gate_ok"] for r in results)

    timestamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sha = _git_sha()
    report = _render_report(results, sha=sha, timestamp=timestamp, all_pass=all_pass)

    out_path = args.out or _REPORTS_DIR / f"{dt.date.today().isoformat()}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")

    if not args.quiet:
        print(report)
        print(f"\nReport written to {out_path}")
        _ = os.environ.get("EVAL_USE_REAL_LLM")  # touch for future hook

    return 0 if all_pass else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
