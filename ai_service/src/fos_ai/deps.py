"""Singleton dependencies: settings, LLM client, menu cache, DB connection, corpus."""

from __future__ import annotations

import logging
from typing import Any

from fos_ai.config import Settings
from fos_ai.ml.corpus import MenuCorpus
from fos_ai.ml.embedding import Embedder
from fos_ai.ml.vector_store import VectorStore
from fos_ai.schemas import FoodMeta
from fos_ai.services.llm_client import LlmClient
from fos_ai.services.session_store import SessionStore

logger = logging.getLogger(__name__)

# ---- module-level singletons (populated by startup hook in main.py) ----

_settings: Settings | None = None
_llm_client: LlmClient | None = None
_menu: list[FoodMeta] = []
_db_conn: Any = None
_embedder: Embedder | None = None
_corpus: MenuCorpus = MenuCorpus()
_session_store: SessionStore = SessionStore()
_vector_store: VectorStore | None = None


def init_settings(settings: Settings) -> None:
    global _settings
    _settings = settings


def init_llm_client(client: LlmClient) -> None:
    global _llm_client
    _llm_client = client


def init_menu(menu: list[FoodMeta]) -> None:
    global _menu
    _menu = menu


def init_db_conn(conn: Any) -> None:
    global _db_conn
    _db_conn = conn


def init_embedder(embedder: Embedder) -> None:
    global _embedder
    _embedder = embedder


def init_corpus(corpus: MenuCorpus) -> None:
    global _corpus
    _corpus = corpus


def init_session_store(store: SessionStore) -> None:
    global _session_store
    _session_store = store


def init_vector_store(store: VectorStore | None) -> None:
    global _vector_store
    _vector_store = store


# ---- getters ----

def get_settings() -> Settings:
    assert _settings is not None, "Settings not initialised"
    return _settings


def get_llm_client() -> LlmClient:
    assert _llm_client is not None, "LLM client not initialised"
    return _llm_client


def get_menu() -> list[FoodMeta]:
    return _menu


def get_db_conn() -> Any:
    assert _db_conn is not None, "DB connection not initialised"
    return _db_conn


def get_embedder() -> Embedder:
    assert _embedder is not None, "Embedder not initialised"
    return _embedder


def get_corpus() -> MenuCorpus:
    return _corpus


def get_session_store() -> SessionStore:
    return _session_store


def get_vector_store() -> VectorStore | None:
    """Return the active vector store, or ``None`` if hybrid search is disabled."""
    return _vector_store
