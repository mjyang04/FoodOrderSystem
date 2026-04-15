"""Tests for parse_order — mocked LLM, no real API calls."""

from __future__ import annotations

from typing import Any

import pytest

from fos_ai.schemas import FoodMeta
from fos_ai.services.llm_client import TextOnlyResult, ToolCallResult
from fos_ai.services.parser import parse_order


# ---- fake LLM client ----

class FakeLlmClient:
    """Returns a pre-configured response for testing."""

    def __init__(self, response: ToolCallResult | TextOnlyResult) -> None:
        self._response = response
        self.last_system: str = ""
        self.last_user: str = ""
        self.last_tools: list[dict] = []

    def tool_call(
        self,
        *,
        system: str,
        user: str,
        tools: list[dict[str, Any]],
        max_tokens: int = 1024,
    ) -> ToolCallResult | TextOnlyResult:
        self.last_system = system
        self.last_user = user
        self.last_tools = tools
        return self._response


# ---- tests ----

class TestParserHappyPath:
    """LLM returns a valid tool call."""

    def test_single_restaurant_two_items(self, sample_menu: list[FoodMeta]):
        """Standard case: user orders 2 items from one restaurant."""
        llm = FakeLlmClient(ToolCallResult(
            tool_name="create_order_draft",
            tool_input={
                "restaurant_name": "Sichuan Delight",
                "delivery_option": "Standard",
                "items": [
                    {"food_name": "Kung Pao Chicken", "quantity": 2},
                    {"food_name": "Mapo Tofu", "quantity": 1},
                ],
            },
        ))

        result = parse_order("两份宫保鸡丁一份麻婆豆腐", sample_menu, llm)

        assert result.confidence == 1.0
        assert result.issues == []
        assert result.draft.restaurant_id == 1
        assert result.draft.restaurant_name == "Sichuan Delight"
        assert len(result.draft.items) == 2
        assert result.draft.items[0].food_id == 1
        assert result.draft.items[0].quantity == 2
        assert result.draft.items[1].food_id == 2
        assert result.draft.estimated_total == 32.0  # 12*2 + 8*1

    def test_case_insensitive_food_match(self, sample_menu: list[FoodMeta]):
        """LLM returns food name with different casing."""
        llm = FakeLlmClient(ToolCallResult(
            tool_name="create_order_draft",
            tool_input={
                "restaurant_name": "Sichuan Delight",
                "items": [{"food_name": "kung pao chicken", "quantity": 1}],
            },
        ))

        result = parse_order("one kung pao", sample_menu, llm)

        assert len(result.draft.items) == 1
        assert result.draft.items[0].food_id == 1

    def test_substring_food_match(self, sample_menu: list[FoodMeta]):
        """LLM returns a partial name — parser resolves via substring."""
        llm = FakeLlmClient(ToolCallResult(
            tool_name="create_order_draft",
            tool_input={
                "restaurant_name": "Sichuan Delight",
                "items": [{"food_name": "Dan Dan", "quantity": 1}],
            },
        ))

        result = parse_order("dan dan noodles please", sample_menu, llm)

        assert result.draft.items[0].food_id == 3
        assert result.draft.items[0].food_name == "Dan Dan Noodles"

    def test_default_delivery_option(self, sample_menu: list[FoodMeta]):
        """When LLM omits delivery_option, defaults to Standard."""
        llm = FakeLlmClient(ToolCallResult(
            tool_name="create_order_draft",
            tool_input={
                "restaurant_name": "Sichuan Delight",
                "items": [{"food_name": "Mapo Tofu", "quantity": 1}],
            },
        ))

        result = parse_order("一份麻婆豆腐", sample_menu, llm)
        assert result.draft.delivery_option == "Standard"

    def test_restaurant_hint_constrains_menu(self, sample_menu: list[FoodMeta]):
        """System prompt only includes the hinted restaurant's menu."""
        llm = FakeLlmClient(ToolCallResult(
            tool_name="create_order_draft",
            tool_input={
                "restaurant_name": "Sichuan Delight",
                "items": [{"food_name": "Kung Pao Chicken", "quantity": 1}],
            },
        ))

        parse_order("chicken", sample_menu, llm, restaurant_hint_id=1)

        # System prompt should mention Sichuan Delight but not Cantonese Kitchen
        assert "Sichuan Delight" in llm.last_system
        assert "Cantonese Kitchen" not in llm.last_system


