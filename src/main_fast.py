#!/usr/bin/env python3
"""
Fast Translation Entry Point
Optimized for speed with Ollama - single stage, batch processing, larger chunks.

Usage:
    python -m src.main_fast --novel 古道仙鸿 --chapter 1
    python -m src.main_fast --novel 古道仙鸿 --all
"""

import argparse
import logging
import signal
import sys
import atexit
from pathlib import Path
from typing import Optional

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.file_handler import FileHandler
from src.utils.ollama_client import OllamaClient
from src.memory.memory_manager import MemoryManager
from src.agents.fast_translator import FastTranslator
from src.agents.fast_refiner import FastRefiner
from src.agents.preprocessor import Preprocessor

# Global state for resource management
_active_ollama_client: Optional[OllamaClient] = None
_active_memory_manager: Optional[MemoryManager] = None
_shutdown_requested = False


def setup_logging():
    """Setup logging with simpler format for speed."""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    timestamp = logging.Formatter('%(asctime)s').format(logging.LogRecord(
        '', 0, '', 0, '', (), None
    )).replace(',', '').replace(' ', '_').replace(':', '')
    
    log_file = log_dir / f"fast_translation_{timestamp[:15]}.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    return log_file


def register_active_resources(ollama_client: Optional[OllamaClient] = None, 
                              memory_manager: Optional[MemoryManager] = None) -> None:
    """Register active resources for cleanup on shutdown."""
    global _active_ollama_client, _active_memory_manager
    if ollama_client:
        _active_ollama_client = ollama_client
    if memory_manager:
        _active_memory_manager = memory_manager


def cleanup_resources() -> None:
    """Cleanup all active resources."""
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
    """Handle interrupt signals gracefully."""
    global _shutdown_requested
    logger = logging.getLogger(__name__)
    
    print("\n\n" + "=" * 60)
    print("⚠️  Shutdown requested. Cleaning up...")
    print("=" * 60)
    
    _shutdown_requested = True
    
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


def load_fast_config():
    """Load fast configuration."""
    config_path = Path("config/settings.fast.yaml")
    
    if config_path.exists():
        return FileHandler.read_yaml(str(config_path))
    else:
        # Fallback to default config
        return FileHandler.read_yaml("config/settings.yaml")


