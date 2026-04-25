#!/usr/bin/env python3
"""
Translator Agent
Core Chinese to Myanmar translation using Ollama.
"""

import logging
from typing import Dict, List, Optional

from src.utils.ollama_client import OllamaClient
from src.memory.memory_manager import MemoryManager
from src.utils.progress_logger import ProgressLogger

from src.utils.postprocessor import clean_output, validate_output, detect_language_leakage
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
        Translate a single paragraph with English detection and retry.
        
        Args:
            paragraph: Chinese text paragraph
            chapter_num: Current chapter number for logging
            
        Returns:
            Myanmar translation
        """
        # Build prompt with context
        prompt = self.build_prompt(paragraph)
        
        # First attempt
        raw = self.ollama.chat(
            prompt=prompt,
            system_prompt=TRANSLATOR_SYSTEM_PROMPT
        )
        
        # Clean output
        translated = clean_output(raw)
        
        # Check for language leakage (English or Chinese)
        leakage = detect_language_leakage(translated)
        needs_retry = False
        retry_reason = ""
        
        if leakage.get("has_english", False) and leakage.get("latin_words", 0) > 3:
            needs_retry = True
            retry_reason = f"English ({leakage['latin_words']} words)"
        
        if leakage.get("chinese_chars", 0) > 0:
            needs_retry = True
            retry_reason = f"Chinese ({leakage['chinese_chars']} chars)"
        
        if needs_retry:
            logger.warning(f"{retry_reason} detected in translation (chapter {chapter_num}), retrying with stronger prompt...")
            
            # Retry with reinforced language guard
            retry_prompt = prompt + "\n\n⚠️ CRITICAL: Your previous output contained " + retry_reason + ". This time output ONLY Myanmar text. NO Chinese or English allowed. Use 【?term?】 for unknown words."
            retry_system = TRANSLATOR_SYSTEM_PROMPT + "\n\n[RETRY MODE] Previous output failed - contained " + retry_reason + ". This time output 100% Myanmar ONLY."
            
            raw_retry = self.ollama.chat(
                prompt=retry_prompt,
                system_prompt=retry_system
            )
            translated_retry = clean_output(raw_retry)
            
            # Check if retry is better
            leakage_retry = detect_language_leakage(translated_retry)
            
            # Determine if retry improved
            improved = False
            if leakage.get("chinese_chars", 0) > 0 and leakage_retry.get("chinese_chars", 0) < leakage.get("chinese_chars", 0):
                improved = True
                logger.info(f"Retry successful - reduced Chinese chars from {leakage['chinese_chars']} to {leakage_retry['chinese_chars']}")
            elif leakage.get("latin_words", 0) > 0 and leakage_retry.get("latin_words", 0) < leakage.get("latin_words", 0):
                improved = True
                logger.info(f"Retry successful - reduced English words from {leakage['latin_words']} to {leakage_retry['latin_words']}")
            
            if improved:
                translated = translated_retry
            else:
                logger.warning(f"Retry did not improve language content")
        
        # Validate and log quality report
        report = validate_output(translated, chapter_num)
        if report["status"] == "REJECTED":
            logger.error(f"CRITICAL: Translation REJECTED in chapter {chapter_num}: {report}")
        elif report["status"] == "NEEDS_REVIEW":
            logger.warning(f"Translation quality issue in chapter {chapter_num}: {report}")
        
        # Push to context buffer
        self.memory.push_to_buffer(translated)
        
        return translated
    
    def translate_chunks(
        self,
        chunks: List[Dict],
        chapter_num: int = 0,
        progress_logger: Optional[ProgressLogger] = None,
    ) -> List[str]:
        """
        Translate multiple chunks.
        
        Args:
            chunks: List of chunk dictionaries from preprocessor
            chapter_num: Current chapter number
            progress_logger: Optional ProgressLogger for real-time progress tracking
            
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
                
                # Log progress if logger is provided
                if progress_logger:
                    progress_logger.log_chunk(
                        chunk_index=i - 1,
                        chunk_text=result,
                        source_text=chunk.get('text', '')
                    )
                
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
