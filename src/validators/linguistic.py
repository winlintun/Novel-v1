"""Linguistic validators — language detection, script purity, punctuation."""

import regex

from src.dataset_alignment.config import get_alignment_config
from src.dataset_alignment.database import connect, insert_issue
from src.dataset_alignment.loaders import read_chapter_text
from . import Validator, ValidatorContext, register

MYANMAR_PATTERN = regex.compile(r"[\u1000-\u109F\uAA60-\uAA7F\uA9E0-\uA9FF]")
INDIC_PATTERN = regex.compile(
    r"[\u0900-\u097F"  # Devanagari
    r"\u0980-\u09FF"   # Bengali
    r"\u0A00-\u0A7F"   # Gurmukhi
    r"\u0A80-\u0AFF"   # Gujarati
    r"\u0B00-\u0B7F"   # Oriya
    r"\u0B80-\u0BFF"   # Tamil
    r"\u0C00-\u0C7F"   # Telugu
    r"\u0C80-\u0CFF"   # Kannada
    r"\u0D00-\u0D7F"   # Malayalam
    r"]"
)
CHINESE_PATTERN = regex.compile(r"[\u4E00-\u9FFF]{2,}")
THAI_PATTERN = regex.compile(r"[\u0E00-\u0E7F]")
KHMER_PATTERN = regex.compile(r"[\u1780-\u17FF]")
LATIN_PATTERN = regex.compile(r"[A-Za-z]{4,}")


@register
class LanguageDetectionValidator(Validator):
    name = "language_detection"

    def run(self, ctx: ValidatorContext) -> int:
        n = 0
        cfg = get_alignment_config()
        with connect() as conn:
            tgt_files = conn.execute(
                "SELECT id, filename FROM files WHERE novel=? AND lang=?",
                (ctx.novel, cfg.tgt_lang),
            ).fetchall()

            for f in tgt_files:
                try:
                    text = read_chapter_text(f["id"])
                except Exception:
                    continue

                mm_ratio = len(MYANMAR_PATTERN.findall(text)) / max(len(text), 1)
                latin_ratio = len(LATIN_PATTERN.findall(text)) / max(len(text), 1)

                if mm_ratio < 0.5:
                    insert_issue(
                        conn,
                        file_id=f["id"],
                        category="linguistic.low_myanmar_ratio",
                        severity="error",
                        message=f"'{f['filename']}' has only {mm_ratio:.0%} Myanmar chars",
                        evidence=f"mm_ratio={mm_ratio:.3f}, latin={latin_ratio:.3f}",
                    )
                    n += 1
        return n


@register
class ScriptPurityValidator(Validator):
    name = "script_purity"

    def run(self, ctx: ValidatorContext) -> int:
        n = 0
        with connect() as conn:
            tgt_lang = get_alignment_config().tgt_lang
            tgt_files = conn.execute(
                "SELECT id, filename FROM files WHERE novel=? AND lang=?",
                (ctx.novel, tgt_lang),
            ).fetchall()

            for f in tgt_files:
                try:
                    text = read_chapter_text(f["id"])
                except Exception:
                    continue

                if INDIC_PATTERN.search(text):
                    insert_issue(
                        conn,
                        file_id=f["id"],
                        category="linguistic.indic_script_leak",
                        severity="error",
                        message=f"Indic script found in '{f['filename']}'",
                        auto_fixable=True,
                    )
                    n += 1
                if CHINESE_PATTERN.search(text):
                    insert_issue(
                        conn,
                        file_id=f["id"],
                        category="linguistic.chinese_script_leak",
                        severity="warn",
                        message=f"Chinese chars found in '{f['filename']}'",
                        auto_fixable=True,
                    )
                    n += 1
                if THAI_PATTERN.search(text):
                    insert_issue(
                        conn,
                        file_id=f["id"],
                        category="linguistic.thai_script_leak",
                        severity="error",
                        message=f"Thai script found in '{f['filename']}'",
                        auto_fixable=True,
                    )
                    n += 1
                if KHMER_PATTERN.search(text):
                    insert_issue(
                        conn,
                        file_id=f["id"],
                        category="linguistic.khmer_script_leak",
                        severity="error",
                        message=f"Khmer script found in '{f['filename']}'",
                        auto_fixable=True,
                    )
                    n += 1
        return n


@register
class PunctuationValidator(Validator):
    name = "punctuation"

    def run(self, ctx: ValidatorContext) -> int:
        n = 0
        with connect() as conn:
            rows = conn.execute(
                """SELECT s.id, s.text, s.chapter_id, c.chapter_no
                   FROM sentences s JOIN chapters c ON s.chapter_id = c.id
                   WHERE c.novel=? AND s.lang=?
                   LIMIT 200""",
                (ctx.novel, get_alignment_config().tgt_lang),
            ).fetchall()

            for r in rows:
                has_ender = bool(regex.search(r"[။?!]$", r["text"].strip()))
                if not has_ender:
                    insert_issue(
                        conn,
                        sentence_id=r["id"],
                        chapter_id=r["chapter_id"],
                        category="linguistic.missing_ender",
                        severity="info",
                        message=f"Chapter {r['chapter_no']}: sentence missing ender",
                        evidence=r["text"][:100],
                    )
                    n += 1
        return n
