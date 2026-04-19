#!/usr/bin/env python3
"""
Chinese-to-Burmese Novel Translation Pipeline

This is the main orchestrator that runs the complete translation pipeline:
1. Scan input_novels/ for .txt files
2. Skip already-translated novels
3. Resume from checkpoint if incomplete
4. Run pipeline: preprocess → chunk → translate → check → postprocess → assemble
5. Start web UI for live monitoring
6. Handle graceful shutdown with Ctrl+C

Usage:
    python main.py

The pipeline saves atomic checkpoints after every chunk, so it's safe to cancel
and resume at any time.
"""

import os
import sys
import json
import time
import signal
import logging
import subprocess
import webbrowser
import threading
from pathlib import Path
from datetime import datetime, timedelta

# Setup logging first
LOG_DIR = Path("working_data/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / "main.log", encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Global state for graceful shutdown
shutdown_requested = False
current_checkpoint = None
web_ui_process = None


def signal_handler(signum, frame):
    """Handle Ctrl+C for graceful shutdown."""
    global shutdown_requested
    
    if not shutdown_requested:
        logger.info("=" * 60)
        logger.info("Shutdown requested (Ctrl+C). Saving checkpoint...")
        logger.info("=" * 60)
        shutdown_requested = True
    else:
        logger.info("Force exit requested.")
        sys.exit(1)


# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def load_config():
    """Load configuration from config.json."""
    try:
        config_path = Path("config/config.json")
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error("Config file not found: config/config.json")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in config file: {e}")
        raise
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        raise


def ensure_directories():
    """Create all necessary working directories."""
    try:
        dirs = [
            "working_data/clean",
            "working_data/chunks",
            "working_data/translated_chunks",
            "working_data/preview",
            "working_data/readability_reports",
            "working_data/logs",
            "working_data/checkpoints",
            "input_novels",
            "translated_novels",
        ]
        
        for dir_path in dirs:
            Path(dir_path).mkdir(parents=True, exist_ok=True)
            
        logger.info("Directory structure verified")
        
    except Exception as e:
        logger.error(f"Error creating directories: {e}")
        raise


def scan_input_novels():
    """
    Scan input_novels/ directory and classify each novel.
    
    Returns:
        List of dictionaries with novel info and status
    """
    try:
        input_dir = Path("input_novels")
        
        if not input_dir.exists():
            logger.warning("input_novels/ directory not found, creating...")
            input_dir.mkdir(parents=True, exist_ok=True)
            return []
        
        novels = []
        
        for txt_file in sorted(input_dir.glob("*.txt")):
            try:
                novel_name = txt_file.stem
                status = classify_novel_status(novel_name)
                
                novels.append({
                    'name': novel_name,
                    'file': str(txt_file),
                    'status': status['status'],
                    'checkpoint': status['checkpoint'],
                    'resume_chunk': status.get('resume_chunk', 0),
                    'total_chunks': status.get('total_chunks', 0)
                })
                
            except Exception as e:
                logger.error(f"Error processing {txt_file}: {e}")
                continue
        
        return novels
        
    except Exception as e:
        logger.error(f"Error scanning input novels: {e}")
        return []


def classify_novel_status(novel_name):
    """
    Classify the translation status of a novel.
    
    Status values:
    - 'done': Already fully translated (output exists + checkpoint completed)
    - 'resuming': Partially translated (checkpoint exists but incomplete)
    - 'new': Never been translated (no checkpoint)
    """
    try:
        output_file = Path("translated_novels") / f"{novel_name}_burmese.md"
        checkpoint_file = Path("working_data/checkpoints") / f"{novel_name}.json"
        
        # Check if output file exists and checkpoint shows completed
        if output_file.exists():
            if checkpoint_file.exists():
                try:
                    with open(checkpoint_file, 'r', encoding='utf-8') as f:
                        checkpoint = json.load(f)
                        
                    if checkpoint.get('status') == 'completed':
                        return {
                            'status': 'done',
                            'checkpoint': str(checkpoint_file),
                            'resume_chunk': checkpoint.get('current_chunk', 0),
                            'total_chunks': checkpoint.get('total_chunks', 0)
                        }
                except Exception as e:
                    logger.error(f"Error reading checkpoint for {novel_name}: {e}")
        
        # Check for partial checkpoint
        if checkpoint_file.exists():
            try:
                with open(checkpoint_file, 'r', encoding='utf-8') as f:
                    checkpoint = json.load(f)
                
                if checkpoint.get('status') == 'in_progress':
                    return {
                        'status': 'resuming',
                        'checkpoint': str(checkpoint_file),
                        'resume_chunk': checkpoint.get('current_chunk', 0),
                        'total_chunks': checkpoint.get('total_chunks', 0)
                    }
            except Exception as e:
                logger.error(f"Error reading checkpoint for {novel_name}: {e}")
        
        # New novel
        return {
            'status': 'new',
            'checkpoint': None,
            'resume_chunk': 0,
            'total_chunks': 0
        }
        
    except Exception as e:
        logger.error(f"Error classifying novel {novel_name}: {e}")
        return {'status': 'new', 'checkpoint': None, 'resume_chunk': 0, 'total_chunks': 0}


def save_checkpoint_atomic(novel_name, checkpoint_data):
    """
    Save checkpoint atomically to prevent corruption.
    
    Uses temp file + rename pattern for atomic writes.
    """
    global current_checkpoint
    
    try:
        checkpoint_dir = Path("working_data/checkpoints")
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        checkpoint_path = checkpoint_dir / f"{novel_name}.json"
        temp_path = checkpoint_dir / f"{novel_name}.json.tmp"
        
        # Update global state
        current_checkpoint = checkpoint_data
        
        # Write to temp file first
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(checkpoint_data, f, ensure_ascii=False, indent=2)
        
        # Atomic rename (this is atomic on POSIX systems)
        temp_path.replace(checkpoint_path)
        
        logger.debug(f"Checkpoint saved: {checkpoint_path} (chunk {checkpoint_data.get('current_chunk', 0)})")
        return True
        
    except Exception as e:
        logger.error(f"Error saving checkpoint for {novel_name}: {e}")
        # Clean up temp file if it exists
        try:
            if temp_path.exists():
                temp_path.unlink()
        except Exception:
            pass
        return False


def load_checkpoint(novel_name):
    """Load checkpoint for a novel."""
    try:
        checkpoint_path = Path("working_data/checkpoints") / f"{novel_name}.json"
        
        if checkpoint_path.exists():
            with open(checkpoint_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        return None
        
    except Exception as e:
        logger.error(f"Error loading checkpoint for {novel_name}: {e}")
        return None


def start_web_ui(config):
    """Start the web UI server as a subprocess."""
    global web_ui_process
    
    try:
        port = config.get('web_ui_port', 5000)
        auto_open = config.get('auto_open_browser', True)
        
        logger.info(f"Starting Web UI on port {port}...")
        
        # Start web_ui.py as subprocess
        cmd = [sys.executable, "web_ui.py"]
        
        try:
            web_ui_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(Path(__file__).parent)
            )
            
            logger.info(f"Web UI started (PID: {web_ui_process.pid})")
            
            # Wait a moment for server to start
            time.sleep(2)
            
            # Open browser if enabled
            if auto_open:
                url = f"http://localhost:{port}"
                logger.info(f"Opening browser at {url}")
                webbrowser.open(url)
            
            return web_ui_process
            
        except Exception as e:
            logger.error(f"Error starting web UI process: {e}")
            return None
            
    except Exception as e:
        logger.error(f"Error starting web UI: {e}")
        return None


def stop_web_ui():
    """Stop the web UI server gracefully."""
    global web_ui_process
    
    try:
        if web_ui_process and web_ui_process.poll() is None:
            logger.info("Stopping Web UI...")
            web_ui_process.terminate()
            
            # Wait for graceful shutdown
            try:
                web_ui_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning("Web UI did not terminate gracefully, forcing...")
                web_ui_process.kill()
                web_ui_process.wait()
            
            logger.info("Web UI stopped")
            
    except Exception as e:
        logger.error(f"Error stopping web UI: {e}")


def run_preprocessing(novel_name, input_file):
    """Run preprocessing on a novel file."""
    try:
        logger.info(f"[PREPROCESS] {novel_name}")
        
        output_file = Path("working_data/clean") / f"{novel_name}_clean.txt"
        
        # Import and run preprocessing
        sys.path.insert(0, str(Path("scripts").absolute()))
        from preprocess_novel import preprocess_novel
        
        result = preprocess_novel(input_file, output_file)
        
        if result['success']:
            logger.info(f"✓ Preprocessing complete: {result['cleaned_length']} chars")
            return str(output_file)
        else:
            raise RuntimeError("Preprocessing failed")
            
    except Exception as e:
        logger.error(f"Preprocessing failed for {novel_name}: {e}")
        raise


def run_chunking(novel_name, clean_file, chapter_based=True):
    """Run chunking on preprocessed novel."""
    try:
        logger.info(f"[CHUNK] {novel_name}")
        logger.info(f"  Chapter-based mode: {chapter_based}")
        
        output_dir = Path("working_data/chunks")
        
        # Import and run chunking
        sys.path.insert(0, str(Path("scripts").absolute()))
        from chunk_text import chunk_text
        
        result = chunk_text(clean_file, output_dir, chapter_based=chapter_based)
        
        if result['success']:
            if result.get('chapter_based'):
                logger.info(f"✓ Chunking complete: {result['total_chapters']} chapters, {result['total_chunks']} total chunks")
            else:
                logger.info(f"✓ Chunking complete: {result['total_chunks']} chunks")
            return result
        else:
            raise RuntimeError("Chunking failed")
            
    except Exception as e:
        logger.error(f"Chunking failed for {novel_name}: {e}")
        raise


def load_translate_module():
    """Load the translate_chunk module dynamically."""
    import importlib.util
    
    # Ensure scripts directory is in path for imports
    scripts_path = str(Path("scripts").absolute())
    if scripts_path not in sys.path:
        sys.path.insert(0, scripts_path)
    
    # Load translate_chunk module
    spec = importlib.util.spec_from_file_location(
        "translate_chunk", 
        Path("scripts/translate_chunk.py")
    )
    translate_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(translate_module)
    
    return translate_module


def translate_single_chunk(translate_module, chunk_file, output_file, novel_name, chunk_num):
    """Translate a single chunk and run readability check."""
    try:
        # Skip if already translated
        if output_file.exists():
            logger.info(f"  Chunk {chunk_num} already translated, skipping")
            return True, 0
        
        # Time the translation
        start_time = time.time()
        
        # Call translate_chunk
        result = translate_module.translate_chunk(
            str(chunk_file),
            str(output_file),
            novel_name=novel_name
        )
        
        if not result['success']:
            logger.error(f"Translation failed for chunk {chunk_num}: {result.get('error', 'Unknown error')}")
            return False, 0
        
        # Calculate timing
        elapsed = time.time() - start_time
        
        logger.info(f"  Translated: {result['output_chars']} chars in {elapsed:.1f}s")
        
        # Run Myanmar readability check
        run_readability_check(str(output_file), novel_name, chunk_num)
        
        return True, elapsed
        
    except Exception as e:
        logger.error(f"Error translating chunk {chunk_num}: {e}")
        return False, 0


def assemble_chapter_markdown(novel_name, chapter_num, chapter_title, translated_chunks_dir, output_file):
    """
    Assemble translated chunks of a chapter into a single Markdown file.
    
    Args:
        novel_name: Name of the novel
        chapter_num: Chapter number
        chapter_title: Chapter title in Chinese (will be translated to Burmese header)
        translated_chunks_dir: Directory containing translated chunk files
        output_file: Path to save the assembled .md file
    """
    try:
        logger.info(f"  Assembling Chapter {chapter_num}: {chapter_title}")
        
        # Find all translated chunks for this chapter
        chunk_files = sorted(Path(translated_chunks_dir).glob(f"{novel_name}_ch{chapter_num:03d}_chunk_*.txt"))
        
        if not chunk_files:
            logger.warning(f"  No translated chunks found for chapter {chapter_num}")
            return False
        
        # Read all chunks
        chapter_content = []
        for chunk_file in chunk_files:
            try:
                with open(chunk_file, 'r', encoding='utf-8') as f:
                    chapter_content.append(f.read())
            except Exception as e:
                logger.error(f"  Error reading chunk {chunk_file}: {e}")
                continue
        
        # Combine content
        full_text = '\n\n'.join(chapter_content)
        
        # Create Markdown with Burmese chapter header
        # Convert chapter number to Burmese numerals
        burmese_digits = '၀၁၂၃၄၅၆၇၈၉'
        burmese_chapter_num = ''.join(burmese_digits[int(d)] for d in str(chapter_num))
        
        # Create markdown content
        markdown_content = f"""# {novel_name} - အခန်း {burmese_chapter_num}

## {chapter_title}

{full_text}

---
*ဤအခန်းကို OpenCode AI Chinese-to-Burmese Translator ဖြင့် ဘာသာပြန်ဆိုခဲ့သည်။*
"""
        
        # Ensure output directory exists
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Write markdown file
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        
        logger.info(f"  ✓ Chapter {chapter_num} saved: {output_file}")
        return True
        
    except Exception as e:
        logger.error(f"  Error assembling chapter {chapter_num}: {e}")
        return False


def run_translation(novel_name, chunk_info, checkpoint=None, chapter_based=True):
    """
    Run translation on all chunks with streaming and progress updates.
    
    This is the core translation loop that:
    - Translates each chunk via Ollama with streaming
    - Saves atomic checkpoints after each chunk
    - Updates web UI with progress
    - Handles graceful shutdown on Ctrl+C
    - If chapter_based=True, saves each chapter as separate .md file after completion
    """
    try:
        translate_module = load_translate_module()
        
        logger.info(f"[TRANSLATE] {novel_name}")
        logger.info(f"  Chapter-based mode: {chapter_based}")
        
        total_chunks = chunk_info['total_chunks']
        chunk_files = chunk_info['chunk_files']
        
        # Determine starting point from checkpoint
        start_chunk = 1
        if checkpoint and checkpoint.get('status') == 'in_progress':
            start_chunk = checkpoint.get('current_chunk', 0) + 1
            logger.info(f"Resuming from chunk {start_chunk}/{total_chunks}")
        
        # Track timing for ETA calculation
        chunk_times = []
        
        # Track chapters for chapter-based assembly
        current_chapter = None
        chapter_completed_chunks = {}
        
        # If chapter-based, get chapter info
        if chapter_based and chunk_info.get('chapter_based'):
            chapters = chunk_info.get('chapters', [])
            # Map chunk files to chapters
            chunk_to_chapter = {}
            for chapter in chapters:
                ch_num = chapter['chapter_number']
                ch_files = chapter['chunk_files']
                for ch_file in ch_files:
                    chunk_to_chapter[ch_file] = {
                        'number': ch_num,
                        'title': chapter['chapter_title'],
                        'dir': chapter['chapter_dir']
                    }
        else:
            chapter_based = False
            chunk_to_chapter = {}
        
        for i in range(start_chunk - 1, total_chunks):
            if shutdown_requested:
                logger.info(f"Shutdown requested, stopping after chunk {i}")
                break
            
            chunk_num = i + 1
            chunk_file = chunk_files[i]
            
            logger.info(f"[CHUNK] {chunk_num}/{total_chunks} ({(chunk_num/total_chunks*100):.1f}%)")
            
            # Determine output path
            if chapter_based:
                # Get chapter info for this chunk
                ch_info = chunk_to_chapter.get(chunk_file)
                if ch_info:
                    translated_dir = Path("working_data/translated_chunks") / novel_name / f"chapter_{ch_info['number']:03d}"
                    current_chapter = ch_info['number']
                    if current_chapter not in chapter_completed_chunks:
                        chapter_completed_chunks[current_chapter] = {'title': ch_info['title'], 'count': 0}
                else:
                    translated_dir = Path("working_data/translated_chunks") / novel_name
            else:
                translated_dir = Path("working_data/translated_chunks") / novel_name
            
            translated_dir.mkdir(parents=True, exist_ok=True)
            
            # Create output filename
            if chapter_based and current_chapter:
                output_file = translated_dir / f"{novel_name}_ch{current_chapter:03d}_chunk_{chunk_num:05d}_burmese.txt"
            else:
                output_file = translated_dir / f"{novel_name}_chunk_{chunk_num:05d}_burmese.txt"
            
            # Translate the chunk
            success, elapsed = translate_single_chunk(
                translate_module, chunk_file, output_file, novel_name, chunk_num
            )
            
            if success:
                chunk_times.append(elapsed)
                if current_chapter:
                    chapter_completed_chunks[current_chapter]['count'] += 1
            else:
                # Continue with next chunk instead of failing entirely
                continue
            
            # Calculate ETA
            if len(chunk_times) > 5:
                chunk_times = chunk_times[-5:]
            if chunk_times:
                avg_time = sum(chunk_times) / len(chunk_times)
                remaining_chunks = total_chunks - chunk_num
                eta_seconds = avg_time * remaining_chunks
                eta_str = str(timedelta(seconds=int(eta_seconds)))
                logger.info(f"  ETA: {eta_str}")
            
            # Save checkpoint atomically after each chunk
            checkpoint_data = {
                'novel_name': novel_name,
                'status': 'in_progress',
                'current_chunk': chunk_num,
                'total_chunks': total_chunks,
                'last_updated': datetime.now().isoformat(),
                f'chunk_{chunk_num}_done': True
            }
            
            save_checkpoint_atomic(novel_name, checkpoint_data)
            
            # Check if shutdown was requested during this chunk
            if shutdown_requested:
                logger.info(f"Checkpoint saved at chunk {chunk_num}. Exiting gracefully...")
                return False  # Indicate incomplete
        
        # All chunks complete
        if not shutdown_requested:
            # If chapter-based, assemble each chapter into separate .md files
            if chapter_based and chunk_info.get('chapter_based'):
                logger.info("[ASSEMBLE CHAPTERS] Saving each chapter as separate .md file")
                for chapter in chunk_info.get('chapters', []):
                    ch_num = chapter['chapter_number']
                    ch_title = chapter['chapter_title']
                    ch_dir = chapter['chapter_dir']
                    
                    # Determine output file path
                    chapter_md_file = Path("translated_novels") / novel_name / f"{novel_name}_chapter_{ch_num:03d}.md"
                    
                    # Assemble this chapter
                    assemble_chapter_markdown(
                        novel_name, ch_num, ch_title, 
                        Path("working_data/translated_chunks") / novel_name / f"chapter_{ch_num:03d}",
                        chapter_md_file
                    )
            
            checkpoint_data = {
                'novel_name': novel_name,
                'status': 'completed',
                'current_chunk': total_chunks,
                'total_chunks': total_chunks,
                'completed_at': datetime.now().isoformat()
            }
            save_checkpoint_atomic(novel_name, checkpoint_data)
            logger.info(f"✓ Translation complete: {total_chunks} chunks")
            return True
        else:
            return False
            
    except Exception as e:
        logger.error(f"Translation failed for {novel_name}: {e}")
        raise


def run_readability_check(translated_file, novel_name, chunk_num):
    """Run Myanmar readability check on a translated chunk."""
    try:
        import importlib.util
        
        # Ensure scripts directory is in path for imports
        scripts_path = str(Path("scripts").absolute())
        if scripts_path not in sys.path:
            sys.path.insert(0, scripts_path)
        
        # Load myanmar_checker module
        spec = importlib.util.spec_from_file_location(
            "myanmar_checker",
            Path("scripts/myanmar_checker.py")
        )
        checker_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(checker_module)
        
        # Run check
        results = checker_module.check_file(translated_file)
        
        status = "PASS" if results['passed'] else "FLAGGED"
        
        # Log detailed results
        myanmar_ratio = results['checks'].get('myanmar_ratio', {}).get('value', 0)
        sentence_count = results['checks'].get('sentence_boundaries', {}).get('value', 0)
        
        logger.info(f"  [CHECKER] Chunk {chunk_num} → {status} (Myanmar: {myanmar_ratio:.1%}, Sentences: {sentence_count})")
        
        return results
        
    except Exception as e:
        logger.error(f"Readability check failed for chunk {chunk_num}: {e}")
        # Non-fatal, continue with translation
        return None


def run_postprocessing(novel_name):
    """Run post-processing on translated chunks."""
    try:
        logger.info(f"[POSTPROCESS] {novel_name}")
        
        import importlib.util
        
        # Ensure scripts directory is in path for imports
        scripts_path = str(Path("scripts").absolute())
        if scripts_path not in sys.path:
            sys.path.insert(0, scripts_path)
        
        # Load postprocess_translation module
        spec = importlib.util.spec_from_file_location(
            "postprocess_translation",
            Path("scripts/postprocess_translation.py")
        )
        postprocess_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(postprocess_module)
        
        # Run post-processing
        result = postprocess_module.postprocess_novel(novel_name)
        
        if result['success']:
            logger.info(f"✓ Post-processing complete: {result['processed']}/{result['total_chunks']} chunks")
            return True
        else:
            logger.warning(f"Post-processing completed with {len(result['errors'])} errors")
            return True  # Continue even with errors
            
    except Exception as e:
        logger.error(f"Post-processing failed for {novel_name}: {e}")
        # Non-fatal, continue
        return True


def run_assembly(novel_name):
    """Run final assembly of translated chunks."""
    try:
        logger.info(f"[ASSEMBLE] {novel_name}")
        
        import importlib.util
        
        # Ensure scripts directory is in path for imports
        scripts_path = str(Path("scripts").absolute())
        if scripts_path not in sys.path:
            sys.path.insert(0, scripts_path)
        
        # Load assemble_novel module
        spec = importlib.util.spec_from_file_location(
            "assemble_novel",
            Path("scripts/assemble_novel.py")
        )
        assemble_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(assemble_module)
        
        # Run assembly
        result = assemble_module.assemble_novel(novel_name)
        
        if result['success']:
            logger.info(f"✓ Assembly complete: {result['output_file']}")
            logger.info(f"  - {result['character_count']:,} characters")
            return result['output_file']
        else:
            raise RuntimeError("Assembly failed")
            
    except Exception as e:
        logger.error(f"Assembly failed for {novel_name}: {e}")
        raise


def process_novel(novel_info, config, chapter_based=True):
    """
    Process a single novel through the entire pipeline.
    
    Pipeline order:
    1. Preprocess → Clean text, enforce UTF-8
    2. Chunk → Split into overlapping chunks (by chapters if chapter_based=True)
    3. Translate → Ollama with streaming
    4. Check → Myanmar readability validation
    5. Postprocess → Fix punctuation & consistency
    6. Assemble → Merge into final .md (or save chapters separately if chapter_based)
    
    Args:
        novel_info: Dictionary with novel information
        config: Configuration dictionary
        chapter_based: If True, process chapters separately and save each as .md file
    """
    global shutdown_requested
    
    novel_name = novel_info['name']
    input_file = novel_info['file']
    status = novel_info['status']
    
    logger.info("=" * 60)
    logger.info(f"Processing: {novel_name}")
    logger.info(f"Status: {status}")
    logger.info(f"Chapter-based mode: {chapter_based}")
    logger.info("=" * 60)
    
    try:
        # Load checkpoint if resuming
        checkpoint = None
        if status == 'resuming':
            checkpoint = load_checkpoint(novel_name)
            logger.info(f"Resuming from chunk {checkpoint.get('current_chunk', 0)}")
        
        # Step 1: Preprocess (skip if resuming and already preprocessed)
        clean_file = Path("working_data/clean") / f"{novel_name}_clean.txt"
        
        if checkpoint and checkpoint.get('preprocessing_done'):
            logger.info("Preprocessing already done, skipping")
        else:
            clean_file = run_preprocessing(novel_name, input_file)
            
            # Save checkpoint
            if checkpoint is None:
                checkpoint = {'novel_name': novel_name, 'status': 'in_progress'}
            checkpoint['preprocessing_done'] = True
            save_checkpoint_atomic(novel_name, checkpoint)
        
        if shutdown_requested:
            return False
        
        # Step 2: Chunk (skip if resuming and already chunked)
        chunks_dir = Path("working_data/chunks") / novel_name
        chunk_info_file = chunks_dir / f"{novel_name}_chunks.json"
        
        if checkpoint and checkpoint.get('chunking_done') and chunk_info_file.exists():
            logger.info("Chunking already done, loading chunk info...")
            with open(chunk_info_file, 'r', encoding='utf-8') as f:
                chunk_info = json.load(f)
        else:
            chunk_info = run_chunking(novel_name, clean_file, chapter_based=chapter_based)
            
            # Save checkpoint
            checkpoint['chunking_done'] = True
            checkpoint['total_chunks'] = chunk_info['total_chunks']
            if chunk_info.get('chapter_based'):
                checkpoint['chapter_based'] = True
                checkpoint['total_chapters'] = chunk_info.get('total_chapters', 1)
            save_checkpoint_atomic(novel_name, checkpoint)
        
        if shutdown_requested:
            return False
        
        # Step 3: Translate with streaming and checkpointing
        translation_complete = run_translation(novel_name, chunk_info, checkpoint, chapter_based=chunk_info.get('chapter_based', False))
        
        if not translation_complete:
            logger.info(f"Translation paused for {novel_name}")
            return False  # Will resume on next run
        
        if shutdown_requested:
            return False
        
        # Step 4: Myanmar readability check
        # (Already done during translation)
        logger.info("[CHECK] Myanmar readability validation complete")
        
        if shutdown_requested:
            return False
        
        # Step 5 & 6: Post-processing and Assembly
        if chunk_info.get('chapter_based'):
            # For chapter-based processing, assembly is already done during translation
            # Each chapter is saved as a separate .md file
            logger.info("[COMPLETE] Chapters saved as separate .md files")
            output_file = f"translated_novels/{novel_name}/ (chapter files)"
        else:
            # Regular processing - run postprocess and assembly
            run_postprocessing(novel_name)
            
            if shutdown_requested:
                return False
            
            output_file = run_assembly(novel_name)
        
        # Mark as completed
        checkpoint_data = {
            'novel_name': novel_name,
            'status': 'completed',
            'output_file': output_file,
            'completed_at': datetime.now().isoformat()
        }
        save_checkpoint_atomic(novel_name, checkpoint_data)
        
        logger.info("=" * 60)
        logger.info(f"✓ COMPLETE: {novel_name}")
        logger.info(f"  Output: {output_file}")
        logger.info("=" * 60)
        
        return True
        
    except Exception as e:
        logger.error(f"=" * 60)
        logger.error(f"✗ FAILED: {novel_name}")
        logger.error(f"  Error: {e}")
        logger.error(f"=" * 60)
        return False


def main():
    """
    Main entry point - orchestrates the entire translation pipeline.
    """
    global shutdown_requested, web_ui_process
    
    try:
        logger.info("=" * 60)
        logger.info("Chinese-to-Burmese Novel Translation Pipeline")
        logger.info("=" * 60)
        
        # Load configuration
        config = load_config()
        logger.info(f"Loaded configuration from config/config.json")
        
        # Ensure directory structure
        ensure_directories()
        
        # Scan input novels
        logger.info("[SCAN] Scanning input_novels/ for .txt files...")
        novels = scan_input_novels()
        
        if not novels:
            logger.warning("No novels found in input_novels/")
            logger.info("Please place .txt files in input_novels/ directory")
            return
        
        logger.info(f"Found {len(novels)} novel(s):")
        
        # Print status for each novel
        for novel in novels:
            status_symbol = {
                'done': '✓',
                'resuming': '↻',
                'new': '✎'
            }.get(novel['status'], '?')
            
            logger.info(f"  [{status_symbol}] {novel['name']}: {novel['status']}")
        
        # Filter to novels needing translation
        novels_to_translate = [n for n in novels if n['status'] != 'done']
        
        if not novels_to_translate:
            logger.info("All novels are already translated!")
            return
        
        logger.info(f"\n{len(novels_to_translate)} novel(s) to translate")
        
        # Start web UI
        web_ui_process = start_web_ui(config)
        
        # Process each novel
        successful = 0
        failed = 0
        
        for novel in novels_to_translate:
            if shutdown_requested:
                logger.info("Shutdown requested, stopping after current novel")
                break
            
            try:
                success = process_novel(novel, config)
                if success:
                    successful += 1
                else:
                    failed += 1
                    if shutdown_requested:
                        break
            except Exception as e:
                logger.error(f"Failed to process {novel['name']}: {e}")
                failed += 1
        
        # Final summary
        logger.info("=" * 60)
        logger.info("Pipeline Summary")
        logger.info("=" * 60)
        logger.info(f"Total novels: {len(novels)}")
        logger.info(f"  - Already done: {len([n for n in novels if n['status'] == 'done'])}")
        logger.info(f"  - Processed now: {len(novels_to_translate)}")
        logger.info(f"    - Successful: {successful}")
        logger.info(f"    - Failed: {failed}")
        
        if shutdown_requested:
            logger.info("\n⚠ Pipeline stopped by user (Ctrl+C)")
            logger.info("Run again to resume from checkpoint")
        else:
            logger.info("\n✓ Pipeline complete!")
        
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Fatal error in main pipeline: {e}")
        sys.exit(1)
    finally:
        # Cleanup
        stop_web_ui()
        
        # Final checkpoint save if shutdown was requested
        if shutdown_requested and current_checkpoint:
            logger.info("Final checkpoint save...")
            # Already saved per-chunk, but ensure state is consistent


if __name__ == "__main__":
    main()
