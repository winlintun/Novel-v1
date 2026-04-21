#!/usr/bin/env python3
"""
Main Orchestrator - Chinese → Myanmar Novel Translator
"""

import os
import sys
import time
import random
import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import Callable, TypeVar, Optional
from functools import wraps

# Define generic type variable for retry decorator
T = TypeVar('T')

# Import our modules from scripts folder
from scripts.preprocessor import preprocess
from scripts.chunker import auto_chunk, split_into_paragraphs, print_chunk_analysis
from scripts.translator import get_translator, get_system_prompt, BaseTranslator
from scripts.postprocessor import postprocess
from scripts.assembler import assemble

# =============================================================================
# CONSTANTS
# =============================================================================

# Chunking constants
DEFAULT_CHUNK_SIZE = 1000
DEFAULT_OVERLAP_SIZE = 100
MAX_CHUNK_SIZE = 5000
MIN_CHUNK_SIZE = 100

# Retry constants
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 1.0  # seconds
MAX_RETRY_DELAY = 60.0  # seconds
BACKOFF_FACTOR = 2.0
JITTER_FACTOR = 0.1

# Translation constants
DEFAULT_REQUEST_DELAY = 1.0  # seconds between chunks
SAMPLE_SIZE_FOR_READABILITY = 2000  # characters
MAX_READABILITY_REPORT_ITEMS = 10

# Logging constants
LOG_DIR = "working_data/logs"
BOOKS_DIR = "books"
INPUT_DIR = "input_novels"

# =============================================================================
# SETUP LOGGING
# =============================================================================

os.makedirs(LOG_DIR, exist_ok=True)
log_file = f"{LOG_DIR}/translation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# =============================================================================
# RETRY LOGIC
# =============================================================================

class RetryExhaustedError(Exception):
    """Raised when all retry attempts have been exhausted."""
    pass


