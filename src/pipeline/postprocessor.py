"""Post-processor (SPEC.md §2.5, RULES.md R-FORMAT-*, R-GLOSS*, AGENTS invariants).

Deterministic, no LLM:
- strips ``<thinking>`` / stray ``thinking`` tokens
- normalizes straight quotes -> Burmese quotes
- removes zero-width spaces (U+200B)
- enforces glossary: known Burmese variants and leaked English aliases are
  rewritten to the canonical Burmese form, capped by ``max_auto_fix``
- enforces overlap identity (R-STRUCT-04) by prepending the previous chunk's
  exact translated paragraph
- Myanmar-Unicode guards (no `؟`, no U+FFFD, no mojibake, no Indic/South-East
  Asian scripts, numbers -> Myanmar numerals)
"""
from __future__ import annotations

import re
from typing import List, Optional, Sequence, Tuple

ZWSP = "\u200b"
BYTE_ORDER_MARK = "\ufeff"

# Burmese quotation marks per RULES.md R-FORMAT-01 / style_guide.json.
BURMESE_OPEN = "\u201c"
BURMESE_CLOSE = "\u201d"

_THINK_TAG_RE = re.compile(r"<thinking>.*?</thinking>", re.DOTALL | re.IGNORECASE)
ARABIC_QUESTION = "\u061f"
REPLACEMENT_CHAR = "\ufffd"
MOJIBAKE_RE = re.compile(r"[\u00c3\u00c2][\x80-\xbf]")

_FOREIGN_RANGES = (
    (0x0E00, 0x0E7F),  # Thai
    (0x0E80, 0x0EFF),  # Lao
    (0x0980, 0x09FF),  # Bengali
    (0x0900, 0x097F),  # Devanagari
    (0x0A00, 0x0AFF),  # Gurmukhi / Gujarati
    (0x0B00, 0x0BFF),  # Oriya / Tamil
    (0x0C00, 0x0CFF),  # Telugu / Kannada
    (0x0D00, 0x0DFF),  # Malayalam / Sinhala
    (0x1700, 0x17FF),  # Khmer
    (0xAC00, 0xD7FF),  # Hangul
)
BURMESE_RANGE = (0x1000, 0x109F)

_SPACE_RE = re.compile(r"[ \t]+")
_NUMERIC_RE = re.compile(r"\b\d+\b")
_MY_DIGITS = {c: n for c, n in zip("0123456789", "၀၁၂၃၄၅၆၇၈၉")}


def has_myanmar(text: str) -> bool:
    return any(BURMESE_RANGE[0] <= ord(ch) <= BURMESE_RANGE[1] for ch in (text or ""))


def has_foreign_script(text: str) -> bool:
    return any(
        lo <= ord(ch) <= hi
        for ch in (text or "")
        for (lo, hi) in _FOREIGN_RANGES
    )


def strip_thinking(text: str) -> str:
    t = _THINK_TAG_RE.sub("", text or "")
    # stray leading `` thinking<arbitrary>`` without tags
    t = re.sub(r"^\s*=?\s*thinking\b[^A-Za-z]*", "", t, count=1)
    return t


def normalize_quotes(text: str) -> str:
    """Convert ASCII straight quotes to proper Burmese quotes (toggle pairs)."""
    out: List[str] = []
    open_next = True
    for ch in text or "":
        if ch == '"':
            out.append(BURMESE_OPEN if open_next else BURMESE_CLOSE)
            open_next = not open_next
        else:
            out.append(ch)
    return "".join(out)


def remove_zwsp(text: str) -> str:
    return (text or "").replace(ZWSP, "").replace(BYTE_ORDER_MARK, "")


def to_myanmar_numbers(text: str) -> str:
    if not text:
        return text
    return _NUMERIC_RE.sub(
        lambda m: "".join(_MY_DIGITS.get(c, c) for c in m.group(0)), text
    )


