#!/usr/bin/env python3
"""
Manual Chapter Translation Script with Retry Logic
Translate a single chapter from Chinese to Myanmar/Burmese

Usage:
    python translate_chapter_manual.py <chapter_number>
    python translate_chapter_manual.py 1
    python translate_chapter_manual.py 1 --model gemini --delay 10
"""

import os
import sys
import time
import argparse
import requests
from pathlib import Path

# Add parent directory to path to import from scripts folder
sys.path.insert(0, str(Path(__file__).parent.parent))

# ANSI Colors
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
RESET  = "\033[0m"

def info(msg):    print(f"{CYAN}[INFO]{RESET} {msg}")
def success(msg): print(f"{GREEN}[OK]{RESET} {msg}")
def warn(msg):    print(f"{YELLOW}[WARN]{RESET} {msg}")
def error(msg):   print(f"{RED}[ERROR]{RESET} {msg}")


def translate_with_retry(translator, content, system_prompt, max_retries=5):
    """Translate with retry logic for rate limiting."""
    for attempt in range(1, max_retries + 1):
        try:
            info(f"Translation attempt {attempt}/{max_retries}...")
            
            if hasattr(translator, 'translate_stream'):
                # Streaming mode
                print(CYAN + "[Streaming] " + RESET, end='', flush=True)
                
                translated_lines = []
                token_count = 0
                char_count = 0
                
                for token in translator.translate_stream(content, system_prompt):
                    translated_lines.append(token)
                    token_count += 1
                    char_count += len(token)
                    
                    # Print token
                    print(token, end='', flush=True)
                    
                    # Show progress every 500 chars
                    if char_count % 500 == 0 and char_count > 0:
                        print(f"\n{YELLOW}... [{char_count} chars] ...{RESET}\n", end='', flush=True)
                
                print()  # New line
                return "".join(translated_lines), char_count, token_count
            else:
                # Non-streaming mode
                translated_text = translator.translate(content, system_prompt)
                print(translated_text)
                return translated_text, len(translated_text), 0
                
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                # Rate limit - retry with exponential backoff
                wait_time = min(120, 10 * (2 ** (attempt - 1)))  # Cap at 120 seconds
                warn(f"Rate limited (429). Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
                if attempt == max_retries:
                    raise
            else:
                raise
        except Exception as e:
            # Other errors - retry with shorter delay
            if attempt < max_retries:
                wait_time = 5 * attempt
                warn(f"Error: {e}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise
    
    raise RuntimeError("Max retries reached")


def main():
    parser = argparse.ArgumentParser(
        description="Translate a single chapter manually"
    )
    parser.add_argument("chapter", type=int, help="Chapter number (e.g., 1, 2, 3)")
    parser.add_argument("--model", default="gemini", 
                        choices=["gemini", "openrouter", "ollama"],
                        help="AI model to use")
    parser.add_argument("--novel", default="古道仙鸿",
                        help="Novel name (default: 古道仙鸿)")
    parser.add_argument("--delay", type=float, default=0,
                        help="Delay in seconds before starting (useful for rate limits)")
    parser.add_argument("--chunk-size", type=int, default=1500,
                        help="Split chapter into chunks of this size (0 = no splitting)")
    
    args = parser.parse_args()
    
    # Delay if requested
    if args.delay > 0:
        info(f"Waiting {args.delay}s before starting...")
        time.sleep(args.delay)
    
    # Build chapter file path
    chapter_file = f"chinese_chapters/{args.novel}/{args.novel}_chapter_{args.chapter:03d}.md"
    
    if not Path(chapter_file).exists():
        error(f"Chapter file not found: {chapter_file}")
        sys.exit(1)
    
    # Build output path
    output_dir = Path(f"translated_novels/{args.novel}")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{args.novel}_chapter_{args.chapter:03d}_myanmar.md"
    
    print(f"="*60)
    print(f"Manual Chapter Translation")
    print(f"="*60)
    print(f"Novel: {args.novel}")
    print(f"Chapter: {args.chapter}")
    print(f"Model: {args.model}")
    print(f"Input: {chapter_file}")
    print(f"Output: {output_file}")
    print(f"="*60)
    print()
    
    # Import translator module
    import importlib.util
    spec = importlib.util.spec_from_file_location("translator", Path("scripts/translator.py"))
    translator_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(translator_module)
    
    # Load translator
    info(f"Loading {args.model} translator...")
    try:
        translator = translator_module.get_translator(args.model)
        success(f"Loaded: {translator.name}")
    except ValueError as e:
        error(str(e))
        print()
        print("To fix this:")
        print("1. Edit the .env file with your API key")
        print("2. Or use Ollama locally (no API key needed):")
        print("   python translate_chapter_manual.py 1 --model ollama")
        sys.exit(1)
    
    # Read chapter
    info(f"Reading chapter {args.chapter}...")
    with open(chapter_file, "r", encoding="utf-8") as f:
        content = f.read()
    
    print(f"Chapter size: {len(content)} characters")
    print()
    
    # Get system prompt
    system_prompt = translator_module.get_system_prompt("Myanmar (Burmese)", "Chinese")
    
    # Translate
    info("Starting translation with retry logic...")
    print("-"*60)
    print()
    
    try:
        translated_text, char_count, token_count = translate_with_retry(
            translator, content, system_prompt, max_retries=5
        )
        
        print()
        print("-"*60)
        success("Translation complete!")
        info(f"Output: {char_count} characters, {token_count} tokens")
        
        # Save to file
        header = f"# {args.novel} - အခန်း {args.chapter}\n"
        header += f"# Chapter {args.chapter} - Myanmar Translation\n\n"
        header += f"---\n\n"
        
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(header)
            f.write(translated_text)
        
        success(f"Saved to: {output_file}")
        
    except Exception as e:
        print()
        print("-"*60)
        error(f"Translation failed: {e}")
        print()
        print("Suggestions:")
        print("1. Wait a few minutes and try again (rate limit may reset)")
        print("2. Try a different model:")
        print("   python translate_chapter_manual.py 1 --model ollama")
        print("3. Use Ollama locally (no rate limits):")
        print("   python translate_chapter_manual.py 1 --model ollama")
        print("4. Add a delay before starting:")
        print("   python translate_chapter_manual.py 1 --delay 30")
        sys.exit(1)


if __name__ == "__main__":
    main()
