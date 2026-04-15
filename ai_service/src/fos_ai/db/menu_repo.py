"""Read-only MySQL access for menu data."""

from __future__ import annotations

import logging
from typing import Any

from fos_ai.schemas import FoodMeta

logger = logging.getLogger(__name__)

_MENU_QUERY = """
SELECT f.id        AS food_id,
       f.name      AS food_name,
       f.price     AS unit_price,
       f.description,
       f.preferences,
       r.id        AS restaurant_id,
       r.name      AS restaurant_name
FROM   foods f
JOIN   restaurants r ON f.restaurant_id = r.id
ORDER BY r.id, f.id
"""

_USER_ORDER_FOOD_IDS_QUERY = """
SELECT DISTINCT oi.food_id
FROM   order_items oi
JOIN   orders o ON oi.order_id = o.id
WHERE  o.user_id = %s
  AND  oi.food_id IS NOT NULL
"""


def fetch_all_foods(conn: Any) -> list[FoodMeta]:
    """Load the full menu (foods joined with restaurants)."""
    cursor = conn.cursor(dictionary=True)
    cursor.execute(_MENU_QUERY)
    rows = cursor.fetchall()
    cursor.close()
    return [
        FoodMeta(
            food_id=row["food_id"],
            food_name=row["food_name"],
            unit_price=float(row["unit_price"]),
            description=row.get("description") or "",
            preferences=row.get("preferences") or "",
            restaurant_id=row["restaurant_id"],
            restaurant_name=row["restaurant_name"],
        )
        for row in rows
    ]


def fetch_user_order_food_ids(conn: Any, user_id: int) -> list[int]:
    """Return distinct food IDs the user has ordered before."""
    cursor = conn.cursor()
    cursor.execute(_USER_ORDER_FOOD_IDS_QUERY, (user_id,))
    rows = cursor.fetchall()
    cursor.close()
    return [row[0] for row in rows]
