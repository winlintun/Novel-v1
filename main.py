#!/usr/bin/env python3
"""
Main Orchestrator - Chinese → Myanmar Novel Translator
"""

import os
import re
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
from scripts.translator import get_translator, get_system_prompt, BaseTranslator, apply_name_mapping
from scripts.postprocessor import postprocess
from scripts.assembler import assemble
from scripts.glossary_manager import GlossaryManager
from scripts.rewriter import BurmeseRewriter, get_raw_translation_prompt
from scripts.context_manager import ContextManager
from scripts.name_converter import NameConverter

# =============================================================================
# CONSTANTS
# =============================================================================

# Chunking constants
DEFAULT_CHUNK_SIZE = 1000
DEFAULT_OVERLAP_SIZE = 0
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

# Source directories for novel chapters
ENGLISH_CHAPTERS_DIR = "english_chapters"
CHINESE_CHAPTERS_DIR = "chinese_chapters"

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
            error_str = str(e).lower()
            
            # Check if it's a rate limit error (429)
            is_rate_limit = "429" in error_str or "rate limit" in error_str or "too many requests" in error_str
            
            if attempt == max_retries:
                logger.error(
                    f"Translation failed after {max_retries + 1} attempts for chunk. "
                    f"Last error: {e}"
                )
                
                # Provide specific message for rate limiting
                if is_rate_limit:
                    # Check if it's OpenRouter
                    is_openrouter = "openrouter" in str(translator).lower() or "openrouter" in str(last_error).lower()
                    
                    if is_openrouter:
                        raise RetryExhaustedError(
                            f"❌ OpenRouter Rate Limit Exceeded (429)\n\n"
                            f"You've hit the free tier limits:\n"
                            f"- 20 requests per minute (RPM)\n"
                            f"- 200 requests per DAY (daily limit)\n\n"
                            f"💡 SOLUTIONS (pick one):\n\n"
                            f"1. ✅ RECOMMENDED: Use local Ollama (no limits):\n"
                            f"   python main.py input_novels/chapter_001.md --model ollama\n\n"
                            f"2. Wait until tomorrow (daily quota resets)\n\n"
                            f"3. Add credits to OpenRouter for paid tier\n\n"
                            f"4. Try Gemini instead (different limits):\n"
                            f"   python main.py input_novels/chapter_001.md --model gemini"
                        ) from e
                    else:
                        raise RetryExhaustedError(
                            f"❌ Gemini Rate Limit Exceeded (429)\n\n"
                            f"Google Gemini free tier has strict limits:\n"
                            f"- 15 requests per minute (RPM)\n"
                            f"- 1 million tokens per minute (TPM)\n\n"
                            f"💡 SOLUTIONS (pick one):\n\n"
                            f"1. ✅ RECOMMENDED: Use local Ollama (no limits):\n"
                            f"   python main.py input_novels/chapter_001.md --model ollama\n\n"
                            f"2. Wait 1-2 minutes and try again\n\n"
                            f"3. Use OpenRouter instead: --model openrouter\n\n"
                            f"4. Upgrade to Gemini paid tier"
                        ) from e
                
                raise RetryExhaustedError(
                    f"Failed to translate chunk after {max_retries + 1} attempts: {e}"
                ) from e
            
            # For rate limit errors, use longer delays
            if is_rate_limit:
                # Check if it's OpenRouter
                is_openrouter = "openrouter" in str(translator).lower() or "openrouter" in str(last_error).lower()
                
                if is_openrouter:
                    # OpenRouter free tier: 20 RPM = 1 per 3 seconds, 200/day total
                    delay = max(delay, 5.0)  # 5 seconds for OpenRouter
                    logger.warning(
                        f"⚠️  OpenRouter rate limit (429) on attempt {attempt + 1}/{max_retries + 1}.\n"
                        f"   Free tier limits: 20 requests/minute, 200 requests/day\n"
                        f"   Waiting {delay:.1f}s before retry...\n"
                        f"   💡 Tip: Use local Ollama model to avoid API limits entirely:\n"
                        f"      python main.py input_novels/chapter_001.md --model ollama"
                    )
                else:
                    # Gemini free tier: 15 RPM = 1 per 4 seconds
                    delay = max(delay, 4.0)
                    logger.warning(
                        f"Rate limit hit (429) on attempt {attempt + 1}/{max_retries + 1}. "
                        f"Waiting {delay:.1f}s before retry...\n"
                        f"Tip: Set REQUEST_DELAY=4.0 in .env to avoid rate limits"
                    )
            else:
                # Calculate delay with jitter for other errors
                jitter_amount = delay * JITTER_FACTOR * (2 * random.random() - 1)
                delay = min(delay + jitter_amount, MAX_RETRY_DELAY)
                logger.warning(
                    f"Translation attempt {attempt + 1}/{max_retries + 1} failed: {e}. "
                    f"Retrying in {delay:.1f}s..."
                )
            
            time.sleep(delay)
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
    chapter_name: str = "",
    previous_translation: Optional[str] = None,
    use_two_stage: bool = False,
    rewriter: Optional[BurmeseRewriter] = None,
    glossary_manager = None,
    stage1_translator: Optional[BaseTranslator] = None
) -> Optional[str]:
    """Translate a single chunk with context retention.

    Args:
        chunk: Text chunk to translate
        chunk_index: Index of the current chunk (1-based)
        total_chunks: Total number of chunks
        translator: Translator instance (for single-stage or stage 2)
        system_prompt: System prompt for translation
        chapter_name: Name of the current chapter
        previous_translation: Previous chunk's translation for context (sliding window)
        use_two_stage: Whether to use two-stage translation (raw + rewrite)
        rewriter: BurmeseRewriter instance for stage 2 (required if use_two_stage=True)
        glossary_manager: GlossaryManager for name consistency in stage 1
        stage1_translator: Optional separate translator for stage 1 (e.g., Gemini)

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

CURRENT TEXT TO TRANSLATE (from {chapter_name}):
{chunk}"""
    else:
        # First chunk - still tell it what chapter we are in
        user_content = f"CHAPTER: {chapter_name}\n\nTEXT TO TRANSLATE:\n{chunk}"

    try:
        # STAGE 1: Raw Translation
        if use_two_stage:
            logger.info(f"Chunk {chunk_index}: Stage 1 - Raw translation")
            # Get glossary text for name consistency in stage 1
            glossary_text = ""
            if glossary_manager is not None:
                try:
                    glossary_text = glossary_manager.get_glossary_text()
                except Exception as e:
                    logger.warning(f"Could not get glossary text for stage 1: {e}")
            
            raw_prompt = get_raw_translation_prompt(glossary_text=glossary_text)
            
            # Use stage1_translator if provided, otherwise fall back to translator
            raw_translator = stage1_translator if stage1_translator is not None else translator
            logger.info(f"  Using {raw_translator.name} for Stage 1")
            
            rough_translation = retry_translate_chunk(raw_translator, user_content, raw_prompt)
            logger.info(f"Chunk {chunk_index}: Raw translation complete: {len(rough_translation)} chars")
            
            # STAGE 2: Rewrite
            if rewriter is not None:
                logger.info(f"Chunk {chunk_index}: Stage 2 - Rewriting")
                context_for_rewrite = previous_translation[-500:] if previous_translation else ""
                translated_text = rewriter.rewrite(rough_translation, context=context_for_rewrite)
                logger.info(f"Chunk {chunk_index}: Rewrite complete: {len(translated_text)} chars")
            else:
                logger.warning(f"Chunk {chunk_index}: No rewriter available, using raw translation")
                translated_text = rough_translation
        else:
            # Single-stage translation
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
    if current_index >= total_chunks:
        return
        
    # No delay needed for local Ollama models
    if "ollama" in model_name.lower():
        return
    
    # For cloud APIs, use appropriate delays to avoid rate limits
    if "openrouter" in model_name.lower():
        # OpenRouter free tier: 20 RPM = 1 request per 3 seconds minimum
        default_delay = 3.5  # 3.5 seconds to stay safely under 20 RPM
    elif "gemini" in model_name.lower():
        # Gemini free tier: 15 RPM = 1 request per 4 seconds minimum
        default_delay = 4.0  # 4 seconds for Gemini to stay under 15 RPM
    else:
        default_delay = DEFAULT_REQUEST_DELAY
            
    delay = float(os.getenv("REQUEST_DELAY", str(default_delay)))
    
    # Ensure minimum delays to avoid rate limits
    if "openrouter" in model_name.lower() and delay < 3.0:
        delay = 3.5
        logger.debug(f"Enforcing minimum 3.5s delay for OpenRouter to avoid rate limits")
    elif "gemini" in model_name.lower() and delay < 4.0:
        delay = 4.0
        logger.debug(f"Enforcing minimum 4s delay for Gemini to avoid rate limits")
    
    if delay > 0:
        logger.info(f"Waiting {delay:.1f}s before next chunk...")
        time.sleep(delay)


