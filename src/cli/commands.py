#!/usr/bin/env python3
"""
CLI command handlers for the novel translation pipeline.

Implements command handlers for:
- Translation commands (single, all, range)
- Glossary generation
- UI launching
- Testing
"""

import os
import logging
from pathlib import Path
import argparse
from typing import Optional, List, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.config import AppConfig, load_config
from src.cli.parser import get_chapter_list
from src.exceptions import NovelTranslationError, ConfigurationError

# Constants
DEFAULT_CHUNK_SIZE = 1500
INPUT_DIR = "data/input"
OUTPUT_DIR = "data/output"
WORKING_DIR = "working_data"
LOG_DIR = "logs"
MAX_GLOSSARY_WORKERS = 4  # Parallel threads for glossary extraction


def _discover_chapters(novel_dir: Path) -> List[int]:
    """Discover all available chapter files in a novel directory.
    
    Args:
        novel_dir: Path to the novel's input directory
        
    Returns:
        Sorted list of chapter numbers found
    """
    import re
    chapters = set()
    
    if not novel_dir.exists():
        return []
    
    for file_path in novel_dir.glob("*.md"):
        filename = file_path.stem
        
        # Pattern 1: {novel_name}_chapter_{XXX}.md (e.g., wayfarer_chapter_001.md)
        match = re.match(r".+_chapter_(\d+)", filename)
        if match:
            chapters.add(int(match.group(1)))
            continue
            
        # Pattern 2: chapter_{XXX}.md (e.g., chapter_001.md)
        match = re.match(r"chapter_(\d+)", filename)
        if match:
            chapters.add(int(match.group(1)))
            continue
            
        # Pattern 3: {XXX}.md (e.g., 001.md)
        match = re.match(r"(\d+)", filename)
        if match:
            chapters.add(int(match.group(1)))
    
    return sorted(chapters)


def setup_logging(log_file: Optional[str] = None) -> logging.Logger:
    """Configure logging with file and console handlers.
    
    Args:
        log_file: Path to log file (optional)
        
    Returns:
        Configured logger
    """
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(WORKING_DIR, exist_ok=True)

    if not log_file:
        from datetime import datetime
        log_file = f"{LOG_DIR}/translation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    # Remove existing handlers to avoid duplicates
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8-sig'),
            logging.StreamHandler()
        ]
    )

    return logging.getLogger(__name__)