def exponential_backoff_retry(
    max_retries: int = MAX_RETRIES,
    initial_delay: float = INITIAL_RETRY_DELAY,
    max_delay: float = MAX_RETRY_DELAY,
    backoff_factor: float = BACKOFF_FACTOR,
    jitter: float = JITTER_FACTOR,
    exceptions: tuple = (Exception,)
) -> Callable:
    """Decorator for exponential backoff retry logic.
    
    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay between retries (seconds)
        max_delay: Maximum delay between retries (seconds)
        backoff_factor: Multiplier for delay between retries
        jitter: Random jitter factor (0-1) to add to delay
        exceptions: Tuple of exception types to catch and retry
        
    Returns:
        Decorated function with retry logic
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_retries:
                        logger.error(
                            f"Function {func.__name__} failed after {max_retries + 1} attempts. "
                            f"Last error: {e}"
                        )
                        raise RetryExhaustedError(
                            f"Failed after {max_retries + 1} attempts: {e}"
                        ) from e
                    
                    # Calculate delay with jitter
                    jitter_amount = delay * jitter * (2 * random.random() - 1)
                    actual_delay = min(delay + jitter_amount, max_delay)
                    
                    logger.warning(
                        f"Attempt {attempt + 1}/{max_retries + 1} for {func.__name__} failed: {e}. "
                        f"Retrying in {actual_delay:.1f}s..."
                    )
                    time.sleep(actual_delay)
                    delay = min(delay * backoff_factor, max_delay)
            
            # Should never reach here
            raise RetryExhaustedError("Unexpected exit from retry loop")
        
        return wrapper
    return decorator


def retry_translate_chunk(
    translator: BaseTranslator,
    chunk: str,
    system_prompt: str,
    max_retries: int = MAX_RETRIES
) -> str:
    """Translate a chunk with exponential backoff retry (batch mode).
    
    Args:
        translator: Translator instance
        chunk: Text chunk to translate
        system_prompt: System prompt for translation
        max_retries: Maximum retry attempts
        
    Returns:
        Translated text
        
    Raises:
        RetryExhaustedError: If all retries fail
    """
    delay = INITIAL_RETRY_DELAY
    last_error = None
    
    for attempt in range(max_retries + 1):
        try:
            # Use batch translate instead of streaming
            return translator.translate(chunk, system_prompt)
        except Exception as e:
            last_error = e
            if attempt == max_retries:
                logger.error(
                    f"Translation failed after {max_retries + 1} attempts for chunk. "
                    f"Last error: {e}"
                )
                raise RetryExhaustedError(
                    f"Failed to translate chunk after {max_retries + 1} attempts: {e}"
                ) from e
            
            # Calculate delay with jitter
            jitter_amount = delay * JITTER_FACTOR * (2 * random.random() - 1)
            actual_delay = min(delay + jitter_amount, MAX_RETRY_DELAY)
            
            logger.warning(
                f"Translation attempt {attempt + 1}/{max_retries + 1} failed: {e}. "
                f"Retrying in {actual_delay:.1f}s..."
            )
            time.sleep(actual_delay)
            delay = min(delay * BACKOFF_FACTOR, MAX_RETRY_DELAY)
    
    raise RetryExhaustedError("Unexpected exit from retry loop")


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _preprocess_file(filepath: Path) -> str:
    """Preprocess a file and return clean text.
    
    Args:
        filepath: Path to the input file
        
    Returns:
        Clean preprocessed text
        
    Raises:
        Exception: If preprocessing fails
    """
    logger.info(f"Preprocessing file: {filepath}")
    try:
        clean_text = preprocess(str(filepath))
        logger.info(f"Preprocessing complete: {len(clean_text)} characters")
        return clean_text
    except Exception as e:
        logger.error(f"Preprocessing failed: {e}")
        raise


def _chunk_text(clean_text: str, max_chars: int, overlap_chars: int) -> tuple:
    """Split text into chunks.
    
    Args:
        clean_text: Preprocessed text
        max_chars: Maximum characters per chunk
        
    Returns:
        Tuple of (paragraphs, chunks)
    """
    logger.info("Chunking text...")
    paragraphs = split_into_paragraphs(clean_text)
    chunks = auto_chunk(clean_text, max_chars, overlap_chars=overlap_chars)
    logger.info(f"Created {len(chunks)} chunks from {len(paragraphs)} paragraphs")
    return paragraphs, chunks


def _load_translator_with_retry(model_name: str) -> BaseTranslator:
    """Load translator with retry logic.
    
    Args:
        model_name: Name of the translation model
        
    Returns:
        Translator instance
        
    Raises:
        ValueError: If translator cannot be loaded
    """
    @exponential_backoff_retry(
        max_retries=2,
        initial_delay=0.5,
        exceptions=(ValueError, ConnectionError)
    )
    def _load():
        return get_translator(model_name)
    
    return _load()


def _translate_single_chunk(
    chunk: str,
    chunk_index: int,
    total_chunks: int,
    translator: BaseTranslator,
    system_prompt: str,
    previous_translation: Optional[str] = None
) -> Optional[str]:
    """Translate a single chunk with context retention.

    Args:
        chunk: Text chunk to translate
        chunk_index: Index of the current chunk (1-based)
        total_chunks: Total number of chunks
        translator: Translator instance
        system_prompt: System prompt for translation
        previous_translation: Previous chunk's translation for context (sliding window)

    Returns:
        Translated text or None if translation failed
    """
    logger.info(
        f"Translating chunk {chunk_index}/{total_chunks}: "
        f"{len(chunk)} chars using {translator.name}"
    )

    # Check if this is NLLB translator (doesn't need context prompts)
    is_nllb = "nllb" in translator.name.lower()

    # Build contextualized prompt with previous translation for consistency
    user_content = chunk
    if previous_translation and chunk_index > 1 and not is_nllb:
        # Context retention: Provide previous translation as context
        # This maintains consistency in dialogue, character names, and plot flow
        # Only for LLM-based translators (not NLLB)
        context_preview = previous_translation[-1200:] if len(previous_translation) > 1200 else previous_translation
        user_content = f"""PREVIOUS CONTEXT (for consistency):
{context_preview}

---

