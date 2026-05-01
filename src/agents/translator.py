#!/usr/bin/env python3
"""
Translator Agent
Core Chinese to Myanmar translation using Ollama.
"""

import logging
import re
from typing import Dict, List, Optional, Any

from src.utils.ollama_client import OllamaClient
from src.memory.memory_manager import MemoryManager
from src.utils.progress_logger import ProgressLogger

from src.utils.postprocessor import clean_output, validate_output, detect_language_leakage
from src.utils.json_extractor import safe_parse_terms
from src.agents.base_agent import BaseAgent
from src.agents.prompt_patch import TRANSLATOR_SYSTEM_PROMPT, EDITOR_SYSTEM_PROMPT


logger = logging.getLogger(__name__)


def get_language_prompt(source_lang: str) -> str:
    """Get system prompt based on source language with full translation rules.

    Incorporates cn_mm_rules.py (CN→MM) and en_mm_rules.py (EN→MM)
    linguistic transformation rules for comprehensive prompt generation.
    """
    from src.agents.prompt_patch import LANGUAGE_GUARD

    source_lower = source_lang.lower() if source_lang else "english"

    if source_lower == "chinese":
        try:
            from src.agents.prompts.cn_mm_rules import build_linguistic_context as cn_ling_ctx
            ling_rules = cn_ling_ctx()
        except ImportError:
            ling_rules = _fallback_cn_rules()

        return LANGUAGE_GUARD + f"""

You are a master literary translator specializing in Chinese Xianxia and Wuxia novels.
Translate the following Chinese text into natural, high-quality literary Myanmar (Burmese) language.

{ling_rules}

LITERARY TRANSLATION PRINCIPLES:
- Literary, Not Literal: Avoid direct, word-for-word translation. Rephrase sentences and paragraphs to flow naturally in Burmese.
- Tone and Formality: Adapt the tone to a polished, novelistic Burmese. Use sentence structures common in modern Burmese literature.
- Idioms and Figurative Language: Do not translate Chinese idioms literally. Find the closest Burmese cultural equivalent.
- Dialogue: Ensure spoken lines reflect each character's personality, status, and social hierarchy.
- Show, Don't Tell: Convert abstract emotions to physical sensations.

FORMATTING RULES:
- Preserve ALL original Markdown formatting (#, **, *, lists, quotes, > blockquotes, ---)
- Chapter headings MUST be "# အခန်း [number]\\n\\n## [Title in Myanmar]"
- Preserve original paragraph breaks exactly — do NOT merge or split paragraphs
- Keep ellipsis (......) as in source

STRICT RULES:
1. SYNTAX: Convert Chinese SVO structure to natural Myanmar SOV order.
2. TERMINOLOGY: Use EXACT terms from the provided glossary. For unknown terms, output 【?term?】 placeholder.
3. MARKDOWN: Preserve ALL formatting. Do not add or remove any Markdown.
4. TONE: Formal/literary Myanmar (သည်/၏/၌/သော) for narrative. Natural spoken Myanmar (တယ်/ရဲ့/မှာ) for dialogue.
5. REGISTER: Pick ONE register for narration — do NOT mix formal and colloquial particles.
6. EMOTION: For aggressive/angry dialogue, use strong active verbs (သတ်မည်, ဖျက်ဆီးမည်).
7. OUTPUT: Return ONLY Myanmar text. Zero preamble. No Chinese. No English. No Japanese.

Text to translate:"""
    else:
        try:
            from src.agents.prompts.en_mm_rules import build_linguistic_context as en_ling_ctx
            ling_rules = en_ling_ctx(
                source_lang="English",
                scene_type="narration",
                include_unicode_warning=True,
            )
        except ImportError:
            ling_rules = _fallback_en_rules()

        return LANGUAGE_GUARD + f"""

You are a master literary translator, specializing in converting English-language novels into rich, idiomatic Myanmar (Burmese) language. You are not a machine; you are a linguistic artist. Your goal is to produce a translation that reads as if it were originally written in Burmese.

{ling_rules}

LITERARY TRANSLATION PRINCIPLES:
- Literary, Not Literal: Avoid direct, word-for-word translation. Rephrase sentences and paragraphs to flow naturally in Burmese.
- Tone and Formality: Adapt the tone to a polished, novelistic Burmese. Use sentence structures common in modern Burmese literature. Match the scene's emotional tone (tense, romantic, somber, epic).
- Idioms: Do not translate English idioms literally. Find the closest Burmese cultural or linguistic equivalent.
- Dialogue: Ensure spoken lines sound natural and reflect each character's personality, status, and relationship with the speaker.
- Show, Don't Tell: Express emotions through physical sensation — never abstract labels alone.

UNICODE SAFETY:
- NEVER output Korean chars (봤자 해서 는데) — force to U+AC00-U+D7FF
- NEVER output Bengali script (গাঢ় ক খ) — force to U+0980-U+09FF
- NEVER use Arabic question mark (؟) — use standard ?
- NEVER leave Chinese chars or English words in output
- Use ONLY Myanmar Unicode (U+1000-U+109F, U+AA60-U+AA7F)

FORMATTING RULES:
- Preserve ALL original Markdown formatting (#, **, *, lists, quotes, > blockquotes, ---)
- Chapter heading MUST be: "# [Chapter Number]\\n\\n## [Chapter Title in Myanmar]"
- Preserve original paragraph breaks exactly — do NOT merge or split paragraphs
- Keep ellipsis (......) as in source

STRICT RULES:
1. COMPLETENESS: Translate the ENTIRE input. Every sentence, every paragraph. Do not skip or summarize.
2. TERMINOLOGY: Use EXACT glossary terms if provided. Unknown terms → 【?term?】 placeholder.
3. MARKDOWN: Preserve ALL markdown formatting exactly.
4. TONE: Formal literary Burmese (သည်/၏/၌/သော) for narration. Natural speech (တယ်/မှာ/ဘူး) for dialogue.
5. REGISTER: Pick ONE register for narration — do NOT mix formal and colloquial particles.
6. EMOTION: For aggressive dialogue, use strong active verbs. For sadness/fear, show physical sensations.
7. OUTPUT: Return ONLY the translated Myanmar text. Zero preamble. Zero postamble. No thinking tags.
8. ANTI-HALLUCINATION: NEVER invent proper names or characters. If source says \"Brother Zhang\", translate it as \"အစ်ကိုကျန်း\" — do NOT substitute with glossary character names like \"ဖန်ကျန်း\". Only use glossary terms when the EXACT source term appears in the input.
9. FOOTNOTES: Preserve inline markers like (1), (2), [1], [2] exactly as they appear in source.
10. PLACE NAMES: Use EXACT glossary terms for places (e.g., Gu Yue Village → ကူယွဲ့ကျေးရွာ). Do not transliterate differently.

Text to translate:"""


