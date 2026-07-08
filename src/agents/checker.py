"""
Checker Agent
Validates translation quality and glossary consistency.
"""

import random
import re
import logging
from difflib import SequenceMatcher
from typing import List, Dict, Any, Optional

from src.memory.memory_manager import MemoryManager
from src.agents.base_agent import BaseAgent
from src.utils.ollama_client import OllamaClient

logger = logging.getLogger(__name__)

# Sentinel so the lazy adequacy embedder can be loaded exactly once (and so a
# previous failed load is not retried on every call). Tests can inject a stub
# by assigning checker._adequacy_embedder directly.
_UNSET = object()


class Checker(BaseAgent):
    """
    Checks translation for:
    - Glossary consistency
    - Character name consistency
    - Markdown formatting preservation
    - Basic quality indicators
    """

    def __init__(
        self,
        memory_manager: MemoryManager = None,
        config: dict = None,
        ollama_client: Optional[OllamaClient] = None,
    ):
        super().__init__(ollama_client=ollama_client, memory_manager=memory_manager, config=config)
        self.memory = memory_manager
        # Lazy-loaded BGE-M3 embedder for the cross-lingual adequacy gate.
        self._adequacy_embedder = _UNSET

    def check_glossary_consistency(
        self, text: str, source_text: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """
        Check if glossary terms are used consistently.

        Two checks:
        1. Untranslated terms: source term appears verbatim in the translated
           text (it leaked through untranslated).
        2. Target spelling check: for verified character/place names that the
           source chunk actually mentions, flag if the approved target spelling
           is missing from the translation (= a wrong/inconsistent variant was
           used).

        Check 2 requires ``source_text`` (the source chunk) to know whether the
        term belongs in this chunk at all. Without it the check is skipped:
        otherwise every verified name in the novel is reported as "missing" from
        every chunk that doesn't happen to mention it, producing one false
        positive per term per chunk.

        Returns list of issues with 'term', 'expected', 'found'.
        """
        issues = []

        # Get all glossary terms
        terms = self.memory.get_all_terms()

        for term in terms:
            source = term.get('source') or term.get('source_term', '')
            target = term.get('target') or term.get('target_term', '')
            category = term.get('category', '')

            if not source or not target or len(source) < 2:
                continue

            # Check 1: Source term leaked untranslated
            if source in text:
                issues.append({
                    'type': 'untranslated_term',
                    'term': source,
                    'expected': target,
                    'found': source
                })
            # Check 2: For verified character/place names that THIS chunk's
            # source actually contains, verify the approved target spelling was
            # used. Gated on source_text + source presence to avoid flagging
            # terms that simply don't appear in this chunk.
            elif (
                source_text
                and term.get('verified')
                and category in ('character', 'place')
                and source in source_text
                and target not in text
            ):
                issues.append({
                    'type': 'target_missing',
                    'term': source,
                    'expected': target,
                    'found': '?'
                })

        return issues

    def check_markdown_formatting(self, original: str, translated: str) -> List[str]:
        """
        Check if markdown formatting is preserved.
        
        Returns list of formatting issues.
        """
        issues = []

        # Count headers in original
        original_headers = len(re.findall(r'^#+ ', original, re.MULTILINE))
        translated_headers = len(re.findall(r'^#+ ', translated, re.MULTILINE))

        if original_headers != translated_headers:
            issues.append(
                f"Header count mismatch: {original_headers} -> {translated_headers}"
            )

        # Count bold/italic markers
        original_bold = original.count('**')
        translated_bold = translated.count('**')

        if original_bold != translated_bold:
            issues.append(
                f"Bold marker count mismatch: {original_bold} -> {translated_bold}"
            )

        return issues

    def check_myanmar_unicode(self, text: str) -> List[str]:
        """
        Check for Myanmar Unicode issues.
        
        Returns list of Unicode issues.
        """
        issues = []

        # Check for common Unicode problems
        if '�' in text:
            issues.append("Contains replacement character (�)")

        # Check for mixed scripts (Myanmar range: U+1000-U+109F)
        # Allow Myanmar, punctuation, whitespace, digits
        _MYANMAR = r'\u1000-\u109F'
        _PUNCT = r'\u2000-\u206F\u3000-\u303F'
        _ALLOWED = r'\s\d.,!?;:\-\'"()[]{}'
        # NOTE: '[' and ']' MUST be escaped inside the class \u2014 an unescaped ']'
        # closes the class early, turning the rest into literals and making this
        # check silently match almost nothing.
        non_myanmar = re.findall(r'[^\u1000-\u109F\u2000-\u206F\u3000-\u303F\s\d.,!?;:\-\'"()\[\]{}]', text)
        if len(non_myanmar) > len(text) * 0.3:  # More than 30% non-Myanmar
            issues.append(f"High non-Myanmar character ratio: {len(non_myanmar)} chars")

        return issues

    def check_foreign_characters(self, text: str) -> List[Dict[str, str]]:
        """
        Check for foreign script leakage (Korean, Japanese, Chinese, etc.)
        except Bengali which is handled separately.
        
        Returns list of issues found.
        """
        issues = []
        
        # Korean Hangul (U+AC00-U+D7AF main block, U+1100-U+11FF Jamo)
        korean_chars = re.findall(r'[\uac00-\ud7af\u1100-\u11ff]', text)
        if korean_chars:
            issues.append({
                'type': 'foreign_language',
                'language': 'Korean',
                'found': ''.join(korean_chars[:10]),  # First 10 chars
                'expected': 'Translate to Burmese'
            })
        
        # Japanese Katakana (U+30A0-U+30FF)
        japanese_chars = re.findall(r'[\u30a0-\u30ff]', text)
        if japanese_chars:
            issues.append({
                'type': 'foreign_language',
                'language': 'Japanese',
                'found': ''.join(japanese_chars[:10]),
                'expected': 'Translate to Burmese'
            })
        
        # Chinese characters (already checked by LANGUAGE_GUARD but double-check)
        chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
        if chinese_chars:
            issues.append({
                'type': 'foreign_language',
                'language': 'Chinese',
                'found': ''.join(chinese_chars[:10]),
                'expected': 'Translate to Burmese'
            })
        
        return issues

    def check_incomplete_sentences(self, text: str) -> List[Dict[str, str]]:
        """
        Check for incomplete sentences (abrupt cutoffs).
        
        Looks for sentences that end mid-word or without proper ending.
        """
        issues = []
        
        # Split by sentence endings
        sentences = re.split(r'[။၊!?\n]+', text)
        
        for i, sent in enumerate(sentences):
            sent = sent.strip()
            if not sent:
                continue
                
            # Check if sentence ends abruptly (no proper ending, just cut off)
            # Pattern: ends with consonant + virama (္) without final character
            if re.search(r'[က-အ်ျြှၚၛၜၝၡၥၦၧၨၩၪၫၬၭၮၯၰၱၲၳၴၵၶၷၸၹၺၻၼၽၾၿႀႁႂႃႄႅႆႇႈႉႊႋႌႍႎႏ႐႑႒႓႔႕႖႗႘႙ႚႛႜႝ႞႟ႠႡႢႣႤႥႦႧႨႩႪႫႬႭႮႯႰႱႲႳႴႵႶႷႸႹႺႻႼႽႾႿჀჁჂჃჄჅ჆Ⴧ჈჉჊჋჌Ⴭ჎჏აბგდევზთიკლმნოპჟრსტუფქღყშჩცძწჭხჯჰჱჲჳჴჵჶჷჸჹჺ჻ჼჽჾჿᄀᄁᄂᄃᄄᄅᄆᄇᄈᄉᄊᄋᄌᄍᄎᄏᄐᄑᄒᄓᄔᄕᄖᄗᄘᄙᄚᄛᄜᄝᄞᄟᄠᄡᄢᄣᄤᄥᄦᄧᄨᄩᄪᄫᄬᄭᄮᄯᄰᄱᄲᄳᄴᄵᄶᄷᄸᄹᄺᄻᄼᄽᄾᄿᅀᅁᅂᅃᅄᅅᅆᅇᅈᅉᅊᅋᅌᅍᅎᅏᅐᅑᅒᅓᅔᅕᅖᅗᅘᅙᅚᅛᅜᅝᅞᅟᅠᅡᅢᅣᅤᅥᅦᅧᅨᅩᅪᅫᅬᅭᅮᅯᅰᅱᅲᅳᅴᅵᅶᅷᅸᅹᅺᅻᅼᅽᅾᅿᆀᆁᆂᆃᆄᆅᆆᆇᆈᆉᆊᆋᆌᆍᆎᆏᆐᆑᆒᆓᆔᆕᆖᆗᆘᆙᆚᆛᆜᆝᆞᆟᆠᆡᆢᆣᆤᆥᆦᆧᆨᆩᆪᆫᆬᆭᆮᆯᆰᆱᆲᆳᆴᆵᆶᆷᆸᆹᆺᆻᆼᆽᆾᆿᇀᇁᇂᇃᇄᇅᇆᇇᇈᇉᇊᇋᇌᇍᇎᇏᇐᇑᇒᇓᇔᇕᇖᇗᇘᇙᇚᇛᇜᇝᇞᇟᇠᇡᇢᇣᇤᇥᇦᇧᇨᇩᇪᇫᇬᇭᇮᇯᇰᇱᇲᇳᇴᇵᇶᇷᇸᇹᇺᇻᇼᇽᇾᇿሀሁሂሃሄህሆሇለሉሊላሌልሎሏሐሑሒሓሔሕሖሗመሙሚማሜምሞሟሠሡሢሣሤሥሦሧረሩሪራሬርሮሯሰሱሲሳሴስሶሷሸሹሺሻሼሽሾሿቀቁቂቃቄቅቆቇቈ቉ቊቋቌቍ቎቏ቐቑቒቓቔቕቖ቗ቘ቙ቚቛቜቝ቞቟በቡቢባቤብቦቧቨቩቪቫቬቭቮቯተቱቲታቴትቶቷቸቹቺቻቼችቾቿኀኁኂኃኄኅኆኇኈ኉ኊኋኌኍ኎኏ነኑኒናኔንኖኗኘኙኚኛኜኝኞኟአኡኢኣኤእኦኧከኩኪካኬክኮኯኰ኱ኲኳኴኵ኶኷ኸኹኺኻኼኽኾ኿ዀ዁ዂዃዄዅ዆዇ወዉዊዋዌውዎዏዐዑዒዓዔዕዖ዗ዘዙዚዛዜዝዞዟዠዡዢዣዤዥዦዧየዩዪያዬይዮዯደዱዲዳዴድዶዷዸዹዺዻዼዽዾዿጀጁጂጃጄጅጆጇገጉጊጋጌግጎጏጐ጑ጒጓጔጕ጖጗ጘጙጚጛጜጝጞጟጠጡጢጣጤጥጦጧጨጩጪጫጬጭጮጯጰጱጲጳጴጵጶጷጸጹጺጻጼጽጾጿፀፁፂፃፄፅፆፇፈፉፊፋፌፍፎፏፐፑፒፓፔፕፖፗፘፙፚ፛፜፝፞፟፠፡።፣፤፥፦፧፨፩፪፫፬፭፮፯፰፱፲፳፴፵፶፷፸፹፺፻፼ᎀᎁᎂᎃᎄᎅᎆᎇᎈᎉᎊᎋᎌᎍᎎᎏ᎐᎑᎒᎓᎔᎕᎖᎗᎘᎙]+$', sent):
                # Check if it's too short to be a valid sentence ending
                if len(sent) < 10 and not re.search(r'[။၊!?]$', sent):
                    issues.append({
                        'type': 'incomplete_sentence',
                        'position': i,
                        'text': sent[:30] + '...' if len(sent) > 30 else sent
                    })
        
        return issues

    def calculate_quality_score(self, text: str) -> float:
        """
        Calculate basic quality score (0-100).
        
        Based on:
        - Myanmar character ratio
        - Sentence count
        - Basic formatting
        """
        score = 100.0

        # Check Myanmar content ratio
        total_chars = len(text)
        myanmar_chars = len(re.findall(r'[\u1000-\u109F]', text))

        if total_chars > 0:
            myanmar_ratio = myanmar_chars / total_chars
            if myanmar_ratio < 0.5:
                score -= 30  # Too little Myanmar content
            elif myanmar_ratio < 0.7:
                score -= 15

        # Check for empty or very short output
        if total_chars < 50:
            score -= 50

        # Check for obvious error markers
        if '[ERROR' in text or '[TRANSLATION ERROR' in text:
            score -= 40

        return max(0.0, score)

    def _back_translate(self, mm_text: str) -> str:
        """
        Back-translate Myanmar text to English using the Ollama client.

        Args:
            mm_text: Myanmar (Burmese) text

        Returns:
            English back-translation, or empty string on failure
        """
        if not self.client:
            logger.warning("No Ollama client available for back-translation")
            return ""
        prompt = f"""Translate the following Myanmar (Burmese) text to English.
Output ONLY the English translation. No explanations, no notes, no Myanmar text.

Myanmar text:
{mm_text}

English translation:"""
        system_prompt = "You are a Myanmar-to-English translator. Output ONLY English. Never include the original Myanmar text."
        try:
            raw = self.client.chat(prompt=prompt, system_prompt=system_prompt)
            return (raw or "").strip()
        except Exception as e:
            logger.warning(f"Back-translation failed: {e}")
            return ""

    def check_back_translation_similarity(
        self,
        original: str,
        translated: str,
        sample_rate: float = 0.1,
        similarity_threshold: float = 0.6,
        quality_gate: float = 80.0,
    ) -> List[Dict[str, Any]]:
        """
        Check translation quality by back-translating Myanmar to English and
        comparing similarity with original source text.

        Cost-controlled via:
        - Quality gate: skip if translated already scores >= quality_gate
        - Sampling: only run on sample_rate fraction of calls
        - Similarity threshold: flag only if ratio < similarity_threshold

        Args:
            original: Original source text (Chinese or English)
            translated: Myanmar translation
            sample_rate: Fraction of calls that actually run (0.0-1.0, default 0.1)
            similarity_threshold: Minimum SequenceMatcher ratio (0.0-1.0, default 0.6)
            quality_gate: Skip if quality score >= this value (default 80)

        Returns:
            List of similarity issue dicts (empty list if skipped or passed)
        """
        issues: List[Dict[str, Any]] = []

        # Quick gate: skip if quality is already good
        score = self.calculate_quality_score(translated)
        if score >= quality_gate:
            return issues

        # Sampling gate: only run on sample_rate of remaining calls
        if random.random() >= sample_rate:
            return issues

        back_translated = self._back_translate(translated)
        if not back_translated:
            return issues

        ratio = SequenceMatcher(None, original, back_translated).ratio()
        logger.info(
            f"Back-translation similarity: {ratio:.3f} "
            f"(threshold: {similarity_threshold}, quality: {score:.0f})"
        )

        if ratio < similarity_threshold:
            issues.append({
                'type': 'back_translation_similarity',
                'score': round(ratio, 3),
                'threshold': similarity_threshold,
                'original_preview': original[:80] + '...' if len(original) > 80 else original,
                'back_translated_preview': back_translated[:80] + '...' if len(back_translated) > 80 else back_translated,
            })

        return issues

    def check_model_collapse(self, text: str) -> List[str]:
        """
        Detect signs of model collapse: name hallucination, foreign chars,
        garbage artifacts, character name in parentheses (e.g. "(Xu )").

        Returns list of issue descriptions.
        """
        issues: List[str] = []
        # Pattern: English word in parentheses after Myanmar text (model explaining itself)
        if re.search(r'[\u1000-\u109F][(][A-Za-z]{2,}\s*[)]', text):
            issues.append("Model self-annotation: English word in parentheses after Myanmar text")
        # Pattern: Vietnamese or other SE Asian characters (not Myanmar, not CJK).
        # Covers Latin Extended-A/B (U+00C0-U+024F) AND Latin Extended Additional
        # (U+1E00-U+1EFF), where Vietnamese tone-marked vowels such as '\u1EEB' (U+1EEB,
        # as in the leaked word "r\u1EEBng") live \u2014 the latter range was previously missed.
        if re.search(r'[\u00C0-\u024F\u1E00-\u1EFF]', text):
            issues.append("Latin Extended (Vietnamese/European) characters found")
        # Pattern: half-width/hanging Latin chars (truncation artifact)
        if re.search(r'\b[A-Za-z]\s{2,}', text):
            issues.append("Stray single English letters with excess spacing (truncation artifact)")
        # Pattern: consecutive duplicated lines (paragraph-level repetition loop)
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        dupe_count = sum(1 for i in range(1, len(lines)) if lines[i] == lines[i-1])
        if dupe_count >= 2:
            issues.append(f"Model repetition loop: {dupe_count} consecutive duplicate lines")
        return issues

    # ── Cross-lingual adequacy gate (BGE-M3) ──────────────────────────────────

    @property
    def adequacy_embedder(self):
        """Lazily load the BGE-M3 embedder used for the adequacy gate.

        Returns the embedder, or None if sentence-transformers / the model are
        unavailable (e.g. in CI). The result is cached — including a failed load
        as None — so we never retry a broken import on every chunk.
        """
        if self._adequacy_embedder is _UNSET:
            logger.info("Initializing BGE-M3 adequacy embedder (first chunk only)...")
            try:
                from src.dataset_alignment.embedder import BGEEmbedder
                self._adequacy_embedder = BGEEmbedder()
            except Exception as e:  # pragma: no cover - depends on optional deps
                logger.debug(f"Adequacy embedder unavailable, gate disabled: {e}")
                self._adequacy_embedder = None
        return self._adequacy_embedder

    @staticmethod
    def _strip_noise(text: str) -> str:
        """Remove BOM/zero-width chars, markdown headings, and footnote markers.

        The BOM/zero-width strip must run first: a leading \\ufeff before '#'
        otherwise defeats the heading regex, leaking the title line as a
        "sentence" that matches nothing (a false hallucination flag).
        """
        text = text.replace('﻿', '').replace('​', '')
        text = re.sub(r'(?m)^\s*#.*$', ' ', text)          # markdown headings
        text = re.sub(r'\[[0-9၀-၉]+\]', ' ', text)         # footnote markers [1]/[၁]
        return text

    @classmethod
    def _split_source_sentences(cls, text: str) -> List[str]:
        """Split English/source text into sentences for adequacy matching."""
        text = cls._strip_noise(text or "")
        parts = re.split(r'(?<=[.!?])\s+|\n{2,}', text)
        return [p.strip() for p in parts if len(p.strip()) >= 12]

    @classmethod
    def _split_target_sentences(cls, text: str) -> List[str]:
        """Split Myanmar text into sentences (terminator ။, dialogue, breaks)."""
        text = cls._strip_noise(text or "")
        # Split on the Myanmar sentence terminator and hard breaks; keep quotes.
        parts = re.split(r'(?<=။)\s*|\n{2,}', text)
        return [p.strip() for p in parts if len(p.strip()) >= 6]

    def check_adequacy(
        self,
        source_text: str,
        translated_text: str,
        threshold: float = 0.45,
    ) -> Dict[str, Any]:
        """Cross-lingual adequacy check using BGE-M3 sentence embeddings.

        Surface gates (Myanmar ratio, n-gram loops) cannot see *meaning* errors —
        a fluent chapter can still drop a sentence, invert a clause, or hallucinate
        content ("sky bridge", "French world") and still score 100/100. BGE-M3
        embeds source and translation into a shared multilingual space, so cosine
        similarity between an English sentence and its Myanmar rendering measures
        adequacy directly.

        For every source sentence we take its best-matching target sentence; a low
        best-match means the content is missing, mistranslated, or meaning-flipped.
        Target sentences with no good source match are likely hallucinations.

        Returns dict: {'checked', 'score', 'issues', 'threshold'}. When the
        embedder is unavailable the gate degrades to a no-op (checked=False) so it
        never blocks a run.
        """
        result: Dict[str, Any] = {
            "checked": False, "score": 1.0, "issues": [], "threshold": threshold,
        }
        embedder = self.adequacy_embedder
        if embedder is None:
            return result

        src_sents = self._split_source_sentences(source_text or "")
        tgt_sents = self._split_target_sentences(translated_text or "")
        if not src_sents or not tgt_sents:
            return result

        try:
            import numpy as np
            src_emb = np.asarray(embedder.encode(src_sents))
            tgt_emb = np.asarray(embedder.encode(tgt_sents))
            if src_emb.size == 0 or tgt_emb.size == 0:
                return result
            # Embeddings are L2-normalized, so the dot product is cosine similarity.
            sim = src_emb @ tgt_emb.T  # shape: [n_src, n_tgt]
        except Exception as e:  # pragma: no cover - runtime/model errors
            logger.debug(f"Adequacy check failed (non-fatal): {e}")
            return result

        issues: List[Dict[str, Any]] = []

        # Source sentences poorly covered = omission / mistranslation / meaning-flip.
        src_best = sim.max(axis=1)
        for i, best in enumerate(src_best):
            if best < threshold:
                issues.append({
                    "type": "low_adequacy",
                    "source": src_sents[i][:90],
                    "best_sim": round(float(best), 3),
                })

        # Target sentences with no source support = likely hallucination/addition.
        tgt_best = sim.max(axis=0)
        for j, best in enumerate(tgt_best):
            if best < threshold:
                issues.append({
                    "type": "possible_hallucination",
                    "target": tgt_sents[j][:70],
                    "best_sim": round(float(best), 3),
                })

        result["checked"] = True
        result["score"] = round(float(src_best.mean()), 3)
        result["issues"] = issues
        return result

    def check_chapter(
        self,
        original: str,
        translated: str
    ) -> Dict[str, Any]:
        """
        Run all checks on a chapter translation.
        
        Args:
            original: Original Chinese text
            translated: Myanmar translation
            
        Returns:
            Dict with 'passed', 'score', and 'issues'
        """
        issues = []

        # Glossary consistency
        glossary_issues = self.check_glossary_consistency(translated, source_text=original)
        issues.extend([
            f"Glossary: {i['term']} should be '{i['expected']}'"
            for i in glossary_issues
        ])

        # Markdown formatting
        format_issues = self.check_markdown_formatting(original, translated)
        issues.extend(format_issues)

        # Unicode issues
        unicode_issues = self.check_myanmar_unicode(translated)
        issues.extend(unicode_issues)

        # Foreign character leakage check
        foreign_issues_count = 0
        try:
            foreign_issues = self.check_foreign_characters(translated)
            foreign_issues_count = len(foreign_issues)
            issues.extend([
                f"Foreign ({i['language']}): {i['found'][:20]}..."
                for i in foreign_issues if i.get('found')
            ])
        except Exception as e:
            logger.warning(f"Foreign char check failed: {e}")

        # Incomplete sentences check
        incomplete_issues_count = 0
        try:
            incomplete_issues = self.check_incomplete_sentences(translated)
            incomplete_issues_count = len(incomplete_issues)
            issues.extend([
                f"Incomplete sentence: {i['text'][:30]}..."
                for i in incomplete_issues
            ])
        except Exception as e:
            logger.warning(f"Incomplete sentence check failed: {e}")

        # Back-translation similarity check (gated/sampled to control cost)
        similarity_issues_count = 0
        try:
            similarity_issues = self.check_back_translation_similarity(original, translated)
            similarity_issues_count = len(similarity_issues)
            issues.extend([
                f"Low back-translation similarity ({i['score']} < {i['threshold']}): "
                f"original={i['original_preview'][:40]}..., bt={i['back_translated_preview'][:40]}..."
                for i in similarity_issues
            ])
        except Exception as e:
            logger.warning(f"Back-translation similarity check failed: {e}")

        # Model collapse detection (name hallucination, foreign chars, repetition loops)
        collapse_issues_count = 0
        try:
            collapse_issues = self.check_model_collapse(translated)
            collapse_issues_count = len(collapse_issues)
            issues.extend(collapse_issues)
        except Exception as e:
            logger.warning(f"Model collapse check failed: {e}")

        # Calculate score
        score = self.calculate_quality_score(translated)

        # Adjust score for issues
        score -= len(issues) * 5
        score = max(0.0, score)

        return {
            'passed': score >= 70 and len(issues) < 5,
            'score': score,
            'issues': issues,
            'glossary_issues': len(glossary_issues),
            'format_issues': len(format_issues),
            'unicode_issues': len(unicode_issues),
            'foreign_issues': foreign_issues_count,
            'incomplete_issues': incomplete_issues_count,
            'back_translation_issues': similarity_issues_count,
            'collapse_issues': collapse_issues_count,
        }


