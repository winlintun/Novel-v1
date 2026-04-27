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
import atexit
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.file_handler import FileHandler
from src.utils.ollama_client import OllamaClient
from src.utils.progress_logger import ProgressLogger
from src.memory.memory_manager import MemoryManager
from src.agents.preprocessor import Preprocessor
from src.agents.translator import Translator
from src.agents.refiner import Refiner
from src.agents.checker import Checker
from src.agents.context_updater import ContextUpdater
from src.agents.qa_tester import QATesterAgent
from src.agents.reflection_agent import ReflectionAgent
from src.agents.myanmar_quality_checker import MyanmarQualityChecker


# Constants
DEFAULT_CHUNK_SIZE = 1500
DEFAULT_OVERLAP_SIZE = 100
BOOKS_DIR = "books"
INPUT_DIR = "data/input"
OUTPUT_DIR = "data/output"
WORKING_DIR = "working_data"
LOG_DIR = "logs"

# Global state for signal handling and resource management
_current_translation_state = {}
shutdown_requested = False
_active_ollama_client: Optional[OllamaClient] = None
_active_memory_manager: Optional[MemoryManager] = None


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


class StateUpdatingProgressLogger(ProgressLogger):
    """Progress logger that also updates the global translation state for signal handling."""
    def log_chunk(self, chunk_index: int, chunk_text: str, source_text: Optional[str] = None) -> None:
        super().log_chunk(chunk_index, chunk_text, source_text)
        # Update global state so signal handler can save partial progress
        if '_current_translation_state' in globals():
            _current_translation_state['translated_chunks'][chunk_index] = chunk_text


def setup_logging(log_file: Optional[str] = None):
    """Configure logging with file and console handlers."""
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(WORKING_DIR, exist_ok=True)
    
    if not log_file:
        log_file = f"{LOG_DIR}/translation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    # Create handlers
    file_handler = logging.FileHandler(log_file, encoding='utf-8-sig')
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


def register_active_resources(ollama_client: Optional[OllamaClient] = None, 
                              memory_manager: Optional[MemoryManager] = None) -> None:
    """
    Register active resources for cleanup on shutdown.
    
    Args:
        ollama_client: Active OllamaClient instance
        memory_manager: Active MemoryManager instance
    """
    global _active_ollama_client, _active_memory_manager
    if ollama_client:
        _active_ollama_client = ollama_client
    if memory_manager:
        _active_memory_manager = memory_manager


def cleanup_resources() -> None:
    """
    Cleanup all active resources.
    Called on normal exit and via signal handlers.
    """
    global _active_ollama_client, _active_memory_manager
    
    logger = logging.getLogger(__name__)
    logger.info("Cleaning up resources...")
    
    # Cleanup Ollama client
    if _active_ollama_client:
        try:
            _active_ollama_client.cleanup()
            logger.info("Ollama client cleaned up")
        except Exception as e:
            logger.error(f"Error cleaning up Ollama client: {e}")
        finally:
            _active_ollama_client = None
    
    # Save memory state
    if _active_memory_manager:
        try:
            _active_memory_manager.save_memory()
            logger.info("Memory state saved")
        except Exception as e:
            logger.error(f"Error saving memory: {e}")
        finally:
            _active_memory_manager = None
    
    logger.info("Resource cleanup complete")


def signal_handler(signum, frame):
    """Handle interrupt signals gracefully with resource cleanup."""
    global shutdown_requested
    logger = logging.getLogger(__name__)
    
    print("\n\n" + "=" * 60)
    print("⚠️  Shutdown requested. Saving progress and cleaning up...")
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
    
    # Cleanup resources
    cleanup_resources()
    
    print("✓ Resources cleaned up")
    print("\nYou can resume translation later by running the same command.")
    print("To free system memory, you may want to stop Ollama server:")
    print("  ollama stop <model_name>  or  sudo systemctl stop ollama")
    sys.exit(0)


# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Register cleanup function for normal exit
atexit.register(cleanup_resources)


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
    
    with open(output_file, 'w', encoding='utf-8-sig') as f:
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


def is_two_stage_mode(config: Dict[str, Any]) -> bool:
    """Check if two-stage translation is enabled."""
    pipeline = config.get("translation_pipeline", {})
    return pipeline.get("mode") == "two_stage"


