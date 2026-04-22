#!/usr/bin/env python3
"""
Cloud Main - Cloud API Novel Translator (Gemini, OpenRouter)

For cloud-based translation with rate limiting protection:
- Automatic rate limit handling
- Exponential backoff for retries
- Queue management for multiple chapters
- API key security

Usage:
    python cloud_main.py input_novels/chapter_001.md --model gemini
    python cloud_main.py --novel dao-equaling-the-heavens --model openrouter
    
Environment Variables:
    GEMINI_API_KEY - For Gemini translation
    OPENROUTER_API_KEY - For OpenRouter translation
    REQUEST_DELAY - Override default delays (Gemini: 6s, OpenRouter: 5s)
"""

import os
import re
import sys
import json
import time
import random
import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

# Import modules
from scripts.preprocessor import preprocess
from scripts.chunker import auto_chunk, split_into_paragraphs, print_chunk_analysis
from scripts.translator import get_translator, get_system_prompt
from scripts.postprocessor import postprocess
from scripts.assembler import assemble
from scripts.glossary_manager import GlossaryManager
from scripts.context_manager import ContextManager
from scripts.name_converter import NameConverter, CULTIVATION_TERMS
from scripts.name_mapping_system import NameMappingSystem, NameType

# Constants
DEFAULT_CHUNK_SIZE = 1000
DEFAULT_OVERLAP_SIZE = 0
MAX_CHUNK_SIZE = 5000
MIN_CHUNK_SIZE = 100
LOG_DIR = "working_data/logs"
BOOKS_DIR = "books"
INPUT_DIR = "input_novels"
ENGLISH_CHAPTERS_DIR = "english_chapters"
CHINESE_CHAPTERS_DIR = "chinese_chapters"

# Rate limit configuration
RATE_LIMITS = {
    "gemini": {"rpm": 15, "delay": 6.0, "description": "15 requests/minute"},
    "openrouter": {"rpm": 20, "delay": 5.0, "description": "20 requests/minute"},
}

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


