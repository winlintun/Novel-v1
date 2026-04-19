#!/usr/bin/env python3
"""
Terminal Novel Translation Pipeline

This is a terminal-based translation pipeline that:
1. Scans input_novels/ for *.txt files and chinese_chapters/ for novels
2. Checks if already translated (skips if done)
3. Chunks by paragraph boundaries (no overlap)
4. Translates via AI models with live streaming to terminal
5. Saves checkpoint after every chunk (safe to cancel anytime)
6. Assembles final output to translated_novels/

Usage:
    python translate_terminal.py
    python translate_terminal.py --novel 古道仙鸿
    python translate_terminal.py --model gemini
    python translate_terminal.py --no-stream
"""

import os
import sys
import json
import time
import signal
import argparse
import logging
import requests
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import importlib.util

# Add scripts to path
# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# ─────────────────────────────────────────────
# ANSI Colors
# ─────────────────────────────────────────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
BLUE   = "\033[94m"
MAGENTA = "\033[95m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def info(msg):    print(f"{CYAN}[INFO]{RESET} {msg}")
def success(msg): print(f"{GREEN}[OK]{RESET} {msg}")
def warn(msg):    print(f"{YELLOW}[WARN]{RESET} {msg}")
def error(msg):   print(f"{RED}[ERROR]{RESET} {msg}")
def chunk_msg(msg): print(f"{MAGENTA}[CHUNK]{RESET} {msg}")


# Global shutdown flag
shutdown_requested = False

def signal_handler(signum, frame):
    global shutdown_requested
    print(f"\n{YELLOW}[SHUTDOWN] Saving checkpoint and exiting gracefully...{RESET}")
    shutdown_requested = True

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def load_translator_module():
    """Dynamically load the translator module."""
    spec = importlib.util.spec_from_file_location("translator", Path(__file__).parent / "translator.py")
    translator_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(translator_module)
    return translator_module


def load_chunk_module():
    """Dynamically load the chunk_paragraph module."""
    spec = importlib.util.spec_from_file_location("chunk_paragraph", Path(__file__).parent / "chunk_paragraph.py")
    chunk_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(chunk_module)
    return chunk_module


def scan_novels() -> List[Dict]:
    """
    Scan for novels to translate.
    
    Checks:
    1. input_novels/ for *.txt files (raw novels)
    2. chinese_chapters/ for folders with *.md files (preprocessed novels)
    
    Returns list of novel dictionaries with status.
    """
    novels = []
    
    # Scan input_novels for txt files
    input_dir = Path("input_novels")
    if input_dir.exists():
        for txt_file in sorted(input_dir.glob("*.txt")):
            novel_name = txt_file.stem
            status = check_translation_status(novel_name)
            novels.append({
                'name': novel_name,
                'source': 'txt',
                'source_path': str(txt_file),
                'status': status['status'],
                'checkpoint': status.get('checkpoint'),
                'progress': status.get('progress', 0)
            })
    
    # Scan chinese_chapters for preprocessed novels
    chapters_dir = Path("chinese_chapters")
    if chapters_dir.exists():
        for novel_dir in sorted(chapters_dir.iterdir()):
            if novel_dir.is_dir():
                novel_name = novel_dir.name
                md_files = list(novel_dir.glob("*.md"))
                if md_files:
                    # Check if this novel already tracked from txt
                    existing = [n for n in novels if n['name'] == novel_name]
                    if not existing:
                        status = check_translation_status(novel_name)
                        novels.append({
                            'name': novel_name,
                            'source': 'chapters',
                            'source_path': str(novel_dir),
                            'chapter_count': len(md_files),
                            'status': status['status'],
                            'checkpoint': status.get('checkpoint'),
                            'progress': status.get('progress', 0)
                        })
    
    return novels