def get_stage_models(config: Dict[str, Any]) -> Tuple[str, str]:
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
    two_stage: bool = None,
    unload_on_exit: bool = False
) -> Optional[Path]:
    """
    Translate a single chapter file with proper resource management.
    
    Args:
        filepath: Path to chapter file
        config: Configuration dict
        skip_refinement: Whether to skip refinement
        two_stage: Override config for two-stage mode
        unload_on_exit: Whether to unload model from GPU after translation
        
    Returns:
        Path to output file or None on failure
    """
    logger = logging.getLogger(__name__)
    
    # Determine two-stage mode
    if two_stage is None:
        two_stage = is_two_stage_mode(config)
    
    # Initialize components with context manager for cleanup
    logger.info("Initializing translation pipeline...")
    
    # Ollama client with optional unload on exit
    ollama_client = OllamaClient(
        model=config['models']['translator'],
        base_url=config['models'].get('ollama_base_url', 'http://localhost:11434'),
        temperature=config['processing'].get('temperature', 0.5),
        top_p=config['processing'].get('top_p', 0.92),
        top_k=config['processing'].get('top_k', 50),
        repeat_penalty=config['processing'].get('repeat_penalty', 1.3),
        max_retries=config['processing'].get('max_retries', 3),
        unload_on_cleanup=unload_on_exit
    )
    
    # Register for cleanup
    register_active_resources(ollama_client=ollama_client)
    
    try:
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
        register_active_resources(memory_manager=memory)
        
        # Agents
        preprocessor = Preprocessor(
            chunk_size=config['processing'].get('chunk_size', DEFAULT_CHUNK_SIZE),
            overlap_size=config['processing'].get('chunk_overlap', DEFAULT_OVERLAP_SIZE)
        )
        
        # Determine if pivot translation is needed
        pipeline_config = config.get('translation_pipeline', {})
        is_pivot = pipeline_config.get('stage1_target_lang') == 'english'
        
        if is_pivot:
            from src.agents.pivot_translator import PivotTranslator
            translator = PivotTranslator(ollama_client, memory, config)
        else:
            translator = Translator(ollama_client, memory, config)
        
        # Get batch size from config for refiner
        batch_size = config['processing'].get('batch_processing', {}).get('batch_size', 5)
        
        # Process pipeline mode (full/lite/fast per need_fix.md Phase 1.1)
        # Use config mode by default, CLI args.mode can override but not yet supported in function
        config_pipeline_mode = config.get('translation_pipeline', {}).get('mode', 'full')
        actual_mode = config_pipeline_mode
        
        # Initialize agents based on pipeline mode
        refiner = None
        reflection_agent = None
        myanmar_checker = None
        qa_tester = None
        
        if actual_mode == 'full':
            # Full 6-stage pipeline
            refiner = Refiner(ollama_client, batch_size=batch_size) if not skip_refinement else None
            reflection_agent = ReflectionAgent(ollama_client, config) if config.get('translation_pipeline', {}).get('use_reflection', False) else None
            myanmar_checker = MyanmarQualityChecker(config)
            qa_tester = QATesterAgent(memory)
        elif actual_mode == 'lite':
            # Lite 3-stage: Translate → Refine → Quality (skip reflection)
            refiner = Refiner(ollama_client, batch_size=batch_size) if not skip_refinement else None
            myanmar_checker = MyanmarQualityChecker(config)
        elif actual_mode == 'fast':
            # Fast 2-stage: Translate → Quality only (skip refinement)
            myanmar_checker = MyanmarQualityChecker(config)
        
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
        
        # Initialize progress logger for real-time tracking
        progress_logger = StateUpdatingProgressLogger(
            book_id=book_id,
            chapter_name=chapter_name,
            total_chunks=len(chunks),
        )
        logger.info(f"Progress logging enabled: {progress_logger.get_log_path()}")
        print(f"📋 Progress log: {progress_logger.get_log_path()}")
        
        # Load original text for checking
        original_text = FileHandler.read_text(filepath)
        
        if is_pivot:
            # Setup paths
            en_dir = Path(OUTPUT_DIR) / book_id / "en"
            mm_dir = Path(OUTPUT_DIR) / book_id / "mm"
            en_dir.mkdir(parents=True, exist_ok=True)
            mm_dir.mkdir(parents=True, exist_ok=True)
            en_path = en_dir / f"{chapter_name}.md"
            
            # Check if English translation already exists (resume capability)
            if en_path.exists():
                logger.info(f"Found existing English translation: {en_path}")
                print(f"📄 Using existing English translation: {en_path}")
                english_text = FileHandler.read_text(str(en_path))
                # Split English text back into chunks (by double newline)
                english_chunks = english_text.split('\n\n')
                # Filter out empty chunks
                english_chunks = [chunk.strip() for chunk in english_chunks if chunk.strip()]
            else:
                # STEP 1: CN -> EN
                logger.info(f"STEP 1: Translating {len(chunks)} chunks to English...")
                print(f"🔄 Step 1: Translating {len(chunks)} chunks Chinese → English...")
                english_chunks = translator.translate_chunks_stage1(chunks)
                english_text = '\n\n'.join(english_chunks)
                
                # Save English version
                FileHandler.write_text(en_path, english_text)
                logger.info(f"Step 1 Complete. English version saved to: {en_path}")
                print(f"✅ Step 1 Complete! English saved to: {en_path}")
            
            # STEP 2: EN -> MM (reads from saved EN file)
            logger.info(f"STEP 2: Translating from English to Myanmar...")
            print(f"🔄 Step 2: Translating {len(english_chunks)} chunks English → Myanmar...")
            translated_chunks = translator.translate_chunks_stage2(
                english_chunks, 
                chapter_num,
                progress_logger=progress_logger
            )
        else:
            # Standard CN -> MM
            logger.info(f"Translating {len(chunks)} chunks...")
            translated_chunks = translator.translate_chunks(
                chunks,
                chapter_num,
                progress_logger=progress_logger
            )
        
        translated_text = '\n\n'.join(translated_chunks)
        
        # Mark progress as complete for translation phase
        progress_logger.finalize(success=True)
        logger.info(f"Progress log finalized: {progress_logger.get_log_path()}")
        
        # Refine (depending on mode: full/lite - fast skips)
        if refiner is not None and not skip_refinement:
            logger.info("Refining translation...")
            translated_text = refiner.refine_full_text(translated_text)
        
        # Reflection & Self-Correction (full mode only)
        if reflection_agent is not None and not skip_refinement:
            logger.info("Running reflection and self-correction...")
            translated_text = reflection_agent.reflect_and_improve(translated_text, original_text)
        
        # Check quality (all modes have checker)
        logger.info("Checking translation quality...")
        check_result = checker.check_chapter(original_text, translated_text)
        
        # Myanmar Quality Check (full/lite modes)
        if myanmar_checker is not None:
            myanmar_quality = myanmar_checker.check_quality(translated_text)
            check_result['myanmar_quality_score'] = myanmar_quality['score']
            check_result['myanmar_issues'] = myanmar_quality['issues']
        
        # QA Validation (full mode only)
        if qa_tester is not None:
            qa_report = qa_tester.validate_output(translated_text, chapter_num)
            check_result['qa_passed'] = qa_report['passed']
            check_result['qa_issues'] = qa_report['issues']
        
        print("\n" + checker.generate_report(chapter_num, check_result))
        
        # Add Myanmar quality report if issues found
        if myanmar_quality['issues']:
            print(f"🇲🇲 Myanmar Quality Issues: {len(myanmar_quality['issues'])}")
            for issue in myanmar_quality['issues'][:5]:
                print(f"  - {issue}")
        
        # Save output (MM version)
        if is_pivot:
            mm_dir = Path(OUTPUT_DIR) / book_id / "mm"
            mm_dir.mkdir(parents=True, exist_ok=True)
            output_path = mm_dir / f"{chapter_name}.md"
            
            # Add metadata
            progress_info = f"""<!--
Translation Progress:
- Chapter: {chapter_name}
- Chunks Completed: {len(chunks)}/{len(chunks)}
- Source: {en_path}
- Timestamp: {datetime.now().isoformat()}
- Status: COMPLETE
-->

"""
            FileHandler.write_text(output_path, progress_info + translated_text)
            logger.info(f"Myanmar translation saved to: {output_path}")
            print(f"✅ Myanmar translation saved to: {output_path}")
        else:
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
        print(f"\n✅ Progress log saved: {progress_logger.get_log_path()}")
        return output_path
        
    except Exception as e:
        logger.error(f"Translation failed: {e}", exc_info=True)
        # Finalize progress logger with failure status if it exists
        if 'progress_logger' in locals():
            progress_logger.finalize(success=False)
            print(f"\n⚠️  Progress log saved (with errors): {progress_logger.get_log_path()}")
        raise
    finally:
        # Ensure cleanup happens
        cleanup_resources()


