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
)


def main() -> int:
    """Main entry point.
    
    Command priority (descending):
    1. --ui  (with optional --novel --chapter to translate first)
    2. --test, --view, --review, --stats, --auto-promote (standalone)
    3. --generate-glossary (before translation if both specified)
    4. Translation pipeline (--novel / --input)
    
    If --generate-glossary AND --novel --chapter are both given,
    run glossary generation first, then translation.
    
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    # Parse arguments
    args = parse_arguments()

    # ── UI: if --novel and --chapter also given, translate first ──
    if args.ui:
        if args.novel and (args.chapter or args.all or args.chapter_range):
            result = _run_translation_with_opts(args)
            if result != 0:
                return result
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

    # ── Translation commands (with optional glossary generation) ──
    # Validate arguments for translation
    validate_arguments(args)

    # Generate glossary BEFORE translation if requested
    if args.generate_glossary:
        result = run_glossary_generation(args)
        if result != 0:
            return result

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
