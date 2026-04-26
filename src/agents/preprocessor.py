#!/usr/bin/env python3
"""
Preprocessor Agent
Splits text into chunks, cleans markdown, prepares for translation.
"""

import re
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

from src.utils.file_handler import FileHandler
from src.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class Preprocessor(BaseAgent):
    """
    Preprocesses novel chapters for translation.
    - Splits into paragraphs
    - Creates chunks with overlap
    - Preserves markdown formatting
    """
    
    def __init__(
        self,
        chunk_size: int = 1500,
        overlap_size: int = 100,
        ollama_client: Optional[Any] = None,
        memory_manager: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        super().__init__(ollama_client, memory_manager, config)
        self.chunk_size = chunk_size
        self.overlap_size = overlap_size
    
    def detect_language(self, text: str) -> str:
        """Detect language of input text (chinese, english, or unknown).
        
        Uses simple character analysis:
        - Chinese: high count of CJK characters or common Chinese particles
        - English: high count of ASCII letters
        - unknown: default fallback
        """
        if not text or len(text.strip()) < 50:
            return "unknown"
        
        text_sample = text[:500]
        
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text_sample))
        ascii_letters = sum(1 for c in text_sample if c.isascii() and c.isalpha())
        
        chinese_particles = ["的", "是", "我", "你", "他", "在", "有", "个", "来", "不", "到", "这", "那"]
        particle_count = sum(1 for p in chinese_particles if p in text_sample[:100])
        
        if chinese_chars > 10 or particle_count >= 3:
            return "chinese"
        elif ascii_letters > 100:
            return "english"
        else:
            return "unknown"
    
    def _llm_detect_language(self, client: Optional[Any] = None, text: str = "english") -> str:
        """Fallback language detection using LLM (slower but more accurate)."""
        if client is None:
            return "english"
        
        prompt = f"""Detect the source language of this text. Answer only with one word: 'chinese' or 'english'.

Text: {text[:300]}
Language:"""
        try:
            result = client.generate(prompt)
            return result.strip().lower()
        except Exception:
            return "english"
    
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for Chinese text."""
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        other_chars = len(text) - chinese_chars
        return int(chinese_chars * 1.5 + other_chars * 0.5)
    
    def split_into_paragraphs(self, text: str) -> List[str]:
        """Split text into paragraphs preserving structure."""
        # Split on double newlines
        paragraphs = []
        
        for block in text.split('\n\n'):
            block = block.strip()
            if block:
                paragraphs.append(block)
        
        return paragraphs
    
    def create_chunks(self, text: str) -> List[Dict[str, Any]]:
        """
        Create chunks from text with sliding window overlap.
        
        Returns list of dicts with:
        - chunk_id: int
        - text: str
        - size: int (estimated tokens)
        """
        paragraphs = self.split_into_paragraphs(text)
        
        if not paragraphs:
            return []
        
        chunks = []
        current_chunk = []
        current_size = 0
        
        for para in paragraphs:
            para_size = self.estimate_tokens(para)
            
            # Check if adding this paragraph exceeds chunk size
            if current_size + para_size > self.chunk_size and current_chunk:
                # Save current chunk
                chunk_text = '\n\n'.join(current_chunk)
                chunks.append({
                    'chunk_id': len(chunks) + 1,
                    'text': chunk_text,
                    'size': current_size
                })
                
                # Create overlap for next chunk (last paragraph or two)
                overlap_paras = current_chunk[-2:] if len(current_chunk) >= 2 else [current_chunk[-1]]
                overlap_text = '\n\n'.join(overlap_paras)
                
                current_chunk = [overlap_text, para]
                current_size = self.estimate_tokens(overlap_text) + para_size
            else:
                current_chunk.append(para)
                current_size += para_size
        
        # Don't forget the last chunk
        if current_chunk:
            chunk_text = '\n\n'.join(current_chunk)
            chunks.append({
                'chunk_id': len(chunks) + 1,
                'text': chunk_text,
                'size': current_size
            })
        
        logger.info(f"Created {len(chunks)} chunks from {len(paragraphs)} paragraphs")
        return chunks
    
    def clean_markdown(self, text: str) -> str:
        """Clean and normalize markdown formatting."""
        # Remove excessive whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Ensure headers have space after #
        text = re.sub(r'^(#{1,6})([^\s#])', r'\1 \2', text, flags=re.MULTILINE)
        
        return text.strip()
    
    def load_and_preprocess(self, filepath: str) -> List[Dict[str, Any]]:
        """
        Load a chapter file and preprocess it.
        
        Args:
            filepath: Path to chapter .md file
            
        Returns:
            List of chunk dictionaries
        """
        logger.info(f"Loading: {filepath}")
        
        # Read file
        text = FileHandler.read_text(filepath)
        
        # Clean markdown
        text = self.clean_markdown(text)
        
        # Create chunks
        chunks = self.create_chunks(text)
        
        return chunks
    
    def get_chapter_info(self, filepath: str) -> Dict[str, Any]:
        """Extract chapter information from filename."""
        path = Path(filepath)
        
        # New format: novel_name_chapter_XXX.md
        match = re.match(r'(.+)_chapter_(\d+)\.md', path.name)
        
        if match:
            novel_name = match.group(1)
            chapter_num = int(match.group(2))
        else:
            # Legacy format: novel_name_XXX.md
            match = re.match(r'(.+)_(\d+)\.md', path.name)
            if match:
                novel_name = match.group(1)
                chapter_num = int(match.group(2))
            else:
                novel_name = path.stem
                chapter_num = 0
        
        return {
            'filepath': filepath,
            'filename': path.name,
            'novel_name': novel_name,
            'chapter_num': chapter_num
        }