def check_translation_status(novel_name: str) -> Dict:
    """
    Check if a novel has been translated.
    
    Returns dict with:
    - status: 'done', 'in_progress', or 'new'
    - checkpoint: path to checkpoint file if exists
    - progress: percentage complete
    """
    translated_dir = Path("translated_novels") / novel_name
    checkpoint_file = Path("working_data/checkpoints") / f"{novel_name}.json"
    
    # Check if fully translated (output exists and completed checkpoint)
    if translated_dir.exists() and checkpoint_file.exists():
        try:
            with open(checkpoint_file, 'r', encoding='utf-8') as f:
                checkpoint = json.load(f)
            
            if checkpoint.get('status') == 'completed':
                return {
                    'status': 'done',
                    'checkpoint': str(checkpoint_file),
                    'progress': 100
                }
            elif checkpoint.get('status') == 'in_progress':
                total = checkpoint.get('total_chunks', 1)
                current = checkpoint.get('current_chunk', 0)
                progress = (current / total) * 100 if total > 0 else 0
                return {
                    'status': 'in_progress',
                    'checkpoint': str(checkpoint_file),
                    'progress': progress,
                    'current_chunk': current,
                    'total_chunks': total
                }
        except Exception:
            pass
    
    # Check for checkpoint only (in progress)
    if checkpoint_file.exists():
        try:
            with open(checkpoint_file, 'r', encoding='utf-8') as f:
                checkpoint = json.load(f)
            
            total = checkpoint.get('total_chunks', 1)
            current = checkpoint.get('current_chunk', 0)
            progress = (current / total) * 100 if total > 0 else 0
            return {
                'status': 'in_progress',
                'checkpoint': str(checkpoint_file),
                'progress': progress,
                'current_chunk': current,
                'total_chunks': total
            }
        except Exception:
            pass
    
    # New novel
    return {
        'status': 'new',
        'checkpoint': None,
        'progress': 0
    }


def chunk_novel(novel: Dict, max_chunk_size: int = 1500) -> Dict:
    """
    Chunk a novel using paragraph-boundary splitting (no overlap).
    
    Args:
        novel: Novel dictionary with source info
        max_chunk_size: Maximum characters per chunk
        
    Returns:
        Dictionary with chunking results
    """
    chunk_module = load_chunk_module()
    
    novel_name = novel['name']
    source_path = Path(novel['source_path'])
    output_dir = Path("working_data/chunks")
    
    info(f"Chunking: {novel_name}")
    
    if novel['source'] == 'chapters':
        # Chunk all chapters in the directory
        result = chunk_module.chunk_novel_chapters(source_path, output_dir, max_chunk_size)
    else:
        # Chunk single txt file
        result = chunk_module.chunk_text_file(source_path, output_dir, max_chunk_size)
    
    return result


def translate_chunk_with_stream(
    translator,
    chunk_text: str,
    system_prompt: str,
    chunk_num: int,
    total_chunks: int,
    novel_name: str,
    max_retries: int = 5
) -> str:
    """
    Translate a single chunk with live streaming to terminal.
    
    Args:
        translator: Translator instance
        chunk_text: Text to translate
        system_prompt: System prompt for translation
        chunk_num: Current chunk number
        total_chunks: Total chunks
        novel_name: Novel name for display
        max_retries: Maximum retry attempts for rate limiting
        
    Returns:
        Translated text
    """
    chunk_msg(f"[{chunk_num}/{total_chunks}] Starting translation...")
    
    for attempt in range(1, max_retries + 1):
        translated_text = ""
        token_count = 0
        char_count = 0
        
        try:
            if hasattr(translator, 'translate_stream'):
                # Streaming translation
                print(f"   {CYAN}Streaming:{RESET} ", end='', flush=True)
                
                for token in translator.translate_stream(chunk_text, system_prompt):
                    if shutdown_requested:
                        print(f"\n{YELLOW}[INTERRUPTED]{RESET}")
                        break
                    
                    translated_text += token
                    token_count += 1
                    char_count += len(token)
                    
                    # Print token
                    print(token, end='', flush=True)
                    
                    # Show progress every 100 chars
                    if char_count % 100 == 0 and char_count > 0:
                        print(f"\n   {YELLOW}↳ [{char_count} chars]{RESET} ", end='', flush=True)
                
                print()  # New line after streaming
                success(f"Chunk {chunk_num} complete: {char_count} chars, {token_count} tokens")
            else:
                # Fallback to non-streaming
                warn("Streaming not available, using non-streaming mode")
                translated_text = translator.translate(chunk_text, system_prompt)
                success(f"Chunk {chunk_num} complete: {len(translated_text)} chars")
            
            return translated_text
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                # Rate limit - retry with exponential backoff (longer delays)
                wait_time = min(60, 5 * (2 ** (attempt - 1)))  # Cap at 60 seconds
                warn(f"Rate limited (429). Waiting {wait_time}s before retry {attempt}/{max_retries}...")
                time.sleep(wait_time)
                if attempt == max_retries:
                    error(f"Max retries reached for chunk {chunk_num}")
                    raise
            else:
                error(f"HTTP error: {e}")
                raise
        except Exception as e:
            error(f"Translation failed: {e}")
            raise
    
    raise RuntimeError(f"Failed to translate chunk {chunk_num} after {max_retries} attempts")