def run_translation_pipeline(args: argparse.Namespace) -> int:
    """Run the translation pipeline with given arguments.
    
    Args:
        args: Parsed command line arguments
        
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    # Clean cache if requested
    if getattr(args, 'clean', False):
        from src.utils.cache_cleaner import clean_cache_with_report
        clean_cache_with_report()

    logger = setup_logging()

    try:
        # Load configuration
        config = load_config(args.config)

        # Apply command line overrides
        if args.model:
            config.models.translator = args.model
            config.models.editor = args.model

        if args.provider:
            config.models.provider = args.provider

        if args.mode:
            config.translation_pipeline.mode = args.mode

        if args.use_reflection:
            config.translation_pipeline.use_reflection = True

        if args.output_dir:
            config.paths.output_dir = args.output_dir

        if args.no_metadata:
            config.output.add_metadata = False

        # Handle storage backend overrides
        if args.use_sql:
            config.storage.backend = "sqlite"
            logger.info("Using SQLite backend (CLI override)")

        if args.db_path:
            config.storage.db_path = args.db_path

        # Handle migrate-sql command
        if args.migrate_sql:
            return _run_sql_migration(args, config, logger)

        # Handle workflow resolution with auto-detection
        workflow = _resolve_workflow(args)
        detected_lang = None

        # Detect source language for display
        if hasattr(args, 'input_file') and args.input_file:
            try:
                from src.utils.file_handler import FileHandler
                from src.agents.preprocessor import Preprocessor
                text = FileHandler.read_text(args.input_file)
                preprocessor = Preprocessor()
                detected_lang = preprocessor.detect_language(text)
            except Exception:
                detected_lang = "unknown"

        if workflow:
            config = _apply_workflow_config(config, workflow, logger)

        # Get chapters to translate
        chapters = get_chapter_list(args)

        # Import formatters for verbose output
        from src.cli.formatters import (
            print_translation_header,
            print_pipeline_stages,
            print_success,
            print_error,
            print_info,
            print_section_header,
            print_auto_detection_result,
            print_progress_event,
        )

        # Print auto-detection results if workflow was auto-detected
        if workflow and detected_lang:
            models_info = {
                "translator": config.models.translator,
                "editor": config.models.editor,
                "refiner": config.models.refiner,
            }
            print_auto_detection_result(detected_lang, workflow, models_info)

        # Print detailed header information
        novel_name = args.novel if args.novel else (args.input_file if args.input_file else "Unknown")
        print_translation_header(config, novel_name)
        print_pipeline_stages(config)

        # Build progress reporter for live CLI output (after novel_name is set)
        def _progress_reporter(event: dict) -> None:
            print_progress_event(event, novel_name=novel_name)

        # Import and run pipeline
        from src.pipeline.orchestrator import TranslationPipeline

        pipeline = TranslationPipeline(config)
        pipeline.set_progress_callback(_progress_reporter)

        print_section_header("Starting Translation")

        # Wait for database to be available (retry on lock)
        import sqlite3
        import time
        from pathlib import Path
        
        db_path = config.storage.db_path if hasattr(config, 'storage') else "data/novel_translation.db"
        db_file = Path(db_path)
        
        if db_file.exists():
            max_wait = 30  # Maximum 30 seconds wait
            wait_interval = 0.5
            total_wait = 0
            
            while total_wait < max_wait:
                try:
                    # Try to open the database in read-write mode
                    conn = sqlite3.connect(str(db_file), timeout=1)
                    conn.execute("SELECT 1")
                    conn.close()
                    break  # Success, database is available
                except sqlite3.OperationalError as e:
                    if "database is locked" in str(e).lower():
                        if total_wait == 0:
                            print_info("Waiting for database to become available...")
                        time.sleep(wait_interval)
                        total_wait += wait_interval
                    else:
                        raise  # Different error, re-raise
            else:
                logger.error(f"Database locked for {max_wait}s - another process may be using it")
                print_error("Database is locked by another process. Please wait and try again.")
                return 1

        if args.input_file:
            # Single file translation
            print_info(f"Input file: {args.input_file}")
            result = pipeline.translate_file(args.input_file)
        elif args.novel:
            # Novel translation
            if args.all or args.chapter_range:
                results = pipeline.translate_novel(args.novel, chapters)
                # Handle list of results
                success_count = sum(1 for r in results if r.get("success"))
                total_count = len(results)

                if success_count == total_count:
                    logger.info(f"All {total_count} chapters translated successfully")
                    return 0
                elif success_count > 0:
                    logger.warning(f"Partial success: {success_count}/{total_count} chapters translated")
                else:
                    logger.error(f"All {total_count} chapters failed to translate")

                # Always log per-chapter details for failures
                if success_count < total_count:
                    for i, r in enumerate(results):
                        if not r.get("success"):
                            chapter_num = chapters[i] if i < len(chapters) else f"index_{i}"
                            errors = r.get('errors', ['Unknown'])
                            logger.error(f"Chapter {chapter_num} failed: {errors}")
                return 1 if success_count < total_count else 0
            else:
                result = pipeline.translate_chapter(args.novel, args.chapter)
        else:
            logger.error("No input specified")
            return 1

        # Handle single result (for input_file or single chapter)
        if isinstance(result, dict):
            if result.get("success"):
                output_path = result.get('output_path')
                duration = result.get('duration_seconds', 0)
                metrics = result.get('metrics', {})

                print_success("Translation completed successfully!")
                print_info(f"Output file: {output_path}")
                if duration:
                    print_info(f"Duration: {duration:.1f} seconds")
                if metrics:
                    print_info(f"Metrics: {metrics}")

                logger.info(f"Translation completed successfully: {output_path}")
                return 0
            else:
                errors = result.get('errors', ['Unknown error'])
                print_error("Translation failed", str(errors))
                logger.error(f"Translation failed: {errors}")
                return 1
        else:
            print_error(f"Unexpected result type: {type(result)}")
            logger.error(f"Unexpected result type: {type(result)}")
            return 1

    except ConfigurationError as e:
        logger.error(f"Configuration error: {e.message}")
        return 1
    except NovelTranslationError as e:
        logger.error(f"Translation error: {e.message}")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return 1


def run_glossary_generation(args: argparse.Namespace) -> int:
    """Run glossary generation for a novel with parallel processing.
    
    Args:
        args: Parsed command line arguments
        
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    logger = setup_logging()

    try:
        config = load_config(args.config)

        if not args.novel:
            logger.error("--novel is required for glossary generation")
            return 1

        # Get chapter range
        # Handle --all flag for glossary generation (like translation does)
        if getattr(args, 'all', False):
            # Discover all chapters in the input folder
            novel_dir = Path(INPUT_DIR) / args.novel
            if novel_dir.exists():
                chapters = _discover_chapters(novel_dir)
                logger.info(f"--all flag detected: will scan {len(chapters)} chapters")
            else:
                logger.warning(f"Novel directory not found: {novel_dir}")
                chapters = []
        else:
            chapters = get_chapter_list(args)
            if not chapters:
                chapters = list(range(1, 6))  # Default to first 5 chapters

        # Resolve chapter file paths first (outside thread pool)
        chapter_files = []
        for chapter_num in chapters:
            # Try multiple file naming formats
            # Format 1: {novel_name}_chapter_{XXX}.md (e.g., 古道仙鸿_chapter_001.md)
            chapter_file = Path(INPUT_DIR) / args.novel / f"{args.novel}_chapter_{chapter_num:03d}.md"

            # Format 2: {XXX}.md (e.g., 001.md) - legacy format
            if not chapter_file.exists():
                chapter_file = Path(INPUT_DIR) / args.novel / f"{chapter_num:03d}.md"

            # Format 3: chapter_{XXX}.md (e.g., chapter_001.md)
            if not chapter_file.exists():
                chapter_file = Path(INPUT_DIR) / args.novel / f"chapter_{chapter_num:03d}.md"

            if chapter_file.exists():
                chapter_files.append((chapter_num, chapter_file))
            else:
                logger.warning(f"Chapter file not found for chapter {chapter_num}")

        if not chapter_files:
            logger.error("No valid chapter files found")
            return 1

        logger.info(f"Processing {len(chapter_files)} chapters in parallel (max {MAX_GLOSSARY_WORKERS} workers)")

        # Process chapters in parallel
        from src.agents.glossary_generator import GlossaryGenerator
        from src.utils.ollama_client import OllamaClient
        from src.memory.memory_manager import MemoryManager

        client = OllamaClient(
            model=config.models.translator,
            base_url=config.models.ollama_base_url
        )
        memory = MemoryManager(novel_name=args.novel)
        generator = GlossaryGenerator(client, memory, config.dict())

        def process_chapter(chapter_num_and_file):
            """Process a single chapter - thread worker function."""
            ch_num, ch_file = chapter_num_and_file
            return generator.generate_from_chapter(str(ch_file), ch_num)

        # Use ThreadPoolExecutor for parallel processing
        completed = 0
        total_terms = 0
        with ThreadPoolExecutor(max_workers=MAX_GLOSSARY_WORKERS) as executor:
            futures = {executor.submit(process_chapter, cf): cf for cf in chapter_files}
            for future in as_completed(futures):
                ch_num, ch_file = futures[future]
                try:
                    terms_count = future.result()
                    completed += 1
                    total_terms += terms_count
                    logger.info(f"Progress: {completed}/{len(chapter_files)} chapters done (extracted {total_terms} terms total)")
                except Exception as e:
                    logger.error(f"Chapter {ch_num} failed: {e}")

        # Always persist glossary.json + context_memory.json so all 3 files
        # exist after glossary generation, even when the novel is brand new.
        memory.save_memory()
        logger.info(f"Glossary generation completed: {completed} chapters processed, {total_terms} terms extracted")
        return 0

    except Exception as e:
        logger.error(f"Glossary generation failed: {e}", exc_info=True)
        return 1