CURRENT TEXT TO TRANSLATE:
{chunk}"""

    try:
        translated_text = retry_translate_chunk(translator, user_content, system_prompt)
        logger.info(f"Chunk {chunk_index} translated: {len(translated_text)} characters")
        return translated_text
    except RetryExhaustedError as e:
        logger.error(f"Chunk {chunk_index} translation failed after all retries: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error translating chunk {chunk_index}: {e}")
        return None


def _apply_delay_between_chunks(current_index: int, total_chunks: int, model_name: str = "") -> None:
    """Apply delay between chunks based on environment settings and model type."""
    if current_index < total_chunks:
        # No delay needed for local Ollama models
        if "ollama" in model_name.lower():
            return
            
        delay = float(os.getenv("REQUEST_DELAY", str(DEFAULT_REQUEST_DELAY)))
        if delay > 0:
            logger.debug(f"Waiting {delay}s before next chunk...")
            time.sleep(delay)


def translate_single_file(
    filepath: str,
    model_name: str,
    max_chars: int,
    overlap_chars: int,
    do_readability: bool,
    names_path: str,
    source_lang: str = "Chinese"
) -> bool:
    """
    Translate a single file through the complete pipeline.
    
    Returns True on success, False on failure.
    """
    filepath = Path(filepath)
    chapter_name = filepath.stem
    
    print("=" * 60)
    print(f"Translating: {chapter_name}")
    print("=" * 60)
    
    # 1. Preprocess
    print("\n[1/6] Preprocessing...")
    try:
        clean_text = _preprocess_file(filepath)
        print(f"✓ Preprocessed: {len(clean_text)} characters")
    except Exception as e:
        logger.error(f"Preprocessing failed: {e}")
        print(f"✗ Preprocessing failed: {e}")
        return False
    
    # 2. Chunk
    print("\n[2/6] Chunking...")
    try:
        paragraphs, chunks = _chunk_text(clean_text, max_chars, overlap_chars)
        print_chunk_analysis(chunks, paragraphs)
    except Exception as e:
        logger.error(f"Chunking failed: {e}")
        print(f"✗ Chunking failed: {e}")
        return False
    
    # 3. Load translator with retry
    print(f"\n[3/6] Loading translator: {model_name}")
    try:
        translator = _load_translator_with_retry(model_name)
        print(f"✓ Loaded: {translator.name}")
    except ValueError as e:
        logger.error(f"Failed to load translator: {e}")
        print(f"✗ {e}")
        print("\nTo fix this:")
        print("1. Edit .env file with your API key")
        print("2. Or use Ollama locally: python main.py --model ollama")
        return False
    except RetryExhaustedError as e:
        logger.error(f"Failed to load translator after retries: {e}")
        print(f"✗ Failed to load translator after retries: {e}")
        return False
    
    system_prompt = get_system_prompt(source_lang=source_lang)

    # 5. Translate chunks
    print(f"\n[4/6] Translating {len(chunks)} chunks...")
    print("-" * 60)
    
    start_time = time.time()
    previous_translation = None
    translated_chunks = {}  # Store translated chunks in memory
    
    for i, chunk in enumerate(chunks, 1):
        result = _translate_single_chunk(
            chunk=chunk,
            chunk_index=i,
            total_chunks=len(chunks),
            translator=translator,
            system_prompt=system_prompt,
            previous_translation=previous_translation
        )
        
        # Update previous translation for context retention (sliding window)
        if result is not None:
            previous_translation = result
            translated_chunks[i] = result
            print(f"\n[{i}/{len(chunks)}] ✓ Done — {len(result)} Myanmar chars")
        else:
            print(f"\n[{i}/{len(chunks)}] ✗ Translation failed — continuing to next chunk")
        
        # Apply delay between chunks
        _apply_delay_between_chunks(i, len(chunks), model_name=translator.name)
    
    translate_time = time.time() - start_time

    # 6. Postprocess
    print(f"\n[5/6] Postprocessing...")
    
    # Combine all translated chunks, handling potential gaps from failed translations
    # Sort by chunk index and filter out any None values
    sorted_indices = sorted(translated_chunks.keys())
    available_chunks = [translated_chunks[i] for i in sorted_indices if translated_chunks[i] is not None]
    
    # Warn if there are gaps in the translation
    expected_indices = set(range(1, len(chunks) + 1))
    actual_indices = set(translated_chunks.keys())
    missing_indices = expected_indices - actual_indices
    
    if missing_indices:
        missing_list = sorted(missing_indices)
        logger.warning(f"Missing translations for chunk(s): {missing_list}")
        print(f"⚠ Warning: {len(missing_list)} chunk(s) failed to translate and will be skipped")
    
    if not available_chunks:
        logger.error(f"All translation chunks failed for {chapter_name}")
        print(f"\n✗ Translation failed: No chunks were successfully translated")
        return False
    
    full_text = '\n\n'.join(available_chunks)
    processed_text = full_text  # Default to unprocessed if postprocess fails
    
    try:
        # Postprocess
        processed_text = postprocess(full_text, names_path)
    except Exception as e:
        logger.error(f"Postprocessing failed: {e}")
        print(f"✗ Postprocessing failed: {e}")
        print(f"  Using unprocessed text for assembly.")
    
    # 7. Assemble
    print(f"\n[6/6] Assembling...")
    try:
        # Determine book ID (use input file's parent dir name or "default")
        book_id = filepath.parent.name if filepath.parent.name != INPUT_DIR else chapter_name
        book_dir = Path(BOOKS_DIR) / book_id
        book_dir.mkdir(parents=True, exist_ok=True)
        chapters_dir = book_dir / "chapters"
        chapters_dir.mkdir(parents=True, exist_ok=True)
        
        output_file = chapters_dir / f"{chapter_name}_myanmar.md"
        
        assemble(
            original_title=chapter_name,
            chapter_number=1, # Default to 1 for single file mode
            model_name=translator.name,
            translated_content=processed_text,
            output_path=str(output_file),
            book_id=book_id
        )
        
    except Exception as e:
        logger.error(f"Assembly failed: {e}")
        print(f"✗ Assembly failed: {e}")
        return False
    
    # 8. Readability check (optional) - shown as step 7 in output
    if do_readability:
        print(f"\n[7] Readability check...")
        try:
            run_readability_check(processed_text, chapter_name, model_name)
        except Exception as e:
            logger.error(f"Readability check failed: {e}")
            print(f"⚠ Readability check failed: {e}")
    
    # Print completion summary
    print("\n" + "=" * 60)
    print("╔═════════════════════════════════════════╗")
    print("║         Translation Complete!           ║")
    print(f"║ Chapter   : {chapter_name[:35]:<35} ║")
    print(f"║ Model     : {translator.name[:35]:<35} ║")
    print(f"║ Chunks    : {len(chunks)} / {len(chunks):<25} ║")
    print(f"║ Time      : {translate_time/60:.1f}m{' ' * 30}║")
    print(f"║ Output    : {BOOKS_DIR}/{book_id}/chapters/ ║")
    print(f"║             {chapter_name[:30]}_myanmar.md ║")
    print("╚═════════════════════════════════════════╝")
    print("=" * 60)
    
    return True


def run_readability_check(text: str, chapter_name: str, model_name: str) -> None:
    """Run LLM readability check once after assembly.
    
    Args:
        text: Full translated text to check
        chapter_name: Name of the chapter for report file
        model_name: Name of the model to use for readability check
    """
    from scripts.translator import get_translator
    
    logger.info(f"Running readability check for {chapter_name}")
    
    # Use same model for readability check as was used for translation
    model = model_name
    
    try:
        translator = _load_translator_with_retry(model)
    except Exception as e:
        logger.error(f"Failed to load translator for readability check: {e}")
        print(f"⚠ Could not load translator for readability check: {e}")
        return
    
    # Sample first N chars for readability check
    sample = text[:SAMPLE_SIZE_FOR_READABILITY]
    
    prompt = f"""Review this Myanmar translation excerpt and list:
