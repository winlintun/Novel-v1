#!/usr/bin/env python3
"""
Translator Agent
Core Chinese to Myanmar translation using Ollama.
"""

import logging
from typing import Dict, List, Optional

from src.utils.ollama_client import OllamaClient
from src.memory.memory_manager import MemoryManager

from src.utils.postprocessor import clean_output, validate_output
from src.utils.json_extractor import safe_parse_terms
from src.agents.prompt_patch import TRANSLATOR_SYSTEM_PROMPT, EDITOR_SYSTEM_PROMPT


logger = logging.getLogger(__name__)


class Translator:
    """
    Translates Chinese text to Myanmar using LLM.
    Integrates glossary and context memory.
    """
    
    def __init__(
        self,
        ollama_client: OllamaClient,
        memory_manager: MemoryManager
    ):
        self.ollama = ollama_client
        self.memory = memory_manager
    
    def build_prompt(self, text: str) -> str:
        """Build translation prompt with memory context."""
        # Get all memory context
        mem = self.memory.get_all_memory_for_prompt()
        
        prompt_parts = []
        
        # Add glossary
        if mem['glossary']:
            prompt_parts.append(mem['glossary'])
            prompt_parts.append("")
        
        # Add context
        if mem['context'] and mem['context'] != "No previous context.":
            prompt_parts.append(mem['context'])
            prompt_parts.append("")
        
        # Add correction rules
        if mem['rules'] and mem['rules'] != "No session rules.":
            prompt_parts.append(mem['rules'])
            prompt_parts.append("")
        
        # Add source text
        prompt_parts.append("SOURCE TEXT TO TRANSLATE:")
        prompt_parts.append(text)
        prompt_parts.append("")
        prompt_parts.append("MYANMAR TRANSLATION:")
        
        return "\n".join(prompt_parts)
    
    def translate_paragraph(self, paragraph: str, chapter_num: int = 0) -> str:
        """
        Translate a single paragraph.
        
        Args:
            paragraph: Chinese text paragraph
            chapter_num: Current chapter number for logging
            
        Returns:
            Myanmar translation
        """
        # Build prompt with context
        prompt = self.build_prompt(paragraph)
        
        # Call LLM
        raw = self.ollama.chat(
            prompt=prompt,
            system_prompt=TRANSLATOR_SYSTEM_PROMPT
        )
        
        # Clean output: strip <think>, <answer>, tags, etc.
        translated = clean_output(raw)
        
        # Validate and log quality report
        report = validate_output(translated, chapter_num)
        if report["status"] != "APPROVED":
            logger.warning(f"Translation quality issue in chapter {chapter_num}: {report}")
        
        # Push to context buffer
        self.memory.push_to_buffer(translated)
        
        return translated
    
    def translate_chunks(self, chunks: List[Dict], chapter_num: int = 0) -> List[str]:
        """
        Translate multiple chunks.
        
        Args:
            chunks: List of chunk dictionaries from preprocessor
            chapter_num: Current chapter number
            
        Returns:
            List of translated texts
        """
        translated = []
        total = len(chunks)
        
        for i, chunk in enumerate(chunks, 1):
            logger.info(f"Translating chunk {i}/{total}...")
            
            try:
                # Translate chunk with chapter number for quality tracking
                result = self.translate_paragraph(chunk['text'], chapter_num)
                translated.append(result)
                
            except Exception as e:
                logger.error(f"Failed to translate chunk {i}: {e}")
                translated.append(f"[TRANSLATION ERROR: {e}]")
        
        return translated
    
    def translate_chapter(
        self,
        text: str,
        chapter_num: int = 0,
        use_chunking: bool = True
    ) -> str:
        """
        Translate entire chapter text.
        
        Args:
            text: Full chapter text
            chapter_num: Chapter number
            use_chunking: Whether to use chunking for long chapters
            
        Returns:
            Full translated chapter
        """
        from src.agents.preprocessor import Preprocessor
        
        logger.info(f"Translating Chapter {chapter_num}")
        
        # Clear context buffer for new chapter
        self.memory.clear_buffer()
        
        if use_chunking:
            # Use preprocessor to chunk
            preprocessor = Preprocessor()
            chunks = preprocessor.create_chunks(text)
            
            # Translate chunks
            translated_chunks = self.translate_chunks(chunks, chapter_num)
            
            # Join results
            return '\n\n'.join(translated_chunks)
        else:
            # Translate as single paragraph
            return self.translate_paragraph(text)
