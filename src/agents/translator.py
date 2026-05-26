#!/usr/bin/env python3
"""
Translator Agent
Core Chinese to Myanmar translation using Ollama.
"""

import logging
from typing import Dict, List, Optional, Any

from src.utils.ollama_client import OllamaClient
from src.memory.memory_manager import MemoryManager
from src.utils.progress_logger import ProgressLogger

from src.utils.postprocessor import clean_output, validate_output, detect_language_leakage, myanmar_char_ratio
from src.agents.base_agent import BaseAgent
from src.agents.prompts import (
    LANGUAGE_GUARD,
    TRANSLATOR_SYSTEM_PROMPT,
    FALLBACK_CN_RULES,
    FALLBACK_EN_RULES,
    build_translator_prompt,
    get_fallback_rules,
)


logger = logging.getLogger(__name__)


def get_language_prompt(source_lang: str, model_name: str = "") -> str:
    """Get system prompt based on source language with full translation rules.

    Incorporates cn_mm_rules.py (CN→MM) and en_mm_rules.py (EN→MM)
    linguistic transformation rules for comprehensive prompt generation.
    
    Args:
        source_lang: Source language ("chinese" or "english")
        model_name: Model name for prompt optimization (fast prompt for padauk-gemma)
    """
    from src.agents.prompts import build_translator_prompt
    return build_translator_prompt(source_lang, model_name)




