"""GET /ai/stats — admin-only metrics aggregator.

Returns a summary of LLM call volume, token usage, latency, cost, error rate,
and cache hit rates over a rolling window. Intended for dashboards and the
upstream C++ ``GET /api/ai/stats`` admin proxy.

The Python service binds to loopback and trusts the ``X-User-Role`` header
set by the upstream controller (which reads the authenticated role from the
JWT context). Role enforcement at this layer is defense-in-depth.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Header, HTTPException, Query

from fos_ai.obs import metrics

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/stats")
def get_stats(
    window_seconds: int = Query(86_400, ge=1, le=30 * 86_400),
    x_user_id: int = Header(..., alias="X-User-Id"),
    x_user_role: str = Header(..., alias="X-User-Role"),
) -> dict:
    """Return an aggregate of recent LLM + cache activity."""
    if x_user_role.strip().lower() != "admin":
        raise HTTPException(status_code=403, detail="admin role required")

    summary = metrics.summary(window_seconds=window_seconds)
    return {"success": True, "data": summary}
