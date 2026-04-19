#!/usr/bin/env python3
"""
Main Orchestrator - Chinese → Myanmar Novel Translator
"""

import os
import sys
import time
import argparse
import logging
from datetime import datetime
from pathlib import Path

# Import our modules
from preprocessor import preprocess
from chunker import auto_chunk, split_into_paragraphs, print_chunk_analysis
from translator import get_translator, get_system_prompt
from checkpoint import CheckpointManager
from postprocessor import postprocess
from assembler import assemble

# Setup logging
os.makedirs("working_data/logs", exist_ok=True)
log_file = f"working_data/logs/translation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def translate_single_file(
    filepath: str,
    model_name: str,
    max_chars: int,
    do_readability: bool,
    names_path: str
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
    print("\n[1/7] Preprocessing...")
    try:
        clean_text = preprocess(str(filepath))
    except Exception as e:
        logger.error(f"Preprocessing failed: {e}")
        print(f"✗ Preprocessing failed: {e}")
        return False
    
    # 2. Chunk
    print("\n[2/7] Chunking...")
    try:
        paragraphs = split_into_paragraphs(clean_text)
        chunks = auto_chunk(clean_text, max_chars)
        print_chunk_analysis(chunks, paragraphs)
    except Exception as e:
        logger.error(f"Chunking failed: {e}")
        print(f"✗ Chunking failed: {e}")
        return False
    
    # 3. Setup checkpoint manager
    checkpoint = CheckpointManager(chapter_name)
    completed = checkpoint.print_resume_info(len(chunks))
    
    # 4. Load translator
    print(f"\n[3/7] Loading translator: {model_name}")
    try:
        translator = get_translator(model_name)
        print(f"✓ Loaded: {translator.name}")
    except ValueError as e:
        logger.error(f"Failed to load translator: {e}")
        print(f"✗ {e}")
        print("\nTo fix this:")
        print("1. Edit .env file with your API key")
        print("2. Or use Ollama locally: python main.py --model ollama")
        return False
    
    system_prompt = get_system_prompt()
    
    # 5. Translate chunks
    print(f"\n[4/7] Translating {len(chunks)} chunks...")
    print("-" * 60)
    
    start_time = time.time()
    
    for i, chunk in enumerate(chunks, 1):
        # Check if already done
        if checkpoint.is_done(i):
            print(f"\n[{i}/{len(chunks)}] ✓ Checkpoint found — skipping")
            continue
        
        print(f"\n[{i}/{len(chunks)}] Translating • {len(chunk)} chars • {translator.name}")
        print("-" * 60)
        
        try:
            # Stream translation
            translated = []
            for token in translator.translate_stream(chunk, system_prompt):
                print(token, end="", flush=True)
                translated.append(token)
            
            translated_text = "".join(translated)
            print(f"\n✓ Done — {len(translated_text)} Myanmar chars written")
            
            # Save checkpoint
            checkpoint.save(i, translated_text)
            
            # Delay between chunks
            if i < len(chunks):
                delay = float(os.getenv("REQUEST_DELAY", "1.0"))
                time.sleep(delay)
                
        except Exception as e:
            logger.error(f"Translation failed for chunk {i}: {e}")
            print(f"\n✗ Translation failed: {e}")
            print("Waiting 10s before retry...")
            time.sleep(10)
            # Continue to next chunk instead of failing entirely
            continue
    
    translate_time = time.time() - start_time
    
    # 6. Postprocess
    print(f"\n[5/7] Postprocessing...")
    try:
        # Load all checkpoints
        all_chunks = checkpoint.load_all()
        full_text = '\n\n'.join(all_chunks[i] for i in sorted(all_chunks.keys()))
        
        # Postprocess
        processed_text = postprocess(full_text, names_path)
        
        # Save postprocessed version back to checkpoints
        for i, text in enumerate(processed_text.split('\n\n'), 1):
            if i in all_chunks:
                checkpoint.save(i, text)
        
    except Exception as e:
        logger.error(f"Postprocessing failed: {e}")
        print(f"✗ Postprocessing failed: {e}")
    
    # 7. Assemble
    print(f"\n[6/7] Assembling...")
    try:
        output_dir = Path("translated_novels")
        output_dir.mkdir(exist_ok=True)
        output_file = output_dir / f"{chapter_name}_myanmar.md"
        
        assemble(
            original_title=chapter_name,
            chapter_number=1,
            model_name=translator.name,
            translated_content=processed_text,
            output_path=str(output_file)
        )
        
        # Clear checkpoints after successful assembly
        checkpoint.clear_all()
        
    except Exception as e:
        logger.error(f"Assembly failed: {e}")
        print(f"✗ Assembly failed: {e}")
        return False
    
    # 8. Readability check (optional)
    if do_readability:
        print(f"\n[7/7] Readability check...")
        try:
            run_readability_check(processed_text, chapter_name)
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
    print(f"║ Output    : translated_novels/          ║")
    print(f"║             {chapter_name[:30]}_myanmar.md ║")
    print("╚═════════════════════════════════════════╝")
    print("=" * 60)
    
    return True


