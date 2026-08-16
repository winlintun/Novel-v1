"""Assembly-time hard gates + hygiene (todo.md §2/§3, SPEC §4).

The Verifier is a *per-chunk* gate.  These checks treat the fully assembled
chapter as a single artifact and run once, right before commit:

- ``assembly_script_gate()``  HARD — every char must be Myanmar / Unicode
    punctuation+numbers / whitespace, and any Latin token must be on the
    loanword allowlist.  Rejects Thai, Bengali, Devanagari, Hangul, ...
- ``dedup_assembled_paras()`` SOFT — drop paragraphs >85% similar to a recent
    sibling (overlap-window artifacts), returning an audit trail.
- ``assembly_completeness()`` HARD — re-run ``looks_incomplete()`` on the
    whole assembled body (a clean chunk end is no proof the join is clean).
- ``normalize_hygiene()``     post — unify dashes/ellipsis/quotes, strip ASCII
    dividers, collapse whitespace.  Applied *after* the gates so it cannot
    mask a script leak.
- ``check_naming_consistency()`` P2 — flag an entity rendered with >N distinct
    Myanmar spellings (the ``Shu Shu`` / ``park manager`` drift).
"""
from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from typing import List, Optional, Sequence, Tuple

from .postprocessor import looks_incomplete

# Myanmar U+1000-U+109F + Myanmar Extended-A U+AA60-U+AA7F (padauk-gemma).
MYANMAR_BLOCKS = ((0x1000, 0x109F), (0xAA60, 0xAA7F))

# Loanwords we transliterate deterministically instead of rejecting outright
# (todo.md §7: "add a transliteration mapping so the model doesn't emit raw
# Latin").  Keys are matched as whole words, longest-first.
LOANWORD_MAP = {
    "Level": "အဆင့်",
}

_LATIN_TOKEN_RE = re.compile(r"[A-Za-z]+")
_DIVIDER_LINE_RE = re.compile(r"^\s*[_\-=]{3,}\s*$", re.MULTILINE)
_DASH_RUN_RE = re.compile(r"[\u2012\u2013\u2014\u2015]+")
_SPACED_HYPHEN_RE = re.compile(r"(?<=[ \n])-+(?=[ \n])")
_EN_ELLIPSIS_RE = re.compile(r"။\.\.\.|\.\.\.")
_MY_ELLIPSIS_RE = re.compile(r"။{3,}")
_ELLIPSIS_RUN_RE = re.compile(r"\u2026{2,}")


def assembly_script_gate(
    text: str,
    loanword_allowlist: Optional[Sequence[str]] = None,
) -> Tuple[bool, str]:
    """Whitelist gate: Myanmar + punctuation/numbers/whitespace only.

    Latin letter runs are allowed *only* when they are in ``loanword_allowlist``
    (e.g. ``HP``, ``NPC``, ``QQ``); anything else returns ``(False, reason)``.
    """
    allow = set(loanword_allowlist or ())
    body = text or ""
    for token in _LATIN_TOKEN_RE.findall(body):
        if token not in allow:
            return False, f"Unapproved Latin token: '{token}'"
    for ch in body:
        o = ord(ch)
        if any(lo <= o <= hi for lo, hi in MYANMAR_BLOCKS):
            continue
        if ch.isspace():
            continue
        cat = unicodedata.category(ch)
        if cat.startswith("P") or cat.startswith("N"):
            continue
        if o < 0x80:  # remaining ASCII (letters checked above; symbols fine)
            continue
        return False, f"Foreign script char U+{o:04X} ({unicodedata.name(ch, '?')})"
    return True, ""


def dedup_assembled_paras(
    paragraphs: Sequence[str],
    threshold: float = 0.85,
    lookback: int = 5,
) -> Tuple[List[str], List[str]]:
    """Drop paragraphs too similar to a recent sibling; return kept + dropped."""
    cleaned: List[str] = []
    dropped: List[str] = []
    for para in paragraphs:
        p = para.strip()
        if not p:
            continue
        is_dup = any(
            SequenceMatcher(None, p, prev, autojunk=False).ratio() > threshold
            for prev in cleaned[-lookback:]
        )
        if is_dup:
            dropped.append(p)
        else:
            cleaned.append(p)
    return cleaned, dropped


def assembly_completeness(
    paragraphs: Sequence[str],
    source_paras: Optional[Sequence[str]] = None,
) -> Tuple[bool, str]:
    """Re-run ``looks_incomplete()`` on the assembled body (todo.md §2.3)."""
    body = "\n\n".join(p for p in paragraphs if p and p.strip())
    if not body:
        return False, "assembled body is empty"
    source = "\n\n".join(source_paras or ())
    if looks_incomplete(body, source):
        return False, "assembled body looks incomplete (no Myanmar / echo of source)"
    return True, ""


def normalize_hygiene(text: str) -> str:
    """Unify dash/ellipsis/quote style, strip ASCII dividers, tidy whitespace."""
    t = text or ""
    t = t.replace("\u2018", "\u201c").replace("\u2019", "\u201d")
    t = _DASH_RUN_RE.sub("\u2014", t)
    t = _SPACED_HYPHEN_RE.sub("\u2014", t)
    t = _EN_ELLIPSIS_RE.sub("\u2026", t)
    t = _MY_ELLIPSIS_RE.sub("\u2026", t)
    t = _ELLIPSIS_RUN_RE.sub("\u2026", t)
    t = _DIVIDER_LINE_RE.sub("", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    lines = [ln.rstrip() for ln in t.split("\n")]
    return "\n".join(lines).strip()


def translate_loanwords(text: str) -> str:
    """Deterministic transliteration of approved loanwords (whole-word, longest-first)."""
    t = text or ""
    for src in sorted(LOANWORD_MAP, key=len, reverse=True):
        dst = LOANWORD_MAP[src]
        t = re.sub(r"(?<![A-Za-z])" + re.escape(src) + r"(?![A-Za-z])", dst, t)
    return t


def check_naming_consistency(
    text: str,
    glossary_index: Sequence[dict],
    max_variants: int = 2,
) -> List[str]:
    """Flag entities rendered with more than ``max_variants`` spellings.

    Uses the canonical ``my`` plus each entry's ``my_variants``; purely
    advisory (does not block commit) — todo.md §4.
    """
    flags: List[str] = []
    body = text or ""
    for e in glossary_index or ():
        my = e.get("my") or ""
        spellings: set = {s for s in (e.get("my_variants") or []) if s and s in body}
        if my and my in body:
            spellings.add(my)
        if len(spellings) > max_variants:
            flags.append(
                f"{e.get('en')} rendered as {len(spellings)} variants: {sorted(spellings)}"
            )
    return flags
