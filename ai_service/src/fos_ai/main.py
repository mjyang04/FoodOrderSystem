"""FastAPI application entry point for fos_ai."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from fos_ai.config import Settings
from fos_ai import deps
from fos_ai.routers import chat, health, intent, parse, recommend, search

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    settings = Settings()
    settings.validate_llm()
    deps.init_settings(settings)

    # Connect to MySQL and load menu
    try:
        import mysql.connector

        conn = mysql.connector.connect(
            host=settings.db_host,
            port=settings.db_port,
            user=settings.db_user,
            password=settings.db_pass,
            database=settings.db_name,
        )
        deps.init_db_conn(conn)
        logger.info("MySQL connected: %s@%s/%s", settings.db_user, settings.db_host, settings.db_name)

        from fos_ai.db.menu_repo import fetch_all_foods

        menu = fetch_all_foods(conn)
        deps.init_menu(menu)
        logger.info("Menu loaded: %d items", len(menu))
    except Exception:
        logger.warning("MySQL not available — menu will be empty, AI features degraded", exc_info=True)
        menu = []

    # Build embedding corpus
    corpus = None
    embedder = None
    try:
        from fos_ai.ml.embedding import Embedder
        from fos_ai.ml.corpus import build_corpus

        embedder = Embedder()
        deps.init_embedder(embedder)

        if menu:
            corpus = build_corpus(menu, embedder)
            deps.init_corpus(corpus)
            logger.info("Corpus ready — %d items encoded", corpus.size)
        else:
            logger.warning("Skipping corpus build — no menu items")
    except Exception:
        logger.warning("Embedder/corpus init failed — search/recommend degraded", exc_info=True)

    # Wire Qdrant vector store (optional — disabled if QDRANT_URL is unset)
    if settings.qdrant_url and corpus is not None and corpus.ready and embedder is not None:
        try:
            from fos_ai.ml.vector_store import VectorStore

            store = VectorStore(url=settings.qdrant_url)
            store.ensure_collection("menu_items", dim=embedder.dim)
            points: list[tuple[int, list[float], dict]] = []
            for idx, item in enumerate(corpus.items):
                payload = {
                    "food_id": item.food_id,
                    "food_name": item.food_name,
                    "restaurant_id": item.restaurant_id,
                    "restaurant_name": item.restaurant_name,
                    "unit_price": item.unit_price,
                }
                points.append((item.food_id, corpus.tensor[idx].tolist(), payload))
            store.upsert("menu_items", points)
            deps.init_vector_store(store)
            logger.info("Qdrant ready — %d points upserted to menu_items", len(points))
        except Exception:
            logger.warning("Qdrant init failed — falling back to cosine search", exc_info=True)
            deps.init_vector_store(None)
    else:
        logger.info("Hybrid search disabled — QDRANT_URL not set or corpus empty")

    # Wire cross-encoder reranker (optional — disabled unless RERANK_ENABLED=true)
    if settings.rerank_enabled:
        try:
            from fos_ai.ml.reranker import Reranker

            reranker = Reranker(model_name=settings.rerank_model)
            deps.init_reranker(reranker)
            logger.info("Reranker configured (lazy-loaded): %s", settings.rerank_model)
        except Exception:
            logger.warning(
                "Reranker init failed — two-stage retrieval disabled", exc_info=True
            )
            deps.init_reranker(None)
    else:
        logger.info("Reranker disabled — RERANK_ENABLED not set")

    # Create LLM client
    llm = None
    try:
        from fos_ai.services.llm_client import create_llm_client

        llm = create_llm_client(
            provider=settings.llm_provider,
            anthropic_api_key=settings.anthropic_api_key,
            anthropic_base_url=settings.anthropic_base_url,
            anthropic_model=settings.anthropic_model,
            openai_api_key=settings.openai_api_key,
            openai_base_url=settings.openai_base_url,
            openai_model=settings.openai_model,
        )
        deps.init_llm_client(llm)
    except ValueError as exc:
        logger.warning("LLM client not created: %s — parse-order will fail", exc)

    # Wire intent classifier: prefer LoRA adapter, fall back to LLM tool-call
    _wire_intent_classifier(settings, llm)

    logger.info(
        "fos_ai ready — provider=%s, menu=%d items",
        settings.llm_provider,
        len(deps.get_menu()),
    )

    yield  # app runs

    # Shutdown
    if deps._db_conn is not None:
        try:
            deps._db_conn.close()
        except Exception:
            pass
    logger.info("fos_ai shut down")


app = FastAPI(
    title="fos_ai",
    description="AI microservice for FoodOrderSystem",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(parse.router)
app.include_router(search.router)
app.include_router(recommend.router)
app.include_router(chat.router)
app.include_router(intent.router)


def _wire_intent_classifier(settings: Settings, llm) -> None:
    """Pick LoRA adapter if available, else LLM fallback, else none.

    Isolated helper so the lifespan code stays linear.
    """
    from pathlib import Path

    from fos_ai.services.intent_classifier import (
        FallbackIntentClassifier,
        IntentUnavailable,
        LoraIntentClassifier,
    )

    adapter_path = settings.intent_adapter_path
    if adapter_path and Path(adapter_path).exists():
        try:
            classifier = LoraIntentClassifier(
                base_model=settings.intent_base_model,
                adapter_path=adapter_path,
            )
            deps.init_intent_classifier(classifier, source="lora")
            logger.info("Intent classifier: LoRA adapter at %s", adapter_path)
            return
        except IntentUnavailable as exc:
            logger.warning("LoRA intent classifier load failed: %s — trying fallback", exc)

    if llm is not None:
        deps.init_intent_classifier(FallbackIntentClassifier(llm=llm), source="fallback")
        logger.info("Intent classifier: LLM fallback (few-shot tool call)")
        return

    deps.init_intent_classifier(None, source="none")
    logger.warning("Intent classifier: disabled — /ai/intent will 503")
