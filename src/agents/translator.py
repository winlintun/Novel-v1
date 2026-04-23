#!/usr/bin/env python3
"""
Translator Agent
Core Chinese to Myanmar translation using Ollama.
"""

import logging
from typing import Dict, List, Optional

from src.utils.ollama_client import OllamaClient
from src.memory.memory_manager import MemoryManager

logger = logging.getLogger(__name__)


TRANSLATION_SYSTEM_PROMPT = """You are an expert Chinese-to-Myanmar literary translator specializing in Xianxia/Cultivation novels.

CRITICAL RULES:
1. Myanmar SOV Structure: Use Subject-Object-Verb order
2. Tone Control: 
   - Narrative: Formal, literary tone
   - Dialogue: Natural spoken tone matching character personality
3. Glossary Compliance: Use EXACT translations from glossary. Never transliterate names unless specified.
4. Markdown Preservation: Keep all formatting (#, **, *, etc.)
5. Literary Quality: Make it read like original Myanmar literature, not a translation
6. No Additions: Do not add explanations or translator notes

NARRATIVE STYLE:
- Use formal Burmese sentence endings (သည်, သည်, etc.)
- Break long Chinese sentences into readable Myanmar clauses
- Use descriptive, evocative language

DIALOGUE STYLE:
- Short, direct sentences
- Match character personality and status
- Use appropriate particles (လား, ပါ, ဟေ့, etc.)

OUTPUT ONLY the translated Myanmar text. No explanations, no Chinese, no notes."""


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
    
    def translate_paragraph(self, paragraph: str) -> str:
        """
        Translate a single paragraph.
        
        Args:
            paragraph: Chinese text paragraph
            
        Returns:
            Myanmar translation
        """
        # Build prompt with context
        prompt = self.build_prompt(paragraph)
        
        # Call LLM
        translated = self.ollama.chat(
            prompt=prompt,
            system_prompt=TRANSLATION_SYSTEM_PROMPT
        )
        
        # Clean up response
        translated = translated.strip()
        
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
                # Translate chunk
                result = self.translate_paragraph(chunk['text'])
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