def run_ui_launch(args: argparse.Namespace) -> int:
    """Launch the web UI.
    
    Args:
        args: Parsed command line arguments
        
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    from src.web.launcher import launch_web_ui
    return launch_web_ui(args)


def run_test(args: argparse.Namespace) -> int:
    """Run test translation with sample file.
    
    Args:
        args: Parsed command line arguments
        
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    logger = setup_logging()

    try:
        # Use sample.md if it exists
        sample_file = Path(INPUT_DIR) / "sample.md"

        if not sample_file.exists():
            # Create a sample file
            sample_file.parent.mkdir(parents=True, exist_ok=True)
            sample_file.write_text(
                "# Sample Chapter\n\n这是一个测试段落。\n\nThis is a test paragraph.",
                encoding="utf-8"
            )

        args.input_file = str(sample_file)
        return run_translation_pipeline(args)

    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        return 1


def _resolve_workflow(args) -> Optional[str]:
    """Resolve workflow from explicit flag, language flag, or input.
    
    Args:
        args: Parsed command line arguments
        
    Returns:
        Workflow name (way1 or way2) or None
    """
    # Check explicit workflow flag
    if hasattr(args, 'workflow') and args.workflow:
        return args.workflow

    # Check language flag
    lang = getattr(args, 'lang', None)
    if lang:
        lang_lower = lang.lower()
        if lang_lower in ('en', 'english'):
            return 'way1'
        elif lang_lower in ('zh', 'chinese'):
            return 'way2'

    # Try to infer from input file using Preprocessor's detect_language
    input_file = None

    # Check explicit input file
    if hasattr(args, 'input_file') and args.input_file:
        input_file = args.input_file
    # Or resolve from novel + chapter
    elif hasattr(args, 'novel') and args.novel:
        from src.pipeline.orchestrator import TranslationPipeline
        chapter = getattr(args, 'chapter', None)
        # If chapter is None but chapter_range is set, use start chapter from range
        if chapter is None and hasattr(args, 'chapter_range') and args.chapter_range:
            try:
                chapter = int(args.chapter_range.split('-')[0])
            except (ValueError, IndexError):
                chapter = 1
        # Default to chapter 1 if still None
        if chapter is None:
            chapter = 1
        input_file = TranslationPipeline._find_chapter_file(args.novel, chapter)

    if input_file:
        try:
            from src.utils.file_handler import FileHandler
            from src.agents.preprocessor import Preprocessor

            text = FileHandler.read_text(input_file)

            # Use Preprocessor's detect_language for accuracy
            preprocessor = Preprocessor()
            detected_lang = preprocessor.detect_language(text)

            if detected_lang == "chinese":
                return 'way2'
            elif detected_lang == "english":
                return 'way1'
        except Exception:
            pass

    return None


def run_view_file(args: argparse.Namespace) -> int:
    """View a translated .mm.md file with formatted terminal output.
    
    Args:
        args: Parsed command line arguments (must have view_file)
        
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    filepath = args.view_file
    p = Path(filepath)

    if not p.exists():
        print(f"Error: File not found: {filepath}")
        return 1

    print(f"\n{'='*70}")
    print(f"  📖  {p.name}")
    print(f"{'='*70}\n")

    try:
        with open(p, 'r', encoding='utf-8-sig') as f:
            content = f.read()
    except UnicodeDecodeError:
        print(f"Warning: BOM decode failed, trying utf-8 fallback for {p.name}")
        with open(p, 'r', encoding='utf-8') as f:
            content = f.read()

    # Apply postprocessing (single source of truth)
    from src.utils.postprocessor import (
        _split_into_lines_if_needed,
        fix_chapter_heading_format,
        remove_duplicate_headings,
    )
    content = _split_into_lines_if_needed(content)
    content = fix_chapter_heading_format(content)
    content = remove_duplicate_headings(content)

    # Print with formatting
    for line in content.split('\n'):
        stripped = line.strip()
        if not stripped:
            print()
        elif stripped.startswith('# '):
            print(f"\n\033[1;33m{stripped}\033[0m")
        elif stripped.startswith('## '):
            print(f"\033[1;36m{stripped}\033[0m")
        elif stripped.startswith('### '):
            print(f"\n\033[1;32m{stripped}\033[0m")
        else:
            print(stripped)

    print(f"\n{'='*70}")
    print(f"  {len(content):,} chars | {content.count(chr(10)) + 1} lines")
    print(f"{'='*70}\n")
    return 0


def run_review(args: argparse.Namespace) -> int:
    """Run quality review on a translated output file.
    
    Args:
        args: Parsed command line arguments (must have review_file)

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    logger = setup_logging()

    filepath = args.review_file
    p = Path(filepath)

    if not p.exists():
        logger.error(f"File not found: {filepath}")
        return 1

    from src.utils.translation_reviewer import review_and_report

    # Find associated log file (most recent in logs/)
    log_file = None
    logs_dir = Path("logs")
    if logs_dir.is_dir():
        log_files = sorted(logs_dir.glob("translation_*.log"), reverse=True)
        if log_files:
            log_file = str(log_files[0])

    logger.info(f"Reviewing: {filepath}")
    report, report_path = review_and_report(
        str(p),
        log_file=log_file,
    )

    print(f"\n{'='*60}")
    print("  📊 Translation Quality Report")
    print(f"{'='*60}")
    print(f"  Novel:      {report.novel}")
    print(f"  Chapter:    {report.chapter}")
    print(f"  Score:      {report.total_score}/100")
    print(f"  ✅ Passed:  {len(report.passed_checks)}")
    print(f"  ⚠️  Warnings: {len(report.warnings)}")
    print(f"  🔴 Critical: {len(report.critical_fixes)}")
    print(f"{'='*60}")
    print(f"  Report saved: {report_path}")

    if report.critical_fixes:
        print("\n  🔴 Critical Issues:")
        for item in report.critical_fixes[:5]:
            print(f"     - {item}")
    if report.todo_items:
        print("\n  📝 TODO:")
        for item in report.todo_items[:3]:
            print(f"     {item}")

    print()
    return 0 if report.total_score >= 70 else 1