class TestParserPartialMatch:
    """LLM returns items that partially resolve."""

    def test_unresolved_item_lowers_confidence(self, sample_menu: list[FoodMeta]):
        """One valid item + one unknown → confidence drops, issue logged."""
        llm = FakeLlmClient(ToolCallResult(
            tool_name="create_order_draft",
            tool_input={
                "restaurant_name": "Sichuan Delight",
                "items": [
                    {"food_name": "Kung Pao Chicken", "quantity": 1},
                    {"food_name": "Nonexistent Dish", "quantity": 1},
                ],
            },
        ))

        result = parse_order("chicken and something", sample_menu, llm)

        assert len(result.draft.items) == 1  # only resolved item
        assert len(result.issues) == 1
        assert "Nonexistent Dish" in result.issues[0]
        assert result.confidence < 1.0


class TestParserRefusal:
    """LLM refuses or returns unexpected results."""

    def test_text_only_response_raises(self, sample_menu: list[FoodMeta]):
        """LLM returns text instead of tool call → ValueError."""
        llm = FakeLlmClient(TextOnlyResult(
            text="I'm sorry, I don't understand your request.",
            stop_reason="end_turn",
        ))

        with pytest.raises(ValueError, match="LLM_REFUSED"):
            parse_order("asdfghjkl", sample_menu, llm)

    def test_empty_items_raises(self, sample_menu: list[FoodMeta]):
        """LLM calls tool but with empty items → ValueError."""
        llm = FakeLlmClient(ToolCallResult(
            tool_name="create_order_draft",
            tool_input={
                "restaurant_name": "Sichuan Delight",
                "items": [],
            },
        ))

        with pytest.raises(ValueError, match="LLM_REFUSED"):
            parse_order("nothing", sample_menu, llm)

    def test_wrong_tool_name_raises(self, sample_menu: list[FoodMeta]):
        """LLM calls an unexpected tool → ValueError."""
        llm = FakeLlmClient(ToolCallResult(
            tool_name="some_other_tool",
            tool_input={"foo": "bar"},
        ))

        with pytest.raises(ValueError, match="unexpected tool"):
            parse_order("test", sample_menu, llm)

    def test_all_items_unresolvable_raises(self, sample_menu: list[FoodMeta]):
        """Every item fails to resolve → ValueError."""
        llm = FakeLlmClient(ToolCallResult(
            tool_name="create_order_draft",
            tool_input={
                "restaurant_name": "Sichuan Delight",
                "items": [
                    {"food_name": "Imaginary Dish A", "quantity": 1},
                    {"food_name": "Imaginary Dish B", "quantity": 2},
                ],
            },
        ))

        with pytest.raises(ValueError, match="LLM_REFUSED"):
            parse_order("fake food", sample_menu, llm)


class TestParserFuzzyRestaurant:
    """Restaurant name resolution edge cases."""

    def test_fuzzy_restaurant_match(self, sample_menu: list[FoodMeta]):
        """LLM returns partial restaurant name → still resolves."""
        llm = FakeLlmClient(ToolCallResult(
            tool_name="create_order_draft",
            tool_input={
                "restaurant_name": "Sichuan",  # partial
                "items": [{"food_name": "Mapo Tofu", "quantity": 1}],
            },
        ))

        result = parse_order("tofu from sichuan place", sample_menu, llm)

        assert result.draft.restaurant_id == 1

    def test_unknown_restaurant_with_hint(self, sample_menu: list[FoodMeta]):
        """Unknown restaurant but hint provided → uses hint."""
        llm = FakeLlmClient(ToolCallResult(
            tool_name="create_order_draft",
            tool_input={
                "restaurant_name": "Unknown Place",
                "items": [{"food_name": "Kung Pao Chicken", "quantity": 1}],
            },
        ))

        result = parse_order("chicken", sample_menu, llm, restaurant_hint_id=1)

        assert result.draft.restaurant_id == 1
        assert "Unknown Place" in result.issues[0]
        assert result.confidence < 1.0
