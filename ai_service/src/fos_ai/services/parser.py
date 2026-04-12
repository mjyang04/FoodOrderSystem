"""Natural-language order parser using LLM tool-calling.

Takes free-text like "两份宫保鸡丁加一份麻婆豆腐" and returns a structured
``OrderDraft`` without writing anything to the database.
"""

from __future__ import annotations

import logging
from typing import Any

from fos_ai.schemas import (
    FoodMeta,
    OrderDraft,
    OrderDraftItem,
    ParseOrderResponse,
)
from fos_ai.services.llm_client import LlmClient, TextOnlyResult, ToolCallResult

logger = logging.getLogger(__name__)

# ---------- tool definition (Anthropic-style, converted for OpenAI by llm_client) ----------

ORDER_DRAFT_TOOL: dict[str, Any] = {
    "name": "create_order_draft",
    "description": (
        "Create a structured order draft from the user's natural-language request. "
        "Return the restaurant, delivery option, and a list of items with quantities. "
        "If the request is ambiguous or cannot be fulfilled, do NOT call this tool — "
        "reply with a text explanation instead."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "restaurant_name": {
                "type": "string",
                "description": "Exact restaurant name from the menu",
            },
            "delivery_option": {
                "type": "string",
                "enum": ["Standard", "Express", "Scheduled"],
                "description": "Delivery option, default Standard",
            },
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "food_name": {
                            "type": "string",
                            "description": "Exact food name from the menu",
                        },
                        "quantity": {
                            "type": "integer",
                            "minimum": 1,
                            "description": "Number of this item",
                        },
                    },
                    "required": ["food_name", "quantity"],
                },
                "minItems": 1,
            },
        },
        "required": ["restaurant_name", "items"],
    },
}


def _build_system_prompt(menu: list[FoodMeta], restaurant_hint_id: int | None) -> str:
    """Build a system prompt containing the available menu for the LLM."""
    lines = [
        "You are a food ordering assistant. The user will describe what they want "
        "to order in natural language (Chinese or English). Your job is to parse "
        "their request into a structured order draft by calling the "
        "`create_order_draft` tool.",
        "",
        "Rules:",
        "- Only use food items that appear in the menu below.",
        "- Match food names exactly as listed (the names are in English).",
        "- If the user mentions a dish not on the menu, do NOT call the tool — "
        "reply with a text explanation listing what you could not find.",
        "- Default delivery_option to 'Standard' unless the user specifies otherwise.",
        "- If the request is too ambiguous to parse, reply with text asking for clarification.",
        "",
        "Available menu:",
    ]

    # Group by restaurant
    restaurants: dict[int, tuple[str, list[FoodMeta]]] = {}
    for f in menu:
        if restaurant_hint_id and f.restaurant_id != restaurant_hint_id:
            continue
        key = f.restaurant_id
        if key not in restaurants:
            restaurants[key] = (f.restaurant_name, [])
        restaurants[key][1].append(f)

    for rid, (rname, foods) in sorted(restaurants.items()):
        lines.append(f"\n## {rname} (id={rid})")
        for f in foods:
            pref = f" [options: {f.preferences}]" if f.preferences else ""
            lines.append(f"- {f.food_name}: ${f.unit_price:.2f} — {f.description}{pref}")

    return "\n".join(lines)


def _resolve_food(name: str, menu: list[FoodMeta], restaurant_name: str) -> FoodMeta | None:
    """Find a food item by name, scoped to the restaurant.

    Tries exact match first, then case-insensitive, then substring.
    """
    lower = name.lower().strip()

    # Filter to items from the target restaurant
    candidates = [f for f in menu if f.restaurant_name.lower() == restaurant_name.lower()]
    if not candidates:
        candidates = menu  # fallback to full menu

    # Exact match
    for f in candidates:
        if f.food_name == name:
            return f

    # Case-insensitive match
    for f in candidates:
        if f.food_name.lower() == lower:
            return f

    # Substring match (e.g. "Kung Pao" matches "Kung Pao Chicken")
    for f in candidates:
        if lower in f.food_name.lower() or f.food_name.lower() in lower:
            return f

    return None


