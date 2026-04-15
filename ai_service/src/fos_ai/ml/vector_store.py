"""Qdrant vector store wrapper.

Thin wrapper around ``qdrant-client`` with the operations we actually use:
``ensure_collection``, ``upsert``, and ``search`` (with optional payload
filters). Supports both an in-memory backend (used by tests) and a remote
Qdrant instance (used in production via docker-compose).
"""

from __future__ import annotations

import logging

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

logger = logging.getLogger(__name__)


class VectorStore:
    """Minimal Qdrant client wrapper keyed by collection name.

    Args:
        url: Qdrant URL (e.g. ``http://localhost:6333``). Ignored when
            ``in_memory=True``.
        in_memory: If True, use the in-process ``:memory:`` Qdrant backend
            — intended for tests.
    """

    def __init__(self, url: str | None = None, in_memory: bool = False) -> None:
        if in_memory:
            logger.info("VectorStore: using in-memory backend")
            self._client = QdrantClient(":memory:")
        else:
            if not url:
                raise ValueError("VectorStore: url is required when in_memory=False")
            logger.info("VectorStore: connecting to %s", url)
            self._client = QdrantClient(url=url)

    @property
    def client(self) -> QdrantClient:
        return self._client

    def ensure_collection(self, name: str, dim: int) -> None:
        """Create collection ``name`` with Cosine distance if it does not exist."""
        existing = {c.name for c in self._client.get_collections().collections}
        if name in existing:
            logger.debug("Collection %s already exists", name)
            return

        logger.info("Creating Qdrant collection %s (dim=%d, cosine)", name, dim)
        self._client.create_collection(
            collection_name=name,
            vectors_config=qmodels.VectorParams(
                size=dim,
                distance=qmodels.Distance.COSINE,
            ),
        )

    def upsert(
        self,
        name: str,
        points: list[tuple[int, list[float], dict]],
    ) -> None:
        """Upsert a batch of (id, vector, payload) triples into ``name``."""
        if not points:
            return

        qpoints = [
            qmodels.PointStruct(id=pid, vector=vec, payload=payload)
            for pid, vec, payload in points
        ]
        self._client.upsert(collection_name=name, points=qpoints, wait=True)
        logger.info("Upserted %d points into %s", len(qpoints), name)

    def search(
        self,
        name: str,
        query_vec: list[float],
        limit: int,
        filters: dict | None = None,
    ) -> list[tuple[int, float, dict]]:
        """Return top-``limit`` matches as ``(id, score, payload)`` triples.

        ``filters`` is an optional ``{field: value}`` map — matched exactly
        via Qdrant ``FieldCondition + MatchValue``.
        """
        qfilter = _build_filter(filters)
        response = self._client.query_points(
            collection_name=name,
            query=query_vec,
            limit=limit,
            query_filter=qfilter,
            with_payload=True,
        )
        hits = response.points
        return [(int(h.id), float(h.score), dict(h.payload or {})) for h in hits]

    def count(self, name: str) -> int:
        """Return the number of points currently in collection ``name``."""
        try:
            res = self._client.count(collection_name=name, exact=True)
            return int(res.count)
        except Exception:
            logger.warning("count(%s) failed", name, exc_info=True)
            return 0


def _build_filter(filters: dict | None) -> qmodels.Filter | None:
    """Translate a simple ``{field: value}`` dict into a Qdrant Filter."""
    if not filters:
        return None
    must = [
        qmodels.FieldCondition(key=key, match=qmodels.MatchValue(value=value))
        for key, value in filters.items()
    ]
    return qmodels.Filter(must=must)
