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

from src.utils.postprocessor import clean_output, validate_output, detect_language_leakage, myanmar_char_ratio, looks_truncated
from src.utils.cultural_injector import build_cultural_injection
from src.agents.base_agent import BaseAgent
from src.agents.prompts import (
    TRANSLATOR_SYSTEM_PROMPT,
)


logger = logging.getLogger(__name__)

# Token budget for the truncation retry — roughly double the default (2048) so a
# chunk that was cut off mid-sentence has room to finish on the second attempt.
_TRUNCATION_RETRY_TOKENS = 4096


def _clip_example(text: str, limit: int) -> str:
    """Clip a few-shot example to ``limit`` chars without splitting a syllable.

    Myanmar syllable clusters are consonant + combining marks (U+102B–U+103E,
    etc.). A blind ``text[:200]`` slice (the old behaviour) routinely cut a
    cluster in half, producing a broken glyph in the prompt that the model then
    imitated. We back off to the last whitespace so the example always ends on a
    clean word boundary, then append an ellipsis to signal it was trimmed.
    """
    text = " ".join(text.split())  # collapse newlines/runs so examples stay compact
    if len(text) <= limit:
        return text
    cut = text[:limit]
    sp = cut.rfind(" ")
    if sp > limit * 0.5:  # only honour the space if it isn't pathologically early
        cut = cut[:sp]
    return cut.rstrip() + "…"


