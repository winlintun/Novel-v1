"""
Cultural Injector — makes structured cultural rule dicts live.

Reads the static dictionaries in cn_mm_rules.py / en_mm_rules.py
(VOCABULARY_PRECISION, CULTURAL_RULES, CONFRONTATION_SPEECH_PATTERN)
and injects TEXT-SPECIFIC rules into translation prompts whenever
the source text contains matching terms.

This is the bridge that turns 2000+ lines of dead structured data
into runtime-queryable cultural adaptation.
"""

import logging
from typing import Dict, List, Tuple

from src.agents.prompts.cn_mm_rules import (
    VOCABULARY_PRECISION as CN_VOCAB,
    CULTURAL_RULES as CN_CULTURE,
    CULTURAL_REFERENCES,
)
from src.agents.prompts.en_mm_rules import (
    VOCABULARY_PRECISION as EN_VOCAB,
    CULTURAL_RULES as EN_CULTURE,
)

logger = logging.getLogger(__name__)


def _strip_annotation(term: str) -> str:
    """Strip parenthetical English annotations from term strings.

    "魔 (demon)"  → "魔"
    "纯洁/清白 (purity, chastity)" → "纯洁/清白"
    "一石二鸟 (one stone two birds)" → "一石二鸟"
    """
    return term.split("(")[0].strip() if "(" in term else term.strip()


_EN_STOP_WORDS = frozenset({
    'the', 'and', 'for', 'was', 'had', 'you', 'his', 'her', 'its',
    'that', 'with', 'were', 'been', 'have', 'has', 'are', 'not',
    'but', 'all', 'can', 'from', 'this', 'they', 'them', 'our',
    'out', 'too', 'very', 'just', 'like', 'into', 'over', 'also',
})

# Simple stem expansion: add root forms for common past-tense verbs
_STEM_MAP = {
    'hated': ['hate', 'hated'], 'burning': ['burn', 'burning'],
    'killed': ['kill', 'killed'], 'struck': ['strike', 'struck'],
    'fought': ['fight', 'fought'], 'slashed': ['slash', 'slashed'],
    'torn': ['tear', 'torn'], 'shreds': ['shred', 'shreds'],
    'covered': ['cover', 'covered'], 'waved': ['wave', 'waved'],
}


def _extract_en_keywords(context: str, english_phrase: str = "") -> List[str]:
    """Extract meaningful English keywords from context/phrase for matching.

    Examples:
      "Enemy/cultivation antagonist — contemptuous" → ["enemy", "demon", "cultivation"]
      "I hated you with a burning passion" → ["hate", "hated", "burning", "passion"]
      "formal narrative description" → ["narrative", "formal", "description"]
    """
    keywords = set()
    if english_phrase:
        words = english_phrase.lower().split()
        for w in words:
            w = w.strip(".,!?;:\"'()")
            if len(w) >= 3 and w not in _EN_STOP_WORDS:
                keywords.add(w)
                if w in _STEM_MAP:
                    keywords.update(_STEM_MAP[w])
    else:
        parts = context.lower().replace("/", " ").replace("—", " ").split()
        for w in parts:
            w = w.strip(".,!?;:\"'()")
            if len(w) >= 3 and w not in _EN_STOP_WORDS:
                keywords.add(w)
    return list(keywords)


def _flatten_vocab_mappings(
    vocab_dict: Dict,
    is_english: bool = False,
) -> List[Tuple[str, str, str]]:
    """Extract (source_term, wrong_mm, correct_mm) tuples from VOCABULARY_PRECISION.

    Handles both CN (keyed by cn_term) and EN (keyed by english/context) dicts.
    Strips parenthetical annotations before matching.
    """
    results = []
    seen_terms = set()
    for entry in vocab_dict.values():
        for mapping in entry.get("mappings", []):
            if is_english:
                english_phrase = mapping.get("english", "")
                context = mapping.get("context", "")
                keywords = _extract_en_keywords(context, english_phrase)
                for kw in keywords:
                    if kw in seen_terms:
                        continue
                    seen_terms.add(kw)
                    correct = mapping.get("correct", "") or mapping.get("correct_mm", "")
                    wrong = mapping.get("wrong", "") or mapping.get("wrong_mm", "")
                    if kw and correct:
                        results.append((kw, wrong, correct))
                continue
            source = mapping.get("cn_term", "")
            if not source:
                continue
            clean = _strip_annotation(source)
            # Split multi-variant terms (e.g., "纯洁/清白" → ["纯洁", "清白"])
            # Minimum 2 chars to avoid single-char false positives
            variants = [v.strip() for v in clean.split("/") if v.strip()]
            for variant in variants:
                if len(variant) < 2 or variant in seen_terms:
                    continue
                seen_terms.add(variant)
                correct = mapping.get("correct_mm", "") or mapping.get("correct", "")
                wrong = mapping.get("wrong_mm", "") or mapping.get("wrong", "")
                if variant and correct:
                    results.append((variant, wrong, correct))
    return results


