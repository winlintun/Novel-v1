"""
Fast Translator with Optimized Settings
Larger chunks, streaming support, and optimized parameters.
"""

import logging
from typing import Dict, List

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

        # Initialize glossary matcher for dynamic term extraction
        try:
            from src.utils.glossary_matcher import GlossaryMatcher
            self.glossary_matcher = GlossaryMatcher(memory_manager.glossary_path)
        except Exception as e:
            logging.warning(f"Could not initialize GlossaryMatcher: {e}")
            self.glossary_matcher = None

    def build_prompt(self, text: str) -> str:
        """Build translation prompt with memory context and dynamic glossary."""
        mem = self.memory.get_all_memory_for_prompt()
        prompt_parts = []

        # Add glossary - use dynamic matcher if available, fallback to static
        glossary_section = ""
        if self.glossary_matcher:
            # Get only relevant terms for this text
            dynamic_glossary = self.glossary_matcher.get_relevant_glossary_snippet(text, max_entries=20)
            if dynamic_glossary:
                glossary_section = dynamic_glossary

        if not glossary_section and mem['glossary']:
            # Fallback to static glossary (limited size)
            glossary_section = mem['glossary'][:2000]

        if glossary_section:
            prompt_parts.append(glossary_section)
            prompt_parts.append("")

        # Add context (last paragraph only for speed)
        if mem['context'] and mem['context'] != "No previous context.":
            context_lines = mem['context'].split('\n')
            if len(context_lines) > 2:
                brief_context = '\n'.join(context_lines[-2:])
                prompt_parts.append(brief_context)
                prompt_parts.append("")

        # Add source text with detailed translation instructions
        prompt_parts.append("SOURCE TEXT TO TRANSLATE:")
        prompt_parts.append(text)
        prompt_parts.append("")
        prompt_parts.append("""MYANMAR TRANSLATION RULES:
1. Convert Chinese SVO to Myanmar SOV order
   Example: "他吃饭" (SVO) → "သူစားသည်" (SOV - He rice eats)
2. Use correct particles: သည် (subject), ကို (object), မှာ (location), ဖြင့် (instrument)
3. Use EXACT glossary terms above - do not transliterate character names
4. Preserve all Markdown formatting (#, **, lists, quotes)
5. Output ONLY Myanmar Unicode (U+1000-U+109F). No Thai, no Chinese.

MYANMAR TRANSLATION:""")

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

            # Handle empty response (model collapse)
            if not raw or not raw.strip():
                logger.warning(f"Empty response from model in chapter {chapter_num}. Retrying with reinforced prompt...")
                retry_system = TRANSLATOR_SYSTEM_PROMPT + "\n\nIMPORTANT: You must provide a translation. Do not return an empty response."
                raw = self.ollama.chat(
                    prompt=prompt,
                    system_prompt=retry_system
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