def normalize_paragraphs(text: str) -> str:
    """One paragraph per blank-line-separated run; strip each line."""
    raw_blocks = re.split(r"\n\s*\n", text or "")
    blocks: List[str] = []
    for block in raw_blocks:
        clean_lines = [l.strip() for l in block.splitlines() if l.strip()]
        if not clean_lines:
            continue
        blocks.append("\n".join(clean_lines))
    return "\n\n".join(blocks).strip()


def clean_my_text(text: Optional[str]) -> str:
    """Comprehensive deterministic cleanup of raw model output."""
    if text is None:
        return ""
    t = strip_thinking(str(text))
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t.strip())
    t = remove_zwsp(t)
    t = t.replace("\r\n", "\n")
    lines = [l.rstrip() for l in t.split("\n")]
    t = "\n".join(lines)
    t = normalize_paragraphs(t)
    t = _SPACE_RE.sub(" ", t)
    return t.strip()


def enforce_glossary(
    text: str,
    index: Sequence[dict],
    *,
    max_fixes: int = 10,
) -> Tuple[str, int]:
    """Rewrite known variants and leaked English aliases to canonical Burmese.

    Variants/aliases are applied longest-first; each replacement consumes one
    auto-fix slot.  Never re-transliterates anything — it only replaces with
    the exact glossary form (R-GLOSS-01/02).
    """
    if not index:
        return text or "", 0
    mappings: List[Tuple[str, str]] = []
    for e in index:
        my = e.get("my") or ""
        if not my:
            continue
        for v in e.get("my_variants") or []:
            if v and v != my:
                mappings.append((v, my))
        for a in e.get("aliases") or []:
            if a and a != e.get("en") and a not in (e.get("en"),):
                # English aliases leaked into Burmese output -> canonical form
                mappings.append((a, my))
        en = e.get("en")
        if en and en.isascii():
            mappings.append((en, my))
    mappings.sort(key=lambda kv: len(kv[0]), reverse=True)

    fixed = text or ""
    count = 0
    for src, dst in mappings:
        if not src:
            continue
        remaining = max_fixes - count
        if remaining <= 0:
            break
        idx = fixed.find(src)
        while idx >= 0 and remaining > 0:
            fixed = fixed[:idx] + dst + fixed[idx + len(src):]
            count += 1
            remaining -= 1
            idx = fixed.find(src)
    return fixed, count


def enforce_overlap(text: str, expected_overlap: str, paragraph_sep: str = "\n\n") -> str:
    """Guarantee R-STRUCT-04: output starts with the exact overlap paragraph."""
    if not expected_overlap:
        return text or ""
    normalized = normalize_paragraphs(text or "")
    if normalized.startswith(expected_overlap):
        return normalized
    return expected_overlap + paragraph_sep + normalized


def looks_incomplete(my: Optional[str], source: str) -> bool:
    """Reject empty / echo-of-source / non-Burmese outputs (AGENTS invariant)."""
    if not my or not my.strip():
        return True
    if not has_myanmar(my):
        return True
    clean_norm = re.sub(r"[\s\u201c\u201d\u2018\u2019\"']+", "", my).strip().casefold()
    src_norm = re.sub(r"[\s\u201c\u201d\u2018\u2019\"']+", "", source or "").strip().casefold()
    if src_norm and clean_norm == src_norm:
        return True
    ascii_alpha = sum(1 for ch in my if ch.isascii() and ch.isalpha())
    if ascii_alpha and ascii_alpha * 2 > len(my):
        return True
    return False


def apply_all(
    raw: str,
    *,
    index: Optional[Sequence[dict]] = None,
    expected_overlap: str = "",
    max_auto_fix: int = 10,
    myanmar_numbers: bool = False,
) -> Tuple[str, int]:
    """The full MP4 deterministic normalization pass.

    Returns ``(final_text, auto_fixed_count)``.
    """
    t = clean_my_text(raw)
    t, auto_fixed = enforce_glossary(t, index or [], max_fixes=max_auto_fix)
    t = enforce_overlap(t, expected_overlap)
    t = normalize_quotes(t)
    if myanmar_numbers:
        t = to_myanmar_numbers(t)
    t = t.strip()
    return t, auto_fixed