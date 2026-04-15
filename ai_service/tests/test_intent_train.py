"""Smoke-only tests for the LoRA training entry point.

These are **skipped by default** so CI never downloads a base model.
Set ``TEST_HEAVY_TRAINING=1`` and optionally ``SMOKE_STUB_MODEL=…`` to run.
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest


pytestmark = pytest.mark.skipif(
    os.environ.get("TEST_HEAVY_TRAINING") != "1",
    reason="Heavy training smoke disabled; set TEST_HEAVY_TRAINING=1 to enable.",
)


def test_train_help_exits_zero():
    """At minimum ``--help`` should exit 0 when deps are installed."""
    result = subprocess.run(
        [sys.executable, "-m", "fos_ai_training.intent.train", "--help"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "Qwen2.5-0.5B" in result.stdout or "--model" in result.stdout


def test_train_smoke_with_stub_model():
    stub = os.environ.get("SMOKE_STUB_MODEL")
    if not stub:
        pytest.skip("Set SMOKE_STUB_MODEL to a tiny HF model to run the smoke test")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "fos_ai_training.intent.train",
            "--smoke",
            "--no-save",
        ],
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert result.returncode == 0, result.stderr
