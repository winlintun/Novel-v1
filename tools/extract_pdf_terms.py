#!/usr/bin/env python3
"""
Tool to extract terminology and context from parallel English MD and Myanmar PDF files.
Requires PyMuPDF: pip install PyMuPDF

Usage with Ollama (local):
    python tools/extract_pdf_terms.py --pdf Reverend_Insanity_1_800.pdf --md-dir data/input/reverend-insanity/ --start 1 --end 800

Usage with Gemini API (fast, cloud):
    python tools/extract_pdf_terms.py --pdf Reverend_Insanity_1_800.pdf --md-dir data/input/reverend-insanity/ --start 1 --end 800 --provider gemini --api-key YOUR_API_KEY
"""

import os
import re
import sys
import json
import logging
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional

# Ensure we can import from src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import fitz  # PyMuPDF
except ImportError:
    print("PyMuPDF is required. Installing it now...")
    os.system("pip install PyMuPDF")
    import fitz

from src.utils.ollama_client import OllamaClient
from src.utils.json_extractor import safe_parse_terms
from src.memory.memory_manager import MemoryManager
from src.utils.file_handler import FileHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

ALIGNMENT_PROMPT = """You are an expert bilingual terminology extractor.
I will give you an English text and its Myanmar (Burmese) translation.
Your task is to identify key terminology (characters, places, items, cultivation levels) from the English text and find their EXACT matching translation in the Myanmar text.

RULES:
1. Output ONLY valid JSON. No prose, no markdown formatting.
2. Format: {{"new_terms": [{{"source": "English Term", "target": "Myanmar Term", "category": "character|place|level|item"}}]}}
3. The 'target' MUST be extracted exactly as it appears in the provided Myanmar text.
4. If you cannot confidently find the match, skip the term.

ENGLISH TEXT:
{english_text}

MYANMAR TRANSLATION:
{myanmar_text}

JSON OUTPUT:"""

SUMMARY_PROMPT = """Summarize the key events and plot points of this chapter in 3-5 sentences.
Focus on character progression, items acquired, and locations visited.

TEXT:
{text}

SUMMARY:"""


class GeminiClient:
    """Simple client for Google Gemini API."""
    
    # Known working model names for Gemini API
    VALID_MODELS = {
        "gemini-1.5-flash": "gemini-1.5-flash",
        "gemini-1.5-flash-latest": "gemini-1.5-flash-latest",
        "gemini-1.5-pro": "gemini-1.5-pro",
        "gemini-1.5-pro-latest": "gemini-1.5-pro-latest",
        "gemini-1.0-pro": "gemini-1.0-pro",
        "gemini-pro": "gemini-pro",
        "gemini-1.5-flash-001": "gemini-1.5-flash-001",
        "gemini-1.5-flash-002": "gemini-1.5-flash-002",
        "gemini-1.5-pro-001": "gemini-1.5-pro-001",
        "gemini-1.5-pro-002": "gemini-1.5-pro-002",
    }
    
    def __init__(self, api_key: str, model: str = "gemini-1.5-flash"):
        self.api_key = api_key
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        
        # Normalize model name
        if model in self.VALID_MODELS:
            self.model = self.VALID_MODELS[model]
        else:
            # Use model name as-is without models/ prefix
            self.model = model.replace("models/", "")
        
        logger.info(f"GeminiClient initialized with model: {self.model}")
        
        # List available models on init to help debugging
        self._list_models()
        
    def _list_models(self):
        """List available models from Gemini API."""
        import requests
        
        url = f"{self.base_url}/models?key={self.api_key}"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                models = [m.get("name", "").replace("models/", "") for m in data.get("models", [])]
                # Filter for models that support generateContent
                supported = [m for m in models if "gemini" in m.lower()]
                logger.info(f"Available Gemini models: {supported[:5]}...")
                return supported
            else:
                logger.warning(f"Could not list models: {response.status_code}")
                return []
        except Exception as e:
            logger.warning(f"Could not list models: {e}")
            return []
        
    def chat(self, prompt: str, temperature: float = 0.3) -> str:
        """Send a chat request to Gemini API."""
        import requests
        
        # Construct URL without models/ prefix
        url = f"{self.base_url}/models/{self.model}:generateContent?key={self.api_key}"
        
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": 4096,
            }
        }
        
        try:
            response = requests.post(url, json=payload, timeout=60)
            
            # Log the response status for debugging
            if response.status_code != 200:
                logger.error(f"API Error {response.status_code}: {response.text[:500]}")
            
            response.raise_for_status()
            
            data = response.json()
            
            # Extract text from response
            if "candidates" in data and len(data["candidates"]) > 0:
                candidate = data["candidates"][0]
                if "content" in candidate and "parts" in candidate["content"]:
                    text_parts = [part["text"] for part in candidate["content"]["parts"] if "text" in part]
                    return "\n".join(text_parts)
            
            logger.warning(f"Unexpected Gemini response format: {data}")
            return ""
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Gemini API request failed: {e}")
            raise
    
    def cleanup(self):
        """No-op for Gemini (no local resources to cleanup)."""
        pass
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
        return False