def parse_order(
    text: str,
    menu: list[FoodMeta],
    llm: LlmClient,
    restaurant_hint_id: int | None = None,
) -> ParseOrderResponse:
    """Parse natural-language text into an OrderDraft.

    Args:
        text: User's free-text order request.
        menu: Full menu (or filtered if corpus provides a subset).
        llm: Provider-agnostic LLM client.
        restaurant_hint_id: If set, constrain the menu context to this restaurant.

    Returns:
        ParseOrderResponse with draft, confidence, and any issues.

    Raises:
        ValueError: If the LLM refuses or returns an unparseable response.
    """
    system_prompt = _build_system_prompt(menu, restaurant_hint_id)
    result = llm.tool_call(
        system=system_prompt,
        user=text,
        tools=[ORDER_DRAFT_TOOL],
        max_tokens=1024,
    )

    # LLM refused — replied with text instead of calling the tool
    if isinstance(result, TextOnlyResult):
        raise ValueError(f"LLM_REFUSED: {result.text}")

    assert isinstance(result, ToolCallResult)

    if result.tool_name != "create_order_draft":
        raise ValueError(f"LLM called unexpected tool: {result.tool_name}")

    inp = result.tool_input
    restaurant_name: str = inp.get("restaurant_name", "")
    delivery_option: str = inp.get("delivery_option", "Standard")
    raw_items: list[dict[str, Any]] = inp.get("items", [])

    if not raw_items:
        raise ValueError("LLM_REFUSED: tool call returned empty items list")

    # Resolve restaurant
    restaurant_id: int | None = None
    for f in menu:
        if f.restaurant_name.lower() == restaurant_name.lower():
            restaurant_id = f.restaurant_id
            break

    issues: list[str] = []
    if restaurant_id is None:
        # Try fuzzy restaurant match
        for f in menu:
            if restaurant_name.lower() in f.restaurant_name.lower():
                restaurant_id = f.restaurant_id
                restaurant_name = f.restaurant_name
                break
        if restaurant_id is None:
            issues.append(f"Restaurant '{restaurant_name}' not found in menu")
            # Use hint if available
            if restaurant_hint_id:
                restaurant_id = restaurant_hint_id
                for f in menu:
                    if f.restaurant_id == restaurant_hint_id:
                        restaurant_name = f.restaurant_name
                        break

    # Resolve items
    resolved_items: list[OrderDraftItem] = []
    for raw in raw_items:
        food_name = raw.get("food_name", "")
        quantity = raw.get("quantity", 1)

        food = _resolve_food(food_name, menu, restaurant_name)
        if food is None:
            issues.append(f"Food '{food_name}' not found on {restaurant_name}'s menu")
            continue

        resolved_items.append(OrderDraftItem(
            food_id=food.food_id,
            food_name=food.food_name,
            quantity=quantity,
            unit_price=food.unit_price,
        ))

    if not resolved_items:
        raise ValueError(
            "LLM_REFUSED: none of the requested items could be resolved. "
            f"Issues: {'; '.join(issues)}"
        )

    estimated_total = sum(item.unit_price * item.quantity for item in resolved_items)

    # Confidence: 1.0 if no issues, degrade by 0.15 per issue
    confidence = max(0.0, 1.0 - 0.15 * len(issues))

    draft = OrderDraft(
        restaurant_id=restaurant_id or 0,
        restaurant_name=restaurant_name,
        delivery_option=delivery_option,
        items=resolved_items,
        estimated_total=round(estimated_total, 2),
    )

    return ParseOrderResponse(
        draft=draft,
        confidence=round(confidence, 2),
        issues=issues,
    )