class RateLimiter:
    """Rate limiter for cloud API requests."""
    
    def __init__(self, provider: str):
        self.provider = provider.lower()
        self.config = RATE_LIMITS.get(self.provider, {"delay": 5.0})
        self.min_delay = float(os.getenv("REQUEST_DELAY", self.config["delay"]))
        self.last_request_time = 0
        self.request_count = 0
        self.window_start = time.time()
    
    def wait_if_needed(self):
        """Wait if necessary to comply with rate limits."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_delay:
            wait_time = self.min_delay - elapsed
            logger.info(f"Rate limiting: waiting {wait_time:.1f}s to comply with {self.provider} limits")
            time.sleep(wait_time)
        self.last_request_time = time.time()
        self.request_count += 1
    
    def handle_rate_limit_error(self, attempt: int) -> float:
        """Calculate backoff time for rate limit errors."""
        base_delay = self.min_delay * 2
        backoff = base_delay * (1.5 ** attempt)
        return min(backoff, 60.0)  # Max 60 seconds


def translate_with_retry(translator, chunk: str, system_prompt: str, rate_limiter: RateLimiter, max_retries: int = 4) -> Optional[str]:
    """Translate with rate limit handling and retries."""
    
    for attempt in range(max_retries + 1):
        try:
            # Wait for rate limit
            rate_limiter.wait_if_needed()
            
            # Attempt translation
            return translator.translate(chunk, system_prompt)
            
        except Exception as e:
            error_str = str(e).lower()
            is_rate_limit = "429" in error_str or "rate limit" in error_str or "too many requests" in error_str
            
            if attempt == max_retries:
                logger.error(f"Translation failed after {max_retries + 1} attempts: {e}")
                if is_rate_limit:
                    print(f"\n❌ Rate limit exceeded. The API quota may be exhausted.")
                    print(f"   Try again later or use local_main.py with Ollama:")
                    print(f"   python local_main.py {chunk[:50]}...")
                return None
            
            if is_rate_limit:
                delay = rate_limiter.handle_rate_limit_error(attempt)
                logger.warning(f"Rate limit hit (429), attempt {attempt + 1}/{max_retries + 1}. Waiting {delay:.1f}s...")
                print(f"⚠️  Rate limited. Waiting {delay:.1f}s before retry...")
                time.sleep(delay)
            else:
                # Other error, use shorter delay
                delay = 2.0 * (attempt + 1)
                logger.warning(f"Translation error, attempt {attempt + 1}/{max_retries + 1}. Waiting {delay:.1f}s...")
                time.sleep(delay)
    
    return None


def translate_single_file_cloud(
    filepath: str,
    model_name: str,
    max_chars: int,
    overlap_chars: int,
    source_lang: str = "Chinese",
    book_id: str = None,
    chapter_num: int = 1,
    context_manager: ContextManager = None,
    auto_learn: bool = True
) -> bool:
    """Translate a single file using cloud APIs with rate limiting."""
    
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
    
    # Setup rate limiter
    provider = "gemini" if "gemini" in model_name.lower() else "openrouter" if "openrouter" in model_name.lower() else "unknown"
    rate_limiter = RateLimiter(provider)
    
    # Show rate limit info
    config = RATE_LIMITS.get(provider, {"delay": 5.0, "description": "Unknown"})
    env_delay = os.getenv("REQUEST_DELAY")
    actual_delay = float(env_delay) if env_delay else config["delay"]
    
    print("=" * 60)
    print(f"Translating: {chapter_name}")
    print(f"Book ID: {book_id}")
    print(f"Provider: {provider.upper()}")
    print(f"Rate Limit: {config['description']}")
    print(f"Delay: {actual_delay}s between requests")
    print("=" * 60)
    
    # 1. Preprocess
    print("\n[1/7] Preprocessing...")
    try:
        clean_text = preprocess(str(filepath))
        print(f"✓ Preprocessed: {len(clean_text)} characters")
    except Exception as e:
        logger.error(f"Preprocessing failed: {e}")
        return False
    
    # 2. Chunk
    print("\n[2/7] Chunking...")
    try:
        paragraphs = split_into_paragraphs(clean_text)
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
    
    # 4. Load translator (Cloud API)
    print(f"\n[4/7] Loading {provider} translator...")
    try:
        translator = get_translator(model_name)
        print(f"✓ Loaded: {translator.name}")
    except ValueError as e:
        print(f"✗ {e}")
        print("\nTo fix this:")
        if provider == "gemini":
            print("1. Get API key: https://makersuite.google.com/app/apikey")
            print("2. Edit .env: GEMINI_API_KEY=your_key")
        else:
            print("1. Get API key: https://openrouter.ai/keys")
            print("2. Edit .env: OPENROUTER_API_KEY=your_key")
        return False
    except Exception as e:
        print(f"✗ Failed: {e}")
        return False
    
    # Get system prompt
    system_prompt = get_system_prompt(source_lang=source_lang, glossary_manager=glossary)
    if name_mapping_system:
        name_mappings_text = name_mapping_system.get_prompt_text()
        if name_mappings_text:
            system_prompt += "\n" + name_mappings_text
    if context_text:
        system_prompt += f"\n\n{'='*80}\nNOVEL CONTEXT:\n{'='*80}\n{context_text}\n{'='*80}"
    
    # 5. Translate chunks (WITH RATE LIMITING)
    print(f"\n[5/7] Translating {len(chunks)} chunks (with rate limiting)...")
    print(f"   Estimated time: ~{len(chunks) * actual_delay / 60:.1f} minutes")
    print("-" * 60)
    
    start_time = time.time()
    previous_translation = None
    translated_chunks = {}
    
    for i, chunk in enumerate(chunks, 1):
        logger.info(f"Translating chunk {i}/{len(chunks)}: {len(chunk)} chars using {translator.name}")
        
        user_content = chunk
        if previous_translation and i > 1:
            context_preview = previous_translation[-1200:] if len(previous_translation) > 1200 else previous_translation
            user_content = f"PREVIOUS CONTEXT:\n{context_preview}\n\n---\n\nCURRENT TEXT:\n{chunk}"
        else:
            user_content = f"CHAPTER: {chapter_name}\n\nTEXT:\n{chunk}"
        
        if name_mapping_system:
            user_content = name_mapping_system.apply_mappings(user_content)
        
        # Translate with retry and rate limiting
        translated_text = translate_with_retry(translator, user_content, system_prompt, rate_limiter)
        
        if translated_text:
            previous_translation = translated_text
            translated_chunks[i] = translated_text
            print(f"\n[{i}/{len(chunks)}] ✓ Done — {len(translated_text)} chars")
        else:
            print(f"\n[{i}/{len(chunks)}] ✗ Failed after all retries")
    
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
            chapter_number=1,
            model_name=translator.name,
            translated_content=processed_text,
            output_path=str(output_file),
            book_id=book_id
        )
        print(f"✓ Saved: {output_file}")
    except Exception as e:
        logger.error(f"Assembly failed: {e}")
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
    
    print("\n" + "=" * 60)
    print("╔═════════════════════════════════════════╗")
    print("║         Translation Complete!           ║")
    print(f"║ Chapter   : {chapter_name[:35]:<35} ║")
    print(f"║ Book ID   : {book_id[:35]:<35} ║")
    print(f"║ Provider  : {provider.upper()[:35]:<35} ║")
    print(f"║ Chunks    : {len(available_chunks)}/{len(chunks):<25} ║")
    print(f"║ Time      : {translate_time/60:.1f}m{' '*30}║")
    print("╚═════════════════════════════════════════╝")
    print("=" * 60)
    
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Cloud API Novel Translator (Gemini, OpenRouter)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cloud_main.py input_novels/chapter_001.md --model gemini
  python cloud_main.py --novel dao-equaling-the-heavens --model openrouter
  python cloud_main.py --model gemini --max-chars 800

Environment Variables:
  GEMINI_API_KEY      - Required for Gemini
  OPENROUTER_API_KEY  - Required for OpenRouter
  REQUEST_DELAY       - Override rate limit delays
        """
    )
    
    parser.add_argument("file", nargs="?", help="Single file to translate")
    parser.add_argument("--novel", help="Translate a specific novel")
    parser.add_argument("--model", required=True, choices=["gemini", "openrouter"],
                       help="Cloud API provider to use")
    parser.add_argument("--source-lang", default="Chinese", choices=["Chinese", "Chinese_Simplified", "Chinese_Traditional", "English"])
    parser.add_argument("--max-chars", type=int, default=DEFAULT_CHUNK_SIZE, help=f"Max chars per chunk (default: {DEFAULT_CHUNK_SIZE})")
    parser.add_argument("--overlap-chars", type=int, default=DEFAULT_OVERLAP_SIZE, help=f"Overlap chars (default: {DEFAULT_OVERLAP_SIZE})")
    parser.add_argument("--no-auto-learn", action="store_true", help="Disable auto name learning")
    
    args = parser.parse_args()
    
    from dotenv import load_dotenv
    load_dotenv()
    
    # Validate API keys
    if args.model == "gemini":
        if not os.getenv("GEMINI_API_KEY"):
            print("❌ GEMINI_API_KEY not set in .env file")
            print("   Get your key: https://makersuite.google.com/app/apikey")
            print("   Or use local_main.py for local Ollama translation")
            return
    elif args.model == "openrouter":
        if not os.getenv("OPENROUTER_API_KEY"):
            print("❌ OPENROUTER_API_KEY not set in .env file")
            print("   Get your key: https://openrouter.ai/keys")
            print("   Or use local_main.py for local Ollama translation")
            return
    
    # Discover files
    files = []
    if args.file:
        files.append((Path(args.file), args.file.parent.name if Path(args.file).parent.name != INPUT_DIR else Path(args.file).stem, 1, args.source_lang))
    elif args.novel:
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
        input_dir = Path(INPUT_DIR)
        if input_dir.exists():
            for f in sorted(input_dir.glob("*.md")) + sorted(input_dir.glob("*.txt")):
                files.append((f, f.stem, 1, args.source_lang))
    
    if not files:
        print("No files found to translate")
        print(f"Add files to {INPUT_DIR}/ or use --novel")
        return
    
    print(f"\nFound {len(files)} file(s) to process")
    print("⚠️  Note: Cloud APIs have rate limits. Translation will take longer.")
    print("=" * 60)
    
    # Process files
    success_count = 0
    for filepath, book_id, chapter_num, source_lang in files:
        if translate_single_file_cloud(
            filepath=str(filepath),
            model_name=args.model,
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
    main()
