"""Read-only MySQL access for order status — used by the chat `check_order_status` tool."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_ORDER_STATUS_QUERY = """
SELECT o.id           AS order_id,
       o.user_id      AS user_id,
       o.status       AS status,
       o.total_amount AS total_amount,
       o.rating       AS rating,
       o.created_at   AS created_at,
       r.name         AS restaurant_name
FROM   orders o
LEFT JOIN restaurants r ON o.restaurant_id = r.id
WHERE  o.id = %s
"""


def fetch_order_status(
    conn: Any,
    order_id: int,
    user_id: int,
) -> dict[str, Any] | None:
    """Return a dict with order status fields, or None if not found / not owned.

    Ownership check: returns None when the order exists but belongs to another
    user — the chat tool should not leak cross-user order info.
    """
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(_ORDER_STATUS_QUERY, (order_id,))
        row = cursor.fetchone()
    finally:
        cursor.close()

    if row is None:
        return None
    if row["user_id"] != user_id:
        logger.info(
            "order lookup blocked: order=%d owner=%d requester=%d",
            order_id, row["user_id"], user_id,
        )
        return None

    return {
        "order_id": int(row["order_id"]),
        "status": str(row["status"]),
        "total_amount": float(row["total_amount"]) if row["total_amount"] is not None else 0.0,
        "rating": float(row["rating"]) if row["rating"] is not None else None,
        "restaurant_name": row.get("restaurant_name") or "",
        "created_at": str(row["created_at"]) if row.get("created_at") else "",
    }
