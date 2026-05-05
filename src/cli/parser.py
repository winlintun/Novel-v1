#!/usr/bin/env python3
"""
CLI argument parser for the novel translation pipeline.

Provides centralized argument parsing with support for:
- Translation commands (single chapter, all chapters, range)
- Configuration overrides
- Workflow selection (way1, way2)
- UI launching
- Glossary generation
"""

import argparse
from pathlib import Path
from typing import Optional, List


def create_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser.
    
    Returns:
        Configured ArgumentParser instance
    """
    parser = argparse.ArgumentParser(
        prog="novel-translate",
        description="AI-powered Chinese/English-to-Myanmar novel translation pipeline (Ollama-only)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
╔══════════════════════════════════════════════════════════════════════╗
║                    QUICKSTART EXAMPLES                              ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  TRANSLATION:                                                        ║
║    python -m src.main --novel reverend-insanity --chapter 1          ║
║    python -m src.main --novel reverend-insanity --all                ║
║    python -m src.main --novel reverend-insanity --chapter-range 1-5 ║
║    python -m src.main --novel reverend-insanity --all --start 10     ║
║    python -m src.main --input data/input/reverend-insanity/ch001.md ║
║    python -m src.main --novel reverend-insanity --all --mode fast    ║
║                                                                      ║
║  WORKFLOW:                                                           ║
║    python -m src.main --novel reverend-insanity --ch 1 --workflow way1  (EN→MM)
║    python -m src.main --novel reverend-insanity --ch 1 --lang zh        (auto way2)
║    python -m src.main --novel reverend-insanity --ch 1 --skip-refinement
║                                                                      ║
║  QUALITY & REVIEW:                                                   ║
║    python -m src.main --review data/output/reverend-insanity/ch017.mm.md
║    python -m src.main --stats --novel reverend-insanity              ║
║    python -m src.main --view data/output/reverend-insanity/ch017.mm.md
║                                                                      ║
║  GLOSSARY:                                                           ║
║    python -m src.main --novel reverend-insanity --generate-glossary --chapter-range 1-5
║    python -m src.main --auto-promote --novel reverend-insanity       ║
║                                                                      ║
║  UTILITIES:                                                          ║
║    python -m src.main --ui         (launch Streamlit web UI)         ║
║    python -m src.main --test       (run sample translation test)     ║
║    python -m src.main --clean      (clear Python cache)              ║
║    python -m src.main --version    (show version)                    ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
        """
    )

    # Input options
    input_group = parser.add_argument_group("Input Options")
    input_group.add_argument(
        "--novel",
        type=str,
        help="Name of the novel to translate"
    )
    input_group.add_argument(
        "--chapter",
        type=int,
        help="Chapter number to translate"
    )
    input_group.add_argument(
        "--input",
        type=str,
        dest="input_file",
        help="Path to single input file to translate"
    )
    input_group.add_argument(
        "--all",
        action="store_true",
        help="Translate all chapters"
    )
    input_group.add_argument(
        "--start",
        type=int,
        default=1,
        help="Start chapter for range translation (default: 1)"
    )
    input_group.add_argument(
        "--end",
        type=int,
        help="End chapter for range translation"
    )
    input_group.add_argument(
        "--chapter-range",
        type=str,
        help="Chapter range (e.g., '1-10')"
    )

    # Configuration options
    config_group = parser.add_argument_group("Configuration Options")
    config_group.add_argument(
        "--config",
        type=str,
        default="config/settings.yaml",
        help="Path to configuration file (default: config/settings.yaml)"
    )
    config_group.add_argument(
        "--model",
        type=str,
        help="Override translator model"
    )
    config_group.add_argument(
        "--provider",
        type=str,
        help="Override model provider"
    )

    # Workflow options
    workflow_group = parser.add_argument_group("Workflow Options")
    workflow_group.add_argument(
        "--workflow",
        type=str,
        choices=["way1", "way2"],
        help="Translation workflow: way1 (EN->MM direct), way2 (CN->EN->MM pivot)"
    )
    workflow_group.add_argument(
        "--lang",
        type=str,
        choices=["zh", "chinese", "en", "english"],
        help="Source language (alias for workflow selection)"
    )
    workflow_group.add_argument(
        "--two-stage",
        action="store_true",
        help="Enable two-stage translation mode"
    )
    workflow_group.add_argument(
        "--skip-refinement",
        action="store_true",
        help="Skip the refinement stage (faster, lower quality)"
    )

    # Pipeline options
    pipeline_group = parser.add_argument_group("Pipeline Options")
    pipeline_group.add_argument(
        "--mode",
        type=str,
        choices=["full", "lite", "fast", "single_stage"],
        help="Pipeline mode: single_stage (1-stage, recommended), lite (3-stage), fast (2-stage), full (6-stage)"
    )
    pipeline_group.add_argument(
        "--use-reflection",
        action="store_true",
        help="Enable reflection agent for self-correction"
    )
    pipeline_group.add_argument(
        "--no-quality-check",
        action="store_true",
        help="Disable Myanmar quality checking"
    )

    # Output options
    output_group = parser.add_argument_group("Output Options")
    output_group.add_argument(
        "--output-dir",
        type=str,
        help="Override output directory"
    )
    output_group.add_argument(
        "--no-metadata",
        action="store_true",
        help="Don't add metadata headers to output"
    )

    # Memory optimization
    memory_group = parser.add_argument_group("Memory Optimization")
    memory_group.add_argument(
        "--unload-after-chapter",
        action="store_true",
        help="Unload model from GPU after each chapter"
    )

    # Utility commands
    utility_group = parser.add_argument_group("Utility Commands")
    utility_group.add_argument(
        "--ui",
        action="store_true",
        help="Launch web UI (default: Flask, port 5000)"
    )
    utility_group.add_argument(
        "--flask",
        action="store_true",
        help="Launch Flask web UI (default port: 5000)"
    )
    utility_group.add_argument(
        "--streamlit",
        action="store_true",
        help="Launch Streamlit web UI (port: 8501)"
    )
    utility_group.add_argument(
        "--port",
        type=int,
        default=5000,
        help="Port for Flask server (default: 5000)"
    )
    utility_group.add_argument(
        "--generate-glossary",
        action="store_true",
        help="Generate glossary from novel chapters"
    )
    utility_group.add_argument(
        "--test",
        action="store_true",
        help="Run test translation with sample file"
    )
    utility_group.add_argument(
        "--view",
        type=str,
        dest="view_file",
        help="View a translated .mm.md file with formatted output in terminal"
    )
    utility_group.add_argument(
        "--review",
        type=str,
        dest="review_file",
        help="Review a translated .mm.md file against quality rules and generate report"
    )
    utility_group.add_argument(
        "--auto-promote",
        action="store_true",
        help="Auto-promote high-confidence pending glossary terms to approved glossary"
    )
    utility_group.add_argument(
        "--approve-glossary",
        action="store_true",
        help="Bulk approve ALL pending glossary terms and add to glossary.json"
    )
    utility_group.add_argument(
        "--stats",
        action="store_true",
        help="Show per-chapter quality score trends for a novel"
    )
    utility_group.add_argument(
        "--version",
        action="version",
        version="%(prog)s 2.0.0",
        help="Show version information"
    )

    return parser


