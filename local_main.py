#!/usr/bin/env python3
"""
Local Main - Ollama-only Novel Translator (No Rate Limits)

Optimized for local Ollama usage with:
- No request delays
- No rate limiting
- Faster processing
- Simpler configuration
- Better timeout handling
- Intermediate saving of partial results

Usage:
    python local_main.py input_novels/chapter_001.md
    python local_main.py --novel dao-equaling-the-heavens
"""

import os
import re
import sys
import json
import time
import signal
import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

# Import modules
from scripts.preprocessor import preprocess
from scripts.chunker import auto_chunk, split_into_paragraphs, print_chunk_analysis
from scripts.translator import get_translator, get_system_prompt
from scripts.postprocessor import postprocess
from scripts.assembler import assemble
from scripts.glossary_manager import GlossaryManager
from scripts.rewriter import BurmeseRewriter, get_raw_translation_prompt
from scripts.context_manager import ContextManager
from scripts.name_converter import NameConverter
from scripts.name_converter import CULTIVATION_TERMS
from scripts.name_mapping_system import NameMappingSystem, NameType

# Load config for two-stage pipeline
CONFIG_PATH = Path(__file__).parent / "config" / "config.json"

def load_config():
    """Load config.json for pipeline settings."""
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Could not load config: {e}")
        return {}

def is_two_stage_mode():
    """Check if two-stage translation is enabled in config."""
    config = load_config()
    pipeline = config.get("translation_pipeline", {})
    return pipeline.get("mode") == "two_stage"

def get_stage_models():
    """Get stage 1 and stage 2 models from config."""
    config = load_config()
    pipeline = config.get("translation_pipeline", {})
    return pipeline.get("stage1_model", "ollama"), pipeline.get("stage2_model", "ollama")

# Constants
DEFAULT_CHUNK_SIZE = 1500  # Larger chunks for local processing
DEFAULT_OVERLAP_SIZE = 100
MAX_CHUNK_SIZE = 5000
MIN_CHUNK_SIZE = 100
LOG_DIR = "working_data/logs"
BOOKS_DIR = "books"
INPUT_DIR = "input_novels"
ENGLISH_CHAPTERS_DIR = "english_chapters"
CHINESE_CHAPTERS_DIR = "chinese_chapters"

# Setup logging
class SensitiveDataFilter(logging.Filter):
    """Filter that masks sensitive data like API keys in log messages."""
    
    SENSITIVE_PATTERNS = [
        (r'key=[a-zA-Z0-9_-]{20,}', 'key=***API_KEY_HIDDEN***'),
        (r'api[_-]?key[=:][\s]*[a-zA-Z0-9_-]{10,}', 'api_key=***API_KEY_HIDDEN***'),
        (r'Authorization[=:][\s]*Bearer[\s]+[a-zA-Z0-9_-]+', 'Authorization=Bearer ***TOKEN_HIDDEN***'),
    ]
    
    def filter(self, record):
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            import re
            msg = record.msg
            for pattern, replacement in self.SENSITIVE_PATTERNS:
                msg = re.sub(pattern, replacement, msg, flags=re.IGNORECASE)
            record.msg = msg
        return True

os.makedirs(LOG_DIR, exist_ok=True)
log_file = f"{LOG_DIR}/translation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

file_handler = logging.FileHandler(log_file, encoding='utf-8')
file_handler.addFilter(SensitiveDataFilter())
console_handler = logging.StreamHandler()
console_handler.addFilter(SensitiveDataFilter())

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[file_handler, console_handler]
)
logger = logging.getLogger(__name__)


class TranslationInterrupted(Exception):
    """Raised when translation is interrupted by user."""
    pass


def translate_chunk(translator, user_content: str, system_prompt: str) -> str:
    """
    Translate a chunk directly without timeout.
    
    Args:
        translator: The translator instance
        user_content: Text to translate
        system_prompt: System prompt
    
    Returns:
        Translated text
    """
    # Simple direct translation - no timeout, no threading
    result = translator.translate(user_content, system_prompt)
    return result


