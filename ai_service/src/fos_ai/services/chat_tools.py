"""Tool definitions and dispatcher for the chat agent.

Tools are declared in Anthropic-native format; the LLM client converts for
OpenAI at the transport layer. Each tool maps to an existing service call.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

from fos_ai.db import menu_repo, order_repo
from fos_ai.ml.corpus import MenuCorpus
from fos_ai.ml.embedding import Embedder
from fos_ai.schemas import FoodMeta
from fos_ai.services import parser, recommender, search
from fos_ai.services.llm_client import LlmClient

logger = logging.getLogger(__name__)


# ---------- tool schemas (Anthropic native) ----------

SEARCH_MENU_TOOL: dict[str, Any] = {
    "name": "search_menu",
    "description": (
        "Search the restaurant menu by a free-text query. Returns up to `limit` "
        "relevant food items with their restaurant, price, and relevance score. "
        "Use this when the user is exploring options or hasn't picked a specific dish."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Free-text search, e.g. 'spicy noodles' or 'vegetarian pasta'.",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 10,
                "description": "Max results to return (default 5).",
            },
        },
        "required": ["query"],
    },
}

CREATE_ORDER_DRAFT_TOOL: dict[str, Any] = {
    "name": "create_order_draft",
    "description": (
        "Parse the user's natural-language order into a structured draft. "
        "Use this AFTER the user has decided on specific dishes and a restaurant. "
        "The draft is not committed — the user must confirm separately via the API."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "The user's order description verbatim.",
            },
            "restaurant_hint_id": {
                "type": "integer",
                "description": "Optional restaurant id to scope the menu lookup.",
            },
        },
        "required": ["text"],
    },
}

CHECK_ORDER_STATUS_TOOL: dict[str, Any] = {
    "name": "check_order_status",
    "description": (
        "Look up the current status of one of the user's existing orders. "
        "Returns status (Pending/Confirmed/Preparing/Delivering/Delivered/Cancelled), "
        "restaurant, total amount, and rating if any."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "order_id": {
                "type": "integer",
                "minimum": 1,
                "description": "The order id to look up.",
            },
        },
        "required": ["order_id"],
    },
}

GET_RECOMMENDATIONS_TOOL: dict[str, Any] = {
    "name": "get_recommendations",
    "description": (
        "Recommend dishes for the current user based on their past order history. "
        "Falls back to popular items for new users. Use this when the user asks "
        "for suggestions or doesn't know what to order."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 10,
                "description": "Max recommendations to return (default 5).",
            },
        },
        "required": [],
    },
}


def all_tools() -> list[dict[str, Any]]:
    return [
        SEARCH_MENU_TOOL,
        CREATE_ORDER_DRAFT_TOOL,
        CHECK_ORDER_STATUS_TOOL,
        GET_RECOMMENDATIONS_TOOL,
    ]


# ---------- dispatcher ----------

class ToolError(Exception):
    """Raised when a tool cannot complete — returned to the LLM as tool_result."""


@dataclass
class ToolContext:
    """Bundle of singletons a tool may need during dispatch."""

    user_id: int
    menu: list[FoodMeta]
    corpus: MenuCorpus
    embedder: Embedder
    llm: LlmClient
    db_conn: Any


class ToolExecutor:
    """Dispatches `tool_name` → matching service call with a ToolContext."""

    def __init__(self, ctx: ToolContext) -> None:
        self._ctx = ctx
        self._handlers: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
            "search_menu": self._search_menu,
            "create_order_draft": self._create_order_draft,
            "check_order_status": self._check_order_status,
            "get_recommendations": self._get_recommendations,
        }

    def execute(self, tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
        handler = self._handlers.get(tool_name)
        if handler is None:
            raise ToolError(f"unknown tool: {tool_name}")
        try:
            return handler(tool_input or {})
        except ToolError:
            raise
        except Exception as exc:  # noqa: BLE001 — surface as tool error to LLM
            logger.exception("tool %s failed", tool_name)
            raise ToolError(f"{tool_name} failed: {exc}") from exc

    # ---- handlers ----

    def _search_menu(self, args: dict[str, Any]) -> dict[str, Any]:
        query = args.get("query", "").strip()
        if not query:
            raise ToolError("search_menu requires non-empty 'query'")
        limit = int(args.get("limit", 5))

        results = search.search(
            query=query,
            corpus=self._ctx.corpus,
            embedder=self._ctx.embedder,
            limit=limit,
        )
        return {
            "query": query,
            "count": len(results),
            "results": [r.model_dump() for r in results],
        }

    def _create_order_draft(self, args: dict[str, Any]) -> dict[str, Any]:
        text = args.get("text", "").strip()
        if not text:
            raise ToolError("create_order_draft requires non-empty 'text'")
        hint = args.get("restaurant_hint_id")

        try:
            parsed = parser.parse_order(
                text=text,
                menu=self._ctx.menu,
                llm=self._ctx.llm,
                restaurant_hint_id=int(hint) if hint else None,
            )
        except ValueError as exc:
            raise ToolError(str(exc)) from exc

        return parsed.model_dump()

    def _check_order_status(self, args: dict[str, Any]) -> dict[str, Any]:
        order_id = args.get("order_id")
        if not isinstance(order_id, int) or order_id <= 0:
            raise ToolError("check_order_status requires positive integer 'order_id'")

        status = order_repo.fetch_order_status(
            conn=self._ctx.db_conn,
            order_id=order_id,
            user_id=self._ctx.user_id,
        )
        if status is None:
            raise ToolError(f"order {order_id} not found or not owned by user")
        return status

    def _get_recommendations(self, args: dict[str, Any]) -> dict[str, Any]:
        limit = int(args.get("limit", 5))
        history = menu_repo.fetch_user_order_food_ids(
            conn=self._ctx.db_conn,
            user_id=self._ctx.user_id,
        )
        strategy, has_history, items = recommender.recommend(
            user_id=self._ctx.user_id,
            corpus=self._ctx.corpus,
            ordered_food_ids=history,
            limit=limit,
        )
        return {
            "strategy": strategy,
            "user_has_history": has_history,
            "count": len(items),
            "items": [i.model_dump() for i in items],
        }
