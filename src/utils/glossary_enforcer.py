"""Deterministic glossary enforcement on translated output.

The translator injects glossary terms as *soft* prompt hints; the model is free
to ignore them (and does — e.g. leaving a name untranslated, or echoing an
English place name like "village gate" verbatim). This pass is a deterministic
safety net: after translation, any glossary source term that (a) appears in the
source chunk AND (b) survived untranslated in the Myanmar output is replaced
with its approved Myanmar target.

It intentionally does NOT try to normalise Myanmar *variant spellings* of a name
(e.g. ဘိုင်ရှါချွန် → ပိုင်ရှောင်ချန်း): there is no reliable variant map, and
fuzzy-matching Burmese text risks corrupting unrelated words. Variant prevention
is the job of text-aware glossary injection, not this pass. Here we only touch
unambiguous Latin-script leakage, which is always safe to replace.
"""

import re
import logging
from typing import Any

logger = logging.getLogger(__name__)


def enforce_variants(
    translated_text: str,
    variants: list[dict[str, Any]],
) -> tuple[str, int]:
    """Normalise known Myanmar misspellings to their canonical glossary target.

    Unlike :func:`enforce_glossary` (which fixes untranslated Latin leakage), this
    handles the case where the model rendered a name in a *variant* Burmese
    spelling — e.g. ပိုင်ရှောင်ချီ for the canonical ပိုင်ရှောင်ချန်း. Each variant
    is, by definition, a misspelling of its target, so the replacement is always
    safe. Burmese has no inter-word spaces, so we use plain substring replacement
    and process longest variants first to avoid partial overlaps.
    """
    if not translated_text or not variants:
        return translated_text, 0

    items = []
    for v in variants:
        var = (v.get("variant_text") or "").strip()
        tgt = (v.get("target") or v.get("target_term") or "").strip()
        if len(var) >= 2 and tgt and var != tgt:
            items.append((var, tgt))
    items.sort(key=lambda p: len(p[0]), reverse=True)

    total = 0
    for var, tgt in items:
        if var in translated_text:
            n = translated_text.count(var)
            translated_text = translated_text.replace(var, tgt)
            total += n
            logger.debug("Variant normalise: %r -> %r (%d)", var, tgt, n)
    return translated_text, total


def enforce_glossary(
    translated_text: str,
    source_text: str,
    terms: list[dict[str, Any]],
) -> tuple[str, int]:
    """Replace verbatim source-term leakage in ``translated_text``.

    Args:
        translated_text: The Myanmar output to clean.
        source_text: The English/Chinese source chunk (used to confirm a term
            is actually relevant before replacing — avoids spurious global edits).
        terms: Glossary rows, each a dict with ``source``/``source_term`` and
            ``target``/``target_term`` keys.

    Returns:
        (clean_text, num_replacements)
    """
    if not translated_text or not terms:
        return translated_text, 0

    src_lower = source_text.lower() if source_text else ""

    # Longest source first so a multi-word term ("Inner Sect disciples") is
    # replaced before any of its substrings ("Inner Sect").
    pairs = []
    for t in terms:
        src = (t.get("source") or t.get("source_term") or "").strip()
        tgt = (t.get("target") or t.get("target_term") or "").strip()
        pairs.append((src, tgt))
    pairs.sort(key=lambda p: len(p[0]), reverse=True)

    total = 0
    for src, tgt in pairs:
        # Skip degenerate terms and placeholder targets.
        if len(src) < 2 or not tgt or "?" in tgt or "【" in tgt:
            continue
        # Only enforce Latin-script source terms — those are the ones that can
        # leak verbatim into Myanmar output and be matched unambiguously.
        if not any("a" <= c.lower() <= "z" for c in src):
            continue
        # Confirm the term is relevant to this chunk before touching the output.
        if src_lower and src.lower() not in src_lower:
            continue
        # Word-boundary, case-insensitive replacement of the leaked Latin token.
        pattern = re.compile(
            r"(?<![A-Za-z0-9])" + re.escape(src) + r"(?![A-Za-z0-9])",
            re.IGNORECASE,
        )
        new_text, n = pattern.subn(tgt, translated_text)
        if n:
            translated_text = new_text
            total += n
            logger.debug("Glossary enforce: %r -> %r (%d)", src, tgt, n)

    return translated_text, total
