"""POST /ai/intent — classify an utterance into one of 9 intents.

Uses whichever :class:`IntentClassifier` was wired in at startup:

- ``LoraIntentClassifier`` if ``INTENT_ADAPTER_PATH`` is set and valid,
- otherwise ``FallbackIntentClassifier`` (few-shot prompt via the LLM client).

Returns ``source`` so callers can observe which path produced the label.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from fos_ai.services.intent_classifier import IntentUnavailable

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])


class IntentRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=500)


class IntentResponse(BaseModel):
    label: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    source: str  # "lora" | "fallback"


@router.post("/intent", response_model=IntentResponse)
def classify_intent(
    body: IntentRequest,
    x_user_id: int = Header(..., alias="X-User-Id"),
) -> IntentResponse:
    from fos_ai.deps import get_intent_classifier, get_intent_source

    classifier = get_intent_classifier()
    if classifier is None:
        raise HTTPException(
            status_code=503,
            detail="Intent classifier not configured (neither LoRA adapter nor LLM fallback is available)",
        )

    try:
        label, conf = classifier.classify(body.text)
    except IntentUnavailable as exc:
        logger.warning("intent classifier unavailable: %s", exc)
        raise HTTPException(status_code=502, detail=f"AI_INTENT_UNAVAILABLE: {exc}") from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("intent classifier error")
        raise HTTPException(status_code=502, detail=f"AI_INTENT_ERROR: {exc}") from exc

    return IntentResponse(label=label, confidence=conf, source=get_intent_source())