def save_checkpoint(novel_name: str, checkpoint_data: Dict):
    """Save checkpoint atomically."""
    checkpoint_dir = Path("working_data/checkpoints")
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    
    checkpoint_path = checkpoint_dir / f"{novel_name}.json"
    temp_path = checkpoint_dir / f"{novel_name}.json.tmp"
    
    try:
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(checkpoint_data, f, ensure_ascii=False, indent=2)
        temp_path.replace(checkpoint_path)
        info(f"Checkpoint saved: chunk {checkpoint_data.get('current_chunk', 0)}/{checkpoint_data.get('total_chunks', 0)}")
    except Exception as e:
        error(f"Failed to save checkpoint: {e}")


def collect_all_chunks(novel_name: str) -> tuple:
    """
    Collect all chunk files for a novel from chapter directories.
    
    Returns:
        Tuple of (total_chunks, chunk_files) sorted by chapter and chunk number
    """
    chunks_base_dir = Path("working_data/chunks")
    all_chunk_files = []
    
    # Look for chapter directories
    for chapter_dir in sorted(chunks_base_dir.glob(f"{novel_name}_chapter_*")):
        if chapter_dir.is_dir():
            # Find chunks in this chapter
            for chunk_file in sorted(chapter_dir.glob(f"{novel_name}_chapter_*_chunk_*.txt")):
                all_chunk_files.append(str(chunk_file))
    
    # Also check for flat structure (single directory)
    flat_dir = chunks_base_dir / novel_name
    if flat_dir.exists():
        for chunk_file in sorted(flat_dir.glob(f"{novel_name}_chunk_*.txt")):
            all_chunk_files.append(str(chunk_file))
    
    return len(all_chunk_files), all_chunk_files


