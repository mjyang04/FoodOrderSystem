"""Hybrid retrieval: BM25 (sparse) + dense embeddings + RRF fusion.

Rationale: BM25 captures exact keyword matches ("roast duck"), while the
dense embeddings capture semantic similarity ("Cantonese crispy fowl").
Reciprocal Rank Fusion (k=60) combines the two rankings without needing
to tune weights — a common industry default.

Fallbacks:
- If the vector store is unavailable (``None`` or the call raises), we
  return BM25-only results. The public API never raises on retrieval
  failure; it degrades gracefully.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from rank_bm25 import BM25Okapi

from fos_ai.ml.corpus import MenuCorpus
from fos_ai.ml.embedding import Embedder
from fos_ai.ml.reranker import Reranker, RerankerUnavailable
from fos_ai.ml.vector_store import VectorStore
from fos_ai.schemas import SearchResult

logger = logging.getLogger(__name__)

_RRF_K = 60
_CANDIDATE_POOL = 50  # Top-N from each retriever before fusion
_DEFAULT_LIMIT = 10
_MAX_LIMIT = 20
_DEFAULT_RERANK_CANDIDATES = 50
_COLLECTION = "menu_items"

_TOKEN_RE = re.compile(r"\W+")


@dataclass
class _BM25Bundle:
    """BM25 index paired with the ordered id list for rank lookup."""

    index: BM25Okapi
    food_ids: list[int]


# Module-level cache so we don't rebuild the BM25 index on every request.
# Keyed on ``id(corpus)`` — rebuilt whenever the corpus object itself changes.
_bm25_cache: dict[int, _BM25Bundle] = {}


def tokenize(text: str) -> list[str]:
    """Split on non-word chars, lowercase, drop empties."""
    return [tok for tok in _TOKEN_RE.split(text.lower()) if tok]


def _build_bm25(corpus: MenuCorpus) -> _BM25Bundle:
    """Build (or fetch cached) BM25 index from the corpus' items."""
    key = id(corpus)
    cached = _bm25_cache.get(key)
    if cached is not None and len(cached.food_ids) == corpus.size:
        return cached

    docs: list[list[str]] = []
    food_ids: list[int] = []
    for item in corpus.items:
        text = f"{item.food_name} {item.description}".strip()
        docs.append(tokenize(text))
        food_ids.append(item.food_id)

    # rank_bm25 requires at least one non-empty doc; fall back to name only.
    if not any(docs):
        logger.warning("All BM25 docs empty — using food_name as fallback")
        docs = [tokenize(item.food_name) or [f"food{item.food_id}"] for item in corpus.items]

    bundle = _BM25Bundle(index=BM25Okapi(docs), food_ids=food_ids)
    _bm25_cache[key] = bundle
    logger.info("BM25 index built — %d docs", len(docs))
    return bundle


def _bm25_rank(query: str, bundle: _BM25Bundle, top_n: int) -> list[tuple[int, float]]:
    """Return top-``top_n`` ``(food_id, bm25_score)`` pairs."""
    query_tokens = tokenize(query)
    if not query_tokens:
        return []
    scores = bundle.index.get_scores(query_tokens)
    # Argsort descending by score
    order = sorted(range(len(scores)), key=lambda i: -scores[i])[:top_n]
    return [(bundle.food_ids[i], float(scores[i])) for i in order]


def _dense_rank(
    query: str,
    embedder: Embedder,
    vector_store: VectorStore,
    top_n: int,
) -> list[tuple[int, float]]:
    """Return top-``top_n`` ``(food_id, score)`` pairs from Qdrant."""
    query_vec = embedder.encode([query])[0].tolist()
    hits = vector_store.search(_COLLECTION, query_vec, limit=top_n)
    return [(fid, score) for fid, score, _payload in hits]


def _rrf_fuse(
    rankings: list[list[tuple[int, float]]],
    k: int = _RRF_K,
) -> list[tuple[int, float]]:
    """Reciprocal Rank Fusion.

    For each ranking, doc at position ``rank`` (1-indexed) contributes
    ``1 / (k + rank)`` to its total score. Returns sorted ``(id, score)``
    pairs in descending order of fused score.
    """
    totals: dict[int, float] = {}
    for ranking in rankings:
        for rank, (doc_id, _score) in enumerate(ranking, start=1):
            totals[doc_id] = totals.get(doc_id, 0.0) + 1.0 / (k + rank)

    fused = sorted(totals.items(), key=lambda kv: -kv[1])
    return fused


