"""Ingest the MySQL menu into a Qdrant collection.

Reads all ``foods`` joined with ``restaurants`` via
``fos_ai.db.menu_repo.fetch_all_foods``, encodes each item with the
multilingual MiniLM embedder, and upserts into the ``menu_items``
collection of the target Qdrant instance.

Usage:
    uv run python scripts/ingest_menu_to_qdrant.py \\
        --qdrant-url http://localhost:6333

Credentials are read from environment / .env via ``Settings``.
"""

from __future__ import annotations

import argparse
import logging
import sys

import mysql.connector

from fos_ai.config import Settings
from fos_ai.db.menu_repo import fetch_all_foods
from fos_ai.ml.corpus import build_corpus
from fos_ai.ml.embedding import Embedder
from fos_ai.ml.vector_store import VectorStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ingest_menu")

_COLLECTION = "menu_items"


def _parse_args() -> argparse.Namespace:
    settings = Settings()
    parser = argparse.ArgumentParser(description="Ingest MySQL menu into Qdrant")
    parser.add_argument(
        "--qdrant-url",
        default=settings.qdrant_url or "http://localhost:6333",
        help="Qdrant URL (default: QDRANT_URL env or http://localhost:6333)",
    )
    parser.add_argument(
        "--collection",
        default=_COLLECTION,
        help="Qdrant collection name (default: menu_items)",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    settings = Settings()

    logger.info("Connecting to MySQL %s@%s/%s", settings.db_user, settings.db_host, settings.db_name)
    conn = mysql.connector.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_pass,
        database=settings.db_name,
    )
    try:
        menu = fetch_all_foods(conn)
    finally:
        conn.close()

    if not menu:
        logger.error("Menu is empty — aborting")
        return 1
    logger.info("Loaded %d menu items", len(menu))

    embedder = Embedder()
    corpus = build_corpus(menu, embedder)

    logger.info("Connecting to Qdrant %s", args.qdrant_url)
    store = VectorStore(url=args.qdrant_url)
    store.ensure_collection(args.collection, dim=embedder.dim)

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

    store.upsert(args.collection, points)
    logger.info("Ingestion complete — %d points in %s", len(points), args.collection)
    return 0


if __name__ == "__main__":
    sys.exit(main())