def parse_arguments(args: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command line arguments.
    
    Args:
        args: Command line arguments (defaults to sys.argv)
        
    Returns:
        Parsed arguments namespace
    """
    parser = create_parser()
    return parser.parse_args(args)


def validate_arguments(args: argparse.Namespace) -> None:
    """Validate parsed arguments.
    
    Args:
        args: Parsed arguments
        
    Raises:
        SystemExit: If validation fails
    """
    # Check for required arguments when not running utility commands
    # --generate-glossary --novel X is a standalone command (no chapter required)
    utility_commands = [args.ui, args.test, args.generate_glossary, args.approve_glossary, args.view_file, args.review_file, args.auto_promote, args.stats]

    if not any(utility_commands):
        if not args.novel and not args.input_file:
            raise SystemExit(
                "Error: Either --novel, --input, or a utility command (--ui, --test) is required.\n"
                "Use --help for usage information."
            )

        if args.novel and not (args.chapter or args.all or args.chapter_range):
            raise SystemExit(
                "Error: When using --novel, specify --chapter, --all, or --chapter-range.\n"
                "Use --help for usage information."
            )

    # Validate chapter range format
    if args.chapter_range:
        try:
            parts = args.chapter_range.split('-')
            if len(parts) != 2:
                raise ValueError()
            start, end = int(parts[0]), int(parts[1])
            if start < 1 or end < start:
                raise ValueError()
        except ValueError:
            raise SystemExit(
                f"Error: Invalid chapter range format: {args.chapter_range}\n"
                "Expected format: 'start-end' (e.g., '1-10')"
            )

    # Validate input file exists
    if args.input_file and not Path(args.input_file).exists():
        raise SystemExit(f"Error: Input file not found: {args.input_file}")

    # Validate config file exists
    if args.config and not Path(args.config).exists():
        raise SystemExit(f"Error: Config file not found: {args.config}")


def get_chapter_list(args: argparse.Namespace) -> List[int]:
    """Get list of chapters to translate from arguments.
    
    Args:
        args: Parsed arguments
        
    Returns:
        List of chapter numbers
    """
    if args.chapter:
        return [args.chapter]

    if args.chapter_range:
        start, end = map(int, args.chapter_range.split('-'))
        return list(range(start, end + 1))

    if args.all:
        # Return empty list to indicate "all chapters"
        return []

    return []