def _match_terms_in_text(
    text: str,
    mappings: List[Tuple[str, str, str]],
) -> List[str]:
    """Find VOCABULARY_PRECISION terms present in source text."""
    matched = []
    for term, wrong_mm, correct_mm in mappings:
        if term in text:
            line = f"  • \"{term}\" → {correct_mm}"
            if wrong_mm:
                line += f"  (NOT {wrong_mm})"
            matched.append(line)
    return matched


def _match_honorifics(
    text: str,
    mappings: Dict[str, str],
) -> List[str]:
    """Find honorific terms from text and return Myanmar equivalents."""
    matched = []
    seen_sources = set()
    for cn_honor, mm_equiv in mappings.items():
        cn_clean = _strip_annotation(cn_honor)
        if cn_clean in seen_sources:
            continue
        seen_sources.add(cn_clean)
        if cn_clean in text:
            matched.append(f"  • \"{cn_clean}\" → {mm_equiv}")
    return matched


def _match_idioms(
    text: str,
    idioms: List[Dict],
    key: str = "cn",
) -> List[str]:
    """Find idioms from text and inject correct Myanmar translations.

    Args:
        text: Source text to scan
        idioms: List of idiom dicts with source/correct/wrong fields
        key: Dict key for the source term ("cn" for Chinese, "en" for English)

    For Chinese (key="cn"): match the full idiom string in text.
    For English (key="en"): extract significant keywords from the idiom phrase
    and match any of them in text (English idioms are full sentences, not
    single words).
    """
    matched = []
    seen_sources = set()
    for idiom in idioms:
        raw = idiom.get(key, "")
        if not raw:
            continue
        source = _strip_annotation(raw)
        # Split multi-variant sources (e.g., "斩草除根" from single entry)
        variants = [v.strip() for v in source.split("/") if v.strip()] or [source]
        matched_variant = None
        for variant in variants:
            if variant in seen_sources:
                matched_variant = variant
                break
            if key == "en":
                eng_keywords = [w.strip(".,!?;:\"'()") for w in variant.lower().split()
                                if len(w.strip(".,!?;:\"'()")) >= 3
                                and w.strip(".,!?;:\"'()") not in _EN_STOP_WORDS]
                if any(kw in text.lower() for kw in eng_keywords):
                    matched_variant = variant
                    break
            elif variant in text:
                matched_variant = variant
                break
        if matched_variant is None:
            continue
        seen_sources.add(matched_variant)

        matched.append(
            f"  • \"{raw}\" → {idiom.get('correct_mm', '')}  "
            f"(NOT {idiom.get('wrong_mm', 'literal')})"
        )
    return matched