def translate_single_file(
    filepath: str,
    model_name: str,
    max_chars: int,
    overlap_chars: int,
    do_readability: bool,
    names_path: str,
    source_lang: str = "Chinese",
    book_id: str = None,
    use_two_stage: bool = None,
    stage1_model: str = None,
    stage2_model: str = None,
    chapter_num: int = 1,
    context_manager: ContextManager = None,
    auto_learn: bool = True
) -> bool:
    """
    Translate a single file through the complete pipeline.
    
    Args:
        filepath: Path to file to translate
        model_name: Translation model to use (for single-stage or fallback)
        max_chars: Maximum characters per chunk
        overlap_chars: Overlap between chunks
        do_readability: Whether to run readability check
        names_path: Path to names JSON file
        source_lang: Source language
        book_id: Book ID for glossary (auto-detected if None)
        use_two_stage: Force two-stage mode (None = auto from config)
        stage1_model: Model for Stage 1 (raw translation) - e.g., "gemini"
        stage2_model: Model for Stage 2 (rewrite) - e.g., "ollama"
        chapter_num: Chapter number
        context_manager: ContextManager instance
        auto_learn: Whether to auto-learn names from chapter
        chapter_num: Chapter number (for context tracking)
        context_manager: ContextManager instance for context injection
    
    Returns True on success, False on failure.
    """
    filepath = Path(filepath)
    chapter_name = filepath.stem
    
    # Determine book ID for glossary management
    if book_id is None:
        if filepath.parent.name != INPUT_DIR:
            # Use parent folder name as book_id if not in input_novels
            book_id = filepath.parent.name
        else:
            # In input_novels folder - extract novel name from chapter filename
            # Pattern: <novel_name>_chapter_<number>.md or <novel_name>_chapter_<number>.txt
            match = re.match(r'^(.+?)_chapter_\d+', chapter_name, re.IGNORECASE)
            if match:
                book_id = match.group(1)
            else:
                # Fallback: use full chapter name if pattern doesn't match
                book_id = chapter_name
    
    # Initialize context manager if not provided
    if context_manager is None:
        context_manager = ContextManager(book_id, source_lang=source_lang)
    
    # Load config to check for two-stage mode
    config = {}
    try:
        config_path = Path("config/config.json")
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
    except Exception as e:
        logger.warning(f"Could not load config: {e}")
    
    # Determine two-stage mode
    if use_two_stage is None:
        pipeline_config = config.get("translation_pipeline", {})
        use_two_stage = pipeline_config.get("mode", "single_stage") == "two_stage"
    
    print("=" * 60)
    print(f"Translating: {chapter_name}")
    print(f"Book ID: {book_id}")
    if use_two_stage:
        print("Mode: Two-Stage Translation (Raw + Rewrite)")
        if stage1_model:
            print(f"  Stage 1 (Raw): {stage1_model}")
        if stage2_model:
            print(f"  Stage 2 (Rewrite): {stage2_model}")
    else:
        print("Mode: Single-Stage Translation")
    print("=" * 60)
    
    # 1. Preprocess
    print("\n[1/7] Preprocessing...")
    try:
        clean_text = _preprocess_file(filepath)
        print(f"✓ Preprocessed: {len(clean_text)} characters")
    except Exception as e:
        logger.error(f"Preprocessing failed: {e}")
        print(f"✗ Preprocessing failed: {e}")
        return False
    
    # 2. Chunk
    print("\n[2/7] Chunking...")
    try:
        paragraphs, chunks = _chunk_text(clean_text, max_chars, overlap_chars)
        print_chunk_analysis(chunks, paragraphs)
    except Exception as e:
        logger.error(f"Chunking failed: {e}")
        print(f"✗ Chunking failed: {e}")
        return False
    
    # 3. Initialize glossary and context manager for this book
    print(f"\n[3/7] Loading glossary and context for: {book_id}")
    try:
        glossary = GlossaryManager(book_id)
        print(f"✓ Glossary loaded: {len(glossary.names)} names")
        if glossary.names:
            glossary.print_summary()
    except Exception as e:
        logger.warning(f"Failed to load glossary: {e}")
        glossary = None
        print(f"⚠ Continuing without glossary")
    
    # Register chapter with context manager
    context_manager.register_chapter(chapter_num, title=chapter_name, word_count=len(clean_text))
    
    # Get context for this chapter (Characters + Story + Previous Chapters)
    context_text = context_manager.get_context_for_chapter(chapter_num)
    if context_text:
        print(f"✓ Context loaded for Chapter {chapter_num}")
        context_manager.print_summary()
    else:
        print(f"ℹ No previous context (Chapter {chapter_num})")
    
    # 4. Load translators
    # Stage 1 translator (for raw translation in two-stage mode)
    stage1_translator = None
    # Stage 2 / Single-stage translator
    translator = None
    
    # Load stage 1 translator if in two-stage mode and stage1_model specified
    if use_two_stage and stage1_model:
        print(f"\n[4/7] Loading Stage 1 translator: {stage1_model}")
        try:
            stage1_translator = _load_translator_with_retry(stage1_model)
            print(f"✓ Stage 1 loaded: {stage1_translator.name}")
        except Exception as e:
            logger.error(f"Failed to load Stage 1 translator: {e}")
            print(f"✗ Failed to load Stage 1 translator: {e}")
            print("Falling back to single-stage mode...")
            use_two_stage = False
    
    # Load main translator (for stage 2 in two-stage, or single-stage)
    # In two-stage mode, this is the stage 2 (rewrite) translator
    main_model = stage2_model if (use_two_stage and stage2_model) else model_name
    print(f"\n[4.5/7] Loading {'Stage 2' if use_two_stage else 'Main'} translator: {main_model}")
    try:
        translator = _load_translator_with_retry(main_model)
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
    
    # Get system prompt with glossary and context
    system_prompt = get_system_prompt(source_lang=source_lang, glossary_manager=glossary)
    
    # Inject context into system prompt if available
    if context_text:
        context_section = f"""

================================================================================
NOVEL CONTEXT - READ THIS CAREFULLY BEFORE TRANSLATING:
================================================================================

{context_text}

================================================================================
END OF CONTEXT
================================================================================
"""
        system_prompt = system_prompt + context_section
        logger.info(f"Injected context ({len(context_text)} chars) into system prompt")
    
    # Initialize rewriter if using two-stage mode
    # Stage 2 translator (qwen:7b via Ollama) is used for rewriting
    rewriter = None
    if use_two_stage:
        print(f"\n[4.6/7] Initializing rewriter (Stage 2)...")
        try:
            # Use the loaded translator (qwen:7b) for rewriting
            rewriter = BurmeseRewriter(main_model, glossary_manager=glossary)
            print(f"✓ Rewriter ready: {main_model}")
        except Exception as e:
            logger.warning(f"Failed to initialize rewriter: {e}")
            print(f"⚠ Failed to initialize rewriter, falling back to single-stage")
            use_two_stage = False

    # 5. Translate chunks
    print(f"\n[5/7] Translating {len(chunks)} chunks...")
    if use_two_stage:
        print("(Two-stage: Raw translation + Rewrite for each chunk)")
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
            chapter_name=chapter_name,
            previous_translation=previous_translation,
            use_two_stage=use_two_stage,
            rewriter=rewriter,
            glossary_manager=glossary,
            stage1_translator=stage1_translator
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
    print(f"\n[6/7] Postprocessing...")

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

    print(f"\n[6.5/7] Applying translation fixes (Dialogue, Emotion, Sentence Structure)...")
    try:
        # Postprocess with glossary manager for per-novel name consistency
        from scripts.fix_translation import postprocess_translation
        processed_text = postprocess_translation(processed_text, novel_name=book_id)
        print(f"✓ Translation fixes applied successfully")
    except Exception as e:
        logger.error(f"Translation fixes failed: {e}")
        print(f"✗ Translation fixes failed: {e}")
        print(f"  Using unprocessed text for assembly.")

    # 7. Assemble
    print(f"\n[7/7] Assembling and saving...")
    try:
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

    # 7.5. Auto-learn names from chapter (Name Converter)
    if auto_learn:
        print(f"\n[7.5] Auto-learning names...")
        try:
            name_converter = NameConverter(book_id, source_lang=source_lang)
            
            # Extract potential names from source text
            potential_names = name_converter.extract_potential_names(clean_text)
            
            if potential_names:
                print(f"  Found {len(potential_names)} potential names")
                
                # Check which names are new (not in existing glossary)
                new_names = [(name, ntype) for name, ntype in potential_names 
                            if name not in name_converter.names]
                
                if new_names:
                    print(f"  {len(new_names)} new names detected:")
                    for name, ntype in new_names[:5]:  # Show first 5
                        suggested = name_converter.suggest_myanmar_name(name, ntype)
                        print(f"    - [{ntype}] {name} → suggested: {suggested}")
                    if len(new_names) > 5:
                        print(f"    ... and {len(new_names) - 5} more")
                    
                    # Auto-add names with high confidence suggestions
                    added_count = 0
                    for name, ntype in new_names:
                        suggested = name_converter.suggest_myanmar_name(name, ntype)
                        # Only auto-add if suggestion is different from original (meaning we have a mapping)
                        if suggested != name and len(suggested) > 1:
                            name_converter.add_name(name, suggested, ntype, confidence=0.7)
                            added_count += 1
                    
                    if added_count > 0:
                        print(f"  ✓ Auto-added {added_count} names to glossary")
                        
                    # Sync to context
                    name_converter.sync_glossary_to_context()
                else:
                    print(f"  All names already in glossary")
            else:
                print(f"  No new names found")
        except Exception as e:
            logger.warning(f"Name learning failed: {e}")
            print(f"  ⚠ Name learning skipped: {e}")

    # 8. Save glossary updates (if glossary manager was initialized)
    if glossary is not None:
        print(f"\n[8] Updating glossary...")
        try:
            # Try to extract new names from this chapter
            new_mappings = glossary.update_from_translation(clean_text, processed_text, chapter_num=chapter_num)
            if new_mappings:
                logger.info(f"Found {len(new_mappings)} potential new names to review")
            glossary.metadata["chapter_count"] = glossary.metadata.get("chapter_count", 0) + 1
            glossary.save()
            print(f"✓ Glossary updated: {len(glossary.names)} total names")
        except Exception as e:
            logger.warning(f"Failed to update glossary: {e}")
            print(f"⚠ Failed to update glossary: {e}")

    # 8.5. Update context with translation information
    print(f"\n[8.5] Updating context...")
    try:
        # Analyze and update context
        analysis = context_manager.analyze_chapter_content(chapter_num, clean_text, processed_text)

        # Update chapter info with basic info
        context_manager.update_chapter_translation(
            chapter_num=chapter_num,
            summary=f"Translated {len(processed_text)} characters",  # Simple summary
            characters_appearing=[],  # Would need AI extraction for full list
            new_characters=analysis.get("new_characters", [])
        )

        # Sync characters from glossary to context using name converter
        try:
            name_converter = NameConverter(book_id, source_lang=source_lang)
            name_converter.sync_glossary_to_context()
        except Exception as e:
            logger.warning(f"Glossary-context sync failed: {e}")

        context_manager.save()
        print(f"✓ Context updated and saved")
    except Exception as e:
        logger.warning(f"Failed to update context: {e}")
        print(f"⚠ Failed to update context: {e}")

    # 9. Readability check (optional)
    if do_readability:
        print(f"\n[9] Readability check...")
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
    print(f"║ Book ID   : {book_id[:35]:<35} ║")
    print(f"║ Model     : {translator.name[:35]:<35} ║")
    print(f"║ Chunks    : {len(available_chunks)}/{len(chunks):<25} ║")
    if glossary:
        print(f"║ Glossary  : {len(glossary.names)} names{' ' * 22} ║")
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


