"""POST /ai/parse-order — natural-language order parsing.

Caching note: the business-layer cache is applied here (router layer) rather
than inside ``services.parser.parse_order``. Reason: the library function
receives the full menu list (a mutable dependency); caching by ``(text,
restaurant_hint_id, menu_signature)`` at the router keeps the cache valid
across a menu reload without silently returning stale drafts.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Header, HTTPException

from fos_ai.obs import cached
from fos_ai.schemas import ParseOrderRequest, ParseOrderResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])


@cached(ttl_seconds=300.0, maxsize=256, namespace="parser.parse_order")
def _cached_parse(
    text: str,
    restaurant_hint_id: int | None,
    menu_signature: tuple[int, int],
) -> dict:
    """Run :func:`parser.parse_order` and return a serialisable dict.

    ``menu_signature`` is ``(menu_size, first_food_id)`` — a cheap fingerprint
    that changes whenever the menu is re-ingested.
    """
    from fos_ai.deps import get_llm_client, get_menu
    from fos_ai.services.parser import parse_order as do_parse

    menu = get_menu()
    llm = get_llm_client()
    result = do_parse(
        text=text,
        menu=menu,
        llm=llm,
        restaurant_hint_id=restaurant_hint_id,
    )
    return result.model_dump()


@router.post("/parse-order", response_model=ParseOrderResponse)
def parse_order(
    body: ParseOrderRequest,
    x_user_id: int = Header(..., alias="X-User-Id"),
) -> ParseOrderResponse:
    """Parse free-text into an order draft via LLM tool-calling.

    The draft is NOT persisted — the client reviews it, then submits
    to ``POST /api/orders`` if satisfied.
    """
    from fos_ai.deps import get_llm_client, get_menu

    menu = get_menu()
    if not menu:
        raise HTTPException(status_code=503, detail="Menu corpus not loaded yet")

    # Ensure LLM client is configured — parse_order would fail downstream.
    get_llm_client()

    sig = (len(menu), menu[0].food_id if menu else 0)

    try:
        payload = _cached_parse(body.text, body.restaurant_hint_id, sig)
    except ValueError as exc:
        msg = str(exc)
        if msg.startswith("LLM_REFUSED"):
            raise HTTPException(status_code=422, detail=msg) from exc
        raise HTTPException(status_code=400, detail=msg) from exc
    except Exception as exc:
        logger.exception("Upstream LLM error")
        raise HTTPException(status_code=502, detail=f"AI_UPSTREAM_ERROR: {exc}") from exc

    return ParseOrderResponse(**payload)
