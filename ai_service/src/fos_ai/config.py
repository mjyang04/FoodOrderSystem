"""Application settings loaded from environment / .env file."""

from __future__ import annotations

import logging

from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """All configuration via env vars (12-factor)."""

    # --- LLM provider ---
    llm_provider: str = "anthropic"  # "anthropic" | "openai"

    # Anthropic
    anthropic_api_key: str | None = None
    anthropic_base_url: str | None = None
    anthropic_model: str = "claude-haiku-4-5-20251001"

    # OpenAI (or any OpenAI-compatible endpoint)
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    openai_model: str = "gpt-4o-mini"

    # --- Database ---
    db_host: str = "127.0.0.1"
    db_port: int = 3306
    db_user: str = "root"
    db_pass: str = ""
    db_name: str = "food_order_system"

    # --- Service bind ---
    ai_bind_host: str = "127.0.0.1"
    ai_bind_port: int = 8000

    # --- Vector store (Qdrant) ---
    qdrant_url: str | None = None  # e.g. "http://localhost:6333"; None disables hybrid search

    # --- Reranker (CrossEncoder) ---
    rerank_enabled: bool = False
    rerank_model: str = "BAAI/bge-reranker-base"

    # --- Intent classifier ---
    # Directory holding a PEFT adapter trained by `fos_ai_training.intent.train`.
    # When unset/missing, the service falls back to an LLM-tool-call classifier.
    intent_adapter_path: str | None = None
    intent_base_model: str = "Qwen/Qwen2.5-0.5B-Instruct"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    def validate_llm(self) -> None:
        """Validate that the chosen LLM provider has a key configured."""
        if self.llm_provider == "anthropic" and not self.anthropic_api_key:
            logger.warning("LLM_PROVIDER=anthropic but ANTHROPIC_API_KEY is not set")
        elif self.llm_provider == "openai" and not self.openai_api_key:
            logger.warning("LLM_PROVIDER=openai but OPENAI_API_KEY is not set")
        elif self.llm_provider not in ("anthropic", "openai"):
            raise ValueError(
                f"LLM_PROVIDER must be 'anthropic' or 'openai', got '{self.llm_provider}'"
            )

        if self.ai_bind_host != "127.0.0.1":
            logger.warning(
                "AI_BIND_HOST=%s — binding to non-loopback breaks the trust boundary!",
                self.ai_bind_host,
            )