def scan_chapter_directories(novel_name: str = None, source_lang: str = None) -> list:
    """
    Scan english_chapters/ and chinese_chapters/ directories for novel chapters.
    
    Directory structures supported:
        - english_chapters/novel_name/novel_name_chapter_001.md
        - chinese_chapters/novel_name/novel_name_chapter_001.md
    
    Args:
        novel_name: Specific novel to scan (optional)
        source_lang: Source language filter ('English' or 'Chinese')
    
    Returns:
        List of tuples: (filepath, novel_name, chapter_num, source_lang)
    """
    files_found = []
    
    # Define directories to scan based on source language
    dirs_to_scan = []
    if source_lang is None or source_lang.lower() == "english":
        dirs_to_scan.append((Path(ENGLISH_CHAPTERS_DIR), "English"))
    if source_lang is None or source_lang.lower() in ["chinese", "chinese_simplified", "chinese_traditional"]:
        dirs_to_scan.append((Path(CHINESE_CHAPTERS_DIR), "Chinese"))
    
    for base_dir, lang in dirs_to_scan:
        if not base_dir.exists():
            continue
        
        if novel_name:
            # Scan specific novel directory
            novel_dir = base_dir / novel_name
            if novel_dir.exists():
                # Pattern: novel_name_chapter_*.md
                pattern = f"{novel_name}_chapter_*.md"
                chapter_files = list(novel_dir.glob(pattern))
                
                for f in chapter_files:
                    # Extract chapter number from filename
                    match = re.search(r'chapter_(\d+)', f.name)
                    chapter_num = int(match.group(1)) if match else 0
                    files_found.append((f, novel_name, chapter_num, lang))
        else:
            # Scan all novels in directory
            for novel_dir in base_dir.iterdir():
                if novel_dir.is_dir():
                    novel_id = novel_dir.name
                    # Pattern: *_chapter_*.md
                    chapter_files = list(novel_dir.glob("*_chapter_*.md"))
                    
                    for f in chapter_files:
                        match = re.search(r'chapter_(\d+)', f.name)
                        chapter_num = int(match.group(1)) if match else 0
                        files_found.append((f, novel_id, chapter_num, lang))
    
    # Sort by novel name, then chapter number
    files_found.sort(key=lambda x: (x[1], x[2]))
    
    logger.info(f"Found {len(files_found)} chapter file(s) in chapter directories")
    return files_found


