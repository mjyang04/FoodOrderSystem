"""Cross-encoder reranker for second-stage retrieval.

Wraps ``sentence_transformers.CrossEncoder`` around
``BAAI/bge-reranker-base`` (~280 MB, CPU-friendly). The model is loaded
lazily on the first ``rerank()`` call so the fos_ai process can start up
fast even when reranking is disabled.

Fallback contract: if the model cannot be loaded (network down, cache
missing, unsupported device), ``rerank()`` raises
``RerankerUnavailable`` so callers can degrade to the first-stage
hybrid RRF ranking without crashing.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "BAAI/bge-reranker-base"


class RerankerUnavailable(RuntimeError):
    """Raised when the cross-encoder model cannot be loaded / used."""


def _auto_device() -> str:
    """Pick a device heuristically: mps on Apple silicon, then cuda, else cpu."""
    try:
        import torch

        if torch.backends.mps.is_available():
            return "mps"
        if torch.cuda.is_available():
            return "cuda"
    except Exception:  # pragma: no cover — torch missing shouldn't happen
        logger.debug("Torch unavailable during device probe", exc_info=True)
    return "cpu"


class Reranker:
    """Score (query, candidate) pairs with a CrossEncoder and return top-k.

    Args:
        model_name: Hugging Face model id (default ``BAAI/bge-reranker-base``).
        device: ``"cpu" | "cuda" | "mps"``. ``None`` → auto-detect.
    """

    def __init__(
        self,
        model_name: str = _DEFAULT_MODEL,
        device: str | None = None,
    ) -> None:
        self._model_name = model_name
        self._device = device or _auto_device()
        self._model: object | None = None  # lazy — type-erased to avoid import at init
        self._load_failed = False

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def device(self) -> str:
        return self._device

    def _ensure_loaded(self) -> object:
        """Load the CrossEncoder on first use. Raise RerankerUnavailable on failure."""
        if self._model is not None:
            return self._model
        if self._load_failed:
            raise RerankerUnavailable(
                f"Reranker {self._model_name!r} previously failed to load"
            )

        try:
            from sentence_transformers import CrossEncoder

            logger.info(
                "Loading cross-encoder reranker: %s (device=%s)",
                self._model_name,
                self._device,
            )
            self._model = CrossEncoder(self._model_name, device=self._device)
            logger.info("Reranker ready — %s", self._model_name)
            return self._model
        except Exception as exc:
            self._load_failed = True
            logger.warning(
                "Failed to load reranker %s: %s",
                self._model_name,
                exc,
                exc_info=True,
            )
            raise RerankerUnavailable(
                f"Failed to load reranker {self._model_name!r}: {exc}"
            ) from exc

    def rerank(
        self,
        query: str,
        candidates: list[tuple[int, str]],
        top_k: int,
    ) -> list[tuple[int, float]]:
        """Rerank ``candidates`` by CrossEncoder relevance to ``query``.

        Args:
            query: The user query.
            candidates: ``(doc_id, text)`` pairs to score. Order does not
                matter; the return value is sorted by rerank score.
            top_k: Number of top results to return (clamped to ``[1,
                len(candidates)]``).

        Returns:
            Top-``top_k`` ``(doc_id, rerank_score)`` pairs sorted desc.

        Raises:
            RerankerUnavailable: If the model cannot be loaded or the
                forward pass fails.
        """
        if not candidates:
            return []
        top_k = max(1, min(top_k, len(candidates)))

        model = self._ensure_loaded()
        pairs = [(query, text) for _doc_id, text in candidates]

        try:
            scores = model.predict(pairs)  # type: ignore[attr-defined]
        except Exception as exc:
            logger.warning("Reranker.predict failed: %s", exc, exc_info=True)
            raise RerankerUnavailable(
                f"Reranker {self._model_name!r} predict failed: {exc}"
            ) from exc

        scored: list[tuple[int, float]] = [
            (doc_id, float(score))
            for (doc_id, _text), score in zip(candidates, scores)
        ]
        scored.sort(key=lambda kv: -kv[1])
        return scored[:top_k]