1. Unnatural sentence flow
2. Missing Myanmar particles (တဲ့၊ပဲ၊တော့)
3. Repeated awkward phrasing
Return max {MAX_READABILITY_REPORT_ITEMS} bullet points only. Be concise.

Text:
{sample}"""
    
    print("⚠ Readability Report:")
    
    # Get response (non-streaming for readability)
    system_prompt = "You are a Myanmar language editor."
    
    try:
        # Use retry logic for readability check
        report_text = retry_translate_chunk(translator, prompt, system_prompt, max_retries=2)
        print(report_text)
        
        # Save report
        report_file = f"{LOG_DIR}/{chapter_name}_readability.txt"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report_text)
        print(f"\n✓ Report saved: {report_file}")
        logger.info(f"Readability report saved: {report_file}")
        
    except RetryExhaustedError as e:
        logger.error(f"Readability check failed after retries: {e}")
        print(f"⚠ Could not generate report after retries: {e}")
    except Exception as e:
        logger.error(f"Error in readability check: {e}")
        print(f"⚠ Could not generate report: {e}")


def scan_input_novels() -> list:
    """Scan input_novels/ for .txt and .md files.
    
    Returns:
        List of Path objects for found files
    """
    input_dir = Path(INPUT_DIR)
    
    if not input_dir.exists():
        logger.info(f"Creating {INPUT_DIR}/ directory")
        print(f"No {INPUT_DIR}/ directory found. Creating...")
        input_dir.mkdir(parents=True, exist_ok=True)
        return []
    
    # Support both .txt and .md files
    txt_files = list(input_dir.glob("*.txt"))
    md_files = list(input_dir.glob("*.md"))
    all_files = txt_files + md_files
    
    logger.info(f"Found {len(all_files)} file(s) in {INPUT_DIR}/")
    return sorted(all_files)


def main() -> None:
    """Main entry point for the translator CLI."""
    parser = argparse.ArgumentParser(
        description="Chinese/English → Myanmar Novel Translator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Examples:
  # Auto-scan and translate all files
  python main.py

  # Single file
  python main.py {INPUT_DIR}/chapter_001.txt

  # Switch model
  python main.py --model openrouter
  python main.py --model gemini
  python main.py --model ollama
  python main.py --model nllb

  # Source language options
  python main.py --source-lang Chinese
  python main.py --source-lang English

  # Chunking options
  python main.py --max-chars {DEFAULT_CHUNK_SIZE}

  # Skip readability check
  python main.py --no-readability
        """
    )

    parser.add_argument("file", nargs="?", help="Single file to translate")
    parser.add_argument("--model", default=None,
                        choices=["openrouter", "gemini", "ollama", "nllb", "nllb200"],
                        help="Translation model to use (overrides .env AI_MODEL)")
    parser.add_argument("--source-lang", default=None,
                        choices=["Chinese", "Chinese_Simplified", "Chinese_Traditional", "English"],
                        help="Source language (overrides .env SOURCE_LANGUAGE)")
    parser.add_argument("--max-chars", type=int, default=DEFAULT_CHUNK_SIZE,
                        help=f"Maximum characters per chunk (default: {DEFAULT_CHUNK_SIZE})")
    parser.add_argument("--overlap-chars", type=int, default=DEFAULT_OVERLAP_SIZE,
                        help=f"Overlap characters between chunks (default: {DEFAULT_OVERLAP_SIZE})")
    parser.add_argument("--no-readability", action="store_true",
                        help="Skip readability check")
    parser.add_argument("--names", default="names.json",
                        help="Character names mapping file")

    args = parser.parse_args()
    
    # Load environment
    from dotenv import load_dotenv
    load_dotenv()
    
    # Load config
    import json
    config = {}
    config_path = Path("config/config.json")
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

    # Priority: --model CLI arg > AI_MODEL env var > config.ai_backend > default (openrouter)
    if args.model is not None:
        model = args.model
    else:
        model = os.getenv("AI_MODEL", config.get("ai_backend", "openrouter"))

    # Source language: CLI arg > env var > config > default (Chinese)
    if args.source_lang is not None:
        source_lang = args.source_lang.replace("_", " ")
    else:
        source_lang = os.getenv("SOURCE_LANGUAGE", config.get("source_language", "Chinese"))

    # Validate chunk size
    if not MIN_CHUNK_SIZE <= args.max_chars <= MAX_CHUNK_SIZE:
        logger.warning(
            f"Chunk size {args.max_chars} outside recommended range "
            f"[{MIN_CHUNK_SIZE}, {MAX_CHUNK_SIZE}]. Using closest valid value."
        )
        args.max_chars = max(MIN_CHUNK_SIZE, min(args.max_chars, MAX_CHUNK_SIZE))

    logger.info("=" * 60)
    logger.info(f"{source_lang} → Myanmar Novel Translator Started")
    logger.info(f"Model: {model}, Chunk size: {args.max_chars}, Overlap size: {args.overlap_chars}")
    logger.info("=" * 60)

    print("=" * 60)
    print(f"{source_lang} → Myanmar Novel Translator")
    print("=" * 60)
    print(f"Model: {model}")
    print(f"Source: {source_lang}")
    print(f"Max chars per chunk: {args.max_chars}")
    print(f"Overlap chars: {args.overlap_chars}")
    print("=" * 60)
    print()
    
    # Determine files to process
    if args.file:
        files = [Path(args.file)]
        logger.info(f"Processing single file: {args.file}")
    else:
        files = scan_input_novels()
        if not files:
            logger.warning(f"No files found in {INPUT_DIR}/")
            print(f"No .txt or .md files found in {INPUT_DIR}/")
            print("Add files and run again.")
            return
        logger.info(f"Found {len(files)} file(s) to process")
        print(f"Found {len(files)} file(s) to translate:\n")
        for f in files:
            print(f"  - {f.name}")
        print()
    
    # Process each file
    success_count = 0
    fail_count = 0
    
    for filepath in files:
        logger.info(f"Processing file: {filepath}")
        success = translate_single_file(
            filepath=str(filepath),
            model_name=model,
            max_chars=args.max_chars,
            overlap_chars=args.overlap_chars,
            do_readability=not args.no_readability,
            names_path=args.names,
            source_lang=source_lang
        )
        
        if success:
            success_count += 1
            logger.info(f"Successfully translated: {filepath}")
        else:
            fail_count += 1
            logger.error(f"Failed to translate: {filepath}")
        
        print()
    
    # Summary
    logger.info("=" * 60)
    logger.info("Translation Summary")
    logger.info(f"Total: {len(files)}, Success: {success_count}, Failed: {fail_count}")
    logger.info("=" * 60)
    
    print("=" * 60)
    print("Translation Summary")
    print("=" * 60)
    print(f"Total files: {len(files)}")
    print(f"Successful:  {success_count}")
    print(f"Failed:      {fail_count}")
    print("=" * 60)


if __name__ == "__main__":
    main()
