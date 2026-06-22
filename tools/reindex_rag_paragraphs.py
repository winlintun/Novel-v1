#!/usr/bin/env python3
"""Build a PARAGRAPH-level ChromaDB index for RAG retrieval.

The original ``alignment_pairs`` collection holds *sentence*-level EN→MY pairs,
but the translator queries with ~600-char paragraph chunks. That granularity
mismatch makes cosine similarity collapse (~0.06–0.18 in practice), so semantic
RAG injects near-irrelevant examples and is effectively dead weight.

This tool reconstructs paragraph-level pairs from the sentence alignment DB
(``data/novel_alignment.db``): for each chapter it walks the 1:1 aligned pairs in
source-sentence order and groups consecutive ones into paragraph-sized units,
then embeds the English paragraph and upserts it into a new collection
(``alignment_paragraphs``) whose ``my_text`` metadata is the matching Myanmar
paragraph. Querying this with a chunk yields meaningful similarity.

Usage:
    python tools/reindex_rag_paragraphs.py --novel a-will-eternal
    python tools/reindex_rag_paragraphs.py --novel a-will-eternal --target-chars 500
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from src.dataset_alignment.database import connect
from src.dataset_alignment.embedder import BGEEmbedder

logger = logging.getLogger("reindex_rag_paragraphs")


def _iter_paragraphs(novel: str, target_chars: int, max_sents: int, min_sim: float):
    """Yield (para_id, en_para, my_para, avg_sim, chapter_no) paragraph units."""
    with connect() as conn:
        chapters = conn.execute(
            "SELECT id, chapter_no FROM chapters WHERE novel=? ORDER BY chapter_no",
            (novel,),
        ).fetchall()

        for ch in chapters:
            ch_id, ch_no = ch["id"], ch["chapter_no"]
            rows = conn.execute(
                """SELECT src_ids, tgt_ids, similarity FROM alignments
                   WHERE chapter_id=? AND kind='1:1' AND similarity>=?""",
                (ch_id, min_sim),
            ).fetchall()

            # Resolve sentence texts and order by source sentence seq.
            pairs = []
            for r in rows:
                try:
                    s_seq = json.loads(r["src_ids"])[0]
                    t_seq = json.loads(r["tgt_ids"])[0]
                except (json.JSONDecodeError, TypeError, IndexError):
                    continue
                src = conn.execute(
                    "SELECT text FROM sentences WHERE chapter_id=? AND seq=? AND lang='en'",
                    (ch_id, s_seq),
                ).fetchone()
                tgt = conn.execute(
                    "SELECT text FROM sentences WHERE chapter_id=? AND seq=? AND lang='my'",
                    (ch_id, t_seq),
                ).fetchone()
                if src and tgt and src["text"].strip() and tgt["text"].strip():
                    pairs.append((s_seq, src["text"].strip(), tgt["text"].strip(), r["similarity"]))

            pairs.sort(key=lambda p: p[0])

            # Group consecutive pairs into paragraph-sized windows.
            en_buf, my_buf, sims = [], [], []
            seq_start = None
            for s_seq, en, my, sim in pairs:
                if seq_start is None:
                    seq_start = s_seq
                en_buf.append(en)
                my_buf.append(my)
                sims.append(sim)
                en_len = sum(len(x) for x in en_buf)
                if en_len >= target_chars or len(en_buf) >= max_sents:
                    yield (
                        f"{novel}_ch{ch_no}_p{seq_start}",
                        " ".join(en_buf), " ".join(my_buf),
                        sum(sims) / len(sims), ch_no,
                    )
                    en_buf, my_buf, sims, seq_start = [], [], [], None
            if en_buf:
                yield (
                    f"{novel}_ch{ch_no}_p{seq_start}",
                    " ".join(en_buf), " ".join(my_buf),
                    sum(sims) / len(sims), ch_no,
                )


def main() -> int:
    p = argparse.ArgumentParser(description="Build paragraph-level RAG index")
    p.add_argument("--novel", required=True)
    p.add_argument("--chroma-path", default="data/chroma")
    p.add_argument("--collection", default="alignment_paragraphs")
    p.add_argument("--target-chars", type=int, default=500,
                   help="Approx English chars per paragraph unit (default 500)")
    p.add_argument("--max-sents", type=int, default=6,
                   help="Max sentences per paragraph unit (default 6)")
    p.add_argument("--min-sim", type=float, default=0.65,
                   help="Min sentence-alignment similarity to include (default 0.65)")
    p.add_argument("--batch-size", type=int, default=256)
    p.add_argument("--log-level", default="INFO")
    args = p.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level),
                        format="%(asctime)s - %(levelname)s - %(message)s")

    try:
        import chromadb
    except ImportError:
        logger.error("chromadb not installed.")
        return 1

    logger.info("Reconstructing paragraph units for '%s'...", args.novel)
    units = list(_iter_paragraphs(args.novel, args.target_chars, args.max_sents, args.min_sim))
    if not units:
        logger.warning("No paragraph units produced — is the alignment DB populated?")
        return 0
    logger.info("Built %d paragraph units. Embedding + indexing...", len(units))

    embedder = BGEEmbedder()
    chroma_path = Path(args.chroma_path)
    chroma_path.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(chroma_path))
    # Rebuild cleanly so stale units never linger.
    try:
        client.delete_collection(args.collection)
    except Exception:
        pass
    collection = client.get_or_create_collection(name=args.collection)

    try:
        max_batch = min(client.get_max_batch_size(), 2000)
    except Exception:
        max_batch = 2000
    batch_size = min(args.batch_size, max_batch)

    t0 = time.time()
    done = 0
    for start in range(0, len(units), batch_size):
        batch = units[start:start + batch_size]
        en_texts = [u[1] for u in batch]
        embeddings = embedder.encode(en_texts)
        if embeddings is None or getattr(embeddings, "size", 0) == 0:
            logger.warning("Empty embeddings at offset %d — skipping", start)
            continue
        collection.upsert(
            ids=[u[0] for u in batch],
            embeddings=[e.tolist() for e in embeddings],
            documents=en_texts,
            metadatas=[{
                "my_text": u[2][:1500],
                "auto_score": str(round(min(2.5 + u[3] * 2.5, 5.0), 3)),
                "source_file": f"{args.novel}_chapter_{u[4]}",
                "novel": args.novel,
            } for u in batch],
        )
        done += len(batch)
        rate = done / max(time.time() - t0, 1e-6)
        eta = (len(units) - done) / max(rate, 1e-6)
        logger.info("  %d/%d (%.0f/s, ETA %.0fs)", done, len(units), rate, eta)

    logger.info("=" * 50)
    logger.info("Paragraph index complete: %d units in collection '%s' (%.0fs)",
                collection.count(), args.collection, time.time() - t0)
    logger.info("Set rag.collection: %s in config/settings.yaml to use it.", args.collection)
    return 0


if __name__ == "__main__":
    sys.exit(main())