def save_partial_translation(book_id: str, chapter_name: str, translated_chunks: Dict[int, str],
                            chunks_total: int, is_final: bool = False) -> Path:
    """
    Save partial translation to a file so user can see progress.
    
    Args:
        book_id: Book identifier
        chapter_name: Chapter name
        translated_chunks: Dictionary of chunk index -> translated text
        chunks_total: Total number of chunks
        is_final: Whether this is the final save
    
    Returns:
        Path to the saved file
    """
    book_dir = Path(BOOKS_DIR) / book_id
    book_dir.mkdir(parents=True, exist_ok=True)
    chapters_dir = book_dir / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)
    
    # Determine filename based on status
    if is_final:
        output_file = chapters_dir / f"{chapter_name}_myanmar.md"
    else:
        output_file = chapters_dir / f"{chapter_name}_myanmar_PARTIAL.md"
    
    # Build partial content
    sorted_indices = sorted(translated_chunks.keys())
    available_chunks = [translated_chunks[i] for i in sorted_indices]
    
    if not available_chunks:
        return None
    
    full_text = '\n\n'.join(available_chunks)
    
    # Add progress header
    progress_info = f"""# Translation Progress
- Chapter: {chapter_name}
- Book: {book_id}
- Progress: {len(translated_chunks)}/{chunks_total} chunks translated
- Saved at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- Status: {'COMPLETED' if is_final else 'IN PROGRESS'}

---

"""
    
    content = progress_info + full_text
    
    # Write to file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return output_file


# Global flag for graceful shutdown
shutdown_requested = False
_current_translation_state = {"translated_chunks": {}, "book_id": None, "chapter_name": None, "chunks_total": 0}

