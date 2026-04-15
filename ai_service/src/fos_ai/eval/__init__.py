"""``fos_ai.eval`` — CLI-accessible re-export of the ``ai_service/eval`` suite.

Design choice (Sprint 6 Phase 3)
--------------------------------
The labelled data, fixtures, and pytest test modules live next to the
service code at ``ai_service/eval/`` so pytest can discover them without
installing the service package. The runners and metrics, however, want
to be reachable via ``python -m fos_ai.eval.run`` so CI and ad-hoc reports
share the same entry point as other service modules.

We therefore keep the test tree as the source of truth and this package
bootstraps ``sys.path`` at import time so ``eval.runners`` resolves to
``<repo>/ai_service/eval/runners``. The alternative — duplicating code in
both trees — was rejected because the test-side runners must stay live
for pytest fixtures, and a single source beats drift every time.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Repo layout: <ai_service>/src/fos_ai/eval/__init__.py -> go up 3 levels.
_AI_SERVICE_DIR = Path(__file__).resolve().parents[3]
_EVAL_PARENT = _AI_SERVICE_DIR  # contains the ``eval/`` test package

if str(_EVAL_PARENT) not in sys.path:
    sys.path.insert(0, str(_EVAL_PARENT))

from eval.runners import (  # noqa: E402  — after path mutation
    RunResult,
    run_chat,
    run_parse,
    run_recommend,
    run_search,
)

__all__ = [
    "RunResult",
    "run_chat",
    "run_parse",
    "run_recommend",
    "run_search",
]
