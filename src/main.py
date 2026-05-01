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
    run_ui_launch,
    run_test,
    run_view_file,
    run_review,
)


def main() -> int:
    """Main entry point.
    
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    # Parse arguments
    args = parse_arguments()
    
    # Handle utility commands first
    if args.ui:
        return run_ui_launch(args)
    
    if args.test:
        return run_test(args)
    
    if args.view_file:
        return run_view_file(args)

    if args.review_file:
        return run_review(args)
    
    # Validate arguments for translation commands
    validate_arguments(args)
    
    # Handle glossary generation
    if args.generate_glossary:
        return run_glossary_generation(args)
    
    # Run translation pipeline
    return run_translation_pipeline(args)


if __name__ == "__main__":
    sys.exit(main())