def _apply_workflow_config(config: AppConfig, workflow: str, logger: Optional[logging.Logger] = None) -> AppConfig:
    """Apply workflow-specific configuration overrides with automatic model selection.
    
    Args:
        config: Base configuration
        workflow: Workflow name (way1 or way2)
        logger: Optional logger for reporting auto-detected settings
        
    Returns:
        Modified configuration
    """
    from src.config import merge_configs

    if workflow == 'way1':
        # way1: English -> Myanmar direct
        # Use padauk-gemma:q8_0 for best Myanmar output
        # SINGLE_STAGE mode: padauk-gemma produces BETTER quality in single-stage
        # (direct translation only) than full pipeline (translate→refine→reflect).
        # Full pipeline adds 2 extra API calls per chunk (3x slower) and the
        # refinement/reflection steps with padauk-gemma collapse paragraph breaks
        # and degrade output quality. See ERROR-050.
        overrides = {
            "project": {
                "source_language": "en-US"
            },
            "translation_pipeline": {
                "mode": "single_stage",
                "use_reflection": False,
                "stage1_model": "padauk-gemma:q8_0",
                "stage2_model": "padauk-gemma:q8_0"
            },
            "models": {
                "translator": "padauk-gemma:q8_0",
                "editor": "padauk-gemma:q8_0",
                "refiner": "padauk-gemma:q8_0"
            }
        }
        if logger:
            logger.info("🔄 Auto-detected ENGLISH source → Using way1 (EN→MM direct, single-stage)")
            logger.info("🤖 Auto-selected models: padauk-gemma:q8_0 (best for Myanmar)")

    elif workflow == 'way2':
        # way2: Chinese -> English -> Myanmar pivot
        # Use alibayram/hunyuan:7b for CN→EN, padauk-gemma:q8_0 for EN→MM
        overrides = {
            "project": {
                "source_language": "zh-CN"
            },
            "translation_pipeline": {
                "mode": "two_stage",
                "stage1_model": "alibayram/hunyuan:7b",
                "stage2_model": "padauk-gemma:q8_0"
            },
            "models": {
                "translator": "alibayram/hunyuan:7b",
                "editor": "padauk-gemma:q8_0",
                "refiner": "padauk-gemma:q8_0"
            }
        }
        if logger:
            logger.info("🔄 Auto-detected CHINESE source → Using way2 (CN→EN→MM pivot)")
            logger.info("🤖 Auto-selected models:")
            logger.info("   - Stage 1 (CN→EN): alibayram/hunyuan:7b")
            logger.info("   - Stage 2 (EN→MM): padauk-gemma:q8_0")
    else:
        return config

    return merge_configs(config, overrides)


def run_glossary_promotion(args: argparse.Namespace) -> int:
    """Auto-promote high-confidence pending glossary terms to approved glossary.

    Threshold: confidence ≥ 0.85 AND appears in ≥ 3 chapters → auto-approve.
    Uses MemoryManager.auto_approve_by_confidence() which already implements
    these heuristics.

    Args:
        args: Parsed command line arguments (must have --novel)

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    logger = setup_logging()

    if not args.novel:
        logger.error("--novel is required for --auto-promote")
        return 1

    from src.memory.memory_manager import MemoryManager

    memory = MemoryManager(novel_name=args.novel)

    # Show pending count before promotion
    pending_before = memory.get_pending_terms()
    logger.info(
        f"Loaded glossary for '{args.novel}': "
        f"{memory.glossary.get('total_terms', 0)} approved, "
        f"{len(pending_before)} pending"
    )

    # Auto-approve by confidence (threshold 0.85 per spec)
    promoted = memory.auto_approve_by_confidence(confidence_threshold=0.85)

    # Also auto-approve any manually marked 'approved'
    manual_count = memory.auto_approve_pending_terms()

    total_promoted = promoted + manual_count

    # Show results
    pending_after = memory.get_pending_terms()
    print(f"\n{'='*50}")
    print(f"  Glossary Promotion — {args.novel}")
    print(f"{'='*50}")
    print(f"  Pending before: {len(pending_before)}")
    print(f"  Auto-promoted (confidence): {promoted}")
    print(f"  Auto-promoted (manual):    {manual_count}")
    print(f"  Total promoted:            {total_promoted}")
    print(f"  Pending remaining:         {len(pending_after)}")
    print(f"  Approved total:            {memory.glossary.get('total_terms', 0)}")
    print(f"{'='*50}")

    if total_promoted > 0:
        logger.info(f"Promoted {total_promoted} terms to approved glossary")
    else:
        logger.info("No terms met promotion threshold")

    memory.save_memory()
    return 0


def run_glossary_approval(args: argparse.Namespace) -> int:
    """Bulk approve ALL pending glossary terms and add to glossary.json.

    This command:
    1. Reads glossary_pending.json
    2. Adds all "pending" status terms to glossary.json
    3. Removes approved terms from pending list

    Args:
        args: Parsed command line arguments (must have --novel)

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    logger = setup_logging()

    if not args.novel:
        logger.error("--novel is required for --approve-glossary")
        return 1

    from src.memory.memory_manager import MemoryManager

    memory = MemoryManager(novel_name=args.novel)

    # Show pending count before approval
    pending_before = memory.get_pending_terms()
    logger.info(
        f"Loaded glossary for '{args.novel}': "
        f"{memory.glossary.get('total_terms', 0)} approved, "
        f"{len(pending_before)} pending"
    )

    # Bulk approve all pending terms
    approved_count = memory.bulk_approve_all_pending()

    # Show results
    pending_after = memory.get_pending_terms()
    print(f"\n{'='*50}")
    print(f"  Glossary Approval — {args.novel}")
    print(f"{'='*50}")
    print(f"  Pending before:   {len(pending_before)}")
    print(f"  Approved:        {approved_count}")
    print(f"  Pending after:   {len(pending_after)}")
    print(f"{'='*50}")

    if approved_count > 0:
        print(f"✅ Successfully approved {approved_count} terms!")
    else:
        print("ℹ️  No terms to approve")

    return 0


