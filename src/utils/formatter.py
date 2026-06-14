"""
src/utils/formatter.py
One-click formatting cleanup for Myanmar fiction translation files.

Each fixer is independent: fix_*(text) -> (new_text, FixResult).
Composite entry point: format_chapter(text, options) -> FormatterReport.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ── Re-use postprocessor helpers (no duplication) ─────────────────────────────
from src.utils.postprocessor import (
    fix_chapter_heading_format,
    remove_duplicate_headings,
    ensure_markdown_readability,
    remove_korean_characters,
    remove_bengali_characters,
    remove_chinese_characters,
    remove_indic_characters,
)


# ──────────────────────────────────────────────────────────────────────────────
# Data types
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class FixResult:
    name: str
    description: str
    changes: int = 0

    def as_dict(self) -> dict:
        return {"name": self.name, "description": self.description, "changes": self.changes}


@dataclass
class FormatterReport:
    original: str
    text: str
    fixes: list[FixResult] = field(default_factory=list)

    @property
    def total_changes(self) -> int:
        return sum(f.changes for f in self.fixes)

    @property
    def changed(self) -> bool:
        return self.text != self.original

    def as_dict(self) -> dict:
        return {
            "text": self.text,
            "fixes": [f.as_dict() for f in self.fixes],
            "total_changes": self.total_changes,
            "changed": self.changed,
        }


# ──────────────────────────────────────────────────────────────────────────────
# Individual fixers
# ──────────────────────────────────────────────────────────────────────────────

def fix_line_endings(text: str) -> tuple[str, FixResult]:
    """CRLF → LF; strip trailing whitespace per line."""
    r = FixResult("line_endings", "Normalize line endings (CRLF→LF) and strip trailing spaces")
    crlf = text.count('\r\n')
    lone_cr = text.count('\r') - crlf
    lines_before = text.split('\n')
    trailing = sum(1 for ln in lines_before if ln != ln.rstrip())

    text = text.replace('\r\n', '\n').replace('\r', '\n')
    text = '\n'.join(ln.rstrip() for ln in text.split('\n'))
    r.changes = crlf + lone_cr + trailing
    return text, r


def fix_blank_lines(text: str) -> tuple[str, FixResult]:
    """Collapse 4+ newlines (= 3+ blank lines) to 2 blank lines."""
    r = FixResult("blank_lines", "Collapse excess blank lines (3+ consecutive → 2)")
    before = text
    text = re.sub(r'\n{4,}', '\n\n\n', text)
    r.changes = len(re.findall(r'\n{4,}', before))
    return text, r


def fix_punctuation(text: str) -> tuple[str, FixResult]:
    """Fix Arabic marks, spaces before Myanmar enders, double sentence-enders."""
    r = FixResult("punctuation", "Fix punctuation: Arabic marks, space-before-ender, double-enders")
    changes = 0

    # Arabic / full-width punctuation → ASCII / Myanmar equivalents
    subs = [
        ('؟', '?'),    # Arabic question mark
        ('،', ','),    # Arabic comma
        ('؛', ';'),    # Arabic semicolon
        ('！', '!'),   # Full-width exclamation
        ('？', '?'),   # Full-width question mark
        ('　', ' '),   # Full-width space
    ]
    for bad, good in subs:
        n = text.count(bad)
        if n:
            text = text.replace(bad, good)
            changes += n

    # Space(s) before sentence-ender ။ (but NOT inside markdown like # headings)
    n = len(re.findall(r'[ \t]+(?=။)', text))
    text = re.sub(r'[ \t]+(?=။)', '', text)
    changes += n

    # Space(s) before clause-ender ၊
    n = len(re.findall(r'[ \t]+(?=၊)', text))
    text = re.sub(r'[ \t]+(?=၊)', '', text)
    changes += n

    # Double sentence-ender ။ ။ → ။  (with optional space between)
    n = len(re.findall(r'။[ 	]*(?:။)+', text))
    text = re.sub(r'။[ 	]*(?:။)+', '။', text)
    changes += n

    # Space(s) immediately before ! or ? (when NOT part of common patterns like ?!)
    n = len(re.findall(r'[ \t]+(?=[!?])', text))
    text = re.sub(r'[ \t]+(?=[!?])', '', text)
    changes += n

    # Multiple internal spaces → single (preserves leading indentation)
    n = len(re.findall(r'(?<=\S)[ \t]{2,}(?=\S)', text))
    text = re.sub(r'(?<=\S)[ \t]{2,}(?=\S)', ' ', text)
    changes += n

    r.changes = changes
    return text, r


def fix_quote_style(text: str) -> tuple[str, FixResult]:
    """Normalize smart/curly quotes to plain straight double quotes."""
    r = FixResult("quote_style", "Normalize curly/smart quotes to plain straight double quotes")
    changes = 0
    replacements = [
        ('“', '"'),  # " LEFT DOUBLE QUOTATION MARK
        ('”', '"'),  # " RIGHT DOUBLE QUOTATION MARK
        ('‘', "'"),  # ' LEFT SINGLE QUOTATION MARK
        ('’', "'"),  # ' RIGHT SINGLE QUOTATION MARK
        ('«', '"'),  # « LEFT-POINTING DOUBLE ANGLE QUOTATION
        ('»', '"'),  # » RIGHT-POINTING DOUBLE ANGLE QUOTATION
        ('„', '"'),  # „ DOUBLE LOW-9 QUOTATION MARK
        ('‟', '"'),  # ‟ DOUBLE HIGH-REVERSED-9 QUOTATION MARK
    ]
    for bad, good in replacements:
        n = text.count(bad)
        if n:
            text = text.replace(bad, good)
            changes += n
    r.changes = changes
    return text, r


def fix_ellipsis(text: str) -> tuple[str, FixResult]:
    """Normalize ellipsis to Myanmar 6-dot convention (…, 3/4/5 dots → ......)."""
    r = FixResult("ellipsis", "Normalize ellipsis to Myanmar 6-dot convention (......)")
    changes = 0

    # Unicode ellipsis character → 6 dots
    n = text.count('…')
    if n:
        text = text.replace('…', '......')
        changes += n

    # 4 or 5 consecutive dots → 6 dots
    before = text
    text = re.sub(r'(?<!\.)\.{4,5}(?!\.)', '......', text)
    changes += len(re.findall(r'(?<!\.)\.{4,5}(?!\.)', before))

    # 3 consecutive dots NOT already part of ...... → ......
    # Uses negative lookbehind/ahead for dot
    before = text
    text = re.sub(r'(?<!\.)\.{3}(?!\.)', '......', text)
    changes += len(re.findall(r'(?<!\.)\.{3}(?!\.)', before))

    r.changes = changes
    return text, r


def fix_script_leakage(text: str) -> tuple[str, FixResult]:
    """Remove Korean, Bengali, Chinese, Indic script characters that crept into Myanmar text."""
    r = FixResult("script_leakage",
                  "Remove foreign script leakage (Korean, Bengali, Chinese, Indic)")
    # Count before removal
    korean  = len(re.findall(r'[가-힯ᄀ-ᇿ　-〿]', text))
    bengali = len(re.findall(r'[ঀ-৿]', text))
    chinese = len(re.findall(r'[一-鿿㐀-䶿]', text))
    indic   = len(re.findall(
        r'[ऀ-ॿ਀-੿઀-૿଀-୿஀-௿'
        r'ఀ-౿ಀ-೿ഀ-ൿ඀-෿]', text))

    text = remove_korean_characters(text)
    text = remove_bengali_characters(text)
    text = remove_chinese_characters(text)
    text = remove_indic_characters(text)

    r.changes = korean + bengali + chinese + indic
    return text, r


def fix_duplicate_paragraphs(text: str) -> tuple[str, FixResult]:
    """Remove consecutively duplicate paragraphs (exact match after strip)."""
    r = FixResult("duplicates", "Remove consecutive duplicate paragraphs")
    paras = text.split('\n\n')
    deduped: list[str] = []
    prev_stripped: Optional[str] = None
    changes = 0
    for para in paras:
        s = para.strip()
        if s and s == prev_stripped:
            changes += 1
            continue
        deduped.append(para)
        if s:
            prev_stripped = s
    r.changes = changes
    return '\n\n'.join(deduped), r


_MYANMAR_RE = re.compile(r'[က-႟]')

# Patterns that indicate a natural paragraph break point in Myanmar fiction
# 1. After dialogue closing quote + dialogue tag, before next opening quote or narration
# 2. After ...... (ellipsis scene transition)
# 3. After ། followed by optional space and opening quote "

_DIALOGUE_SPLIT_PATTERN = re.compile(
    r'(?<=[၊།])\s+(?=")',   # after clause/sentence-ender + space + opening quote
)
_ELLIPSIS_SPLIT_PATTERN = re.compile(
    r'(?<=\.{6})\s+(?=[က-႟"])',  # after 6+ dots + space + Myanmar/quote
)
_POST_TAG_SPLIT_PATTERN = re.compile(
    # After dialogue tag ending in တယ်/သည်/ပြီ/ခဲ့ etc. before new content
    r'(?<=[တ][ယ်])\s+(?=[က-႟"])|'
    r'(?<=[သ][ည်])\s+(?=[က-႟"])|'
    r'(?<=[ပ][ြ][ီ])\s+(?=[က-႟"])',
)


def fix_paragraph_breaks(text: str, min_blob_len: int = 500) -> tuple[str, FixResult]:
    """
    Restore paragraph breaks in over-long 'blob' paragraphs.

    Paragraphs longer than min_blob_len chars are split at natural boundaries:
    - After sentence-ender (། ၊) immediately before opening quote "
    - After 6-dot ellipsis ......
    - After common dialogue-tag endings before new content
    """
    r = FixResult("paragraph_breaks",
                  f"Restore paragraph breaks in blob paragraphs (>{min_blob_len} chars)")
    paras = text.split('\n\n')
    new_paras: list[str] = []
    changes = 0

    for para in paras:
        stripped = para.strip()
        # Skip: short paragraphs, headings, separators
        if len(stripped) <= min_blob_len or stripped.startswith('#') or stripped.startswith('---'):
            new_paras.append(para)
            continue

        # No Myanmar content → leave alone
        if not _MYANMAR_RE.search(stripped):
            new_paras.append(para)
            continue

        # Apply split patterns in order of reliability
        working = stripped

        # Pass 1: after sentence-ender before opening quote
        parts = _DIALOGUE_SPLIT_PATTERN.split(working)
        if len(parts) > 1:
            changes += len(parts) - 1
            new_paras.extend(p.strip() for p in parts if p.strip())
            continue

        # Pass 2: after ellipsis
        parts = _ELLIPSIS_SPLIT_PATTERN.split(working)
        if len(parts) > 1:
            changes += len(parts) - 1
            new_paras.extend(p.strip() for p in parts if p.strip())
            continue

        # Pass 3: after dialogue-tag endings
        parts = _POST_TAG_SPLIT_PATTERN.split(working)
        if len(parts) > 1:
            changes += len(parts) - 1
            new_paras.extend(p.strip() for p in parts if p.strip())
            continue

        # No split found: leave as-is
        new_paras.append(para)

    r.changes = changes
    return '\n\n'.join(new_paras), r


def fix_chapter_heading(text: str) -> tuple[str, FixResult]:
    """Fix malformed chapter headings and remove duplicates."""
    r = FixResult("chapter_heading", "Fix malformed/duplicate chapter headings")
    before = text
    text = fix_chapter_heading_format(text)
    text = remove_duplicate_headings(text)
    r.changes = 0 if text == before else 1
    return text, r


# ──────────────────────────────────────────────────────────────────────────────
# Composite entry point
# ──────────────────────────────────────────────────────────────────────────────

DEFAULT_OPTIONS = {
    "line_endings":        True,
    "blank_lines":         True,
    "punctuation":         True,
    "quote_style":         True,
    "ellipsis":            True,
    "script_leakage":      True,
    "duplicate_paragraphs":True,
    "paragraph_breaks":    True,
    "chapter_heading":     True,
    "markdown_readability":True,
}


def format_chapter(text: str, options: Optional[dict] = None) -> FormatterReport:
    """
    Run all enabled formatters on text and return a FormatterReport.

    Args:
        text:    Raw Myanmar chapter content (markdown)
        options: Dict of {fixer_name: bool}. Defaults to all enabled.

    Returns:
        FormatterReport with fixed text and per-fixer change counts.
    """
    opt = {**DEFAULT_OPTIONS, **(options or {})}
    report = FormatterReport(original=text, text=text)

    def _run(enabled: bool, fn, *args):
        if not enabled:
            return
        new_text, fix = fn(report.text, *args)
        report.text = new_text
        report.fixes.append(fix)

    _run(opt["line_endings"],         fix_line_endings)
    _run(opt["blank_lines"],          fix_blank_lines)
    _run(opt["script_leakage"],       fix_script_leakage)
    _run(opt["duplicate_paragraphs"], fix_duplicate_paragraphs)
    _run(opt["paragraph_breaks"],     fix_paragraph_breaks)
    _run(opt["punctuation"],          fix_punctuation)
    _run(opt["quote_style"],          fix_quote_style)
    _run(opt["ellipsis"],             fix_ellipsis)
    _run(opt["chapter_heading"],      fix_chapter_heading)

    if opt.get("markdown_readability", True):
        before = report.text
        report.text = ensure_markdown_readability(report.text)
        if report.text != before:
            report.fixes.append(FixResult("markdown", "Ensure proper markdown paragraph spacing", 1))

    report.text = report.text.strip()
    return report


# ──────────────────────────────────────────────────────────────────────────────
# File-level helpers
# ──────────────────────────────────────────────────────────────────────────────

def format_file(path: str | Path, backup: bool = True, options: Optional[dict] = None) -> FormatterReport:
    """
    Load a .mm.md file, format it, write it back, return the report.
    Creates a .bak.md backup unless backup=False.
    """
    path = Path(path)
    with open(path, 'r', encoding='utf-8-sig') as f:
        original = f.read()

    report = format_chapter(original, options)

    if report.changed:
        if backup:
            bak = path.with_suffix('.bak.md')
            shutil.copy2(path, bak)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(report.text)

    return report


def format_novel(novel_output_dir: str | Path,
                 backup: bool = True,
                 options: Optional[dict] = None) -> list[dict]:
    """
    Format all *.mm.md files in a directory. Returns a list of per-file summaries.
    """
    output_dir = Path(novel_output_dir)
    results = []
    for path in sorted(output_dir.glob("*.mm.md")):
        try:
            report = format_file(path, backup=backup, options=options)
            results.append({
                "file": path.name,
                "total_changes": report.total_changes,
                "changed": report.changed,
                "fixes": [f.as_dict() for f in report.fixes if f.changes > 0],
                "error": None,
            })
        except Exception as e:
            results.append({
                "file": path.name,
                "total_changes": 0,
                "changed": False,
                "fixes": [],
                "error": str(e),
            })
    return results