def main():
    """Fast translation main function."""
    parser = argparse.ArgumentParser(
        description='Fast Novel Translation with Ollama'
    )
    parser.add_argument('--novel', required=True, help='Novel name')
    parser.add_argument('--chapter', type=int, help='Chapter number (omit for all)')
    parser.add_argument('--all', action='store_true', help='Translate all chapters')
    parser.add_argument('--start', type=int, default=1, help='Start from chapter N')
    parser.add_argument('--unload-after-chapter', action='store_true',
                       help='Unload model from GPU after each chapter to save VRAM')
    
    args = parser.parse_args()
    
    # Setup logging
    log_file = setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("="*60)
    logger.info("FAST TRANSLATION MODE")
    logger.info("="*60)
    logger.info("Optimizations enabled:")
    logger.info("  - Single-stage translation (no separate refinement)")
    logger.info("  - Larger chunks (3000 chars vs 1500)")
    logger.info("  - Batch refinement (5 paragraphs at once)")
    logger.info("  - Streaming responses")
    logger.info("  - 7B models (faster than 14B)")
    logger.info("="*60)
    
    # Load config
    config = load_fast_config()
    logger.info("Loaded fast config")
    
    # Initialize components
    model_config = config.get('models', {})
    
    # Get processing config
    processing_config = config.get('processing', {})
    
    ollama_client = OllamaClient(
        model=model_config.get('translator', 'qwen2.5:7b'),
        base_url=model_config.get('ollama_base_url', 'http://localhost:11434'),
        temperature=processing_config.get('temperature', 0.5),
        top_p=processing_config.get('top_p', 0.92),
        top_k=processing_config.get('top_k', 50),
        repeat_penalty=processing_config.get('repeat_penalty', 1.3),
        max_retries=processing_config.get('max_retries', 3),
        timeout=processing_config.get('request_timeout', 120),
        unload_on_cleanup=args.unload_after_chapter
    )
    
    # Register for cleanup
    register_active_resources(ollama_client=ollama_client)
    
    # Check model availability
    if not ollama_client.check_model_available():
        logger.error(f"Model not available. Run: ollama pull {ollama_client.model}")
        sys.exit(1)
    
    # Initialize memory
    paths = config.get('paths', {})
    memory = MemoryManager(
        glossary_path=paths.get('glossary_file', 'data/glossary.json'),
        context_path=paths.get('context_memory_file', 'data/context_memory.json')
    )
    register_active_resources(memory_manager=memory)
    
    logger.info(f"Memory loaded: {memory.glossary.get('total_terms', 0)} glossary terms")
    
    # Initialize translator (single-stage for speed)
    translator = FastTranslator(
        ollama_client=ollama_client,
        memory_manager=memory,
        use_streaming=True
    )
    
    # Find chapters to translate
    input_dir = Path(paths.get('input_dir', 'data/input')) / args.novel
    
    if not input_dir.exists():
        logger.error(f"Input directory not found: {input_dir}")
        sys.exit(1)
    
    # Get chapter files
    chapter_files = sorted(input_dir.glob(f"{args.novel}_chapter_*.md"))
    
    if args.chapter:
        # Single chapter
        chapter_files = [f for f in chapter_files if f.stem.endswith(f"{args.chapter:03d}")]
    elif args.all:
        # All chapters from start
        chapter_files = [f for f in chapter_files if args.start <= extract_chapter_num(f.stem)]
    
    if not chapter_files:
        logger.error("No chapters found to translate")
        sys.exit(1)
    
    logger.info(f"Found {len(chapter_files)} chapters to translate")
    
    # Create output directory
    output_dir = Path(paths.get('output_dir', 'data/output')) / args.novel
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Translate chapters
    preprocessor = Preprocessor(chunk_size=3000, overlap_size=50)
    
    try:
        for i, chapter_file in enumerate(chapter_files, 1):
            chapter_num = extract_chapter_num(chapter_file.stem)
            
            logger.info(f"\n{'='*60}")
            logger.info(f"Chapter {i}/{len(chapter_files)}: Chapter {chapter_num}")
            logger.info(f"{'='*60}")
            
            # Check if shutdown requested
            if _shutdown_requested:
                logger.info("Shutdown requested, stopping...")
                break
            
            try:
                # Load chapter
                logger.info(f"Loading: {chapter_file}")
                text = FileHandler.read_text(str(chapter_file))
                
                # Translate (single-stage, large chunks)
                logger.info("Translating with large chunks...")
                translated = translator.translate_chapter(text, chapter_num, use_chunking=True)
                
                # Check for repetition issues
                validation_config = config.get('processing', {}).get('validation', {})
                if validation_config.get('enabled', True):
                    from src.utils.postprocessor import check_repetition
                    rep_threshold = validation_config.get('max_repetition_ratio', 0.35)
                    if check_repetition(translated, threshold=rep_threshold):
                        logger.warning(f"⚠️  High repetition detected in chapter {chapter_num} (>{rep_threshold*100:.0f}%). Marking for review...")
                        # Add warning marker to output
                        translated = f"<!-- WARNING: High repetition detected (>35%). Please review this translation. -->\n\n{translated}"
                
                # Optional: Quick batch refinement if enabled
                pipe_config = config.get('translation_pipeline', {})
                if pipe_config.get('mode') == 'two_stage':
                    logger.info("Quick batch refinement...")
                    refiner = FastRefiner(
                        ollama_client=ollama_client,
                        batch_size=5
                    )
                    translated = refiner.refine_full_text(translated)
                
                # Save output
                output_file = output_dir / f"{args.novel}_chapter_{chapter_num:03d}_myanmar.md"
                FileHandler.write_text(str(output_file), translated)
                
                logger.info(f"Saved: {output_file}")
                
                # Update memory
                memory.update_chapter_context(chapter_num)
                memory.save_memory()
                
                # Unload model if requested (and not last chapter)
                if args.unload_after_chapter and i < len(chapter_files):
                    logger.info("Unloading model from GPU to free VRAM...")
                    ollama_client.unload_model()
                    
            except Exception as e:
                logger.error(f"Failed to translate chapter {chapter_num}: {e}")
                continue
        
        logger.info(f"\n{'='*60}")
        logger.info("Translation complete!")
        logger.info(f"Output directory: {output_dir}")
        logger.info(f"Log file: {log_file}")
        logger.info(f"{'='*60}")
        print("\nTo free system memory, you may want to stop Ollama server:")
        print("  ollama stop <model_name>  or  sudo systemctl stop ollama")
        
    except KeyboardInterrupt:
        logger.info("\n\nInterrupted by user.")
        print("\nInterrupted. Cleaning up...")
    finally:
        # Ensure cleanup happens
        cleanup_resources()


def extract_chapter_num(filename: str) -> int:
    """Extract chapter number from filename."""
    try:
        # Format: novel_name_chapter_001.md
        parts = filename.split('_')
        if len(parts) >= 2:
            num_part = parts[-1]
            if num_part.isdigit():
                return int(num_part)
            # Handle .md extension
            num_part = num_part.replace('.md', '')
            if num_part.isdigit():
                return int(num_part)
    except Exception:
        pass
    return 0


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")
        cleanup_resources()
        sys.exit(130)