def run_stats(args: argparse.Namespace) -> int:
    """Aggregate per-chapter quality review reports and show score trends.

    Reads all reports in logs/report/ for the given novel and displays:
    - Per-chapter scores with pass/warn/critical counts
    - Score trend (improving/degrading/stable)
    - Summary statistics

    Args:
        args: Parsed command line arguments (must have --novel)

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    import re
    import glob

    logger = setup_logging()

    if not args.novel:
        logger.error("--novel is required for --stats")
        return 1

    novel = args.novel.replace(' ', '_').replace('/', '_')

    # Find all review reports for this novel
    report_dir = Path("logs/report")
    if not report_dir.exists():
        logger.error("No report directory found at logs/report/")
        return 1

    pattern = str(report_dir / f"{novel}_chapter_*_review_*.md")
    report_files = sorted(glob.glob(pattern))

    if not report_files:
        logger.error(f"No review reports found for novel '{novel}' in logs/report/")
        logger.info(f"Searched pattern: {pattern}")
        return 1

    # Parse each report
    chapters: List[dict] = []

    for rp in report_files:
        try:
            with open(rp, 'r', encoding='utf-8-sig') as f:
                content = f.read()
        except Exception:
            continue

        # Extract chapter number from filename
        ch_match = re.search(r'chapter_(\d+)_review', Path(rp).name)
        if not ch_match:
            continue
        ch_num = int(ch_match.group(1))

        # Extract score
        score_match = re.search(r'Overall Score:\s*(\d+)/100', content)
        score = int(score_match.group(1)) if score_match else 0

        # Extract metrics
        passed_match = re.search(r'✅ Passed\s*\|\s*(\d+)', content)
        passed = int(passed_match.group(1)) if passed_match else 0
        warn_match = re.search(r'⚠️ Warnings\s*\|\s*(\d+)', content)
        warnings = int(warn_match.group(1)) if warn_match else 0
        crit_match = re.search(r'🔴 Critical\s*\|\s*(\d+)', content)
        critical = int(crit_match.group(1)) if crit_match else 0

        # Extract duration
        dur_match = re.search(r'Duration.*?:\s*([\d.]+)s', content)
        duration = float(dur_match.group(1)) if dur_match else 0

        # Extract pipeline mode
        pipe_match = re.search(r'Pipeline.*?:\s*(\w+)', content)
        pipeline = pipe_match.group(1) if pipe_match else "?"

        chapters.append({
            "chapter": ch_num,
            "score": score,
            "passed": passed,
            "warnings": warnings,
            "critical": critical,
            "duration": duration,
            "pipeline": pipeline,
        })

    if not chapters:
        logger.error("Could not parse any report data")
        return 1

    chapters.sort(key=lambda c: c["chapter"])

    # Compute trends
    scores = [c["score"] for c in chapters]
    avg_score = sum(scores) / len(scores)
    min_score = min(scores)
    max_score = max(scores)

    # Trend: compare first half vs second half
    half = len(chapters) // 2
    first_half_avg = sum(scores[:half]) / half if half > 0 else avg_score
    second_half_avg = sum(scores[half:]) / (len(chapters) - half) if len(chapters) > half else avg_score
    delta = second_half_avg - first_half_avg

    if delta > 5:
        trend = "📈 IMPROVING"
    elif delta < -5:
        trend = "📉 DEGRADING"
    else:
        trend = "📊 STABLE"

    # Display
    print(f"\n{'='*60}")
    print(f"  📊 Quality Score Trends — {novel}")
    print(f"{'='*60}")
    print(f"  Reports found: {len(chapters)} chapters")
    print(f"  Average score: {avg_score:.0f}/100")
    print(f"  Range: {min_score} – {max_score}")
    print(f"  Trend: {trend} ({delta:+.0f} pts)")
    print(f"  First half avg: {first_half_avg:.0f}  →  Second half avg: {second_half_avg:.0f}")
    print(f"\n{'─'*60}")
    print(f"  {'Ch':>4} {'Score':>6} {'P':>4} {'W':>4} {'C':>4} {'Time':>7}  Pipeline")
    print(f"  {'───':>4} {'─────':>6} {'───':>4} {'───':>4} {'───':>4} {'─────':>7}  {'───────'}")

    for c in chapters:
        bar = "█" * min(20, c["score"] // 5)
        gap = "░" * (20 - len(bar))
        print(
            f"  {c['chapter']:>4} {c['score']:>3}/100 {c['passed']:>3} "
            f"{c['warnings']:>3} {c['critical']:>3} "
            f"{c['duration']:>5.0f}s  {c['pipeline']}  {bar}{gap}"
        )

    print("\n  Legend: P=Passed  W=Warnings  C=Critical")
    print(f"{'='*60}\n")

    return 0


def run_rebuild_meta(args: argparse.Namespace) -> int:
    """Scan output folder and rebuild single novel_name.mm.meta.json file."""
    import json
    import os
    from pathlib import Path
    from datetime import datetime
    
    logger = setup_logging()
    
    if not args.novel:
        logger.error("--novel is required for --rebuild-meta")
        return 1
        
    output_dir = Path("data/output") / args.novel
    if not output_dir.exists():
        logger.error(f"Output directory {output_dir} does not exist.")
        return 1
        
    logger.info(f"Scanning {output_dir} for .mm.md files...")
    
    # Find all chapter files and build cumulative meta
    import re
    chapter_regex = re.compile(r"chapter_(\d+)\.mm\.md$")
    chapters_meta = {}
    
    for filename in os.listdir(output_dir):
        match = chapter_regex.search(filename)
        if match:
            chapter_num = int(match.group(1))
            chapter_file = output_dir / filename
            
            # Get file stats
            file_stat = chapter_file.stat()
            char_count = file_stat.st_size
            
            # Read a sample to estimate Myanmar ratio (simplified)
            myanmar_ratio = 0.85  # Default estimate for rebuilt
            
            chapters_meta[str(chapter_num)] = {
                "chapter": chapter_num,
                "translated_at": datetime.now().isoformat(),
                "pipeline": "Rebuilt",
                "model": "padauk-gemma:q8_0",
                "char_count": char_count,
                "myanmar_ratio": myanmar_ratio,
            }
    
    # Build cumulative meta
    cumulative_meta = {
        "novel": args.novel,
        "last_updated": datetime.now().isoformat(),
        "total_chapters": len(chapters_meta),
        "chapters": chapters_meta,
    }
    
    # Write single cumulative meta file
    meta_file = output_dir / f"{args.novel}.mm.meta.json"
    try:
        with open(meta_file, 'w', encoding='utf-8') as f:
            json.dump(cumulative_meta, f, indent=2, ensure_ascii=False)
        logger.info(f"Successfully rebuilt meta.json with {len(chapters_meta)} chapters.")
    except Exception as e:
        logger.error(f"Failed to write meta.json: {e}")
        return 1

    return 0


def _run_sql_migration(args: argparse.Namespace, config: Any, logger: logging.Logger) -> int:
    """Run JSON to SQLite migration for a novel.

    Args:
        args: Command line arguments
        config: Application configuration
        logger: Logger instance

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    from src.cli.formatters import print_section_header, print_info, print_success, print_error

    if not args.novel:
        print_error("--migrate-sql requires --novel <name>")
        return 1

    print_section_header(f"SQL Migration: {args.novel}")

    try:
        from src.db.connection import DatabaseConnection
        from src.db.migrator import JsonToSqlMigrator

        db = DatabaseConnection(config.storage.db_path)
        migrator = JsonToSqlMigrator(db, args.novel)

        summary = migrator.migrate()

        print_success("Migration complete!")
        print_info(f"  Backup: {summary['backup_dir']}")
        print_info(f"  Glossary terms: {summary['glossary_terms']}")
        print_info(f"  Pending terms: {summary['pending_terms']}")
        print_info(f"  Chapters: {summary['chapters']}")
        print_info(f"  Context snapshots: {summary['context_snapshots']}")
        print_info(f"  Database: {config.storage.db_path}")

        db.close()
        return 0
    except Exception as e:
        print_error(f"Migration failed: {e}")
        logger.exception("SQL migration error")
        return 1


