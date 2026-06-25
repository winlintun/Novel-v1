#!/usr/bin/env python3
"""Build the combined ChatML fine-tuning dataset from ALL aligned novels.

Pulls BGE-M3-aligned EN→MY pairs out of the alignment database, applies the
pair-quality filter, splits by chapter (held-out test), and writes
train/val/test JSONL ready for LoRA fine-tuning.

Prereq: the alignment pipeline must have run for each novel first, e.g.
    python -m src.main --align-dataset            # all novels
or, to run it from here, pass --run-alignment.

Usage:
    python scripts/build_finetune_dataset.py
    python scripts/build_finetune_dataset.py --novels a-will-eternal renegade-immortal \\
        --holdout 30 --out data/finetune --run-alignment
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.dataset_alignment.database import connect          # noqa: E402
from src.dataset_alignment.alignment import get_all_aligned_pairs  # noqa: E402
from src.training.dataset_builder import build_splits, write_splits  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("build_finetune_dataset")


def _aligned_novels() -> list[str]:
    """Novels that have at least one stored 1:1 alignment."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT DISTINCT c.novel FROM alignments a "
            "JOIN chapters c ON a.chapter_id = c.id WHERE a.kind='1:1'"
        ).fetchall()
    return sorted(r["novel"] for r in rows)


def _chapter_no_map() -> dict[int, int]:
    """Map alignment chapter_id (DB row) → human chapter number."""
    with connect() as conn:
        rows = conn.execute("SELECT id, chapter_no FROM chapters").fetchall()
    return {r["id"]: r["chapter_no"] for r in rows}


def collect_pairs(novels: list[str], min_similarity: float) -> list[dict]:
    """Collect aligned pairs across novels, tagged with novel + chapter_no."""
    ch_map = _chapter_no_map()
    all_pairs: list[dict] = []
    for novel in novels:
        pairs = get_all_aligned_pairs(novel, min_similarity=min_similarity)
        for p in pairs:
            p["novel"] = novel
            p["chapter_no"] = ch_map.get(p.get("chapter_id"))
        all_pairs.extend(pairs)
        log.info("  %-22s %6d aligned pairs (sim>=%.2f)", novel, len(pairs), min_similarity)
    return all_pairs


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--novels", nargs="*", help="Novels to include (default: all aligned)")
    ap.add_argument("--out", default="data/finetune", help="Output directory")
    ap.add_argument("--holdout", type=int, default=20,
                    help="Held-out test chapters per novel (default 20)")
    ap.add_argument("--val-fraction", type=float, default=0.02)
    ap.add_argument("--min-similarity", type=float, default=0.70,
                    help="Min alignment cosine similarity to include (default 0.70)")
    ap.add_argument("--run-alignment", action="store_true",
                    help="Run the alignment pipeline for the novels first (slow)")
    args = ap.parse_args()

    if args.run_alignment:
        from src.dataset_alignment.pipeline import run_alignment_pipeline
        targets = args.novels or [
            d.name for d in Path("data/input").iterdir()
            if d.is_dir() and (d / "en").exists() and (d / "mm").exists()
        ]
        for novel in targets:
            log.info("Running alignment for %s ...", novel)
            run_alignment_pipeline(novel_name=novel, populate_rag=False,
                                   min_similarity=args.min_similarity)

    novels = args.novels or _aligned_novels()
    if not novels:
        log.error("No aligned novels found. Run the alignment pipeline first "
                  "(or pass --run-alignment).")
        sys.exit(1)

    log.info("Collecting aligned pairs from %d novel(s):", len(novels))
    pairs = collect_pairs(novels, args.min_similarity)
    log.info("Total raw aligned pairs: %d", len(pairs))

    splits = build_splits(pairs, holdout_chapters=args.holdout,
                          val_fraction=args.val_fraction)
    counts = write_splits(splits, args.out)

    log.info("\nWrote dataset to %s/", args.out)
    log.info("  train: %d", counts["train"])
    log.info("  val  : %d", counts["val"])
    log.info("  test : %d  (held-out chapters — used by chrF eval)", counts["test"])
    if counts["train"] < 2000:
        log.warning("Train set is small (<2k). Consider lowering --min-similarity "
                    "or aligning more novels for a stronger LoRA.")


if __name__ == "__main__":
    main()
