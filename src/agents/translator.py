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

from src.utils.postprocessor import clean_output, validate_output, detect_language_leakage
from src.agents.base_agent import BaseAgent
from src.agents.prompt_patch import TRANSLATOR_SYSTEM_PROMPT


logger = logging.getLogger(__name__)


def get_language_prompt(source_lang: str, model_name: str = "") -> str:
    """Get system prompt based on source language with full translation rules.

    Incorporates cn_mm_rules.py (CN→MM) and en_mm_rules.py (EN→MM)
    linguistic transformation rules for comprehensive prompt generation.
    
    Args:
        source_lang: Source language ("chinese" or "english")
        model_name: Model name for prompt optimization (fast prompt for padauk-gemma)
    """
    from src.agents.prompt_patch import LANGUAGE_GUARD

    source_lower = source_lang.lower() if source_lang else "english"
    is_padauk = "padauk" in model_name.lower()

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

        # Fast prompt for padauk-gemma: skip verbose rules (model is natively Burmese)
        # But still include LANGUAGE_GUARD to prevent language leakage
        if is_padauk:
            return LANGUAGE_GUARD + FAST_EN_MM_PROMPT

        return LANGUAGE_GUARD + f"""
You are a master literary translator, specializing in converting English-language
novels into rich, idiomatic Myanmar (Burmese). You are not a machine; you are a
linguistic artist. Your goal is to produce a translation that reads as if it were
originally written in Burmese.
{ling_rules}
LITERARY TRANSLATION PRINCIPLES:
- Literary, Not Literal: Avoid direct, word-for-word translation
- Tone and Formality: Adapt to polished, novelistic Burmese. Match scene's emotional tone
- Idioms: Do not translate English idioms literally
- Dialogue: Reflect character personality, status, relationship
- Show, Don't Tell: Express emotions through physical sensation
UNICODE SAFETY:
- NEVER output Korean chars (봤자 해서 는데) — U+AC00-U+D7FF
- NEVER output Bengali script (গাঢ় ক খ) — U+0980-U+09FF
- NEVER use Arabic question mark (؟) — use standard ?
- NEVER leave Chinese chars or English words in output
- Use ONLY Myanmar Unicode (U+1000-U+109F, U+AA60-U+AA7F)
FORMATTING RULES:
- Preserve ALL Markdown formatting
- Chapter heading: "# [Chapter Number]\n\n## [Chapter Title in Myanmar]"
- Preserve paragraph breaks exactly
- Keep ellipsis as in source
STRICT RULES:
1. COMPLETENESS: Translate every sentence
2. TERMINOLOGY: Use EXACT glossary terms, unknown → 【?term?】
3. MARKDOWN: Preserve ALL formatting
4. TONE: Formal (သည်/၏/၌) for narration, natural (တယ်/မှာ/ဘူး) for dialogue
5. REGISTER: Pick ONE register — don't mix
6. EMOTION: Show physical sensations
7. OUTPUT: Return ONLY Myanmar text, no preamble, no postamble
8. ANTI-HALLUCINATION: Don't substitute glossary names for generic terms like "Brother Zhang"
9. FOOTNOTES: Preserve (1), (2), [1], [2] markers
10. PLACE NAMES: Use EXACT glossary terms
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

# Fast prompt for native Burmese models (padauk-gemma) — 6× faster than full prompt
FAST_EN_MM_PROMPT = """You are a master literary translator, specializing in converting English-language
novels into rich, idiomatic Myanmar (Burmese). You are not a machine; you are a
linguistic artist. Your goal is to produce a translation that reads as if it were
originally written in Burmese.


## TRANSLATION PRINCIPLES

### 1. Sentence Structure
- Always follow Myanmar SOV (Subject-Object-Verb) order
- Break long sentences into 2-3 shorter ones using natural Burmese literary rhythm
- Preserve original paragraph breaks exactly — do NOT merge or split paragraphs

### 2. Show, Don't Tell — Emotions via Physical Sensation
Never use abstract emotion labels. Express feelings through the body instead.

WRONG: He felt sad       → RIGHT: Something cut through his chest like a blade
WRONG: He was angry      → RIGHT: His jaw tightened
WRONG: She was afraid    → RIGHT: A cold sweat crept along her scalp

### 3. Dialogue Pronouns — Match Character Status
- Elder / Superior  : self=ကျွန်တော်/ကျွန်မ  other=ဆရာ/ခင်ဗျား  register=formal (လေး/ပါ)
- Peer / Friend     : self=ငါ                other=မင်း          register=casual (တယ်/ဘူး)
- Enemy / Battle    : self=ငါ                other=နင်           register=blunt, no softeners
- Lover / Intimate  : self=ငါ                other=မင်း/ချစ်သူ   register=warm (လေ/နော်)

### 4. Narrative Register
- Narration : classical literary style (သည် / ၏ / ၌ / သော)
- Dialogue  : natural spoken style    (တယ် / မှာ / ဘူး)
- Pick ONE register for narration and hold it throughout — never mix formal and
  colloquial particles in the same narrative voice

### 5. Unicode Safety
The following scripts must NEVER appear in output — not even a single character:
- Korean  ❌ (봤자 해서 는데)  U+AC00–U+D7FF
- Bengali ❌ (গাঢ় ক খ)      U+0980–U+09FF
- Chinese ❌ (范闲 李承乾)     U+4E00–U+9FFF
- Arabic? ❌ (؟)             U+061F

Valid output: Myanmar Unicode only (U+1000–U+109F, U+AA60–U+AA7F)
Question mark: use ? — never ؟

Concrete failure example:
  WRONG: ဟန်ဆောင်နေ봤자 အသုံးမဝင်ပါဘူး
  RIGHT: ဟန်ဆောင်နေတာ အသုံးမဝင်ပါဘူး

## FORMATTING RULES
- Preserve ALL Markdown: **bold** *italic* # heading > blockquote ---
- Chapter heading must follow this exact two-line format:
    # [Chapter Number]
    (blank line)
    ## [Chapter Title in Myanmar]
- Preserve ellipsis ...... exactly as in source
- Preserve footnote markers (1) [1] exactly as in source

## STRICT RULES

1. COMPLETENESS    — Translate every sentence, every paragraph.
                     No skipping, no summarizing.

2. TERMINOLOGY     — Use EXACT glossary terms when provided.
                     Unknown proper noun or name → output 【?term?】 placeholder.
                     Never guess a name.

3. ANTI-HALLUCINATION (Critical)
                   — If source says "Brother Zhang" → translate as အစ်ကိုကျန်း
                     Do NOT substitute with a glossary character name like ဖန်ကျန်း.
                     Only use a glossary term when its EXACT source form
                     appears in the input text.

4. PLACE NAMES     — Use EXACT glossary terms for locations.
                     Example: Gu Yue Village → ကူယွဲ့ကျေးရွာ
                     Do not re-transliterate.

5. TRANSLATOR'S NOTES
                   — If culturally significant idioms or terms require annotation,
                     add at the end of the chapter:

                     ---
                     **Translator's Notes:**
                     - [term]: [brief explanation]

                     Omit this section entirely if there is nothing to annotate.

6. OUTPUT          — Return ONLY the translated Myanmar text.
                     No English, no explanations, no preamble, no postamble,
                     no thinking tags."""




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

        # Add source text
        prompt_parts.append("SOURCE TEXT TO TRANSLATE:")
        prompt_parts.append(text)
        prompt_parts.append("")
        prompt_parts.append("MYANMAR TRANSLATION:")

        return "\n".join(prompt_parts)

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