def translate_novel(
    novel: Dict,
    model_name: str = None,
    stream: bool = True,
    max_chunk_size: int = 1500
) -> bool:
    """
    Translate a novel with checkpointing and streaming.
    
    Args:
        novel: Novel dictionary
        model_name: Model to use (overrides env)
        stream: Enable streaming output
        max_chunk_size: Maximum chunk size
        
    Returns:
        True if completed, False if interrupted
    """
    global shutdown_requested
    
    novel_name = novel['name']
    
    print(f"\n{BOLD}{'═'*70}{RESET}")
    print(f"{BOLD} Translating: {novel_name}{RESET}")
    print(f"{BOLD}{'═'*70}{RESET}\n")
    
    # Load translator
    translator_module = load_translator_module()
    model_name = model_name or os.getenv("AI_MODEL", "gemini")
    
    info(f"Using model: {BOLD}{model_name}{RESET}")
    try:
        translator = translator_module.get_translator(model_name)
        success(f"Loaded: {translator.name}")
    except Exception as e:
        error(f"Failed to load translator: {e}")
        return False
    
    # Check if already chunked
    total_chunks, chunk_files = collect_all_chunks(novel_name)
    
    if total_chunks == 0:
        # Need to chunk first
        info("Chunking novel by paragraphs (no overlap)...")
        chunk_info = chunk_novel(novel, max_chunk_size)
        if not chunk_info['success']:
            error(f"Chunking failed: {chunk_info.get('error', 'Unknown error')}")
            return False
        total_chunks, chunk_files = collect_all_chunks(novel_name)
    else:
        info(f"Found {total_chunks} existing chunks")
    
    success(f"Total chunks: {total_chunks}")
    
    # Load checkpoint if exists
    checkpoint_file = Path("working_data/checkpoints") / f"{novel_name}.json"
    start_chunk = 1
    
    if checkpoint_file.exists():
        try:
            with open(checkpoint_file, 'r', encoding='utf-8') as f:
                checkpoint = json.load(f)
            if checkpoint.get('status') == 'in_progress':
                start_chunk = checkpoint.get('current_chunk', 0) + 1
                info(f"Resuming from chunk {start_chunk}/{total_chunks}")
        except Exception as e:
            warn(f"Could not load checkpoint: {e}")
    
    # Setup output directory
    output_dir = Path("working_data/translated_chunks") / novel_name
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # System prompt
    system_prompt = translator_module.get_system_prompt("Myanmar (Burmese)", "Chinese")
    
    # Track timing for ETA
    chunk_times = []
    
    # Translate chunks
    for i in range(start_chunk - 1, total_chunks):
        if shutdown_requested:
            warn("Shutdown requested, saving checkpoint...")
            break
        
        chunk_num = i + 1
        chunk_file = chunk_files[i]
        
        # Check if already translated
        output_file = output_dir / f"{novel_name}_chunk_{chunk_num:05d}_burmese.txt"
        if output_file.exists() and output_file.stat().st_size > 0:
            info(f"Chunk {chunk_num} already translated, skipping")
            continue
        
        # Read chunk
        with open(chunk_file, 'r', encoding='utf-8') as f:
            chunk_text = f.read()
        
        chunk_msg(f"[{chunk_num}/{total_chunks}] ({(chunk_num/total_chunks*100):.1f}%)")
        print(f"   File: {Path(chunk_file).name}")
        print(f"   Size: {len(chunk_text)} chars")
        
        # Translate with streaming
        start_time = time.time()
        
        try:
            translated = translate_chunk_with_stream(
                translator,
                chunk_text,
                system_prompt,
                chunk_num,
                total_chunks,
                novel_name
            )
            
            # Save translated chunk
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(translated)
            
            elapsed = time.time() - start_time
            chunk_times.append(elapsed)
            
            # Calculate ETA
            if len(chunk_times) > 5:
                chunk_times = chunk_times[-5:]
            avg_time = sum(chunk_times) / len(chunk_times)
            remaining = total_chunks - chunk_num
            eta = timedelta(seconds=int(avg_time * remaining))
            
            info(f"Time: {elapsed:.1f}s | ETA: {eta}")
            
            # Save checkpoint
            checkpoint_data = {
                'novel_name': novel_name,
                'status': 'in_progress',
                'current_chunk': chunk_num,
                'total_chunks': total_chunks,
                'model': model_name,
                'timestamp': datetime.now().isoformat()
            }
            save_checkpoint(novel_name, checkpoint_data)
            
            # Delay between chunks to avoid rate limiting
            if chunk_num < total_chunks:
                delay = float(os.getenv("REQUEST_DELAY", "5"))
                time.sleep(delay)
            
        except Exception as e:
            error(f"Failed to translate chunk {chunk_num}: {e}")
            # Continue with next chunk instead of failing entirely
            continue
    
    if shutdown_requested:
        warn(f"Translation interrupted at chunk {chunk_num}")
        return False
    
    # Count successfully translated chunks
    translated_count = len(list(output_dir.glob(f"{novel_name}_chunk_*_burmese.txt")))
    
    if translated_count == total_chunks:
        # All chunks complete
        checkpoint_data = {
            'novel_name': novel_name,
            'status': 'completed',
            'current_chunk': total_chunks,
            'total_chunks': total_chunks,
            'model': model_name,
            'completed_at': datetime.now().isoformat()
        }
        save_checkpoint(novel_name, checkpoint_data)
        success(f"Translation complete: {translated_count}/{total_chunks} chunks")
        return True
    else:
        warn(f"Translation incomplete: {translated_count}/{total_chunks} chunks")
        warn("Run again to retry failed chunks")
        return False