def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully - save partial results immediately."""
    global shutdown_requested
    print("\n\n⚠️  Shutdown requested by user (Ctrl+C)...")
    shutdown_requested = True
    
    # Try to save whatever we have so far
    if _current_translation_state["translated_chunks"] and _current_translation_state["book_id"]:
        try:
            partial_file = save_partial_translation(
                _current_translation_state["book_id"],
                _current_translation_state["chapter_name"],
                _current_translation_state["translated_chunks"],
                _current_translation_state["chunks_total"],
                is_final=False
            )
            if partial_file:
                print(f"💾 Emergency save: {partial_file}")
        except Exception as e:
            print(f"⚠️  Could not save partial translation: {e}")

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def translate_single_file_local(
    filepath: str,
    max_chars: int,
    overlap_chars: int,
    source_lang: str = "Chinese",
    book_id: str = None,
    chapter_num: int = 1,
    context_manager: ContextManager = None,
    auto_learn: bool = True
) -> bool:
    """Translate a single file using local Ollama (no rate limits)."""
    
    filepath = Path(filepath)
    chapter_name = filepath.stem
    
    # Determine book ID
    if book_id is None:
        if filepath.parent.name != INPUT_DIR:
            book_id = filepath.parent.name
        else:
            match = re.match(r'^(.+?)_chapter_\d+', chapter_name, re.IGNORECASE)
            book_id = match.group(1) if match else chapter_name
    
    if context_manager is None:
        context_manager = ContextManager(book_id, source_lang=source_lang)
    
    # Check two-stage mode early for display
    two_stage = is_two_stage_mode()
    stage1_model, stage2_model = get_stage_models()
    
    print("=" * 60)
    print(f"Translating: {chapter_name}")
    print(f"Book ID: {book_id}")
    if two_stage:
        print(f"Mode: TWO-STAGE Translation")
        print(f"   Stage 1: {stage1_model}")
        print(f"   Stage 2: {stage2_model}")
    else:
        print("Mode: Single-Stage Translation (Ollama)")
    print("Features: No timeout, auto-save partial results")
    print("Press Ctrl+C to stop and save partial translation")
    print("=" * 60)
    
    # 1. Preprocess
    print("\n[1/7] Preprocessing...")
    try:
        from scripts.preprocessor import preprocess
        clean_text = preprocess(str(filepath))
        print(f"✓ Preprocessed: {len(clean_text)} characters")
    except Exception as e:
        logger.error(f"Preprocessing failed: {e}")
        return False
    
    # 2. Chunk
    print("\n[2/7] Chunking...")
    try:
        paragraphs = split_into_paragraphs(clean_text)
        from scripts.chunker import auto_chunk
        chunks = auto_chunk(clean_text, max_chars, overlap_chars=overlap_chars)
        print_chunk_analysis(chunks, paragraphs)
    except Exception as e:
        logger.error(f"Chunking failed: {e}")
        return False
    
    # 3. Initialize resources
    print(f"\n[3/7] Loading resources for: {book_id}")
    try:
        glossary = GlossaryManager(book_id)
        print(f"✓ Glossary: {len(glossary.names)} names")
    except:
        glossary = None
        print("⚠ No glossary")
    
    name_mapping_system = None
    try:
        name_mapping_system = NameMappingSystem(book_id, source_lang=source_lang)
        detected = name_mapping_system.detect_names(clean_text, chapter_num=chapter_num)
        if detected:
            print(f"  → Detected {len(detected)} new names")
        clean_text = name_mapping_system.apply_mappings(clean_text)
        name_mapping_system.save()
    except Exception as e:
        logger.warning(f"Name mapping error: {e}")
    
    context_manager.register_chapter(chapter_num, title=chapter_name, word_count=len(clean_text))
    context_text = context_manager.get_context_for_chapter(chapter_num)
    if context_text:
        print(f"✓ Context loaded")
    
    # 4. Load translator(s) based on mode
    if two_stage:
        print(f"\n[4/7] Loading translators (TWO-STAGE MODE)...")
        print(f"   Stage 1 (Raw): {stage1_model}")
        print(f"   Stage 2 (Rewrite): {stage2_model}")
        try:
            # Stage 1 translator
            if stage1_model.startswith("ollama:"):
                stage1_translator = get_translator("ollama")
                stage1_translator.name = stage1_model  # Track actual model name
            else:
                stage1_translator = get_translator(stage1_model)
            
            # Stage 2 rewriter
            rewriter = BurmeseRewriter(stage2_model, glossary)
            print(f"✓ Loaded: {stage1_translator.name} → {stage2_model}")
        except Exception as e:
            print(f"✗ Failed to load translators: {e}")
            print("Make sure Ollama is running: ollama serve")
            return False
        
        # Stage 1 prompt (raw translation)
        name_mappings_text = ""
        if name_mapping_system:
            name_mappings_text = name_mapping_system.get_prompt_text()
        system_prompt = get_raw_translation_prompt(source_lang, name_mappings_text)
        if context_text:
            system_prompt += f"\n\n{'='*80}\nNOVEL CONTEXT:\n{'='*80}\n{context_text}\n{'='*80}"
    else:
        print(f"\n[4/7] Loading Ollama translator (single-stage)...")
        try:
            stage1_translator = get_translator("ollama")
            rewriter = None
            print(f"✓ Loaded: {stage1_translator.name}")
        except Exception as e:
            print(f"✗ Failed to load Ollama: {e}")
            print("Make sure Ollama is running: ollama serve")
            return False
        
        # Single-stage prompt
        system_prompt = get_system_prompt(source_lang=source_lang, glossary_manager=glossary)
        if name_mapping_system:
            name_mappings_text = name_mapping_system.get_prompt_text()
            if name_mappings_text:
                system_prompt += "\n" + name_mappings_text
        if context_text:
            system_prompt += f"\n\n{'='*80}\nNOVEL CONTEXT:\n{'='*80}\n{context_text}\n{'='*80}"
    
    # 5. Translate chunks
    if two_stage:
        print(f"\n[5/7] Translating {len(chunks)} chunks (TWO-STAGE)...")
    else:
        print(f"\n[5/7] Translating {len(chunks)} chunks...")
    print("-" * 60)
    
    start_time = time.time()
    previous_translation = None
    translated_chunks = {}
    failed_chunks = []
    
    # Update global state for emergency save on interrupt
    global _current_translation_state
    _current_translation_state["book_id"] = book_id
    _current_translation_state["chapter_name"] = chapter_name
    _current_translation_state["chunks_total"] = len(chunks)
    
    for i, chunk in enumerate(chunks, 1):
        # Check if shutdown was requested
        if shutdown_requested:
            print(f"\n⚠️  Stopping translation at chunk {i}/{len(chunks)}")
            break
        
        logger.info(f"Translating chunk {i}/{len(chunks)}: {len(chunk)} chars using {stage1_translator.name}")
        print(f"\n[{i}/{len(chunks)}] Translating {len(chunk)} chars...", end=" ", flush=True)
        
        user_content = chunk
        if previous_translation and i > 1:
            context_preview = previous_translation[-1200:] if len(previous_translation) > 1200 else previous_translation
            user_content = f"PREVIOUS CONTEXT:\n{context_preview}\n\n---\n\nCURRENT TEXT:\n{chunk}"
        else:
            user_content = f"CHAPTER: {chapter_name}\n\nTEXT:\n{chunk}"
        
        # Apply name mappings
        if name_mapping_system:
            user_content = name_mapping_system.apply_mappings(user_content)
        
        chunk_start = time.time()
        
        try:
            # Direct translation - no timeout, wait until complete
            raw_translation = translate_chunk(stage1_translator, user_content, system_prompt)
            
            # Stage 2: Rewrite if two-stage mode
            if two_stage and rewriter:
                print(f"\n    [{i}/{len(chunks)}] Rewriting...", end=" ", flush=True)
                try:
                    translated_text = rewriter.rewrite(raw_translation)
                    print(f"✓ ({len(translated_text)} chars)")
                except Exception as e:
                    logger.warning(f"Rewrite failed, using raw translation: {e}")
                    translated_text = raw_translation
            else:
                translated_text = raw_translation
            
            previous_translation = translated_text
            translated_chunks[i] = translated_text
            # Update global state for emergency save
            _current_translation_state["translated_chunks"] = translated_chunks.copy()
            chunk_time = time.time() - chunk_start
            print(f"✓ Done ({chunk_time:.1f}s) — {len(translated_text)} chars")
            
            # Save intermediate result after each chunk
            if len(translated_chunks) > 0:
                partial_file = save_partial_translation(
                    book_id, chapter_name, translated_chunks, len(chunks), is_final=False
                )
                if partial_file:
                    print(f"    💾 Saved partial: {partial_file.name}")
                    
        except Exception as e:
            chunk_time = time.time() - chunk_start
            logger.error(f"Chunk {i} failed: {e}")
            print(f"✗ Failed: {str(e)[:50]}")
            failed_chunks.append(i)
            continue
    
    translate_time = time.time() - start_time
    
    # 6. Postprocess
    print(f"\n[6/7] Postprocessing...")
    sorted_indices = sorted(translated_chunks.keys())
    available_chunks = [translated_chunks[i] for i in sorted_indices]
    
    if not available_chunks:
        print("✗ No chunks translated successfully")
        return False
    
    full_text = '\n\n'.join(available_chunks)
    
    print(f"\n[6.5/7] Applying translation fixes...")
    try:
        from scripts.fix_translation import postprocess_translation
        processed_text = postprocess_translation(full_text, novel_name=book_id)
        print(f"✓ Fixes applied")
    except Exception as e:
        logger.error(f"Fixes failed: {e}")
        processed_text = full_text
    
    # 7. Assemble and save final (or partial) result
    print(f"\n[7/7] Assembling and saving...")
    try:
        book_dir = Path(BOOKS_DIR) / book_id
        book_dir.mkdir(parents=True, exist_ok=True)
        chapters_dir = book_dir / "chapters"
        chapters_dir.mkdir(parents=True, exist_ok=True)
        
        # Determine if we have all chunks
        is_complete = len(translated_chunks) == len(chunks) and len(failed_chunks) == 0
        
        if is_complete and not shutdown_requested:
            # Final complete translation
            output_file = chapters_dir / f"{chapter_name}_myanmar.md"
            
            # Remove partial file if it exists
            partial_file = chapters_dir / f"{chapter_name}_myanmar_PARTIAL.md"
            if partial_file.exists():
                partial_file.unlink()
            
            assemble(
                original_title=chapter_name,
                chapter_number=1,
                model_name=stage1_translator.name,
                translated_content=processed_text,
                output_path=str(output_file),
                book_id=book_id
            )
            print(f"✓ Saved complete translation: {output_file}")
        else:
            # Partial translation - save with progress info
            output_file = save_partial_translation(
                book_id, chapter_name, translated_chunks, len(chunks), is_final=False
            )
            if output_file:
                print(f"✓ Saved partial translation: {output_file}")
                print(f"  ⚠️  {len(failed_chunks)} chunk(s) failed: {failed_chunks}")
                print(f"  📖 You can view partial results and re-run to complete missing chunks")
    except Exception as e:
        logger.error(f"Assembly failed: {e}")
        # Try to save raw text as fallback
        try:
            fallback_file = chapters_dir / f"{chapter_name}_myanmar_FALLBACK.txt"
            with open(fallback_file, 'w', encoding='utf-8') as f:
                f.write(processed_text)
            print(f"✓ Saved fallback file: {fallback_file}")
        except Exception as e2:
            print(f"✗ Failed to save fallback: {e2}")
            return False
    
    # Update resources
    if name_mapping_system and auto_learn:
        try:
            learned = name_mapping_system.learn_from_parallel(clean_text, processed_text, chapter_num)
            if learned["new_mappings"]:
                print(f"  ✓ Learned {len(learned['new_mappings'])} new mappings")
            name_mapping_system.save()
        except:
            pass
    
    if glossary:
        try:
            glossary.metadata["chapter_count"] = glossary.metadata.get("chapter_count", 0) + 1
            glossary.save()
        except:
            pass
    
    try:
        context_manager.analyze_chapter_content(chapter_num, clean_text, processed_text)
        context_manager.update_chapter_translation(chapter_num, f"Translated {len(processed_text)} chars")
        context_manager.save()
    except:
        pass
    
    # Print summary
    print("\n" + "=" * 60)
    is_complete = len(translated_chunks) == len(chunks) and len(failed_chunks) == 0
    
    if is_complete and not shutdown_requested:
        print("╔═════════════════════════════════════════╗")
        print("║      ✅ Translation Complete!           ║")
        print(f"║ Chapter   : {chapter_name[:35]:<35} ║")
        print(f"║ Book ID   : {book_id[:35]:<35} ║")
        print(f"║ Model     : {stage1_translator.name[:35]:<35} ║")
        print(f"║ Chunks    : {len(available_chunks)}/{len(chunks):<25} ║")
        print(f"║ Time      : {translate_time/60:.1f}m{' '*30}║")
        print("╚═════════════════════════════════════════╝")
    else:
        print("╔═════════════════════════════════════════╗")
        print("║    ⚠️  PARTIAL Translation Saved        ║")
        print(f"║ Chapter   : {chapter_name[:35]:<35} ║")
        print(f"║ Book ID   : {book_id[:35]:<35} ║")
        print(f"║ Model     : {stage1_translator.name[:35]:<35} ║")
        print(f"║ Chunks    : {len(available_chunks)}/{len(chunks):<25} ║")
        if failed_chunks:
            print(f"║ Failed    : {str(failed_chunks)[:35]:<35} ║")
        print(f"║ Time      : {translate_time/60:.1f}m{' '*30}║")
        print("║                                         ║")
        print("║  📁 Check books/{0:25} ║".format(f"{book_id}/chapters/"))
        print("║  🔄 Re-run to complete missing chunks   ║")
        print("╚═════════════════════════════════════════╝")
    print("=" * 60)
    
    return len(translated_chunks) > 0


def main():
    parser = argparse.ArgumentParser(
        description="Local Ollama Novel Translator (No Rate Limits)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python local_main.py input_novels/chapter_001.md
  python local_main.py --novel dao-equaling-the-heavens
  python local_main.py --max-chars 1500
        """
    )
    
    parser.add_argument("file", nargs="?", help="Single file to translate")
    parser.add_argument("--novel", help="Translate a specific novel")
    parser.add_argument("--source-lang", default="Chinese", choices=["Chinese", "Chinese_Simplified", "Chinese_Traditional", "English"])
    parser.add_argument("--max-chars", type=int, default=DEFAULT_CHUNK_SIZE, help=f"Max chars per chunk (default: {DEFAULT_CHUNK_SIZE})")
    parser.add_argument("--overlap-chars", type=int, default=DEFAULT_OVERLAP_SIZE, help=f"Overlap chars (default: {DEFAULT_OVERLAP_SIZE})")
    parser.add_argument("--no-auto-learn", action="store_true", help="Disable auto name learning")
    
    args = parser.parse_args()
    
    from dotenv import load_dotenv
    load_dotenv()
    
    # Validate Ollama is available
    try:
        stage1_translator = get_translator("ollama")
        print(f"✓ Ollama ready: {stage1_translator.name}")
    except Exception as e:
        print(f"✗ Ollama not available: {e}")
        print("\nTo use local_main.py:")
        print("1. Install Ollama: https://ollama.ai")
        print("2. Pull a model: ollama pull qwen2.5:14b")
        print("3. Start Ollama: ollama serve")
        print("\nOr use cloud_main.py for API-based translation")
        return
    
    # Discover files
    files = []
    if args.file:
        files.append((Path(args.file), args.file.parent.name if Path(args.file).parent.name != INPUT_DIR else Path(args.file).stem, 1, args.source_lang))
    elif args.novel:
        # Scan for novel
        base_dir = Path(ENGLISH_CHAPTERS_DIR)
        if not base_dir.exists():
            base_dir = Path(CHINESE_CHAPTERS_DIR)
        novel_dir = base_dir / args.novel
        if novel_dir.exists():
            for f in sorted(novel_dir.glob("*.md")):
                match = re.search(r'chapter_(\d+)', f.name)
                ch_num = int(match.group(1)) if match else 1
                files.append((f, args.novel, ch_num, args.source_lang))
    else:
        # Auto-scan input_novels
        input_dir = Path(INPUT_DIR)
        if input_dir.exists():
            for f in sorted(input_dir.glob("*.md")) + sorted(input_dir.glob("*.txt")):
                files.append((f, f.stem, 1, args.source_lang))
    
    if not files:
        print("No files found to translate")
        print(f"Add files to {INPUT_DIR}/ or use --novel")
        return
    
    print(f"\nFound {len(files)} file(s) to process")
    print("=" * 60)
    
    # Process files
    success_count = 0
    for filepath, book_id, chapter_num, source_lang in files:
        if translate_single_file_local(
            filepath=str(filepath),
            max_chars=args.max_chars,
            overlap_chars=args.overlap_chars,
            source_lang=source_lang,
            book_id=book_id,
            chapter_num=chapter_num,
            auto_learn=not args.no_auto_learn
        ):
            success_count += 1
        print()
    
    print("=" * 60)
    print(f"Completed: {success_count}/{len(files)} files translated successfully")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n" + "=" * 60)
        print("⚠️  Program interrupted by user (Ctrl+C)")
        print("=" * 60)
        # Partial translations should have been saved by signal handler
        print("\n💾 Any completed chunks have been saved to:")
        print("   books/{book_id}/chapters/{chapter_name}_myanmar_PARTIAL.md")
        print("\nYou can re-run the command to continue translation.")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n✗ Fatal error: {e}")
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
