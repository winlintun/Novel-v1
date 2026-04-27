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
import sys
import signal
import logging
from pathlib import Path
import argparse
from typing import List, Optional

from src.config import AppConfig, load_config
from src.cli.parser import get_chapter_list
from src.exceptions import NovelTranslationError, ConfigurationError

# Constants
DEFAULT_CHUNK_SIZE = 1500
DEFAULT_OVERLAP_SIZE = 100
INPUT_DIR = "data/input"
OUTPUT_DIR = "data/output"
WORKING_DIR = "working_data"
LOG_DIR = "logs"


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
        
        # Handle workflow resolution
        workflow = _resolve_workflow(args)
        if workflow:
            config = _apply_workflow_config(config, workflow)
        
        # Get chapters to translate
        chapters = get_chapter_list(args)
        
        # Import and run pipeline
        from src.pipeline.orchestrator import TranslationPipeline
        
        pipeline = TranslationPipeline(config)
        
        if args.input_file:
            # Single file translation
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
                    # Log failed chapters
                    for i, r in enumerate(results):
                        if not r.get("success"):
                            logger.error(f"Chapter {i+1} failed: {r.get('errors', ['Unknown'])}")
                    return 1
                else:
                    logger.error(f"All {total_count} chapters failed to translate")
                    return 1
            else:
                result = pipeline.translate_chapter(args.novel, args.chapter)
        else:
            logger.error("No input specified")
            return 1
        
        # Handle single result (for input_file or single chapter)
        if isinstance(result, dict):
            if result.get("success"):
                logger.info(f"Translation completed successfully: {result.get('output_path')}")
                return 0
            else:
                logger.error(f"Translation failed: {result.get('errors', ['Unknown error'])}")
                return 1
        else:
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
    """Run glossary generation for a novel.
    
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
        chapters = get_chapter_list(args)
        if not chapters:
            chapters = list(range(1, 6))  # Default to first 5 chapters
        
        from src.agents.glossary_generator import GlossaryGenerator
        from src.utils.ollama_client import OllamaClient
        from src.memory.memory_manager import MemoryManager
        
        client = OllamaClient(
            model=config.models.translator,
            base_url=config.models.ollama_base_url
        )
        memory = MemoryManager()
        
        generator = GlossaryGenerator(client, memory, config.dict())
        
        logger.info(f"Generating glossary for {args.novel} from chapters {chapters}")
        
        for chapter_num in chapters:
            chapter_file = Path(INPUT_DIR) / args.novel / f"{chapter_num:03d}.md"
            if chapter_file.exists():
                generator.generate_from_chapter(str(chapter_file), chapter_num)
        
        logger.info("Glossary generation completed")
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
    
    # Try to infer from input file
    if hasattr(args, 'input_file') and args.input_file:
        try:
            from src.utils.file_handler import FileHandler
            text = FileHandler.read_text(args.input_file)
            
            # Simple heuristic detection
            chinese_chars = sum(1 for c in text[:5000] if '\u4e00' <= c <= '\u9fff')
            latin_chars = sum(1 for c in text[:5000] if c.isascii() and c.isalpha())
            
            if chinese_chars >= 5 and chinese_chars >= latin_chars:
                return 'way2'
            elif latin_chars >= 20:
                return 'way1'
        except Exception:
            pass
    
    return None


def _apply_workflow_config(config: AppConfig, workflow: str) -> AppConfig:
    """Apply workflow-specific configuration overrides.
    
    Args:
        config: Base configuration
        workflow: Workflow name (way1 or way2)
        
    Returns:
        Modified configuration
    """
    from src.config import merge_configs
    
    if workflow == 'way1':
        # way1: English -> Myanmar direct
        overrides = {
            "project": {
                "source_language": "en-US"
            },
            "translation_pipeline": {
                "mode": "single_stage"
            }
        }
    elif workflow == 'way2':
        # way2: Chinese -> English -> Myanmar pivot
        overrides = {
            "project": {
                "source_language": "zh-CN"
            },
            "translation_pipeline": {
                "mode": "two_stage"
            }
        }
    else:
        return config
    
    return merge_configs(config, overrides)
