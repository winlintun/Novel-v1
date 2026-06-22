#!/usr/bin/env python3
"""Backfill the ChromaDB ``alignment_pairs`` collection from existing SQLite pairs.

The 83k rows in ``translation_pairs`` (data/novel_v1_dataset.db) were ingested by
an older alignment run that predates the ChromaDB-ingest code, so the semantic
index (data/chroma) was never built and RAGRetriever silently degrades to SQLite
keyword matching. This script embeds the already-clean SQLite pairs with BGE-M3
and upserts them into Chroma, writing exactly the metadata keys RAGRetriever
reads (my_text, auto_score, source_file, novel).

It re-uses the SQLite ``id`` as the Chroma id, so re-running is idempotent and
resumable — already-embedded pairs are simply overwritten in place.

Usage:
    python tools/backfill_chroma.py
    python tools/backfill_chroma.py --novel a-will-eternal --batch-size 256
"""

import argparse
import logging
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.dataset_alignment.embedder import BGEEmbedder

logger = logging.getLogger("backfill_chroma")


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill ChromaDB from SQLite translation_pairs")
    parser.add_argument("--db-path", default="data/novel_v1_dataset.db")
    parser.add_argument("--chroma-path", default="data/chroma")
    parser.add_argument("--collection", default="alignment_pairs")
    parser.add_argument("--novel", default=None, help="Limit to one novel_slug")
    parser.add_argument("--batch-size", type=int, default=256,
                        help="Pairs embedded + upserted per batch")
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    sys.stdout.reconfigure(encoding="utf-8")

    db_path = Path(args.db_path)
    if not db_path.exists():
        logger.error("SQLite DB not found: %s", db_path)
        return 1

    try:
        import chromadb
    except ImportError:
        logger.error("chromadb not installed — cannot backfill.")
        return 1

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    where = "WHERE usable = 1"
    params: list = []
    if args.novel:
        where += " AND novel_slug = ?"
        params.append(args.novel)

    total = conn.execute(
        f"SELECT COUNT(*) AS c FROM translation_pairs {where}", params
    ).fetchone()["c"]
    if total == 0:
        logger.warning("No usable pairs found to backfill.")
        return 0
    logger.info("Backfilling %d usable pairs into Chroma collection '%s'", total, args.collection)

    embedder = BGEEmbedder()
    chroma_path = Path(args.chroma_path)
    chroma_path.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(chroma_path))
    collection = client.get_or_create_collection(name=args.collection)
    start_count = collection.count()
    logger.info("Collection currently holds %d embeddings", start_count)

    # Keep each upsert well under Chroma's 5461 max-batch ceiling.
    try:
        max_batch = min(client.get_max_batch_size(), 2000)
    except Exception:
        max_batch = 2000
    batch_size = min(args.batch_size, max_batch)

    cursor = conn.execute(
        f"""SELECT id, en_text, my_text, auto_score, novel_slug,
                   source_file, chapter_num
            FROM translation_pairs {where}
            ORDER BY id""",
        params,
    )

    ingested = 0
    t0 = time.time()
    batch: list[sqlite3.Row] = []

    def flush(rows: list[sqlite3.Row]) -> int:
        if not rows:
            return 0
        texts = [r["en_text"] for r in rows]
        embeddings = embedder.encode(texts)
        if embeddings is None or getattr(embeddings, "size", 0) == 0:
            logger.warning("Empty embeddings for a batch — skipping %d rows", len(rows))
            return 0
        collection.upsert(
            ids=[r["id"] for r in rows],
            embeddings=[e.tolist() for e in embeddings],
            documents=texts,
            metadatas=[{
                "my_text": (r["my_text"] or "")[:1000],
                "auto_score": str(r["auto_score"] if r["auto_score"] is not None else 0.0),
                "source_file": r["source_file"] or f"{r['novel_slug']}_chapter_{r['chapter_num']}",
                "novel": r["novel_slug"] or "",
            } for r in rows],
        )
        return len(rows)

    for row in cursor:
        batch.append(row)
        if len(batch) >= batch_size:
            ingested += flush(batch)
            batch = []
            rate = ingested / max(time.time() - t0, 1e-6)
            eta = (total - ingested) / max(rate, 1e-6)
            logger.info("  %d/%d (%.0f/s, ETA %.0fs)", ingested, total, rate, eta)

    ingested += flush(batch)

    end_count = collection.count()
    logger.info("=" * 50)
    logger.info("Backfill complete: %d pairs embedded in %.0fs", ingested, time.time() - t0)
    logger.info("Collection '%s' now holds %d embeddings (was %d)",
                args.collection, end_count, start_count)
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