def translate_novel(
    novel_name: str,
    chapter_num: Optional[int],
    config: Dict[str, Any],
    start: int = 1,
    skip_refinement: bool = False,
    unload_after_chapter: bool = False
) -> bool:
    """
    Translate novel chapters with proper resource management.
    
    Args:
        novel_name: Name of the novel
        chapter_num: Specific chapter to translate (None for all)
        config: Configuration dict
        start: Starting chapter number
        skip_refinement: Whether to skip refinement
        unload_after_chapter: Whether to unload model from GPU after each chapter
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
            # For batch translation, only unload on last chapter if requested
            is_last = (i == start + len(chapters_to_process) - 1)
            should_unload = unload_after_chapter if not is_last else True
            
            output = translate_single_file(
                str(chapter_file),
                config,
                skip_refinement=skip_refinement,
                unload_on_exit=should_unload
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
    print("\nTo free system memory, you may want to stop Ollama server:")
    print("  ollama stop <model_name>  or  sudo systemctl stop ollama")
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
  
  # Unload model from GPU after each chapter (saves VRAM)
  python -m src.main --novel 古道仙鸿 --all --unload-after-chapter
        """
    )
    
    # Novel selection
    parser.add_argument("--novel", "-n", help="Novel name (e.g., 古道仙鸿)")
    parser.add_argument("--chapter", "-c", type=int, help="Specific chapter number")
    parser.add_argument("--all", "-a", action="store_true", help="Translate all chapters")
    parser.add_argument("--start", "-s", type=int, default=1, help="Start from chapter (default: 1)")
    
    # File input
    parser.add_argument("--input", "-i", help="Input file path (alternative to --novel)")
    parser.add_argument("--test", "-t", action="store_true", help="Run a test translation using sample.md")
    
    # Processing options
    parser.add_argument("--skip-refinement", action="store_true", help="Skip refinement step")
    parser.add_argument("--two-stage", action="store_true", help="Enable two-stage translation")
    parser.add_argument("--single-stage", action="store_true", help="Force single-stage translation")
    parser.add_argument("--unload-after-chapter", action="store_true", 
                       help="Unload model from GPU after each chapter to save VRAM")
    parser.add_argument("--mode", choices=["full", "lite", "fast"], default="full",
                       help="Pipeline mode: full (6-stage), lite (3-stage), fast (2-stage)")
    
    # Source language (auto-selects config)
    parser.add_argument("--lang", "-l", choices=["en", "zh", "english", "chinese"], 
                       help="Source language: en/english (English→Myanmar) or zh/chinese (Chinese→Myanmar). Auto-selects config.")
    
    # Configuration
    parser.add_argument("--config", default="config/settings.yaml", help="Config file path")
    
    # UI option
    parser.add_argument("--ui", action="store_true", help="Launch the Web UI (Streamlit)")
    
    # Glossary generation
    parser.add_argument("--generate-glossary", action="store_true", 
                       help="Automatically generate glossary from novel chapters before translation")
    
    args = parser.parse_args()
    
    # Setup
    print("=" * 60)
    print("Chinese Xianxia to Myanmar Translation Pipeline")
    print("=" * 60)
    print()
    
    # Launch UI if requested
    if args.ui:
        print("🚀 Launching Web UI...")
        import subprocess
        ui_script = Path("ui/streamlit_app.py")
        if not ui_script.exists():
            print(f"✗ Error: Web UI script not found at {ui_script}")
            return 1
        
        try:
            # Check if streamlit is installed
            subprocess.run(["streamlit", "--version"], capture_output=True, check=True)
            # Run from project root directory
            project_root = Path(__file__).parent.parent
            subprocess.run(["streamlit", "run", str(ui_script)], cwd=project_root)
            return 0
        except subprocess.CalledProcessError:
            print("✗ Error: Streamlit is not installed. Please run: pip install streamlit")
            return 1
        except KeyboardInterrupt:
            print("\nWeb UI stopped.")
            return 0
        except Exception as e:
            print(f"✗ Error launching Web UI: {e}")
            return 1

    # Glossary generation mode
    if args.generate_glossary:
        if not args.novel:
            print("✗ Error: Must specify --novel for glossary generation")
            return 1
        
        print(f"🔍 Generating glossary for novel: {args.novel}")
        
        # Load config
        config = load_config(args.config)
        ollama_client = OllamaClient(
            model=config['models']['translator'],
            unload_on_cleanup=True
        )
        memory = MemoryManager()
        
        # Register for cleanup
        register_active_resources(ollama_client=ollama_client, memory_manager=memory)
        
        from src.agents.glossary_generator import GlossaryGenerator
        generator = GlossaryGenerator(ollama_client, memory, config)
        
        # List files
        input_dir = config['paths'].get('input_dir', INPUT_DIR)
        chapter_files = FileHandler.list_chapters(input_dir, args.novel)
        
        if not chapter_files:
            print(f"✗ Error: No chapters found for {args.novel}")
            return 1
            
        # Process first 5 chapters for glossary (representative sample)
        sample_files = [str(f) for f in chapter_files[:5]]
        source_lang = "Chinese" if args.lang in ['zh', 'chinese'] or not args.lang else "English"
        
        print(f"Processing {len(sample_files)} chapters (Source: {source_lang})...")
        terms = generator.process_files(sample_files, source_lang)
        generator.save_to_pending(terms)
        
        print(f"\n✅ Extracted {len(terms)} terms to data/glossary_pending.json")
        print("Please review and approve them in the glossary file before starting translation.")
        return 0

    # Validate arguments
    if args.test:
        # Use sample.md for testing
        test_file = Path("data/input/sample.md")
        if not test_file.exists():
            print(f"Creating sample test file: {test_file}")
            os.makedirs("data/input", exist_ok=True)
            with open(test_file, "w", encoding="utf-8-sig") as f:
                f.write("# Sample Chapter\n\nThis is a sample text for translation testing.")
        
        args.input = str(test_file)
        if not args.lang:
            args.lang = "en"
            print("Auto-selected language: English (for sample.md)")

    if not args.novel and not args.input:
        parser.print_help()
        print("\n✗ Error: Must specify --novel, --input, or --test")
        return 1
    
    # Load configuration
    try:
        # Auto-select config based on source language
        if args.lang:
            if args.lang in ['en', 'english']:
                args.config = "config/settings.english.yaml"
                print(f"Auto-selected English config: {args.config}")
            elif args.lang in ['zh', 'chinese']:
                args.config = "config/settings.pivot.yaml"
                print(f"Auto-selected Chinese config: {args.config}")
        
        config = load_config(args.config)
        logger = setup_logging()
        logger.info(f"Loaded config from {args.config}")
        print(f"Config: {args.config}")
        print()
    except Exception as e:
        print(f"✗ Failed to load configuration: {e}")
        return 1
    
    # Display model information
    models_config = config.get('models', {})
    provider = models_config.get('provider', 'ollama')
    translator_model = models_config.get('translator', 'qwen2.5:14b')
    editor_model = models_config.get('editor', translator_model)
    
    print("-" * 60)
    print(f"Provider: {provider.upper()}")
    print(f"Translator Model: {translator_model}")
    print(f"Editor Model: {editor_model}")
    print("-" * 60)
    print()
    
    # Override two-stage mode if specified
    if args.two_stage:
        config['translation_pipeline']['mode'] = 'two_stage'
        print("Mode: Two-stage translation")
        print("  Stage 1: Raw translation")
        print("  Stage 2: Literary refinement")
    elif args.single_stage:
        config['translation_pipeline']['mode'] = 'single_stage'
        print("Mode: Single-stage translation")
    elif args.mode:
        config['translation_pipeline']['mode'] = args.mode
        print(f"Mode: {args.mode} pipeline")
        if args.mode == 'full':
            print("  6-stage: Translate → Refine → Reflect → Quality → Consistency → QA")
        elif args.mode == 'lite':
            print("  3-stage: Translate → Refine → Quality")
        elif args.mode == 'fast':
            print("  2-stage: Translate → Quality")
    else:
        mode = config['translation_pipeline'].get('mode', 'single_stage')
        print(f"Mode: {mode.replace('_', '-')} translation")
        if mode == 'two_stage':
            print("  Stage 1: Raw translation")
            print("  Stage 2: Literary refinement")
    
    if args.unload_after_chapter:
        print("\nMemory optimization: Model will be unloaded from GPU after each chapter")
    
    print()
    
    # Run translation
    try:
        if args.input:
            # Single file mode
            output = translate_single_file(
                args.input,
                config,
                skip_refinement=args.skip_refinement,
                unload_on_exit=True
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
                skip_refinement=args.skip_refinement,
                unload_after_chapter=args.unload_after_chapter
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
