#!/usr/bin/env python3
"""
Run the Dataset Alignment Pipeline — process parallel EN/MM chapter files,
align sentences, run quality validators, and populate the RAG database.

This pipeline gives the RAG system real EN-MY pairs to retrieve from
during translation, improving consistency and quality.

Usage:
    python tools/run_dataset_alignment.py --novel a-will-eternal
    python tools/run_dataset_alignment.py --all
    python tools/run_dataset_alignment.py --all --skip-validators
    python tools/run_dataset_alignment.py --novel a-will-eternal --min-similarity 0.6
    python tools/run_dataset_alignment.py --novel a-will-eternal --no-rag
"""

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.dataset_alignment.pipeline import run_alignment_pipeline


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Dataset Alignment Pipeline — prepare EN/MM pairs for RAG",
    )
    parser.add_argument("--novel", help="Novel name (e.g., a-will-eternal)")
    parser.add_argument("--all", action="store_true", help="Process all novels in data/input/")
    parser.add_argument("--skip-validators", action="store_true", help="Skip quality validation")
    parser.add_argument("--no-rag", action="store_true", help="Skip RAG database population")
    parser.add_argument("--min-similarity", type=float, default=0.50,
                        help="Minimum cosine similarity for 1:1 alignment (default: 0.50)")
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"])

    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    if not args.novel and not args.all:
        parser.print_help()
        print("\nError: specify --novel NAME or --all")
        return 1

    novel_name = None if args.all else args.novel

    summary = run_alignment_pipeline(
        novel_name=novel_name,
        skip_validators=args.skip_validators,
        populate_rag=not args.no_rag,
        min_similarity=args.min_similarity,
    )

    print(f"\n{'='*60}")
    print("  DATASET ALIGNMENT — COMPLETE")
    print(f"{'='*60}")
    print(json.dumps(summary, indent=2, default=str))

    if summary.get("errors"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