# ═══════════════════════════════════════════════════════════════════════════
# Version Control Commands
# ═══════════════════════════════════════════════════════════════════════════

def run_list_versions(args: argparse.Namespace) -> int:
    """List all versions for a chapter.
    
    Args:
        args: Parsed arguments with --novel and --chapter
        
    Returns:
        Exit code
    """
    logger = setup_logging()
    
    if not args.novel or not args.chapter:
        logger.error("--versions requires --novel and --chapter")
        return 1
    
    try:
        from src.db.connection import DatabaseConnection
        from src.memory.version_manager import VersionManager
        from src.config import load_config
        
        config = load_config(args.config)
        db = DatabaseConnection(config.storage.db_path)
        vm = VersionManager(db, Path(config.paths.output_dir))
        
        versions = vm.list_versions(args.novel, args.chapter)
        
        print(f"\n{'='*60}")
        print(f"  📚 Chapter Versions — {args.novel} #{args.chapter}")
        print(f"{'='*60}")
        
        if not versions:
            print("  No versions found for this chapter.")
            print(f"{'='*60}\n")
            return 0
        
        print(f"  {'Ver':>4} {'Date':>20} {'Reason':>30}")
        print(f"  {'────':>4} {'──────────────────':>20} {'──────────────────────────────':>30}")
        
        for v in versions:
            date = v['created_at'][:16] if v['created_at'] else 'N/A'
            reason = v.get('reason', 'N/A')[:28]
            print(f"  {v['version_num']:>4} {date:>20} {reason:>30}")
        
        print(f"{'='*60}\n")
        db.close()
        return 0
        
    except Exception as e:
        logger.error(f"Failed to list versions: {e}", exc_info=True)
        return 1