def extract_pdf_chapters(pdf_path: str) -> Dict[int, str]:
    """
    Naively extract chapter texts from a PDF using page markers or regex.
    This uses a heuristic looking for "Chapter" or "အခန်း" to split chapters.
    """
    logger.info(f"Opening PDF: {pdf_path}")
    doc = fitz.open(pdf_path)
    full_text = ""
    
    # Read all text first
    for page in doc:
        full_text += page.get_text("text") + "\n"
    
    # Attempt to split by chapter headers
    # Matches patterns like "Chapter 1", "Chapter 01", "အခန်း ၁", "အခန်း (၁)"
    # This regex is a heuristic and might need adjustment based on the exact PDF formatting.
    chapter_splits = re.split(r'\n(?=Chapter\s*\d+|အခန်း\s*[\d၁၂၃၄၅၆၇၈၉၀]+)', full_text, flags=re.IGNORECASE)
    
    chapters = {}
    current_chapter = 1
    
    # Process splits
    for chunk in chapter_splits:
        if not chunk.strip():
            continue
        
        # Try to infer chapter number from the chunk header
        header_match = re.match(r'(?:Chapter|အခန်း)\s*([0-9၁-၉]+)', chunk.strip(), flags=re.IGNORECASE)
        if header_match:
            # Convert Myanmar numerals to Western if necessary, or just rely on sequential counting
            # For simplicity, we just use sequential counting assuming the chunks are in order
            pass
            
        chapters[current_chapter] = chunk.strip()
        current_chapter += 1
        
    logger.info(f"Extracted approximately {len(chapters)} chapters from PDF.")
    return chapters


def append_to_pending_glossary(new_terms: List[Dict[str, str]], chapter_num: int):
    """
    Appends extracted terms to data/glossary_pending.json.
    Adheres to the strict project rule: New terms NEVER go directly to glossary.json.
    """
    pending_path = "data/glossary_pending.json"
    
    pending_data = {"pending_terms": []}
    if os.path.exists(pending_path):
        pending_data = FileHandler.read_json(pending_path) or pending_data
        
    added = 0
    existing_sources = {t.get("source", "").lower() for t in pending_data.get("pending_terms", [])}
    
    for term in new_terms:
        src = term.get("source", "")
        tgt = term.get("target", "")
        cat = term.get("category", "general")
        
        if src and tgt and src.lower() not in existing_sources:
            pending_data["pending_terms"].append({
                "source": src,
                "target": tgt,
                "category": cat,
                "extracted_from_chapter": chapter_num,
                "status": "pending"
            })
            existing_sources.add(src.lower())
            added += 1
            
    if added > 0:
        FileHandler.write_json(pending_path, pending_data)
        logger.info(f"Added {added} new terms to glossary_pending.json from Chapter {chapter_num}.")


def process_chapter(
    client, 
    memory_manager: MemoryManager,
    chapter_num: int, 
    english_text: str, 
    myanmar_text: str
):
    """Process a single chapter: extract terms and update context."""
    logger.info(f"Processing Chapter {chapter_num} (English len: {len(english_text)}, Myanmar len: {len(myanmar_text)})")
    
    # 1. Term Extraction
    # We take a chunk of both to avoid context length limits, or we could pass the whole thing
    # Qwen 14B handles up to 128k tokens, so a typical chapter is well within limits.
    # To be safe, we'll limit to first 10,000 chars of each to catch main introductions.
    prompt = ALIGNMENT_PROMPT.format(
        english_text=english_text[:10000],
        myanmar_text=myanmar_text[:10000]
    )
    
    try:
        response = client.chat(prompt)
        data = safe_parse_terms(response)
        new_terms = data.get("new_terms", [])
        
        if new_terms:
            append_to_pending_glossary(new_terms, chapter_num)
        else:
            logger.info("No terms extracted.")
    except Exception as e:
        logger.error(f"Failed to extract terms for Chapter {chapter_num}: {e}")
        
    # 2. Context Update
    # Summarize the English text (easier for the model than summarizing the Myanmar text directly)
    summary_prompt = SUMMARY_PROMPT.format(text=english_text[:8000])
    try:
        summary_response = client.chat(summary_prompt)
        
        # Update memory manager
        memory_manager.update_chapter_context(chapter_num, summary_response.strip())
        logger.info(f"Updated context memory for Chapter {chapter_num}.")
        
    except Exception as e:
        logger.error(f"Failed to generate summary for Chapter {chapter_num}: {e}")


