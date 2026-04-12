"""Singleton dependencies: settings, LLM client, menu cache, DB connection."""

from __future__ import annotations

import logging
from typing import Any

from fos_ai.config import Settings
from fos_ai.schemas import FoodMeta
from fos_ai.services.llm_client import LlmClient

logger = logging.getLogger(__name__)

# ---- module-level singletons (populated by startup hook in main.py) ----

_settings: Settings | None = None
_llm_client: LlmClient | None = None
_menu: list[FoodMeta] = []
_db_conn: Any = None


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
