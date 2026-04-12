"""GET /health — readiness probe."""

from __future__ import annotations

from fastapi import APIRouter

from fos_ai.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    from fos_ai.deps import get_menu, get_settings

    settings = get_settings()
    menu = get_menu()
    return HealthResponse(
        ready=len(menu) > 0,
        corpus_size=len(menu),
        llm_provider=settings.llm_provider,
    )
