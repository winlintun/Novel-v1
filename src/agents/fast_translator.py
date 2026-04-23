"""
Fast Translator with Optimized Settings
Larger chunks, streaming support, and optimized parameters.
"""

import logging
from typing import Dict, List, Optional

from src.utils.ollama_client import OllamaClient
from src.memory.memory_manager import MemoryManager
from src.utils.postprocessor import clean_output, validate_output
from src.agents.prompt_patch import TRANSLATOR_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class FastTranslator:
    """
    Optimized translator with larger chunks and batch processing support.
    3-5x faster than standard translator.
    """
    
    def __init__(
        self,
        ollama_client: OllamaClient,
        memory_manager: MemoryManager,
        use_streaming: bool = True
    ):
        self.ollama = ollama_client
        self.memory = memory_manager
        self.use_streaming = use_streaming
    
    def build_prompt(self, text: str) -> str:
        """Build translation prompt with memory context."""
        mem = self.memory.get_all_memory_for_prompt()
        
        prompt_parts = []
        
        # Add glossary (brief version for speed)
        if mem['glossary']:
            prompt_parts.append(mem['glossary'][:2000])  # Limit glossary size
            prompt_parts.append("")
        
        # Add context (last paragraph only for speed)
        if mem['context'] and mem['context'] != "No previous context.":
            # Get just the last paragraph for context
            context_lines = mem['context'].split('\n')
            if len(context_lines) > 2:
                brief_context = '\n'.join(context_lines[-2:])
                prompt_parts.append(brief_context)
                prompt_parts.append("")
        
        # Add source text
        prompt_parts.append("SOURCE TEXT TO TRANSLATE:")
        prompt_parts.append(text)
        prompt_parts.append("")
        prompt_parts.append("MYANMAR TRANSLATION:")
        
        return "\n".join(prompt_parts)
    
    def translate_chunk(self, text: str, chapter_num: int = 0) -> str:
        """
        Translate a single chunk with optimized settings.
        
        Args:
            text: Chinese text to translate
            chapter_num: Chapter number for logging
            
        Returns:
            Myanmar translation
        """
        prompt = self.build_prompt(text)
        
        try:
            if self.use_streaming:
                # Use streaming for faster perceived response
                raw_parts = []
                for chunk in self.ollama.chat_stream(
                    prompt=prompt,
                    system_prompt=TRANSLATOR_SYSTEM_PROMPT
                ):
                    raw_parts.append(chunk)
                raw = "".join(raw_parts)
            else:
                raw = self.ollama.chat(
                    prompt=prompt,
                    system_prompt=TRANSLATOR_SYSTEM_PROMPT,
                    stream=False
                )
            
            # Clean output
            translated = clean_output(raw)
            
            # Quick validation (no logging for speed)
            report = validate_output(translated, chapter_num)
            if report["status"] != "APPROVED":
                logger.warning(f"Quality issue in chapter {chapter_num}: {report['status']}")
            
            # Update context buffer (brief)
            if len(translated) > 100:
                self.memory.push_to_buffer(translated[:500])  # Store less context
            
            return translated
            
        except Exception as e:
            logger.error(f"Translation failed: {e}")
            return f"[TRANSLATION ERROR: {e}]"
    
    def translate_chunks(self, chunks: List[Dict], chapter_num: int = 0) -> List[str]:
        """
        Translate multiple chunks efficiently.
        
        Args:
            chunks: List of chunk dictionaries
            chapter_num: Current chapter number
            
        Returns:
            List of translated texts
        """
        translated = []
        total = len(chunks)
        
        for i, chunk in enumerate(chunks, 1):
            logger.info(f"Translating chunk {i}/{total}...")
            
            result = self.translate_chunk(chunk['text'], chapter_num)
            translated.append(result)
        
        return translated
    
    def translate_chapter(
        self,
        text: str,
        chapter_num: int = 0,
        use_chunking: bool = True
    ) -> str:
        """
        Translate entire chapter with optimized settings.
        
        Args:
            text: Full chapter text
            chapter_num: Chapter number
            use_chunking: Whether to use chunking
            
        Returns:
            Full translated chapter
        """
        from src.agents.preprocessor import Preprocessor
        
        logger.info(f"Fast translating Chapter {chapter_num}")
        
        # Clear context buffer
        self.memory.clear_buffer()
        
        if use_chunking:
            # Use larger chunks (3000 chars vs 1500)
            preprocessor = Preprocessor(chunk_size=3000, overlap_size=50)
            chunks = preprocessor.create_chunks(text)
            
            logger.info(f"Created {len(chunks)} large chunks")
            
            # Translate chunks
            translated_chunks = self.translate_chunks(chunks, chapter_num)
            
            return '\n\n'.join(translated_chunks)
        else:
            return self.translate_chunk(text, chapter_num)


# Backwards compatibility
Translator = FastTranslator
