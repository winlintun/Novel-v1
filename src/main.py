#!/usr/bin/env python3
"""
Main Entry Point - Novel Translation Pipeline

Thin dispatcher that delegates to specialized modules:
- cli/parser.py: Argument parsing
- cli/commands.py: Command handlers
- cli/formatters.py: Output formatting
- pipeline/orchestrator.py: Pipeline coordination
- web/launcher.py: UI launching

Usage:
    python -m src.main --novel 古道仙鸿 --chapter 1
    python -m src.main --novel 古道仙鸿 --all
    python -m src.main --novel 古道仙鸿 --all --start 10
    python -m src.main --input data/input/古道仙鸿_001.md
    python -m src.main --ui
    python -m src.main --test
"""

import os
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.cli import parse_arguments, validate_arguments
from src.cli.commands import (
    run_translation_pipeline,
    run_glossary_generation,
    run_glossary_promotion,
    run_stats,
    run_ui_launch,
    run_test,
    run_view_file,
    run_review,
    run_rebuild_meta,
)


def main() -> int:
    """Main entry point.
    
    Command priority (descending):
    1. --ui → opens Web UI (pass --novel/--chapter as hints via env vars)
    2. --test, --view, --review, --stats, --auto-promote, --rebuild-meta (standalone)
    3. --generate-glossary (runs before translation if both specified)
    4. Translation pipeline (--novel / --input)
    
    When --ui is used with --novel/--chapter, the settings are passed
    as environment variables to the Web UI so it can pre-fill the
    translation form. Translation itself runs from inside the UI.
    
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    # Parse arguments
    args = parse_arguments()

    if args.clean:
        from src.utils.cache_cleaner import clean_cache_with_report
        clean_cache_with_report()
        return 0

    if getattr(args, 'rebuild_meta', False):
        return run_rebuild_meta(args)

    # ── UI: open UI, pass novel/chapter settings as env hints ──
    if args.ui:
        # Pass CLI settings to UI via environment variables
        if args.novel:
            os.environ["NOVEL_TRANSLATE_NOVEL"] = args.novel
        if args.chapter:
            os.environ["NOVEL_TRANSLATE_CHAPTER"] = str(args.chapter)
        if args.all:
            os.environ["NOVEL_TRANSLATE_ALL"] = "1"
        if args.start and args.start > 1:
            os.environ["NOVEL_TRANSLATE_START"] = str(args.start)
        if args.generate_glossary:
            os.environ["NOVEL_TRANSLATE_GEN_GLOSSARY"] = "1"
        return run_ui_launch(args)

    # ── Standalone utilities (no translation) ──
    if args.test:
        return run_test(args)

    if args.view_file:
        return run_view_file(args)

    if args.review_file:
        return run_review(args)

    if args.auto_promote:
        return run_glossary_promotion(args)

    if args.stats:
        return run_stats(args)

    # ── Glossary generation (standalone or pre-translation) ──
    if args.generate_glossary:
        result = run_glossary_generation(args)
        if result != 0:
            return result
        # Standalone glossary run — no chapter/all specified, stop here
        if not (args.chapter or args.all or getattr(args, 'chapter_range', None) or args.input_file):
            return result

    # ── Translation commands ──
    # Validate arguments for translation (chapter/all required)
    validate_arguments(args)

    # Run translation pipeline
    return _run_translation_with_opts(args)


def _run_translation_with_opts(args) -> int:
    """Run translation pipeline with optional pre-processing."""
    from src.config import load_config

    config = load_config(args.config)

    # Override model if specified
    if hasattr(args, 'model') and args.model:
        config.models.translator = args.model
        config.models.editor = args.model

    # Override mode
    if hasattr(args, 'mode') and args.mode:
        config.translation_pipeline.mode = args.mode

    # Override output dir
    if hasattr(args, 'output_dir') and args.output_dir:
        config.paths.output_dir = args.output_dir

    return run_translation_pipeline(args)


if __name__ == "__main__":
    sys.exit(main())