def _fallback_cn_rules() -> str:
    """Fallback CN→MM rules when module import fails."""
    return """
[LINGUISTIC RULES - CN→MM]
1. STRUCTURE: Convert Chinese SVO → Myanmar SOV.
   CN: 他(主) + 吃(动) + 饭(宾) → MM: သူ(သည်) + ထမင်း(ကို) + စား(သည်)
2. PARTICLES: Subject markers (သည်/က/မှာ), Object markers (ကို/သို့/အတွက်)
3. PRONOUNS: Resolve based on hierarchy — ကျွန်တော်/ကျွန်မ (formal), မင်း (equal), နင် (hostile)
4. CULTURAL: Adapt idioms by meaning, not literal translation. Use phonetic transliteration for names.
"""


def _fallback_en_rules() -> str:
    """Fallback EN→MM rules when module import fails."""
    return """
[LINGUISTIC RULES — English → Myanmar]
1. STRUCTURE: English SVO → Myanmar SOV.
   EN: He [S] struck [V] the enemy [O] → MM: သူ [S] ရန်သူကို [O] ထိုးလိုက်တယ် [V]
2. DIALOGUE FORMAT: "speech" လို့ [character] [verb]တယ် — NEVER "speech" ဟု ... လေသည်
3. PRONOUNS: Enemy → နင်, Equal → မင်း, Formal → ခင်ဗျ/ရှင်, Self → ငါ/ကျွန်တော်
4. TENSE: Past = ခဲ့တယ်, Vivid accusation = drop ခဲ့, Continuous = နေတယ်
5. EMOTIONS: Show physically (not abstract labels)
"""




class Translator(BaseAgent):
    """
    Translates Chinese text to Myanmar using LLM.
    Integrates glossary and context memory.
    """
    
    def __init__(
        self,
        ollama_client: Optional[OllamaClient] = None,
        memory_manager: Optional[MemoryManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        super().__init__(ollama_client, memory_manager, config)
        self.ollama = ollama_client
        
        pipeline = self.config.get('translation_pipeline', {})
        self._custom_system_prompt = pipeline.get('stage1_system_prompt')
        self._custom_prompt_template = pipeline.get('stage1_prompt', '{text}')
        self._fallback_system_prompt = TRANSLATOR_SYSTEM_PROMPT
    
    def get_system_prompt(self, source_lang: str = "english") -> str:
        """Get system prompt based on source language (chinese or english)."""
        if self._custom_system_prompt:
            return self._custom_system_prompt
        return get_language_prompt(source_lang)
    
    def build_prompt(self, text: str) -> str:
        """Build translation prompt with memory context."""
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
            paragraph: Source text paragraph (Chinese or English)
            chapter_num: Current chapter number for logging
            
        Returns:
            Myanmar translation
        """
        # Build prompt with context
        prompt = self.build_prompt(paragraph)
        
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
            retry_system = system_prompt + "\n\n[RETRY MODE] Previous output failed - contained " + retry_reason + ". This time output 100% Myanmar ONLY."
            
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