class Translator(BaseAgent):
    """
    Translates Chinese text to Myanmar using LLM.
    Integrates glossary and context memory.
    """

    def __init__(
        self,
        ollama_client: Optional[OllamaClient] = None,
        memory_manager: Optional[MemoryManager] = None,
        config: Optional[Dict[str, Any]] = None,
        rag_retriever: Optional[Any] = None,
    ):
        super().__init__(ollama_client, memory_manager, config)
        self.ollama = ollama_client
        self.rag_retriever = rag_retriever

        pipeline = self.config.get('translation_pipeline', {})
        self._custom_system_prompt = pipeline.get('stage1_system_prompt')
        self._custom_prompt_template = pipeline.get('stage1_prompt', '{text}')
        self._fallback_system_prompt = TRANSLATOR_SYSTEM_PROMPT

        # RAG config
        rag_config = self.config.get('rag', {})
        self.rag_enabled = rag_config.get('enabled', False)
        self.rag_top_k = rag_config.get('top_k', 3)
        self.rag_min_similarity = rag_config.get('min_similarity', 0.3)

    def get_system_prompt(self, source_lang: str = "english") -> str:
        """Get system prompt based on source language (chinese or english)."""
        if self._custom_system_prompt:
            return self._custom_system_prompt
        model_name = getattr(self.ollama, 'model', '') if self.ollama else ''
        return get_language_prompt(source_lang, model_name=model_name)

    def build_prompt(self, text: str, rolling_context: str = "") -> str:
        """Build translation prompt with memory context and rolling translation context.
        
        Args:
            text: Source text to translate
            rolling_context: Tail of previous translated chunk (Myanmar, ≤400 tokens)
        """
        # Get all memory context
        mem = self.memory.get_all_memory_for_prompt()
        glossary_text = mem['glossary'] if mem['glossary'] else ""

        # Use custom template from config if available
        if self._custom_prompt_template and self._custom_prompt_template != '{text}':
            prompt = self._custom_prompt_template.replace('{text}', text).replace('{glossary}', glossary_text)
            if mem['context'] and mem['context'] != "No previous context.":
                prompt = prompt.replace('{context}', mem['context'])
            return prompt

        # Fallback to default template
        prompt_parts = []

        # Add glossary
        if mem['glossary']:
            prompt_parts.append(mem['glossary'])
            prompt_parts.append("")

        # Add RAG examples (few-shot translation examples from ChromaDB/SQLite)
        if self.rag_enabled and self.rag_retriever:
            rag_examples = self._build_rag_examples(text)
            if rag_examples:
                prompt_parts.append(rag_examples)
                prompt_parts.append("")

        # Add rolling context (tail of previous translated chunk)
        if rolling_context:
            prompt_parts.append("PREVIOUS CONTEXT (translated Myanmar, for continuity):")
            prompt_parts.append(rolling_context)
            prompt_parts.append("")
        elif mem['context'] and mem['context'] != "No previous context.":
            # Fallback to accumulated context buffer
            prompt_parts.append(mem['context'])
            prompt_parts.append("")

        # Add correction rules
        if mem['rules'] and mem['rules'] != "No session rules.":
            prompt_parts.append(mem['rules'])
            prompt_parts.append("")

        # Add character voice profiles
        if mem.get('voices'):
            prompt_parts.append(mem['voices'])
            prompt_parts.append("")

        # Add chapter summary memory for long-range continuity
        if mem.get('summary') and mem['summary'] not in ("", "No summary yet."):
            prompt_parts.append("CHAPTER SUMMARY (events so far in this chapter):")
            from src.utils.chunker import estimate_tokens
            summary_text = mem['summary']
            if estimate_tokens(summary_text) > 200:
                summary_text = summary_text[:600] + "..."
            prompt_parts.append(summary_text)
            prompt_parts.append("")

        # Add source text
        prompt_parts.append("SOURCE TEXT TO TRANSLATE:")
        prompt_parts.append(text)
        prompt_parts.append("")
        prompt_parts.append("MYANMAR TRANSLATION:")

        return "\n".join(prompt_parts)

    def _build_rag_examples(self, source_text: str) -> str:
        """Build few-shot examples from RAG retrieval.
        
        Args:
            source_text: Current source text to find similar examples for
            
        Returns:
            Formatted string with translation examples, or empty string if none found
        """
        try:
            examples = self.rag_retriever.retrieve_similar(
                query_text=source_text,
                top_k=self.rag_top_k,
            )

            if not examples:
                return ""

            # Filter by minimum similarity
            examples = [e for e in examples if e.similarity >= self.rag_min_similarity]

            if not examples:
                return ""

            parts = ["REFERENCE TRANSLATION EXAMPLES (match style and terminology):"]
            for i, ex in enumerate(examples, 1):
                parts.append(f"Example {i}:")
                parts.append(f"EN: {ex.en_text[:200]}")
                parts.append(f"MY: {ex.my_text[:200]}")
                parts.append("")

            return "\n".join(parts)

        except Exception as e:
            logger.warning(f"RAG retrieval failed: {e}")
            return ""

    def translate_paragraph(
        self,
        paragraph: str,
        chapter_num: int = 0,
        rolling_context: str = "",
    ) -> str:
        """
        Translate a single paragraph with English detection and retry.
        
        Args:
            paragraph: Source text paragraph (Chinese or English)
            chapter_num: Current chapter number for logging
            rolling_context: Tail of previous translated chunk (≤400 tokens)
            
        Returns:
            Myanmar translation
        """
        # Build prompt with context
        prompt = self.build_prompt(paragraph, rolling_context=rolling_context)

        # Select correct system prompt based on source language
        source_lang = self.config.get('project', {}).get('source_language', 'chinese')
        if 'en' in source_lang.lower():
            lang_key = 'english'
        else:
            lang_key = 'chinese'

        system_prompt = self.get_system_prompt(lang_key)

        # First attempt
        raw = self.ollama.chat(
            prompt=prompt,
            system_prompt=system_prompt
        )

        # Handle empty response (model collapse)
        if not raw or not raw.strip():
            logger.warning(f"Empty response from model in chapter {chapter_num}. Retrying with reinforced prompt...")
            retry_system = system_prompt + "\n\nIMPORTANT: You must provide a translation. Do not return an empty response."
            raw = self.ollama.chat(
                prompt=prompt,
                system_prompt=retry_system
            )

        # Clean output
        translated = clean_output(raw)

        # Check for language leakage (English or Chinese)
        leakage = detect_language_leakage(translated)
        needs_retry = False
        retry_reason = ""

        if leakage.get("has_english", False) and leakage.get("latin_words", 0) > 8:
            needs_retry = True
            retry_reason = f"English ({leakage['latin_words']} words)"

        if leakage.get("chinese_chars", 0) > 0:
            needs_retry = True
            retry_reason = f"Chinese ({leakage['chinese_chars']} chars)"

        if needs_retry:
            logger.warning(f"{retry_reason} detected in translation (chapter {chapter_num}), retrying with stronger prompt...")

            # Check for 0% Myanmar ratio — use few-shot examples
            if myanmar_char_ratio(translated) < 0.01:
                # CRITICAL: 0% Myanmar — use few-shot examples to force Myanmar output
                FEW_SHOT = """CRITICAL: Your output was in English. It MUST be in Myanmar.

EXAMPLES of correct EN->MY translation:
Source: "So, this is the first level of Qi Condensation!"
Myanmar: "ဒါက ချီငွေ့သိပ်သည်းခြင်းရဲ့ ပထမအဆင့်လား။"

Source: He touched the mutation point on his arm.
Myanmar: သူက သူ့လက်မောင်းပေါ်က ဗီဇပြောင်းလဲမှုအစက်ကို ထိကြည့်လိုက်တယ်။

Source: According to the bamboo slip, every level grants an additional tiger's worth of strength.
Myanmar: ဝါးလိပ်ဖော်ပြချက်အရ အဆင့်တိုင်းက ကျားတစ်ကောင်စာ ခွန်အားကိုပေးမယ်။

SOURCE TEXT TO TRANSLATE (MUST output Myanmar ONLY):
{original_text}
Myanmar Translation:"""
                retry_prompt = FEW_SHOT.replace("{original_text}", paragraph)
                retry_system = "You output ONLY Myanmar (Burmese) script. NO English. NO Chinese. Translate every word."
            else:
                # Standard retry for partial leakage
                retry_prompt = prompt + "\n\n⚠️ Previous output had " + retry_reason + ". Output ONLY Myanmar this time."
                retry_system = system_prompt + "\n\nPrevious output failed — output 100% Myanmar ONLY."

            raw_retry = self.ollama.chat(
                prompt=retry_prompt,
                system_prompt=retry_system
            )
            translated_retry = clean_output(raw_retry)

            # If first retry ALSO has < 1% Myanmar, try one more time with stronger instruction
            if myanmar_char_ratio(translated_retry) < 0.01:
                logger.critical(f"Second retry attempt for 0% Myanmar output (chapter {chapter_num})...")
                stronger_prompt = """ABSOLUTE LAST ATTEMPT: You MUST output in Myanmar (Burmese) script ONLY.

PREVIOUS OUTPUTS WERE IN ENGLISH — THIS IS UNACCEPTABLE.

LITERAL TRANSLATION EXAMPLES:
Source: "Hello, how are you?"
Myanmar: "မင်္ဂလာပါ၊ နေကောင်းလား။"

Source: "I am fine."
Myanmar: "ငါနေကောင်းတယ်။"

Source: {original_text}

Now translate the above sentence. ONLY Myanmar script. NO English. NO Chinese. NO explanation.
Myanmar Translation:"""
                raw_retry2 = self.ollama.chat(
                    prompt=stronger_prompt.replace("{original_text}", paragraph),
                    system_prompt="You are a Myanmar translator. Output ONLY Myanmar script. NEVER English."
                )
                translated_retry = clean_output(raw_retry2)

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
                logger.warning("Retry did not improve language content")

        # Validate and log quality report
        report = validate_output(translated, chapter_num)
        if report["status"] == "REJECTED":
            logger.error(f"CRITICAL: Translation REJECTED in chapter {chapter_num}: {report}")
        elif report["status"] == "NEEDS_REVIEW":
            logger.warning(f"Translation quality issue in chapter {chapter_num}: {report}")

        # Push to context buffer
        self.memory.push_to_buffer(translated)

        return translated

    def translate_with_fallback(
        self,
        text: str,
        source_lang: str = "english",
        chapter_num: int = 0
    ) -> str:
        """Translate with fallback retry on empty or short output."""
        result = self.translate_paragraph(text, chapter_num)

        if not result or len(result.strip()) < 50:
            logger.warning("Empty or short output detected. Using fallback prompt...")
            fallback_prompt = self.get_fallback_prompt(source_lang)

            prompt = self.build_prompt(text)
            system_prompt = fallback_prompt

            result = self.ollama.chat(
                prompt=prompt,
                system_prompt=system_prompt
            )

        if not result:
            logger.error("Translation returned empty after fallback")
            raise ValueError("Translation failed completely. Check model and prompt.")

        return result

    def get_fallback_prompt(self, source_lang: str) -> str:
        """Get minimal fallback prompt for retry on empty output."""
        from src.agents.prompt_patch import LANGUAGE_GUARD

        target_instr = "Chinese text to Myanmar" if source_lang.lower() == "chinese" else "English text to Myanmar"

        return LANGUAGE_GUARD + f"""
You are a professional translator. Translate the following {target_instr}.
Keep all names and terms as-is. Output ONLY the translation. No preamble.

Text to translate:"""

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
        rolling_context = ""  # first chunk: no previous context

        for i, chunk in enumerate(chunks, 1):
            logger.info(f"Translating chunk {i}/{total}...")

            try:
                # Translate chunk with rolling context from previous chunk
                result = self.translate_paragraph(
                    chunk['text'], chapter_num, rolling_context=rolling_context
                )
                translated.append(result)

                # Advance rolling context for next chunk
                from src.utils.chunker import get_rolling_context
                rolling_context = get_rolling_context(result, max_context_tokens=400)

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
        chunks: List[Dict[str, Any]],
        chapter_num: int = 0
    ) -> str:
        """
        Translate pre-processed chunks (recommended flow).
        
        This method expects chunks from Preprocessor.create_chunks() to be passed in.
        For the old monolithic flow, use Preprocessor + translate_chunks() externally.
        
        Args:
            chunks: List of chunk dictionaries from Preprocessor
            chapter_num: Chapter number
            
        Returns:
            Full translated chapter
        """
        logger.info(f"Translating Chapter {chapter_num}")

        # Clear context buffer for new chapter
        self.memory.clear_buffer()

        # Translate chunks
        translated_chunks = self.translate_chunks(chunks, chapter_num)

        # Join results
        return '\n\n'.join(translated_chunks)