def run_readability_check(text: str, chapter_name: str):
    """Run LLM readability check once after assembly."""
    from translator import get_translator
    
    # Use same model for readability check
    model = os.getenv("AI_MODEL", "openrouter")
    translator = get_translator(model)
    
    # Sample first 2000 chars for readability check
    sample = text[:2000]
    
    prompt = f"""Review this Myanmar translation excerpt and list:
1. Unnatural sentence flow
2. Missing Myanmar particles (တဲ့၊ပဲ၊တော့)
3. Repeated awkward phrasing
Return max 10 bullet points only. Be concise.

Text:
{sample}"""
    
    print("⚠ Readability Report:")
    
    # Get response (non-streaming for readability)
    system_prompt = "You are a Myanmar language editor."
    
    try:
        # Use non-streaming for readability check
        response = []
        for token in translator.translate_stream(prompt, system_prompt):
            response.append(token)
        
        report = "".join(response)
        print(report)
        
        # Save report
        report_file = f"working_data/logs/{chapter_name}_readability.txt"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"\n✓ Report saved: {report_file}")
        
    except Exception as e:
        print(f"Could not generate report: {e}")


def scan_input_novels():
    """Scan input_novels/ for .txt files."""
    input_dir = Path("input_novels")
    
    if not input_dir.exists():
        print("No input_novels/ directory found. Creating...")
        input_dir.mkdir(parents=True, exist_ok=True)
        return []
    
    txt_files = list(input_dir.glob("*.txt"))
    return sorted(txt_files)


def main():
    parser = argparse.ArgumentParser(
        description="Chinese → Myanmar Novel Translator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Auto-scan and translate all files
  python main.py
  
  # Single file
  python main.py input_novels/chapter_001.txt
  
  # Switch model
  python main.py --model openrouter
  python main.py --model gemini
  python main.py --model ollama
  
  # Chunking options
  python main.py --max-chars 1500
  
  # Skip readability check
  python main.py --no-readability
        """
    )
    
    parser.add_argument("file", nargs="?", help="Single file to translate")
    parser.add_argument("--model", default="openrouter",
                        choices=["openrouter", "gemini", "deepseek", "qwen", "ollama"],
                        help="Translation model to use")
    parser.add_argument("--max-chars", type=int, default=1800,
                        help="Maximum characters per chunk")
    parser.add_argument("--no-readability", action="store_true",
                        help="Skip readability check")
    parser.add_argument("--names", default="names.json",
                        help="Character names mapping file")
    
    args = parser.parse_args()
    
    # Load environment
    from dotenv import load_dotenv
    load_dotenv()
    
    # Override model from .env if AI_MODEL is set
    model = os.getenv("AI_MODEL", args.model)
    
    print("=" * 60)
    print("Chinese → Myanmar Novel Translator")
    print("=" * 60)
    print(f"Model: {model}")
    print(f"Max chars per chunk: {args.max_chars}")
    print("=" * 60)
    print()
    
    # Determine files to process
    if args.file:
        files = [args.file]
    else:
        files = scan_input_novels()
        if not files:
            print("No .txt files found in input_novels/")
            print("Add files and run again.")
            return
        print(f"Found {len(files)} file(s) to translate:\n")
        for f in files:
            print(f"  - {f.name}")
        print()
    
    # Process each file
    success_count = 0
    fail_count = 0
    
    for filepath in files:
        success = translate_single_file(
            filepath=str(filepath),
            model_name=model,
            max_chars=args.max_chars,
            do_readability=not args.no_readability,
            names_path=args.names
        )
        
        if success:
            success_count += 1
        else:
            fail_count += 1
        
        print()
    
    # Summary
    print("=" * 60)
    print("Translation Summary")
    print("=" * 60)
    print(f"Total files: {len(files)}")
    print(f"Successful:  {success_count}")
    print(f"Failed:      {fail_count}")
    print("=" * 60)


if __name__ == "__main__":
    main()
