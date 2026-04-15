"""Pydantic request / response models for fos_ai endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


# ---------- shared food metadata ----------

class FoodMeta(BaseModel):
    """Minimal food info used across search, recommend, and parse."""

    food_id: int
    food_name: str
    restaurant_id: int
    restaurant_name: str
    unit_price: float
    description: str = ""
    preferences: str = ""


# ---------- parse-order ----------

class ParseOrderRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=1000)
    restaurant_hint_id: int | None = None


class OrderDraftItem(BaseModel):
    food_id: int
    food_name: str
    quantity: int = Field(..., ge=1)
    unit_price: float


class OrderDraft(BaseModel):
    restaurant_id: int
    restaurant_name: str
    delivery_option: str = "Standard"
    items: list[OrderDraftItem]
    estimated_total: float


class ParseOrderResponse(BaseModel):
    draft: OrderDraft
    confidence: float = Field(..., ge=0.0, le=1.0)
    issues: list[str] = []


# ---------- search ----------

class SearchResult(BaseModel):
    food_id: int
    food_name: str
    restaurant_id: int
    restaurant_name: str
    unit_price: float
    score: float


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    count: int


# ---------- recommend ----------

class RecommendItem(BaseModel):
    food_id: int
    food_name: str
    restaurant_id: int
    restaurant_name: str
    unit_price: float
    score: float
    reason: str = ""


class RecommendResponse(BaseModel):
    strategy: str  # "content_based" | "popularity_fallback"
    user_has_history: bool
    items: list[RecommendItem]
    count: int


# ---------- health ----------

class HealthResponse(BaseModel):
    ready: bool
    corpus_size: int = 0
    llm_provider: str = ""