def create_client(args) -> Any:
    """Create appropriate client based on provider."""
    if args.provider == "gemini":
        if not args.api_key:
            logger.error("Gemini API key is required when using --provider gemini")
            logger.error("Get a free API key from: https://aistudio.google.com/app/apikey")
            sys.exit(1)
        logger.info(f"Using Gemini API with model: {args.gemini_model}")
        return GeminiClient(api_key=args.api_key, model=args.gemini_model)
    else:
        logger.info(f"Using Ollama with model: {args.model}")
        return OllamaClient(model=args.model, unload_on_cleanup=True)


def main():
    parser = argparse.ArgumentParser(
        description="Extract terms and context from English MD and Myanmar PDF.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Using Ollama (local, default):
  python tools/extract_pdf_terms.py --pdf book.pdf --md-dir data/input/book/ --start 1 --end 100

  # Using Gemini API (fast, cloud - RECOMMENDED for bulk processing):
  python tools/extract_pdf_terms.py --pdf book.pdf --md-dir data/input/book/ --start 1 --end 100 \\
      --provider gemini --api-key YOUR_API_KEY

  # Using specific Gemini model:
  python tools/extract_pdf_terms.py --pdf book.pdf --md-dir data/input/book/ --start 1 --end 100 \\
      --provider gemini --api-key YOUR_API_KEY --gemini-model gemini-2.5-flash
        """
    )
    parser.add_argument("--pdf", required=True, help="Path to the Myanmar translated PDF.")
    parser.add_argument("--md-dir", required=True, help="Directory containing English markdown files.")
    parser.add_argument("--start", type=int, default=1, help="Chapter to start from.")
    parser.add_argument("--end", type=int, default=800, help="Chapter to end at.")
    
    # Provider selection
    parser.add_argument("--provider", type=str, default="ollama", 
                       choices=["ollama", "gemini"],
                       help="AI provider to use (default: ollama)")
    parser.add_argument("--api-key", type=str, 
                       help="API key for the selected provider (required for gemini)")
    
    # Ollama options
    parser.add_argument("--model", type=str, default="qwen2.5:14b", 
                       help="Ollama model to use (default: qwen2.5:14b)")
    
    # Gemini options
    parser.add_argument("--gemini-model", type=str, default="gemini-2.5-flash",
                       help="Gemini model to use (default: gemini-2.5-flash)")
    
    args = parser.parse_args()

    # Verify paths
    if not os.path.exists(args.pdf):
        logger.error(f"PDF file not found: {args.pdf}")
        sys.exit(1)
    if not os.path.exists(args.md_dir):
        logger.error(f"MD directory not found: {args.md_dir}")
        sys.exit(1)

    # Initialize Managers
    memory_manager = MemoryManager()
    
    # Extract PDF text
    pdf_chapters = extract_pdf_chapters(args.pdf)
    
    # Find MD files
    md_files = sorted([f for f in os.listdir(args.md_dir) if f.endswith(".md")])
    
    # Create appropriate client
    with create_client(args) as client:
        
        logger.info(f"Starting extraction from Chapter {args.start} to {args.end}")
        
        for chapter_num in range(args.start, args.end + 1):
            
            # Map chapter_num to MD file (assuming format like reverend-insanity_0001.md)
            md_file = next((f for f in md_files if f"{chapter_num:04d}" in f), None)
            
            if not md_file:
                logger.warning(f"Could not find Markdown file for Chapter {chapter_num}. Skipping.")
                continue
                
            # Naive mapping: The PDF extraction might not align perfectly by chapter_num index
            # If the PDF extraction gave us sequential chapters, we map index to index
            pdf_text = pdf_chapters.get(chapter_num)
            
            if not pdf_text:
                logger.warning(f"Could not find PDF text chunk for Chapter {chapter_num}. Skipping.")
                continue
                
            md_path = os.path.join(args.md_dir, md_file)
            try:
                with open(md_path, 'r', encoding='utf-8-sig') as f:
                    english_text = f.read()
            except Exception as e:
                logger.error(f"Could not read {md_path}: {e}")
                continue
                
            process_chapter(client, memory_manager, chapter_num, english_text, pdf_text)

    logger.info("Extraction completed.")


if __name__ == "__main__":
    main()
