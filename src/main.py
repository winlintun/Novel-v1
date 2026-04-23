#!/usr/bin/env python3
"""
Main Entry Point - Novel Translation Pipeline
Integrates local_main.py features with new structure

Usage:
    python -m src.main --novel 古道仙鸿 --chapter 1
    python -m src.main --novel 古道仙鸿 --all
    python -m src.main --novel 古道仙鸿 --all --start 10
    python -m src.main --input data/input/古道仙鸿_001.md
"""

import os
import sys
import re
import json
import time
import signal
import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from src.utils.file_handler import FileHandler
from src.utils.ollama_client import OllamaClient
from src.memory.memory_manager import MemoryManager
from src.agents.preprocessor import Preprocessor
from src.agents.translator import Translator
from src.agents.refiner import Refiner
from src.agents.checker import Checker
from src.agents.context_updater import ContextUpdater


# Constants
DEFAULT_CHUNK_SIZE = 1500
DEFAULT_OVERLAP_SIZE = 100
BOOKS_DIR = "books"
INPUT_DIR = "data/input"
OUTPUT_DIR = "data/output"
WORKING_DIR = "working_data"
LOG_DIR = "logs"

# Global state for signal handling
_current_translation_state = {}
shutdown_requested = False


class SensitiveDataFilter(logging.Filter):
    """Filter that masks sensitive data like API keys in log messages."""
    
    SENSITIVE_PATTERNS = [
        (r'key=[a-zA-Z0-9_-]{20,}', 'key=***API_KEY_HIDDEN***'),
        (r'api[_-]?key[=:][\s]*[a-zA-Z0-9_-]{10,}', 'api_key=***API_KEY_HIDDEN***'),
        (r'Authorization[=:][\s]*Bearer[\s]+[a-zA-Z0-9_-]+', 'Authorization=Bearer ***TOKEN_HIDDEN***'),
    ]
    
    def filter(self, record):
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            msg = record.msg
            for pattern, replacement in self.SENSITIVE_PATTERNS:
                msg = re.sub(pattern, replacement, msg, flags=re.IGNORECASE)
            record.msg = msg
        return True


def setup_logging(log_file: Optional[str] = None):
    """Configure logging with file and console handlers."""
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(WORKING_DIR, exist_ok=True)
    
    if not log_file:
        log_file = f"{LOG_DIR}/translation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    # Create handlers
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.addFilter(SensitiveDataFilter())
    
    console_handler = logging.StreamHandler()
    console_handler.addFilter(SensitiveDataFilter())
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[file_handler, console_handler]
    )
    
    return logging.getLogger(__name__)


def signal_handler(signum, frame):
    """Handle interrupt signals gracefully."""
    global shutdown_requested
    logger = logging.getLogger(__name__)
    
    print("\n\n" + "=" * 60)
    print("⚠️  Shutdown requested. Saving progress...")
    print("=" * 60)
    
    shutdown_requested = True
    
    # Save any partial translation
    if _current_translation_state.get('translated_chunks'):
        try:
            save_partial_translation(
                _current_translation_state.get('book_id', 'unknown'),
                _current_translation_state.get('chapter_name', 'unknown'),
                _current_translation_state['translated_chunks'],
                _current_translation_state.get('chunks_total', 0),
                is_final=False
            )
            print("✓ Partial translation saved")
        except Exception as e:
            logger.error(f"Failed to save partial translation: {e}")
    
    print("You can resume translation later by running the same command.")
    sys.exit(0)


# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def save_partial_translation(
    book_id: str,
    chapter_name: str,
    translated_chunks: Dict[int, str],
    chunks_total: int,
    is_final: bool = False
) -> Path:
    """Save partial translation for progress tracking."""
    book_dir = Path(OUTPUT_DIR) / book_id
    chapters_dir = book_dir / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)
    
    # Sort chunks by index
    sorted_chunks = sorted(translated_chunks.items())
    full_text = '\n\n'.join([text for _, text in sorted_chunks])
    
    # Determine filename
    if is_final:
        output_file = chapters_dir / f"{chapter_name}_mm.md"
    else:
        output_file = chapters_dir / f"{chapter_name}_mm_PARTIAL.md"
    
    # Add progress header
    progress_info = f"""<!-- 
Translation Progress:
- Chapter: {chapter_name}
- Chunks Completed: {len(translated_chunks)}/{chunks_total}
- Timestamp: {datetime.now().isoformat()}
- Status: {'COMPLETE' if is_final else 'PARTIAL'}
-->

"""
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(progress_info + full_text)
    
    return output_file


def load_config(config_path: str = "config/settings.yaml") -> dict:
    """Load configuration from YAML."""
    try:
        return FileHandler.read_yaml(config_path)
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.warning(f"Could not load config from {config_path}: {e}")
        return get_default_config()


