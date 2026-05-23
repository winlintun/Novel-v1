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
║  🚀 QUICK START (Default: padauk-gemma:q8_0):                        ║
║    python -m src.main --novel sample --chapter 1                     ║
║    python -m src.main --novel wayfarer --chapter-range 21-35         ║
║    python -m src.main --novel reverend-insanity --all                ║
║                                                                      ║
║  📊 COMPARE MODELS (Test ALL models on same chapter):                ║
║    # Translate with all Myanmar models, save to logs/temp/           ║
║    python -m src.main --novel sample --chapter 1 --compare-models    ║
║    python compare_all_models.py --novel sample --chapter 1           ║
║                                                                      ║
║  ⚙️  MODEL CONFIG (Skeleton System):                                 ║
║    # 1. Edit config/models.skeleton.yaml → Set active_model         ║
║    # 2. Run translation (auto-uses active model):                   ║
║    python -m src.main --novel sample --chapter 1                     ║
║    # Override for one run:                                          ║
║    python -m src.main --novel sample --chapter 1 --model qwen:7b     ║
║                                                                      ║
║  🌐 WORKFLOW (Auto-detected):                                        ║
║    python -m src.main --novel novel --ch 1 --workflow way1  (EN→MM)  ║
║    python -m src.main --novel novel --ch 1 --lang zh        (CN→MM)  ║
║                                                                      ║
║  🔍 QUALITY & REVIEW:                                                ║
║    python -m src.main --review output/reverend-insanity/ch017.mm.md  ║
║    python -m src.main --stats --novel reverend-insanity              ║
║    python -m src.main --view output/reverend-insanity/ch017.mm.md    ║
║                                                                      ║
║  📚 GLOSSARY:                                                        ║
║    python -m src.main --novel novel --generate-glossary --ch-range 1-5
║    python -m src.main --auto-promote --novel novel                   ║
║                                                                      ║
║  🖥️  WEB UI:                                                          ║
║    python -m src.main --ui                                           ║
║    python -m src.main --flask --port 8080                            ║
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
    config_group.add_argument(
        "--use-sql",
        action="store_true",
        dest="use_sql",
        help="Use SQLite backend for glossary storage (default: uses config setting)"
    )
    config_group.add_argument(
        "--migrate-sql",
        action="store_true",
        dest="migrate_sql",
        help="Migrate existing JSON glossary to SQLite and exit"
    )
    config_group.add_argument(
        "--db-path",
        type=str,
        dest="db_path",
        default="data/novel_translation.db",
        help="Path to SQLite database (default: data/novel_translation.db)"
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
        help="Launch Flask web UI (port 5000)"
    )
    utility_group.add_argument(
        "--flask",
        action="store_true",
        help="Launch Flask web UI — Dashboard, Translate, Editor, Cleanup, Reader (default port: 5000)"
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
        "--init-glossary",
        action="store_true",
        help="Generate initial glossary (chapters 1-5) then stop for human review. Run --approve-glossary after reviewing."
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
        "--compare-models",
        action="store_true",
        help="Translate chapter with ALL models and save to logs/temp/ for comparison"
    )
    utility_group.add_argument(
        "--model-categories",
        nargs="+",
        choices=["myanmar", "pivot", "utility"],
        default=["myanmar"],
        help="Model categories to test with --compare-models (default: myanmar)"
    )
    utility_group.add_argument(
        "--version",
        action="version",
        version="%(prog)s 2.0.0",
        help="Show version information"
    )

    # Versioning commands
    versioning_group = parser.add_argument_group("Version Control & Change Tracking")
    versioning_group.add_argument(
        "--versions",
        action="store_true",
        help="List chapter versions (requires --novel and --chapter)"
    )
    versioning_group.add_argument(
        "--rollback",
        type=int,
        metavar="VERSION",
        help="Rollback chapter to specific version (requires --novel, --chapter, --rollback N)"
    )
    versioning_group.add_argument(
        "--diff",
        type=str,
        metavar="A,B",
        help="Show diff between two versions (e.g., --diff 1,3)"
    )
    versioning_group.add_argument(
        "--preview-sync",
        type=str,
        metavar="TERM_ID=NEW_VALUE",
        help="Preview which chapters would be affected by a glossary change (e.g., --preview-sync term_123=NEW_VALUE)"
    )
    versioning_group.add_argument(
        "--create-sync-job",
        type=str,
        metavar="TERM_ID=NEW_VALUE",
        help="Create a sync job for glossary change (e.g., --create-sync-job term_123=NEW_VALUE)"
    )
    versioning_group.add_argument(
        "--execute-sync",
        type=int,
        metavar="JOB_ID",
        help="Execute a sync job (use --dry-run to preview)"
    )
    versioning_group.add_argument(
        "--list-sync-jobs",
        action="store_true",
        help="List all sync jobs (optionally filter with --novel)"
    )
    versioning_group.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview sync job without applying changes"
    )
    versioning_group.add_argument(
        "--audit-log",
        action="store_true",
        help="Show audit log (optionally filter with --novel)"
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
    versioning_commands = [args.versions, args.rollback, args.diff, args.preview_sync, args.create_sync_job, args.execute_sync, args.list_sync_jobs, args.audit_log]
    utility_commands = [args.ui, args.test, args.generate_glossary, args.init_glossary, args.approve_glossary, args.view_file, args.review_file, args.auto_promote, args.stats] + versioning_commands

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
