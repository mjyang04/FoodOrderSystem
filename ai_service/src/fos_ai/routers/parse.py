"""POST /ai/parse-order — natural-language order parsing."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Header, HTTPException

from fos_ai.schemas import ParseOrderRequest, ParseOrderResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])


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

    llm = get_llm_client()

    try:
        result = _do_parse(body, menu, llm)
    except ValueError as exc:
        msg = str(exc)
        if msg.startswith("LLM_REFUSED"):
            raise HTTPException(status_code=422, detail=msg) from exc
        raise HTTPException(status_code=400, detail=msg) from exc
    except Exception as exc:
        logger.exception("Upstream LLM error")
        raise HTTPException(status_code=502, detail=f"AI_UPSTREAM_ERROR: {exc}") from exc

    return result


def _do_parse(body, menu, llm):
    from fos_ai.services.parser import parse_order as do_parse

    return do_parse(
        text=body.text,
        menu=menu,
        llm=llm,
        restaurant_hint_id=body.restaurant_hint_id,
    )