def get_default_config() -> dict:
    """Return default configuration."""
    return {
        "models": {
            "translator": "qwen2.5:14b",
            "provider": "ollama",
            "ollama_base_url": "http://localhost:11434"
        },
        "paths": {
            "input_dir": INPUT_DIR,
            "output_dir": OUTPUT_DIR,
            "glossary_file": "data/glossary.json",
            "context_memory_file": "data/context_memory.json"
        },
        "processing": {
            "chunk_size": DEFAULT_CHUNK_SIZE,
            "chunk_overlap": DEFAULT_OVERLAP_SIZE,
            "max_retries": 3,
            "temperature": 0.3
        },
        "translation_pipeline": {
            "mode": "single_stage",
            "stage1_model": "ollama:qwen2.5:14b",
            "stage2_model": "ollama:qwen2.5:14b"
        }
    }


def is_two_stage_mode(config: dict) -> bool:
    """Check if two-stage translation is enabled."""
    pipeline = config.get("translation_pipeline", {})
    return pipeline.get("mode") == "two_stage"


def get_stage_models(config: dict) -> tuple:
    """Get stage 1 and stage 2 models from config."""
    pipeline = config.get("translation_pipeline", {})
    return (
        pipeline.get("stage1_model", "ollama"),
        pipeline.get("stage2_model", "ollama")
    )


def translate_single_file(
    filepath: str,
    config: dict,
    skip_refinement: bool = False,
    two_stage: bool = None
) -> Optional[Path]:
    """
    Translate a single chapter file.
    
    Args:
        filepath: Path to chapter file
        config: Configuration dict
        skip_refinement: Whether to skip refinement
        two_stage: Override config for two-stage mode
        
    Returns:
        Path to output file or None on failure
    """
    logger = logging.getLogger(__name__)
    
    # Determine two-stage mode
    if two_stage is None:
        two_stage = is_two_stage_mode(config)
    
    # Initialize components
    logger.info("Initializing translation pipeline...")
    
    # Ollama client
    ollama_client = OllamaClient(
        model=config['models']['translator'],
        base_url=config['models'].get('ollama_base_url', 'http://localhost:11434'),
        temperature=config['processing'].get('temperature', 0.3),
        max_retries=config['processing'].get('max_retries', 3)
    )
    
    # Check model availability
    if not ollama_client.check_model_available():
        logger.error(f"Model {config['models']['translator']} not available in Ollama")
        logger.info("Run: ollama pull " + config['models']['translator'])
        return None
    
    # Memory manager
    memory = MemoryManager(
        glossary_path=config['paths'].get('glossary_file', 'data/glossary.json'),
        context_path=config['paths'].get('context_memory_file', 'data/context_memory.json')
    )
    
    # Agents
    preprocessor = Preprocessor(
        chunk_size=config['processing'].get('chunk_size', DEFAULT_CHUNK_SIZE),
        overlap_size=config['processing'].get('chunk_overlap', DEFAULT_OVERLAP_SIZE)
    )
    
    translator = Translator(ollama_client, memory)
    refiner = Refiner(ollama_client) if not skip_refinement else None
    checker = Checker(memory)
    context_updater = ContextUpdater(ollama_client, memory)
    
    # Load and preprocess
    logger.info(f"Loading: {filepath}")
    chunks = preprocessor.load_and_preprocess(filepath)
    chapter_info = preprocessor.get_chapter_info(filepath)
    
    book_id = chapter_info['novel_name']
    chapter_name = chapter_info['filename'].replace('.md', '')
    chapter_num = chapter_info['chapter_num']
    
    # Update global state for signal handling
    global _current_translation_state
    _current_translation_state = {
        'book_id': book_id,
        'chapter_name': chapter_name,
        'chunks_total': len(chunks),
        'translated_chunks': {}
    }
    
    # Load original text for checking
    original_text = FileHandler.read_text(filepath)
    
    # Translate
    logger.info(f"Translating {len(chunks)} chunks...")
    translated_chunks = translator.translate_chunks(chunks, chapter_num)
    translated_text = '\n\n'.join(translated_chunks)
    
    # Refine (optional)
    if refiner and not skip_refinement:
        logger.info("Refining translation...")
        translated_text = refiner.refine_full_text(translated_text)
    
    # Check quality
    logger.info("Checking translation quality...")
    check_result = checker.check_chapter(original_text, translated_text)
    
    print("\n" + checker.generate_report(chapter_num, check_result))
    
    # Save output
    output_path = save_partial_translation(
        book_id, chapter_name,
        {i: t for i, t in enumerate(translated_chunks)},
        len(chunks),
        is_final=True
    )
    
    # Update context and glossary
    logger.info("Updating memory and context...")
    context_updater.process_chapter(original_text, translated_text, chapter_num)
    
    logger.info(f"Translation complete: {output_path}")
    return output_path