def discover_novel_files(source_path: str = None, novel_name: str = None, 
                         source_lang: str = None) -> list:
    """
    Discover novel files from various sources.
    
    Priority:
    1. Specific file path (source_path)
    2. Specific novel in chapter directories
    3. input_novels/ directory
    4. All novels in chapter directories
    
    Returns:
        List of tuples: (filepath, novel_name, chapter_num, source_lang)
    """
    files = []
    
    if source_path:
        # Single file mode
        path = Path(source_path)
        if path.exists():
            # Try to extract novel name and chapter from path
            novel_id = path.parent.name if path.parent.name not in [INPUT_DIR, "."] else path.stem
            match = re.search(r'chapter_(\d+)', path.name)
            chapter_num = int(match.group(1)) if match else 1
            lang = source_lang or "English"
            files.append((path, novel_id, chapter_num, lang))
    
    elif novel_name:
        # Specific novel mode - scan chapter directories
        files = scan_chapter_directories(novel_name, source_lang)
    
    else:
        # Auto-discover mode
        # First check input_novels/
        input_files = scan_input_novels()
        for f in input_files:
            novel_id = f.stem
            chapter_num = 1
            lang = source_lang or "English"
            files.append((f, novel_id, chapter_num, lang))
        
        # Then scan chapter directories
        chapter_files = scan_chapter_directories(None, source_lang)
        files.extend(chapter_files)
    
    return files


