#!/usr/bin/env python3
"""
Translate Chinese text chunks to Burmese using Ollama with streaming support.

This script calls Ollama with stream=True.

Usage:
    python scripts/translate_chunk.py <chunk_file> <output_file>
    python scripts/translate_chunk.py working_data/chunks/my_novel/my_novel_chunk_00001.txt working_data/translated_chunks/my_novel/my_novel_chunk_00001_burmese.txt
"""

import os
import sys
import json
import time
import logging
import argparse
import signal
import re
from pathlib import Path
from typing import Optional, Dict, Any

# Import ollama at module level (not inside function)
try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    logging.getLogger(__name__).error("Ollama Python client not installed. Run: pip install ollama")

# Setup logging
LOG_DIR = Path("working_data/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Create logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Only add handlers if they don't exist (prevents duplicate logs when module reloads)
if not logger.handlers:
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler
    file_handler = logging.FileHandler(LOG_DIR / "translate.log", encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

# Global flag for graceful shutdown
shutdown_requested = False


def signal_handler(signum, frame):
    """Handle Ctrl+C for graceful shutdown."""
    global shutdown_requested
    logger.info("Shutdown signal received, will save checkpoint and exit after current chunk...")
    shutdown_requested = True


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


def load_checkpoint(novel_name):
    """Load checkpoint for a novel if it exists."""
    checkpoint_path = Path("working_data/checkpoints") / f"{novel_name}.json"
    
    try:
        if checkpoint_path.exists():
            with open(checkpoint_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading checkpoint: {e}")
    
    return None


def save_checkpoint_atomic(novel_name, checkpoint_data):
    """Save checkpoint atomically to prevent corruption."""
    checkpoint_dir = Path("working_data/checkpoints")
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    
    checkpoint_path = checkpoint_dir / f"{novel_name}.json"
    temp_path = checkpoint_dir / f"{novel_name}.json.tmp"
    
    try:
        # Write to temp file first
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(checkpoint_data, f, ensure_ascii=False, indent=2)
        
        # Atomic rename
        temp_path.replace(checkpoint_path)
        
        logger.info(f"Checkpoint saved atomically: {checkpoint_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error saving checkpoint: {e}")
        # Clean up temp file if it exists
        try:
            if temp_path.exists():
                temp_path.unlink()
        except Exception:
            pass
        return False


def update_preview_file(novel_name, token, mode='a'):
    """Update the live preview file with a new token."""
    try:
        preview_dir = Path("working_data/preview")
        preview_dir.mkdir(parents=True, exist_ok=True)
        
        preview_path = preview_dir / f"{novel_name}_preview.md"
        
        with open(preview_path, mode, encoding='utf-8') as f:
            f.write(token)
            
    except Exception as e:
        logger.error(f"Error updating preview file: {e}")


def translate_with_ollama(text, config, novel_name):
    """
    Translate text using Ollama with streaming support.
    
    Args:
        text: Chinese text to translate
        config: Configuration dictionary
        novel_name: Name of the novel for progress tracking
        socketio_url: Optional SocketIO server URL
        
    Returns:
        Tuple of (translated_text, success_boolean)
    """
    if not OLLAMA_AVAILABLE:
        logger.error("Ollama Python client not installed. Run: pip install ollama")
        return "", False
    
    try:
        model = config.get('model', 'qwen3:7b')
        stream = config.get('stream', True)
        timeout = config.get('request_timeout', 900)
        preview_every = config.get('preview_update_every_n_tokens', 10)
        
        # Build the prompt according to SKILL.md template
        system_prompt = """You are a professional literary translator.
Translate the following Chinese novel text to Burmese (Myanmar script).
Keep the tone, style, and emotions of the original.
Do NOT add chapter titles, headings, or explanations.
Output ONLY the Burmese translation. No Chinese characters. No romanization."""
        
        user_prompt = text
        
        logger.info(f"Calling Ollama model: {model}")
        logger.info(f"Input text length: {len(text)} characters")
        
        translated_text = ""
        token_count = 0
        
        # Call Ollama with streaming
        try:
            response = ollama.generate(
                model=model,
                system=system_prompt,
                prompt=user_prompt,
                stream=stream,
                options={
                    'temperature': 0.3,
                    'num_predict': -1,
                }
            )
            
            if stream:
                # Handle streaming response
                for chunk in response:
                    if shutdown_requested:
                        logger.info("Shutdown requested, stopping translation stream")
                        break
                    
                    # Extract token from chunk
                    token = chunk.get('response', '')
                    
                    if token:
                        translated_text += token
                        token_count += 1
                        
                        
                        # Update preview file every N tokens
                        if token_count % preview_every == 0:
                            update_preview_file(novel_name, token)
                            
            else:
                # Non-streaming response
                translated_text = response.get('response', '')
                update_preview_file(novel_name, translated_text)
                
        except Exception as e:
            logger.error(f"Error during Ollama streaming: {e}")
            raise
        
        # Flush remaining tokens to preview
        if translated_text and stream:
            # Ensure all remaining content is written
            remaining = translated_text[token_count - (token_count % preview_every):]
            if remaining:
                update_preview_file(novel_name, remaining)
        
        logger.info(f"Translation complete: {len(translated_text)} characters ({token_count} tokens)")
        
        return translated_text, True
        
    except Exception as e:
        logger.error(f"Error translating with Ollama: {e}")
        return "", False


def translate_chunk(chunk_file, output_file, novel_name=None, max_retries=3):
    """
    Translate a single chunk file.
    
    Args:
        chunk_file: Path to Chinese chunk file
        output_file: Path to save translated Burmese text
        novel_name: Name of the novel (auto-detected if None)
        socketio_url: Optional SocketIO server URL
        max_retries: Maximum number of retry attempts
        
    Returns:
        Dictionary with translation results
    """
    try:
        chunk_path = Path(chunk_file)
        output_path = Path(output_file)
        
        # Auto-detect novel name if not provided
        if novel_name is None:
            novel_name = chunk_path.stem.rsplit('_chunk_', 1)[0]
        
        logger.info(f"Translating chunk: {chunk_path}")
        logger.info(f"Novel: {novel_name}")
        
        # Load config
        config = load_config()
        
        # Read chunk file
        try:
            with open(chunk_path, 'r', encoding='utf-8') as f:
                text = f.read()
        except Exception as e:
            logger.error(f"Error reading chunk file: {e}")
            raise
        
        if not text.strip():
            raise ValueError("Chunk file is empty")
        
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize preview file
        preview_dir = Path("working_data/preview")
        preview_dir.mkdir(parents=True, exist_ok=True)
        preview_path = preview_dir / f"{novel_name}_preview.md"
        
        # Try translation with retries
        translated_text = None
        success = False
        
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"Translation attempt {attempt}/{max_retries}")
                
                translated_text, success = translate_with_ollama(
                    text, config, novel_name
                )
                
                if success and translated_text.strip():
                    break
                    
                if shutdown_requested:
                    logger.info("Shutdown requested, aborting retries")
                    break
                    
            except Exception as e:
                logger.error(f"Translation attempt {attempt} failed: {e}")
                
                if attempt < max_retries and not shutdown_requested:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.info(f"Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
        
        if not success or not translated_text:
            raise RuntimeError(f"Translation failed after {max_retries} attempts")
        
        # Write translated text to output
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(translated_text)
            logger.info(f"Saved translation to: {output_path}")
        except Exception as e:
            logger.error(f"Error saving translation: {e}")
            raise
        
        
        return {
            'success': True,
            'novel_name': novel_name,
            'chunk_file': str(chunk_path),
            'output_file': str(output_path),
            'input_chars': len(text),
            'output_chars': len(translated_text),
            'shutdown_requested': shutdown_requested
        }
        
    except Exception as e:
        logger.error(f"Error translating chunk: {e}")
        return {
            'success': False,
            'novel_name': novel_name,
            'chunk_file': str(chunk_file),
            'error': str(e),
            'shutdown_requested': shutdown_requested
        }


def main():
    """Command line entry point."""
    parser = argparse.ArgumentParser(
        description='Translate Chinese text chunks to Burmese using Ollama'
    )
    parser.add_argument('chunk_file', help='Path to Chinese chunk file')
    parser.add_argument('output_file', help='Path to save translated Burmese text')
    parser.add_argument('--novel-name', help='Name of the novel (auto-detected if not provided)')
    parser.add_argument('--max-retries', type=int, default=3, help='Maximum retry attempts')
    
    args = parser.parse_args()
    
    try:
        result = translate_chunk(
            args.chunk_file,
            args.output_file,
            args.novel_name,
            args.max_retries
        )
        
        if result['success']:
            print(f"✓ Translation complete: {result['output_chars']} characters")
            sys.exit(0)
        else:
            print(f"✗ Translation failed: {result.get('error', 'Unknown error')}")
            sys.exit(1)
            
    except Exception as e:
        print(f"✗ Translation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