def translate_novel(
    novel_name: str,
    chapter_num: Optional[int],
    config: dict,
    start: int = 1,
    skip_refinement: bool = False
):
    """
    Translate novel chapters.
    
    Args:
        novel_name: Name of the novel
        chapter_num: Specific chapter to translate (None for all)
        config: Configuration dict
        start: Starting chapter number
        skip_refinement: Whether to skip refinement
    """
    logger = logging.getLogger(__name__)
    
    input_dir = config['paths'].get('input_dir', INPUT_DIR)
    
    # List chapter files
    chapter_files = FileHandler.list_chapters(input_dir, novel_name)
    
    if not chapter_files:
        logger.error(f"No chapter files found for '{novel_name}' in {input_dir}")
        logger.info(f"Expected pattern: {novel_name}_XXX.md")
        return False
    
    total = len(chapter_files)
    logger.info(f"Found {total} chapters for '{novel_name}'")
    
    # Determine range
    if chapter_num:
        if chapter_num > total:
            logger.error(f"Chapter {chapter_num} not found. Only {total} chapters available.")
            return False
        chapters_to_process = [chapter_files[chapter_num - 1]]
        start = chapter_num
    else:
        chapters_to_process = chapter_files[start - 1:]
    
    # Process chapters
    for i, chapter_file in enumerate(chapters_to_process, start=start):
        print(f"\n{'='*60}")
        print(f"Chapter {i}/{total}: {chapter_file.name}")
        print(f"{'='*60}")
        
        try:
            output = translate_single_file(
                str(chapter_file),
                config,
                skip_refinement=skip_refinement
            )
            
            if output:
                print(f"✓ Saved: {output}")
            else:
                print(f"✗ Failed to translate chapter {i}")
                
        except KeyboardInterrupt:
            print("\n\nInterrupted by user.")
            return False
        except Exception as e:
            logger.error(f"Error processing chapter {i}: {e}", exc_info=True)
            print(f"✗ Error: {e}")
            continue
    
    print(f"\n{'='*60}")
    print(f"All chapters complete!")
    print(f"{'='*60}")
    return True


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Chinese Xianxia to Myanmar Novel Translation Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Translate single chapter
  python -m src.main --novel 古道仙鸿 --chapter 1
  
  # Translate all chapters
  python -m src.main --novel 古道仙鸿 --all
  
  # Start from chapter 10
  python -m src.main --novel 古道仙鸿 --all --start 10
  
  # Translate specific file
  python -m src.main --input data/input/古道仙鸿_001.md
  
  # Skip refinement (faster)
  python -m src.main --novel 古道仙鸿 --chapter 1 --skip-refinement
        """
    )
    
    # Novel selection
    parser.add_argument("--novel", "-n", help="Novel name (e.g., 古道仙鸿)")
    parser.add_argument("--chapter", "-c", type=int, help="Specific chapter number")
    parser.add_argument("--all", "-a", action="store_true", help="Translate all chapters")
    parser.add_argument("--start", "-s", type=int, default=1, help="Start from chapter (default: 1)")
    
    # File input
    parser.add_argument("--input", "-i", help="Input file path (alternative to --novel)")
    
    # Processing options
    parser.add_argument("--skip-refinement", action="store_true", help="Skip refinement step")
    parser.add_argument("--two-stage", action="store_true", help="Enable two-stage translation")
    parser.add_argument("--single-stage", action="store_true", help="Force single-stage translation")
    
    # Configuration
    parser.add_argument("--config", default="config/settings.yaml", help="Config file path")
    
    args = parser.parse_args()
    
    # Setup
    print("=" * 60)
    print("Chinese Xianxia to Myanmar Translation Pipeline")
    print("=" * 60)
    print()
    
    # Validate arguments
    if not args.novel and not args.input:
        parser.print_help()
        print("\n✗ Error: Must specify --novel or --input")
        return 1
    
    # Load configuration
    try:
        config = load_config(args.config)
        logger = setup_logging()
        logger.info(f"Loaded config from {args.config}")
        print(f"Config: {args.config}")
        print(f"Model: {config['models']['translator']}")
        print()
    except Exception as e:
        print(f"✗ Failed to load configuration: {e}")
        return 1
    
    # Override two-stage mode if specified
    if args.two_stage:
        config['translation_pipeline']['mode'] = 'two_stage'
        print("Mode: Two-stage translation")
    elif args.single_stage:
        config['translation_pipeline']['mode'] = 'single_stage'
        print("Mode: Single-stage translation")
    else:
        mode = config['translation_pipeline'].get('mode', 'single_stage')
        print(f"Mode: {mode.replace('_', '-')} translation")
    
    print()
    
    # Run translation
    try:
        if args.input:
            # Single file mode
            output = translate_single_file(
                args.input,
                config,
                skip_refinement=args.skip_refinement
            )
            
            if output:
                print(f"\n✓ Translation saved: {output}")
                return 0
            else:
                print("\n✗ Translation failed")
                return 1
        
        elif args.novel:
            # Novel mode
            success = translate_novel(
                args.novel,
                args.chapter,
                config,
                start=args.start,
                skip_refinement=args.skip_refinement
            )
            
            return 0 if success else 1
        
    except KeyboardInterrupt:
        print("\n\nPipeline interrupted by user.")
        return 130
    except Exception as e:
        logger.error(f"Pipeline error: {e}", exc_info=True)
        print(f"\n✗ Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