def assemble_novel(novel_name: str) -> bool:
    """
    Assemble all translated chunks into final output.
    
    Args:
        novel_name: Name of the novel
        
    Returns:
        True if successful
    """
    info(f"Assembling: {novel_name}")
    
    chunks_dir = Path("working_data/translated_chunks") / novel_name
    output_dir = Path("translated_novels") / novel_name
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Find all translated chunk files
    chunk_files = sorted(chunks_dir.glob(f"{novel_name}_chunk_*_burmese.txt"))
    
    if not chunk_files:
        error("No translated chunks found")
        return False
    
    info(f"Found {len(chunk_files)} translated chunks")
    
    # Read all chunks
    full_text = []
    for chunk_file in chunk_files:
        with open(chunk_file, 'r', encoding='utf-8') as f:
            full_text.append(f.read())
    
    # Join with paragraph breaks
    assembled = "\n\n".join(full_text)
    
    # Create markdown output with Burmese title
    # Convert novel name info to Burmese header
    burmese_digits = '၀၁၂၃၄၅၆၇၈၉'
    
    header = f"# {novel_name} - မြန်မာဘာသာပြန်\n"
    header += f"# Myanmar Translation\n\n"
    header += f"---\n\n"
    
    output_file = output_dir / f"{novel_name}_myanmar.md"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(header)
        f.write(assembled)
    
    success(f"Assembled: {output_file}")
    success(f"Total: {len(assembled)} characters")
    
    return True


def readability_check(novel_name: str) -> Dict:
    """
    Run readability check on translated text.
    
    Args:
        novel_name: Name of the novel
        
    Returns:
        Dictionary with check results
    """
    info(f"Running readability check: {novel_name}")
    
    # Load myanmar_checker module
    spec = importlib.util.spec_from_file_location("myanmar_checker", Path(__file__).parent / "myanmar_checker.py")
    checker_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker_module)
    
    output_dir = Path("translated_novels") / novel_name
    output_file = output_dir / f"{novel_name}_myanmar.md"
    
    if not output_file.exists():
        warn("Output file not found for readability check")
        return {'passed': False, 'error': 'File not found'}
    
    results = checker_module.check_file(str(output_file))
    
    status = "PASS" if results['passed'] else "FLAGGED"
    myanmar_ratio = results['checks'].get('myanmar_ratio', {}).get('value', 0)
    
    if results['passed']:
        success(f"Readability check: {status} (Myanmar ratio: {myanmar_ratio:.1%})")
    else:
        warn(f"Readability check: {status} (Myanmar ratio: {myanmar_ratio:.1%})")
    
    return results