def build_cultural_injection(
    text: str,
    source_lang: str = "chinese",
) -> str:
    """Generate a prompt block with text-specific cultural translation rules.

    Scans the source text for terms matching entries in the structured
    cultural rule dictionaries and returns a formatted injection block.

    Args:
        text: Source text to analyze
        source_lang: "chinese" or "english"

    Returns:
        Formatted string block (empty string if no matches)
    """
    if not text:
        return ""

    is_en = source_lang.startswith("en")

    if is_en:
        vocab = _flatten_vocab_mappings(EN_VOCAB, is_english=True)
        honorifics = EN_CULTURE.get("honorifics_address", {}).get("mappings", {})
        idioms = EN_CULTURE.get("english_idioms", {}).get("examples", [])
        idiom_key = "en"
    else:
        vocab = _flatten_vocab_mappings(CN_VOCAB)
        honorifics = CN_CULTURE.get("honorifics_titles", {}).get("mappings", {})
        idioms = CN_CULTURE.get("chinese_idioms_chengyu", {}).get("examples", [])
        idiom_key = "cn"

    # Track matched clean terms to deduplicate across sections
    matched_clean_terms = set()
    lines = []

    # Measure words matching (EN and CN)
    if is_en:
        measure_words = EN_CULTURE.get("measure_words", {}).get("examples", [])
        mw_matches = []
        for mw in measure_words:
            noun = mw.get("noun", "")
            classifier = mw.get("classifier", "")
            example = mw.get("example", "")
            if noun and classifier and noun in text.lower():
                mw_matches.append(f"  • \"{noun}\" nouns → classifier \"{classifier}\" (e.g., {example})")
        if mw_matches:
            lines.append("\n[MEASURE WORDS — classifiers for nouns in this text]:")
            lines.extend(mw_matches)
    else:
        # CN measure words from CULTURAL_RULES (was dead — now live)
        cn_mw = CN_CULTURE.get("measure_words", {}).get("chinese_to_myanmar", {})
        mw_matches = []
        for cn_cl, mm_val in cn_mw.items():
            cn_clean = cn_cl.split(" ")[0]  # Extract "个" from "个 people/objects"
            if cn_clean and cn_clean in text:
                mw_matches.append(f"  • \"{cn_cl}\" → {mm_val}")
        if mw_matches:
            lines.append("\n[MEASURE WORDS — classifiers for Chinese nouns]:")
            lines.extend(mw_matches)

    vocab_matches = _match_terms_in_text(text, vocab)
    if vocab_matches:
        lines.append("\n[VOCABULARY PRECISION — terms found in this text]:")
        for m in vocab_matches:
            lines.append(m)
            # Extract the clean term from "  • \"term\" → ..."
            if '"' in m:
                term = m.split('"')[1]
                matched_clean_terms.add(term)

    honorific_matches = _match_honorifics(text, honorifics)
    if honorific_matches:
        filtered = [
            m for m in honorific_matches
            if not any(t in m for t in matched_clean_terms)
        ]
        if filtered:
            lines.append("\n[HONORIFICS — use these Myanmar equivalents]:")
            lines.extend(filtered)

    idiom_matches = _match_idioms(text, idioms, key=idiom_key)
    if idiom_matches:
        lines.append("\n[IDIOMS — found in source, use correct Myanmar]:")
        lines.extend(idiom_matches)

    # ── Cultivation terms (both EN and CN) ──
    if is_en:
        cult_entries = EN_CULTURE.get("cultivation_novel_terms", {}).get("examples", [])
        cult_matches = []
        for ct in cult_entries:
            en_term = ct.get("en", "")
            mm_term = ct.get("mm", "")
            if en_term and mm_term:
                kw = en_term.split("(")[0].strip().lower()
                if kw in text.lower():
                    cult_matches.append(f"  • \"{en_term}\" → {mm_term}")
    else:
        # CN cultivation terms from CULTURAL_RULES (was dead — now live)
        cult_dict = CN_CULTURE.get("cultivation_terms", {}).get("standard_terms", {})
        cult_matches = []
        for cn_term_full, mm_val in cult_dict.items():
            clean_cn = cn_term_full.split("(")[0].strip()
            if not clean_cn:
                continue
            # Check if any '/' variant of the term is in the text
            # Minimum 2 chars to avoid false positives (e.g., 气 in 天气)
            found = False
            for variant in clean_cn.split("/"):
                v = variant.strip()
                if len(v) >= 2 and v in text:
                    found = True
                    break
            if found:
                mm_clean = mm_val.split("→")[0].strip() if "→" in mm_val else mm_val
                cult_matches.append(f"  • \"{cn_term_full}\" → {mm_clean}")
    if cult_matches:
        lines.append("\n[CULTIVATION TERMS — found in this text]:")
        lines.extend(cult_matches)

    # ── CULTURAL REFERENCES (CN only — mythological, kinship, color, allusions, buddhist, historical, festivals, poetry) ──
    if not is_en:
        ref_sections = []

        def _any_variant_in_text(raw: str) -> bool:
            """Check if any '/' variant of a term is in the source text.
            Minimum 2 Chinese chars to avoid false positives (e.g., 气 in 天气).
            """
            clean = _strip_annotation(raw)
            for v in clean.split("/"):
                variant = v.strip()
                if len(variant) >= 2 and variant in text:
                    return True
            return False

        # Mythological beings
        myth_matches = []
        for entry in CULTURAL_REFERENCES.get("mythological_beings", {}).get("mappings", []):
            cn = entry.get("cn", "")
            if cn and _any_variant_in_text(cn):
                myth_matches.append(
                    f"  • \"{cn}\" → {entry.get('mm_translation', '')}  "
                    f"({entry.get('note', '')})"
                )
        if myth_matches:
            ref_sections.append(("\n[CULTURAL REFERENCES — mythological beings]:", myth_matches))

        # Kinship terms
        kin_matches = []
        for entry in CULTURAL_REFERENCES.get("kinship_terms", {}).get("mappings", []):
            cn = entry.get("cn_term", "")
            if cn and _any_variant_in_text(cn):
                kin_matches.append(
                    f"  • \"{cn}\" → {entry.get('mm', '')}  ({entry.get('note', '')})"
                )
        if kin_matches:
            ref_sections.append(("\n[KINSHIP TERMS — simplify to Myanmar]:", kin_matches))

        # Color symbolism
        color_matches = []
        for entry in CULTURAL_REFERENCES.get("color_symbolism", {}).get("mappings", []):
            cn_color = entry.get("cn_color", "")
            if cn_color and _any_variant_in_text(cn_color):
                color_matches.append(
                    f"  • \"{cn_color}\" → {entry.get('mm_render', '')}  "
                    f"({entry.get('note', '')})"
                )
        if color_matches:
            ref_sections.append(("\n[COLOR SYMBOLISM — adapt meaning]:", color_matches))

        # Classical allusions
        allus_matches = []
        for entry in CULTURAL_REFERENCES.get("classical_allusions", {}).get("examples", []):
            cn = entry.get("cn", "")
            if cn and _any_variant_in_text(cn):
                allus_matches.append(
                    f"  • \"{cn}\" → {entry.get('correct', '')}  "
                    f"(NOT {entry.get('wrong', 'literal')}) — {entry.get('meaning', '')}"
                )
        if allus_matches:
            ref_sections.append(("\n[CLASSICAL ALLUSIONS — express meaning, not literal]:", allus_matches))

        # Buddhist terms
        buddhist_matches = []
        for entry in CULTURAL_REFERENCES.get("buddhist_terms", {}).get("mappings", []):
            cn = entry.get("cn", "")
            if cn and _any_variant_in_text(cn):
                buddhist_matches.append(
                    f"  • \"{cn}\" → {entry.get('mm', '')}  ({entry.get('note', '')})"
                )
        if buddhist_matches:
            ref_sections.append(("\n[BUDDHIST TERMS — Mahayana→Theravada adaptation]:", buddhist_matches))

        # Historical/political terms
        hist_matches = []
        for entry in CULTURAL_REFERENCES.get("historical_political_terms", {}).get("mappings", []):
            cn = entry.get("cn", "")
            if cn and _any_variant_in_text(cn):
                hist_matches.append(
                    f"  • \"{cn}\" → {entry.get('mm', '')}  ({entry.get('note', '')})"
                )
        if hist_matches:
            ref_sections.append(("\n[HISTORICAL TERMS — Myanmar equivalents]:", hist_matches))

        # Festivals/food
        fest_matches = []
        for entry in CULTURAL_REFERENCES.get("festivals_food_customs", {}).get("mappings", []):
            cn = entry.get("cn", "")
            if cn and _any_variant_in_text(cn):
                fest_matches.append(
                    f"  • \"{cn}\" → {entry.get('mm', '')}  ({entry.get('note', '')})"
                )
        if fest_matches:
            ref_sections.append(("\n[FESTIVALS & FOOD — cultural adaptation]:", fest_matches))

        # Poetry adaptation (always show if poetry present)
        poetry_matches = []
        for entry in CULTURAL_REFERENCES.get("poetry_adaptation", {}).get("examples", []):
            orig = entry.get("original", "")
            if orig and _any_variant_in_text(orig):
                poetry_matches.append(
                    f"  • {entry.get('cn_form', '')}: \"{orig[:30]}...\" → {entry.get('mm_prose', '')[:80]}..."
                )
        if poetry_matches:
            ref_sections.append(("\n[POETRY — adapt meaning, not meter]:", poetry_matches))

        # Dead CN dicts now live: time expressions from CULTURAL_RULES
        time_matches = []
        for cn, mm in CN_CULTURE.get("time_expressions", {}).get("mappings", {}).items():
            clean_cn = cn.split("(")[0].strip()
            if clean_cn and mm and len(clean_cn) >= 2 and clean_cn in text:
                time_matches.append(f"  • \"{cn}\" → {mm}")
        if time_matches:
            ref_sections.append(("\n[TIME EXPRESSIONS — Myanmar naturalization]:", time_matches))

        for header, matches in ref_sections:
            lines.append(header)
            lines.extend(matches)

    if lines:
        lines.insert(0, "--- TEXT-SPECIFIC TRANSLATION RULES ---")
        lines.append("---")

    return "\n".join(lines)