def _to_results(
    ranked: list[tuple[int, float]],
    corpus: MenuCorpus,
    limit: int,
) -> list[SearchResult]:
    """Materialise ``(food_id, score)`` pairs into ``SearchResult`` objects."""
    by_id = {item.food_id: item for item in corpus.items}
    results: list[SearchResult] = []
    for food_id, score in ranked:
        meta = by_id.get(food_id)
        if meta is None:
            continue
        results.append(
            SearchResult(
                food_id=meta.food_id,
                food_name=meta.food_name,
                restaurant_id=meta.restaurant_id,
                restaurant_name=meta.restaurant_name,
                unit_price=meta.unit_price,
                score=round(score, 4),
            )
        )
        if len(results) >= limit:
            break
    return results


def _apply_reranker(
    query: str,
    fused: list[tuple[int, float]],
    corpus: MenuCorpus,
    reranker: Reranker,
    rerank_candidates: int,
    limit: int,
) -> list[tuple[int, float]] | None:
    """Rerank the top-``rerank_candidates`` of ``fused`` and return top-``limit``.

    Returns ``None`` on reranker failure so the caller can fall back to
    the RRF ranking unchanged.
    """
    pool = fused[:rerank_candidates]
    by_id = {item.food_id: item for item in corpus.items}

    pairs: list[tuple[int, str]] = []
    for food_id, _score in pool:
        meta = by_id.get(food_id)
        if meta is None:
            continue
        text = f"{meta.food_name} {meta.description}".strip()
        pairs.append((food_id, text))

    if not pairs:
        return fused[:limit]

    try:
        return reranker.rerank(query, pairs, top_k=limit)
    except RerankerUnavailable:
        logger.warning(
            "Reranker unavailable — falling back to RRF top-%d",
            limit,
            exc_info=True,
        )
        return None


def hybrid_search(
    query: str,
    corpus: MenuCorpus,
    embedder: Embedder,
    vector_store: VectorStore | None,
    limit: int = _DEFAULT_LIMIT,
    reranker: Reranker | None = None,
    rerank_candidates: int = _DEFAULT_RERANK_CANDIDATES,
) -> list[SearchResult]:
    """Run BM25 + dense + RRF and return top-``limit`` ``SearchResult``.

    Two-stage when ``reranker`` is provided: compute hybrid RRF over the
    top-``rerank_candidates`` candidates, then rerank to ``limit``. When
    the reranker raises ``RerankerUnavailable`` (e.g. model not loaded),
    we log a warning and return the RRF top-``limit`` unchanged.

    If ``vector_store`` is ``None`` or the dense lookup raises, we fall
    back to BM25-only results. Never raises on retrieval errors.
    """
    if not corpus.ready:
        return []

    limit = max(1, min(limit, _MAX_LIMIT))
    rerank_candidates = max(limit, rerank_candidates)
    bundle = _build_bm25(corpus)

    # Pull a large enough candidate pool for reranking if requested.
    pool_size = max(_CANDIDATE_POOL, rerank_candidates) if reranker else _CANDIDATE_POOL

    bm25_ranking = _bm25_rank(query, bundle, top_n=pool_size)

    rankings: list[list[tuple[int, float]]] = []
    if bm25_ranking:
        rankings.append(bm25_ranking)

    dense_ranking: list[tuple[int, float]] = []
    if vector_store is not None:
        try:
            if vector_store.count(_COLLECTION) > 0:
                dense_ranking = _dense_rank(query, embedder, vector_store, top_n=pool_size)
        except Exception:
            logger.warning("Dense retrieval failed — falling back to BM25 only", exc_info=True)
            dense_ranking = []

    if dense_ranking:
        rankings.append(dense_ranking)

    if not rankings:
        return []

    fused = rankings[0] if len(rankings) == 1 else _rrf_fuse(rankings)

    if reranker is not None:
        reranked = _apply_reranker(
            query=query,
            fused=fused,
            corpus=corpus,
            reranker=reranker,
            rerank_candidates=rerank_candidates,
            limit=limit,
        )
        if reranked is not None:
            return _to_results(reranked, corpus, limit)

    return _to_results(fused, corpus, limit)