def postprocess_novel(novel_name: str) -> bool:
    """
    Postprocess the translated novel (fix punctuation, consistency).
    
    Args:
        novel_name: Name of the novel
        
    Returns:
        True if successful
    """
    info(f"Postprocessing: {novel_name}")
    
    # Load postprocess_translation module
    spec = importlib.util.spec_from_file_location("postprocess_translation", Path(__file__).parent / "postprocess_translation.py")
    postprocess_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(postprocess_module)
    
    try:
        result = postprocess_module.postprocess_novel(novel_name)
        if result['success']:
            success(f"Postprocessing complete: {result['processed']} chunks")
            return True
        else:
            warn(f"Postprocessing completed with {len(result.get('errors', []))} errors")
            return True  # Non-fatal
    except Exception as e:
        error(f"Postprocessing failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Terminal Novel Translation Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python translate_terminal.py
  python translate_terminal.py --novel 古道仙鸿
  python translate_terminal.py --model gemini --stream
  python translate_terminal.py --skip-translated
        """
    )
    parser.add_argument("--novel", help="Translate specific novel only")
    parser.add_argument("--model", choices=["gemini", "deepseek", "qwen", "opencode", "openrouter", "ollama"],
                        help="AI model to use (overrides .env)")
    parser.add_argument("--stream", action="store_true", default=True,
                        help="Enable streaming output (default: True)")
    parser.add_argument("--no-stream", action="store_false", dest="stream",
                        help="Disable streaming")
    parser.add_argument("--chunk-size", type=int, default=1500,
                        help="Maximum chunk size in characters (default: 1500)")
    parser.add_argument("--skip-translated", action="store_true",
                        help="Skip already translated novels")
    parser.add_argument("--skip-check", action="store_true",
                        help="Skip readability check")
    parser.add_argument("--skip-postprocess", action="store_true",
                        help="Skip postprocessing")
    
    args = parser.parse_args()
    
    print(f"\n{BOLD}{'═'*70}{RESET}")
    print(f"{BOLD}   Terminal Novel Translation Pipeline{RESET}")
    print(f"{BOLD}{'═'*70}{RESET}\n")
    
    # Scan for novels
    info("Scanning for novels...")
    novels = scan_novels()
    
    if not novels:
        warn("No novels found!")
        info("Place .txt files in input_novels/ or chapter .md files in chinese_chapters/")
        return
    
    print(f"\nFound {len(novels)} novel(s):\n")
    print(f"{'Name':<30} {'Source':<10} {'Status':<15} {'Progress':<10}")
    print("-" * 70)
    
    for novel in novels:
        status_symbol = {
            'done': f'{GREEN}✓ done{RESET}',
            'in_progress': f'{YELLOW}↻ in_progress{RESET}',
            'new': f'{CYAN}✎ new{RESET}'
        }.get(novel['status'], novel['status'])
        
        source = novel.get('source', 'unknown')
        progress = f"{novel.get('progress', 0):.0f}%"
        
        print(f"{novel['name']:<30} {source:<10} {status_symbol:<25} {progress:<10}")
    
    print()
    
    # Filter novels to process
    if args.novel:
        novels = [n for n in novels if n['name'] == args.novel]
        if not novels:
            error(f"Novel not found: {args.novel}")
            return
    
    if args.skip_translated:
        novels = [n for n in novels if n['status'] != 'done']
    
    if not novels:
        success("All novels are already translated!")
        return
    
    info(f"Processing {len(novels)} novel(s)...\n")
    
    # Process each novel
    for novel in novels:
        if shutdown_requested:
            break
        
        # Skip if already done and not resuming
        if novel['status'] == 'done' and not args.novel:
            info(f"Skipping {novel['name']} (already translated)")
            continue
        
        # Translate
        success_translate = translate_novel(
            novel,
            model_name=args.model,
            stream=args.stream,
            max_chunk_size=args.chunk_size
        )
        
        if not success_translate:
            if shutdown_requested:
                break
            continue
        
        # Postprocess
        if not args.skip_postprocess:
            postprocess_novel(novel['name'])
        
        # Assemble
        assemble_novel(novel['name'])
        
        # Readability check
        if not args.skip_check:
            readability_check(novel['name'])
        
        print(f"\n{BOLD}{'─'*70}{RESET}\n")
    
    # Final summary
    print(f"\n{BOLD}{'═'*70}{RESET}")
    print(f"{BOLD} Pipeline Complete{RESET}")
    print(f"{BOLD}{'═'*70}{RESET}\n")
    
    if shutdown_requested:
        warn("Pipeline stopped by user")
        info("Run again to resume from checkpoint")
    else:
        success("All novels processed!")


if __name__ == "__main__":
    main()