def run_rollback(args: argparse.Namespace) -> int:
    """Rollback a chapter to a specific version.
    
    Args:
        args: Parsed arguments with --novel, --chapter, --rollback
        
    Returns:
        Exit code
    """
    logger = setup_logging()
    
    if not args.novel or not args.chapter or not args.rollback:
        logger.error("--rollback requires --novel, --chapter, and --rollback VERSION")
        return 1
    
    try:
        from src.db.connection import DatabaseConnection
        from src.memory.version_manager import VersionManager
        from src.config import load_config
        
        config = load_config(args.config)
        db = DatabaseConnection(config.storage.db_path)
        vm = VersionManager(db, Path(config.paths.output_dir))
        
        version_num = args.rollback
        result = vm.rollback_chapter(args.novel, args.chapter, version_num)
        
        if result:
            print(f"\n✅ Successfully rolled back {args.novel} #{args.chapter} to version {version_num}")
            print(f"   Restored file: {result}")
            return 0
        else:
            print(f"\n❌ Rollback failed for {args.novel} #{args.chapter}")
            return 1
            
    except Exception as e:
        logger.error(f"Rollback failed: {e}", exc_info=True)
        return 1


def run_diff(args: argparse.Namespace) -> int:
    """Show diff between two chapter versions.
    
    Args:
        args: Parsed arguments with --novel, --chapter, --diff A,B
        
    Returns:
        Exit code
    """
    logger = setup_logging()
    
    if not args.novel or not args.chapter or not args.diff:
        logger.error("--diff requires --novel, --chapter, and --diff A,B")
        return 1
    
    try:
        from src.db.connection import DatabaseConnection
        from src.memory.version_manager import VersionManager
        from src.config import load_config
        
        # Parse version numbers
        try:
            version_a, version_b = map(int, args.diff.split(','))
        except ValueError:
            logger.error("--diff format should be 'A,B' (e.g., '1,3')")
            return 1
        
        config = load_config(args.config)
        db = DatabaseConnection(config.storage.db_path)
        vm = VersionManager(db, Path(config.paths.output_dir))
        
        diff_text = vm.diff_versions(args.novel, args.chapter, version_a, version_b)
        
        if diff_text:
            print(f"\n{'='*60}")
            print(f"  Diff: {args.novel} #{args.chapter} (v{version_a} → v{version_b})")
            print(f"{'='*60}\n")
            print(diff_text)
            print(f"\n{'='*60}\n")
            return 0
        else:
            print("Could not generate diff (versions not found)")
            return 1
            
    except Exception as e:
        logger.error(f"Diff failed: {e}", exc_info=True)
        return 1


def run_preview_sync(args: argparse.Namespace) -> int:
    """Preview which chapters would be affected by a glossary change.
    
    Args:
        args: Parsed arguments with --novel and --preview-sync TERM_ID=NEW_VALUE
        
    Returns:
        Exit code
    """
    logger = setup_logging()
    
    if not args.novel or not args.preview_sync:
        logger.error("--preview-sync requires --novel and --preview-sync TERM_ID=NEW_VALUE")
        return 1
    
    try:
        from src.db.connection import DatabaseConnection
        from src.memory.version_manager import VersionManager
        from src.config import load_config
        
        # Parse term_id and new_value
        try:
            term_id, new_value = args.preview_sync.split('=', 1)
        except ValueError:
            logger.error("--preview-sync format should be 'TERM_ID=NEW_VALUE'")
            return 1
        
        config = load_config(args.config)
        db = DatabaseConnection(config.storage.db_path)
        vm = VersionManager(db, Path(config.paths.output_dir))
        
        preview = vm.preview_glossary_change(args.novel, term_id, new_value)
        
        print(f"\n{'='*60}")
        print(f"  🔍 Glossary Change Preview — {args.novel}")
        print(f"{'='*60}")
        print(f"  Term: {preview.get('source_term', 'N/A')}")
        print(f"  Old:  {preview.get('old_value', 'N/A')}")
        print(f"  New:  {preview.get('new_value', 'N/A')}")
        print(f"{'='*60}")
        
        affected = preview.get('affected_chapters', [])
        
        if affected:
            print(f"\n  📁 Affected Chapters: {len(affected)}")
            print(f"  {'Chapter':>10} {'Occurrences':>12} {'File Count':>12}")
            print(f"  {'─────────':>10} {'───────────':>12} {'──────────':>12}")
            
            for ch in affected:
                print(f"  {ch['chapter_num']:>10} {ch['occurrences']:>12} {ch.get('file_occurrences', 0):>12}")
        else:
            print("\n  ✓ No chapters would be affected")
        
        print(f"\n  Total occurrences in DB: {preview.get('total_occurrences', 0)}")
        print(f"{'='*60}\n")
        
        db.close()
        return 0
        
    except Exception as e:
        logger.error(f"Preview failed: {e}", exc_info=True)
        return 1


def run_create_sync_job(args: argparse.Namespace) -> int:
    """Create a sync job for glossary change.
    
    Args:
        args: Parsed arguments with --novel and --create-sync-job TERM_ID=NEW_VALUE
        
    Returns:
        Exit code
    """
    logger = setup_logging()
    
    if not args.novel or not args.create_sync_job:
        logger.error("--create-sync-job requires --novel and --create-sync-job TERM_ID=NEW_VALUE")
        return 1
    
    try:
        from src.db.connection import DatabaseConnection
        from src.memory.version_manager import VersionManager
        from src.config import load_config
        
        # Parse term_id and new_value
        try:
            term_id, new_value = args.create_sync_job.split('=', 1)
        except ValueError:
            logger.error("--create-sync-job format should be 'TERM_ID=NEW_VALUE'")
            return 1
        
        config = load_config(args.config)
        db = DatabaseConnection(config.storage.db_path)
        vm = VersionManager(db, Path(config.paths.output_dir))
        
        job = vm.create_sync_job(args.novel, term_id, new_value)
        
        if job:
            print(f"\n{'='*60}")
            print("  ✅ Sync Job Created")
            print(f"{'='*60}")
            print(f"  Job ID:        {job['id']}")
            print(f"  Term:          {term_id}")
            print(f"  Old → New:     {job['old_value']} → {new_value}")
            print(f"  Status:        {job['status']}")
            print(f"  Created:       {job['created_at']}")
            print(f"\n  To execute:    --execute-sync {job['id']}")
            print(f"  To preview:    --execute-sync {job['id']} --dry-run")
            print(f"{'='*60}\n")
            db.close()
            return 0
        else:
            print("\n❌ Failed to create sync job")
            return 1
            
    except Exception as e:
        logger.error(f"Create sync job failed: {e}", exc_info=True)
        return 1


