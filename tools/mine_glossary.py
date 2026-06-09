#!/usr/bin/env python3
"""
Run offline glossary mining on a parallel EN/MM corpus.

Usage:
    python tools/mine_glossary.py ^
        --novel-id novel_wayfarer ^
        --en-dir data/input/wayfarer ^
        --my-dir data/output/wayfarer ^
        [--dry-run] [--no-llm] [--limit-chapters 5]

All results go directly to the SQLite database — no JSON files.
"""

import argparse
import json
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from glossary_extraction.config import PipelineConfig
from glossary_extraction.pipeline import run_pipeline


def main() -> int:
    p = argparse.ArgumentParser(description="Mine glossary from parallel EN/MM corpus")
    p.add_argument("--novel-id", required=True, help="e.g. novel_wayfarer")
    p.add_argument("--en-dir", required=True, type=Path, help="Directory of English chapter files")
    p.add_argument("--my-dir", required=True, type=Path, help="Directory of Myanmar chapter files")
    p.add_argument("--db-path", type=Path, default=Path("data/novel_translation.db"))
    p.add_argument("--limit-chapters", type=int, default=0, help="Process only first N chapters (0 = all)")
    p.add_argument("--no-llm", action="store_true", help="Skip Ollama LLM verification step")
    p.add_argument("--dry-run", action="store_true", help="No DB writes; print preview only")
    p.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    p.add_argument("--chapter-regex", default=r"chapter[_\-\s]*(\d+)", help="Regex with group(1) = chapter number")

    args = p.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    if args.dry_run:
        print("=" * 60)
        print("  DRY RUN MODE — No database changes will be made")
        print("=" * 60)

    cfg = PipelineConfig(
        db_path=args.db_path,
        en_dir=args.en_dir,
        my_dir=args.my_dir,
        novel_id=args.novel_id,
        limit_chapters=args.limit_chapters,
        use_llm_verify=not args.no_llm,
        dry_run=args.dry_run,
        log_level=args.log_level,
        chapter_regex=args.chapter_regex,
    )

    summary = run_pipeline(cfg)

    print("\n" + "=" * 60)
    print("  GLOSSARY MINING — FINAL SUMMARY")
    print("=" * 60)
    print(json.dumps(summary, indent=2))

    if args.dry_run:
        print("\n  *** DRY RUN — No changes committed ***")

    return 0 if "error" not in summary else 1


if __name__ == "__main__":
    sys.exit(main())
