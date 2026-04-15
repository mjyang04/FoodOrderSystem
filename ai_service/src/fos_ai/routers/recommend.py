"""GET /ai/recommend — personalized food recommendations."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Header, HTTPException, Query

from fos_ai.db.menu_repo import fetch_user_order_food_ids
from fos_ai.schemas import RecommendResponse
from fos_ai.services.recommender import recommend as do_recommend

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/recommend", response_model=RecommendResponse)
def recommend_foods(
    limit: int = Query(5, ge=1, le=20),
    x_user_id: int = Header(..., alias="X-User-Id"),
) -> RecommendResponse:
    """Content-based recommendations for the authenticated user."""
    from fos_ai.deps import get_corpus, get_db_conn

    corpus = get_corpus()
    if not corpus.ready:
        raise HTTPException(status_code=503, detail="Menu corpus not loaded yet")

    # Fetch user's past ordered food IDs
    try:
        conn = get_db_conn()
        ordered_food_ids = fetch_user_order_food_ids(conn, x_user_id)
    except Exception:
        logger.warning("DB unavailable for user history — falling back to cold start", exc_info=True)
        ordered_food_ids = []

    strategy, user_has_history, items = do_recommend(
        user_id=x_user_id,
        corpus=corpus,
        ordered_food_ids=ordered_food_ids,
        limit=limit,
    )
    return RecommendResponse(
        strategy=strategy,
        user_has_history=user_has_history,
        items=items,
        count=len(items),
    )
