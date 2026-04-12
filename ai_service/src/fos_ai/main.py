"""FastAPI application entry point for fos_ai."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from fos_ai.config import Settings
from fos_ai import deps
from fos_ai.routers import health, parse, recommend, search

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

    # Create LLM client
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
