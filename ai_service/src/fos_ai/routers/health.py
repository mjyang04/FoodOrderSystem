"""GET /health — readiness probe."""

from __future__ import annotations

from fastapi import APIRouter

from fos_ai.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    from fos_ai.deps import get_corpus, get_menu, get_settings

    settings = get_settings()
    corpus = get_corpus()
    return HealthResponse(
        ready=corpus.ready,
        corpus_size=corpus.size,
        llm_provider=settings.llm_provider,
    )