def main() -> None:
    """Main entry point for the translator CLI."""
    parser = argparse.ArgumentParser(
        description="Chinese/English → Myanmar Novel Translator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Examples:
  # Auto-scan and translate all files from chapter directories
  python main.py

  # Translate a specific novel from chapter directories
  python main.py --novel dao-equaling-the-heavens
  python main.py --novel dao-equaling-the-heavens --source-lang English

  # Single file (one chapter)
  python main.py {INPUT_DIR}/chapter_001.txt

  # Single model translation
  python main.py --model openrouter
  python main.py --model gemini
  python main.py --model ollama
  python main.py --model nllb

  # Two-stage translation: Use different models for raw translation and rewrite
  python main.py --two-stage --stage1-model ollama:gemma:7b --stage2-model ollama:qwen:7b

  # Source language options
  python main.py --source-lang Chinese
  python main.py --source-lang English

  # Chunking options
  python main.py --max-chars {DEFAULT_CHUNK_SIZE}

  # Skip readability check
  python main.py --no-readability

  # Disable auto name learning
  python main.py --no-auto-learn
        """
    )

    parser.add_argument("file", nargs="?", help="Single file to translate (e.g., input_novels/chapter_001.txt)")
    parser.add_argument("--novel", default=None,
                        help="Translate a specific novel from english_chapters/ or chinese_chapters/ directories")
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
    parser.add_argument("--readability", action="store_true",
                        help="Enable readability check")
    parser.add_argument("--no-auto-learn", action="store_true",
                        help="Disable automatic name learning from chapters")
    parser.add_argument("--names", default="names.json",
                        help="Character names mapping file")

    # Two-stage translation options
    parser.add_argument("--two-stage", action="store_true",
                        help="Enable two-stage translation mode (raw + rewrite)")
    parser.add_argument("--stage1-model", default=None,
                        help="Model for Stage 1 (raw translation). Options: gemini, openrouter, ollama, or ollama:modelname (e.g., ollama:gemma:7b). Default from config.")
    parser.add_argument("--stage2-model", default=None,
                        help="Model for Stage 2 (rewrite). Options: gemini, openrouter, ollama, or ollama:modelname (e.g., ollama:qwen:7b). Default from config")

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

    # Two-stage mode: CLI arg > config > default (False)
    use_two_stage = args.two_stage
    if not use_two_stage:
        pipeline_config = config.get("translation_pipeline", {})
        use_two_stage = pipeline_config.get("mode", "single_stage") == "two_stage"
    
    # Stage 1 and Stage 2 models
    stage1_model = args.stage1_model
    stage2_model = args.stage2_model
    
    # Load pipeline config for defaults
    pipeline_config = config.get("translation_pipeline", {})
    
    # Default two-stage models from config, then fallback to gemini/ollama
    if use_two_stage:
        if stage1_model is None:
            stage1_model = pipeline_config.get("stage1_model", "gemini")
        if stage2_model is None:
            stage2_model = pipeline_config.get("stage2_model", "ollama")

    # Validate chunk size
    if not MIN_CHUNK_SIZE <= args.max_chars <= MAX_CHUNK_SIZE:
        logger.warning(
            f"Chunk size {args.max_chars} outside recommended range "
            f"[{MIN_CHUNK_SIZE}, {MAX_CHUNK_SIZE}]. Using closest valid value."
        )
        args.max_chars = max(MIN_CHUNK_SIZE, min(args.max_chars, MAX_CHUNK_SIZE))

    # Check if using Gemini and warn about rate limits
    using_gemini = (not use_two_stage and "gemini" in model.lower()) or \
                   (use_two_stage and "gemini" in (stage1_model or "").lower())
    
    if using_gemini:
        request_delay = float(os.getenv("REQUEST_DELAY", "4.0"))
        if request_delay < 4.0:
            print("\n⚠️  WARNING: Gemini free tier has strict rate limits (15 requests per minute)")
            print("    Consider setting REQUEST_DELAY=4.0 in .env to avoid 429 errors")
            print()
    
    logger.info("=" * 60)
    logger.info(f"{source_lang} → Myanmar Novel Translator Started")
    if use_two_stage:
        logger.info(f"Mode: Two-Stage | Stage 1: {stage1_model} | Stage 2: {stage2_model}")
    else:
        logger.info(f"Model: {model}")
    logger.info(f"Chunk size: {args.max_chars}, Overlap size: {args.overlap_chars}")
    logger.info("=" * 60)

    print("=" * 60)
    print(f"{source_lang} → Myanmar Novel Translator")
    print("=" * 60)
    if use_two_stage:
        print("Mode: Two-Stage Translation")
        print(f"  Stage 1 (Raw): {stage1_model}")
        print(f"  Stage 2 (Rewrite): {stage2_model}")
    else:
        print(f"Model: {model}")
    print(f"Source: {source_lang}")
    print(f"Max chars per chunk: {args.max_chars}")
    print(f"Overlap chars: {args.overlap_chars}")
    
    # Check if using OpenRouter and show free tier info
    current_model = stage1_model if (use_two_stage and stage1_model) else model
    if "openrouter" in current_model.lower():
        print("\n⚠️  WARNING: OpenRouter Free Tier Limits:")
        print("   - 20 requests per minute")
        print("   - 200 requests per day")
        print("   - With 4s delay: ~28 chapters max per day")
        print("\n   💡 RECOMMENDATION: Use local Ollama to avoid limits:")
        print("      python main.py input_novels/chapter_001.md --model ollama")
        print("   Fallback models enabled for reliability")
    
    print("=" * 60)
    print()

    # Determine files to process using new discovery system
    files = discover_novel_files(
        source_path=args.file,
        novel_name=args.novel,
        source_lang=source_lang
    )

    if not files:
        logger.warning("No files found to translate")
        print("No files found to translate.")
        print(f"Add files to {INPUT_DIR}/, {ENGLISH_CHAPTERS_DIR}/, or {CHINESE_CHAPTERS_DIR}/")
        return

    logger.info(f"Found {len(files)} file(s) to process")
    print(f"Found {len(files)} chapter(s) to translate:\n")
    for filepath, novel_id, chapter_num, lang in files[:10]:  # Show first 10
        print(f"  - {novel_id} Ch {chapter_num}: {filepath.name}")
    if len(files) > 10:
        print(f"  ... and {len(files) - 10} more")
    print()

    # Group files by novel for context management
    novels = {}
    for filepath, novel_id, chapter_num, lang in files:
        if novel_id not in novels:
            novels[novel_id] = {"files": [], "lang": lang}
        novels[novel_id]["files"].append((filepath, chapter_num))

    # Process each novel
    total_success = 0
    total_fail = 0

    for novel_id, novel_data in novels.items():
        print(f"\n{'='*60}")
        print(f"Processing Novel: {novel_id}")
        print(f"Source Language: {novel_data['lang']}")
        print(f"Chapters: {len(novel_data['files'])}")
        print(f"{'='*60}\n")

        # Initialize context manager for this novel
        context_manager = ContextManager(novel_id, source_lang=novel_data['lang'])

        # Sort chapters by number
        novel_data["files"].sort(key=lambda x: x[1])

        # Process each chapter
        for filepath, chapter_num in novel_data["files"]:
            logger.info(f"Processing: {novel_id} Chapter {chapter_num}")
            print(f"\n>>> Translating Chapter {chapter_num}...")

            success = translate_single_file(
                filepath=str(filepath),
                model_name=model,
                max_chars=args.max_chars,
                overlap_chars=args.overlap_chars,
                do_readability=args.readability,
                names_path=args.names,
                source_lang=novel_data['lang'],
                book_id=novel_id,
                use_two_stage=use_two_stage,
                stage1_model=stage1_model,
                stage2_model=stage2_model,
                chapter_num=chapter_num,
                context_manager=context_manager,
                auto_learn=not args.no_auto_learn
            )

            if success:
                total_success += 1
                logger.info(f"Successfully translated: {novel_id} Chapter {chapter_num}")
            else:
                total_fail += 1
                logger.error(f"Failed to translate: {novel_id} Chapter {chapter_num}")

        # Save context for this novel
        context_manager.save()
        print(f"\n✓ Context saved for {novel_id}")

    # Summary
    logger.info("=" * 60)
    logger.info("Translation Summary")
    logger.info(f"Total: {len(files)}, Success: {total_success}, Failed: {total_fail}")
    logger.info("=" * 60)

    print("\n" + "=" * 60)
    print("Translation Summary")
    print("=" * 60)
    print(f"Total chapters: {len(files)}")
    print(f"Successful:     {total_success}")
    print(f"Failed:         {total_fail}")
    print("=" * 60)


if __name__ == "__main__":
    main()