def get_language_prompt(
    source_lang: str,
    model_name: str = "",
    scene_type: str = "narration",
    genre: str = "",
) -> str:
    """Get system prompt based on source language with full translation rules.

    Incorporates cn_mm_rules.py (CN→MM) and en_mm_rules.py (EN→MM)
    linguistic transformation rules for comprehensive prompt generation,
    plus genre-specific rules for novel-type adaptation.
    
    Args:
        source_lang: Source language ("chinese" or "english")
        model_name: Model name for prompt optimization (fast prompt for padauk-gemma)
        scene_type: Scene type for dynamic rule injection
            ("narration" | "dialogue" | "action" | "confrontation")
        genre: Novel genre ("xianxia", "wuxia", "fantasy", "romance", "general")
    """
    from src.agents.prompts import build_translator_prompt as _build_translator_prompt
    return _build_translator_prompt(source_lang, model_name, scene_type, genre)




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
        # Drop retrieved examples whose source is a near-exact match for the query
        # (similarity >= this). Such hits mean the corpus contains the very text
        # being translated (e.g. re-translating a chapter that is itself in the
        # RAG corpus), so the model would just be handed the existing answer
        # instead of a *similar* example to imitate. Set >= 1.0 to disable.
        self.rag_max_similarity = rag_config.get('max_similarity', 0.97)

        # Token budget for the truncation retry (config-driven; see config/settings.yaml
        # models.retry_num_predict). Falls back to the module default if unset.
        self.retry_num_predict = self.config.get('models', {}).get(
            'retry_num_predict', _TRUNCATION_RETRY_TOKENS
        )

        # QE re-ranking (best-of-N). OFF by default — it multiplies generation cost
        # by num_candidates. When enabled, each chunk is sampled num_candidates
        # times (varying only the seed, so Myanmar-safe temperature is unchanged)
        # and the best output is chosen by src.utils.qe_rerank. See settings.yaml
        # `rerank:`.
        rerank_cfg = self.config.get('rerank', {})
        self.rerank_enabled = bool(rerank_cfg.get('enabled', False))
        self.rerank_candidates = max(1, int(rerank_cfg.get('num_candidates', 3)))
        self.rerank_seed_base = int(rerank_cfg.get('seed_base', 1234))

        # Secondary-model fallback for per-chunk model collapse. When the primary
        # translator returns empty twice (e.g. a completion-only model with no
        # chat template intermittently yielding empty output, as translategemma
        # does), re-translate that single chunk with a known chat-capable model
        # (the refiner/editor/checker, typically padauk-gemma) instead of emitting
        # a blank chunk. Resolved once here; only used when it differs from the
        # primary so we never "fall back" to the same failing model.
        models_cfg = self.config.get('models', {}) if self.config else {}
        primary_model = getattr(self.ollama, 'model', '') if self.ollama else ''
        self._fallback_model = (
            models_cfg.get('refiner')
            or models_cfg.get('editor')
            or models_cfg.get('checker')
        )
        if not self._fallback_model or self._fallback_model == primary_model:
            self._fallback_model = None

    def get_system_prompt(self, source_lang: str = "english", scene_type: str = "narration") -> str:
        """Get system prompt based on source language (chinese or english).

        Args:
            source_lang: Source language ("chinese" or "english")
            scene_type: Scene type for dynamic linguistic rule injection
                ("narration" | "dialogue" | "action" | "confrontation")
        """
        if self._custom_system_prompt:
            return self._custom_system_prompt
        model_name = getattr(self.ollama, 'model', '') if self.ollama else ''
        genre = self.config.get('project', {}).get('novel_genre', '') if self.config else ''
        return get_language_prompt(
            source_lang,
            model_name=model_name,
            scene_type=scene_type,
            genre=genre,
        )

    def build_prompt(self, text: str, rolling_context: str = "") -> str:
        """Build translation prompt with memory context and rolling translation context.
        
        Args:
            text: Source text to translate
            rolling_context: Tail of previous translated chunk (Myanmar, ≤400 tokens)
        """
        # Get all memory context. Pass the chunk text so the glossary is filtered
        # to terms that actually appear here (text-aware injection) rather than a
        # fixed chapter-wide top-20.
        mem = self.memory.get_all_memory_for_prompt(source_text=text)
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

        # Add text-specific cultural translation rules (live from structured dicts)
        source_lang = self.config.get('project', {}).get('source_language', 'chinese')
        cultural_rules = build_cultural_injection(text, source_lang=source_lang)
        if cultural_rules:
            prompt_parts.append(cultural_rules)
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
            # Glossary-aware retrieval (F3): pass the current novel's approved
            # glossary source terms so the retriever boosts examples that share
            # vocabulary with this novel. The model then sees human translations
            # of *its* terminology (names, sects, cultivation terms), not just
            # any xianxia paragraph — improving term consistency, not just style.
            glossary_sources: list = []
            try:
                all_terms = self.memory.get_all_terms()
                glossary_sources = [
                    t.get("source", "") for t in all_terms
                    if t.get("source") and t.get("verified")
                ]
            except Exception:
                pass  # glossary unavailable — retrieve without bias (unchanged behavior)

            # Retrieve a LARGER candidate pool than we inject, so the selection
            # step below can enforce a dialogue+descriptive mix and bias toward
            # compressed (transcreated) examples rather than taking raw top-k.
            examples = self.rag_retriever.retrieve_similar(
                query_text=source_text,
                top_k=max(self.rag_top_k * 3, 9),
                glossary_sources=glossary_sources or None,
            )

            # The retriever owns the similarity decision: it returns Chroma
            # results when they clear min_similarity, otherwise SQLite keyword
            # matches (whose word-overlap score is on a different scale). Do NOT
            # re-apply the Chroma cosine threshold here — that would discard the
            # SQLite fallback. Drop only clearly-irrelevant (similarity <= 0).
            examples = [e for e in examples if e.similarity > 0]

            # Drop near-exact matches: when the corpus contains the very text
            # being translated, the top hit is the human translation of THIS
            # source, so injecting it leaks the answer instead of demonstrating
            # style on *different* text. Only filter Chroma-scale cosine scores
            # (0..1); SQLite keyword-overlap scores can also exceed the threshold
            # but are not true similarities, so leave them when Chroma was empty.
            dropped = [e for e in examples if e.similarity >= self.rag_max_similarity]
            filtered = [e for e in examples if e.similarity < self.rag_max_similarity]
            if dropped and filtered:
                logger.info(
                    "RAG: dropped %d near-duplicate example(s) (sim >= %.2f, likely self-reference)",
                    len(dropped), self.rag_max_similarity,
                )
                examples = filtered
            elif dropped and not filtered:
                # Every match was a near-duplicate. Keeping them would just echo
                # the answer; better to inject nothing and let the model translate.
                logger.info(
                    "RAG: all %d match(es) were near-duplicates (sim >= %.2f) — injecting none",
                    len(dropped), self.rag_max_similarity,
                )
                return ""

            if not examples:
                logger.info("RAG: 0 examples — no usable match (Chroma + SQLite both empty)")
                return ""

            # Select from the pool: balanced dialogue+descriptive mix, compression-biased.
            examples = self._select_rag_examples(examples, n=self.rag_top_k)

            top_sim = max(e.similarity for e in examples)
            logger.info(
                "RAG: %d example(s) injected (top sim %.2f)", len(examples), top_sim,
            )

            # Frame the retrieved pairs as a human translator's work to imitate.
            # padauk-gemma follows demonstrated STYLE far more reliably than
            # abstract rules, so this is the strongest single lever for making
            # output read like a person rather than a machine.
            parts = [
                "HUMAN REFERENCE TRANSLATIONS — a professional Myanmar translator produced the pairs below.",
                "Study HOW they translate: natural Burmese flow, SOV order, particle choice (သည်/က/ကို/မှာ),",
                "idiomatic word choice, dialogue register, and sentence rhythm. Match that voice exactly.",
                "Do NOT copy their wording or content — only imitate their style on the SOURCE TEXT.",
                "",
            ]
            for i, ex in enumerate(examples, 1):
                parts.append(f"Example {i}:")
                parts.append(f"  English source : {_clip_example(ex.en_text, 320)}")
                parts.append(f"  Human Myanmar  : {_clip_example(ex.my_text, 400)}")
                parts.append("")

            return "\n".join(parts)

        except Exception as e:
            logger.warning(f"RAG retrieval failed: {e}")
            return ""

    @staticmethod
    def _select_rag_examples(candidates: list, n: int) -> list:
        """Pick `n` few-shot examples from a candidate pool.

        Beyond raw similarity, we want the injected set to (a) include BOTH a
        dialogue and a descriptive example (so the model sees both registers) and
        (b) lean toward COMPRESSED human translations — pairs where the Myanmar
        uses fewer tokens per English word demonstrate the transcreation/
        compression the model fails at. Relevance still dominates; compression is
        a mild tie-breaker so an irrelevant-but-short example can't crowd in.
        """
        import re as _re
        if len(candidates) <= n:
            return candidates

        def mm_tokens(t: str) -> int:
            return len(_re.findall(r'[က-႟]+', t or ""))

        def en_words(t: str) -> int:
            return max(1, len((t or "").split()))

        def is_dialogue(ex) -> bool:
            return any(q in (ex.en_text or "") for q in '"“”')

        def compression(ex) -> float:
            # mm tokens per en word; lower = more compressed = better demonstration
            return mm_tokens(ex.my_text) / en_words(ex.en_text)

        # Relevance-first ranking with a small compression bonus (weight 0.05 keeps
        # cosine [0..1] dominant; compression typically ~1, so the nudge is gentle).
        ranked = sorted(candidates, key=lambda e: e.similarity - 0.05 * compression(e), reverse=True)
        chosen = list(ranked[:n])

        # Guarantee a register mix when the pool actually contains both.
        def ensure(pred):
            if any(pred(e) for e in candidates) and not any(pred(e) for e in chosen):
                extra = next((e for e in ranked if pred(e) and e not in chosen), None)
                if extra:
                    chosen[-1] = extra  # drop the least-relevant pick for the missing type
        ensure(is_dialogue)
        ensure(lambda e: not is_dialogue(e))
        return chosen

    def _detect_scene_type(self, text: str, lang: str = "chinese") -> str:
        """Detect dominant scene type from source text for dynamic rule injection.

        Analyzes text for confrontation, action, and dialogue indicators
        to select the appropriate linguistic rules from build_linguistic_context().

        Args:
            text: Source text paragraph to analyze
            lang: Source language ("chinese" or "english")

        Returns:
            Scene type: "confrontation" | "action" | "dialogue" | "narration"
        """
        if lang == "chinese":
            confrontation_kw = ['你', '死', '杀', '恨', '报仇', '妖', '魔', '畜生']
            action_kw = ['打', '击', '剑', '刀', '攻', '战', '拳', '掌']
        else:
            confrontation_kw = ['you', 'die', 'kill', 'hate', 'revenge', 'demon', 'curse']
            action_kw = [
                'strike', 'struck', 'attack', 'attacked', 'fight', 'fought',
                'sword', 'slash', 'slashed', 'punch', 'punched',
                'battle', 'battled', 'kick', 'kicked',
            ]

        lines = [line for line in text.split('\n') if line.strip()]
        total_lines = len(lines) if lines else 1
        dialogue_lines = sum(1 for line in lines if any(q in line for q in '""「」『』'))
        exclamation_count = text.count('!') + text.count('！')
        confrontation_count = sum(1 for kw in confrontation_kw if kw in text)
        action_count = sum(1 for kw in action_kw if kw in text)
        dialogue_ratio = dialogue_lines / total_lines

        if confrontation_count >= 2 or (exclamation_count >= 2 and dialogue_ratio > 0.3):
            return "confrontation"
        if dialogue_ratio > 0.5:
            return "dialogue"
        if action_count >= 3:
            return "action"
        return "narration"

    def _best_of_n(
        self,
        paragraph: str,
        prompt: str,
        system_prompt: str,
        num_predict: int,
        chapter_num: int,
    ) -> tuple[str, str]:
        """Sample ``rerank_candidates`` translations and return the best one.

        Diversity comes from varying the per-call seed at the SAME temperature, so
        Myanmar output quality (which degrades above temp 0.2) is preserved. The
        winner is chosen by :func:`qe_rerank.generate_and_select` using fluency +
        hard-defect penalties (placeholders, leakage, truncation, loops, length).

        Returns ``(translated, raw)`` where both are the chosen *cleaned* text
        (``raw`` is kept aligned for the existing downstream retry logic). Falls
        back to a reinforced single-shot generation if every candidate is empty.
        """
        from src.utils.qe_rerank import generate_and_select

        def _gen(i: int) -> str:
            raw_i = self.ollama.chat(
                prompt=prompt,
                system_prompt=system_prompt,
                num_predict=num_predict,
                seed=self.rerank_seed_base + i,
            )
            return clean_output(raw_i)

        sel = generate_and_select(paragraph, _gen, n=self.rerank_candidates)
        best = sel.get("best", "")
        if best and best.strip():
            logger.info(
                f"QE best-of-{self.rerank_candidates}: chose candidate "
                f"{sel['best_index']} (chapter {chapter_num})"
            )
            return best, best

        # Every candidate empty — reinforced single-shot fallback (model collapse).
        logger.warning(
            f"QE best-of-N produced no usable output (chapter {chapter_num}); "
            f"retrying with reinforced prompt..."
        )
        retry_system = system_prompt + "\n\nIMPORTANT: You must provide a translation. Do not return an empty response."
        raw = self.ollama.chat(prompt=prompt, system_prompt=retry_system, num_predict=num_predict)
        return clean_output(raw), raw

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

        # Auto-detect scene type for dynamic linguistic rule injection
        scene_type = self._detect_scene_type(paragraph, lang=lang_key)
        system_prompt = self.get_system_prompt(lang_key, scene_type=scene_type)

        # First attempt. Size the output ceiling generously up front (≈ 3× the
        # source token estimate, floored at 2048 and capped at the retry budget)
        # so a genuinely long chunk does not hit the token limit and force the
        # expensive truncation re-generation below. num_predict is a MAX, not a
        # target — the model still stops at its stop token — so a high ceiling is
        # free. (Note: this does not suppress a re-sample retry when the model
        # stops mid-sentence well under the ceiling; that is looks_truncated's
        # job, not the budget's.)
        src_tokens = max(1, int(len(paragraph) * 1.5))
        first_num_predict = min(self.retry_num_predict, max(2048, src_tokens * 3))
        if self.rerank_enabled and self.rerank_candidates > 1:
            # Sample N candidates (varying seed) and keep the best under QE scoring.
            translated, raw = self._best_of_n(
                paragraph, prompt, system_prompt, first_num_predict, chapter_num
            )
        else:
            raw = self.ollama.chat(
                prompt=prompt,
                system_prompt=system_prompt,
                num_predict=first_num_predict,
            )

            # Handle empty response (model collapse)
            if not raw or not raw.strip():
                logger.warning(f"Empty response from model in chapter {chapter_num}. Retrying with reinforced prompt...")
                retry_system = system_prompt + "\n\nIMPORTANT: You must provide a translation. Do not return an empty response."
                retry_raw = self.ollama.chat(
                    prompt=prompt,
                    system_prompt=retry_system
                )
                # The retry can also come back empty/None — keep whatever is
                # non-empty so we never pass None downstream to clean_output.
                raw = retry_raw or raw or ""

                # Still empty after two tries → the primary model has collapsed on
                # this chunk. Rather than blanking it, re-translate the single chunk
                # with a chat-capable secondary model (e.g. padauk-gemma).
                if not raw.strip() and self._fallback_model:
                    logger.warning(
                        f"Primary translator collapsed (empty x2) on a chunk in "
                        f"chapter {chapter_num}; falling back to secondary model "
                        f"'{self._fallback_model}'."
                    )
                    try:
                        fb_raw = self.ollama.chat(
                            prompt=prompt,
                            system_prompt=retry_system,
                            model=self._fallback_model,
                            num_predict=first_num_predict,
                        )
                    except Exception as e:
                        logger.warning(
                            f"Secondary-model fallback raised in chapter {chapter_num}: {e}"
                        )
                        fb_raw = ""
                    if fb_raw and fb_raw.strip():
                        logger.info(
                            f"Secondary model '{self._fallback_model}' recovered the "
                            f"collapsed chunk in chapter {chapter_num}."
                        )
                        raw = fb_raw

                if not raw.strip():
                    logger.warning(f"Model returned empty response twice in chapter {chapter_num}; continuing with empty output.")

            # Clean output
            translated = clean_output(raw)

        # ── Truncation detection + retry ──
        # If the model stopped mid-sentence (hit its token limit), the tail of the
        # chunk is simply missing and no postprocessing can recover it. Re-run once
        # with a larger token budget and keep the result if it completes (or is at
        # least longer). See postprocessor.looks_truncated for the heuristic.
        if looks_truncated(translated):
            prev_len = len(translated)
            logger.warning(
                f"Output looks truncated (chapter {chapter_num}, {prev_len} chars) — "
                f"retrying with larger token budget ({self.retry_num_predict})..."
            )
            # Guard the retry: a failed retry must NOT discard the partial result we
            # already have — a truncated translation beats crashing the chapter.
            try:
                raw_longer = self.ollama.chat(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    num_predict=self.retry_num_predict,
                )
            except Exception as e:
                logger.warning(f"Truncation retry failed ({e}); keeping original output.")
                raw_longer = ""
            translated_longer = clean_output(raw_longer) if raw_longer else ""
            now_complete = translated_longer and not looks_truncated(translated_longer)
            if translated_longer and (now_complete or len(translated_longer) > prev_len):
                raw, translated = raw_longer, translated_longer
                logger.info(
                    f"Truncation retry: {prev_len} -> {len(translated)} chars "
                    f"({'now complete' if now_complete else 'still truncated, kept longer'})."
                )
            else:
                logger.warning("Truncation retry did not improve output; keeping original.")

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

    def back_translate(self, mm_text: str) -> str:
        """
        Back-translate Myanmar text to English using the chat template.

        Args:
            mm_text: Myanmar (Burmese) text to back-translate

        Returns:
            English translation of the Myanmar text
        """
        prompt = f"""Translate the following Myanmar (Burmese) text to English.
Output ONLY the English translation. No explanations, no notes, no Myanmar text.

Myanmar text:
{mm_text}

English translation:"""
        system_prompt = "You are a Myanmar-to-English translator. Output ONLY English. Never include the original Myanmar text."

        raw = self.ollama.chat(
            prompt=prompt,
            system_prompt=system_prompt
        )
        result = (raw or "").strip()
        return result

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