def run_execute_sync(args: argparse.Namespace) -> int:
    """Execute a sync job.
    
    Args:
        args: Parsed arguments with --execute-sync JOB_ID
        
    Returns:
        Exit code
    """
    logger = setup_logging()
    
    if not args.execute_sync:
        logger.error("--execute-sync requires JOB_ID")
        return 1
    
    try:
        from src.db.connection import DatabaseConnection
        from src.memory.version_manager import VersionManager
        from src.config import load_config
        
        config = load_config(args.config)
        db = DatabaseConnection(config.storage.db_path)
        vm = VersionManager(db, Path(config.paths.output_dir))
        
        dry_run = getattr(args, 'dry_run', False)
        
        print(f"\n{'='*60}")
        if dry_run:
            print(f"  🔍 Dry Run — Sync Job {args.execute_sync}")
        else:
            print(f"  ⚡ Executing Sync Job {args.execute_sync}")
        print(f"{'='*60}")
        
        result = vm.execute_sync_job(args.execute_sync, dry_run=dry_run)
        
        if result.get('success'):
            print(f"\n  Term:         {result.get('term', 'N/A')}")
            print(f"  Change:       {result.get('old_value', 'N/A')} → {result.get('new_value', 'N/A')}")
            print(f"  Chapters:     {result.get('chapters_total', 0)} total, {result.get('chapters_pending', 0)} pending")
            print(f"  Updated:      {result.get('chapters_updated', 0)}")
            print(f"  Failed:       {result.get('chapters_failed', 0)}")
            print(f"  Replacements: {result.get('replacements_total', 0)}")
            
            if dry_run:
                print("\n  ✓ Dry run complete. Use without --dry-run to apply.")
            else:
                print("\n  ✓ Sync job complete!")
            
            print(f"{'='*60}\n")
            db.close()
            return 0
        else:
            print(f"\n❌ Sync job failed: {result.get('error', 'Unknown error')}")
            return 1
            
    except Exception as e:
        logger.error(f"Execute sync failed: {e}", exc_info=True)
        return 1


def run_list_sync_jobs(args: argparse.Namespace) -> int:
    """List all sync jobs.
    
    Args:
        args: Parsed arguments with optional --novel filter
        
    Returns:
        Exit code
    """
    logger = setup_logging()
    
    try:
        from src.db.connection import DatabaseConnection
        from src.memory.version_manager import VersionManager
        from src.config import load_config
        
        config = load_config(args.config)
        db = DatabaseConnection(config.storage.db_path)
        vm = VersionManager(db, Path(config.paths.output_dir))
        
        jobs = vm.list_sync_jobs(novel_name=args.novel)
        
        print(f"\n{'='*80}")
        if args.novel:
            print(f"  📋 Sync Jobs — {args.novel}")
        else:
            print("  📋 All Sync Jobs")
        print(f"{'='*80}")
        
        if not jobs:
            print("  No sync jobs found.")
            print(f"{'='*80}\n")
            return 0
        
        print(f"  {'ID':>6} {'Term ID':>20} {'Status':>15} {'Created':>20}")
        print(f"  {'──────':>6} {'────────────────────':>20} {'───────────────':>15} {'────────────────────':>20}")
        
        for job in jobs[:50]:  # Limit to 50 most recent
            created = job['created_at'][:16] if job['created_at'] else 'N/A'
            term_id = job['term_id'][:18] if len(job['term_id']) > 18 else job['term_id']
            print(f"  {job['id']:>6} {term_id:>20} {job['status']:>15} {created:>20}")
        
        if len(jobs) > 50:
            print(f"\n  ... and {len(jobs) - 50} more jobs")
        
        print(f"{'='*80}\n")
        db.close()
        return 0
        
    except Exception as e:
        logger.error(f"List sync jobs failed: {e}", exc_info=True)
        return 1


def run_audit_log(args: argparse.Namespace) -> int:
    """Show audit log.
    
    Args:
        args: Parsed arguments with optional --novel filter
        
    Returns:
        Exit code
    """
    logger = setup_logging()
    
    try:
        from src.db.connection import DatabaseConnection
        from src.memory.version_manager import VersionManager
        from src.config import load_config
        
        config = load_config(args.config)
        db = DatabaseConnection(config.storage.db_path)
        vm = VersionManager(db, Path(config.paths.output_dir))
        
        logs = vm.get_audit_log(novel_name=args.novel, limit=100)
        
        print(f"\n{'='*100}")
        if args.novel:
            print(f"  📜 Audit Log — {args.novel}")
        else:
            print("  📜 Audit Log (All)")
        print(f"{'='*100}")
        
        if not logs:
            print("  No audit entries found.")
            print(f"{'='*100}\n")
            return 0
        
        print(f"  {'Time':>20} {'Table':>15} {'Action':>15} {'Record':>25} {'Source':>10}")
        print(f"  {'────────────────────':>20} {'───────────────':>15} {'───────────────':>15} {'─────────────────────────':>25} {'──────────':>10}")
        
        for entry in logs:
            time = entry['timestamp'][:16] if entry['timestamp'] else 'N/A'
            record = entry['record_id'][:23] if len(entry['record_id']) > 23 else entry['record_id']
            print(f"  {time:>20} {entry['table_name']:>15} {entry['action']:>15} {record:>25} {entry.get('source', 'N/A'):>10}")
        
        print(f"{'='*100}\n")
        db.close()
        return 0
        
    except Exception as e:
        logger.error(f"Audit log failed: {e}", exc_info=True)
        return 1
