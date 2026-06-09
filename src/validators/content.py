"""Content-integrity validators — omission, hallucination, terminology."""

import json
from collections import Counter

import regex

from src.dataset_alignment.database import connect, insert_issue
from src.dataset_alignment.loaders import read_chapter_text
from . import Validator, ValidatorContext, register

_SENTENCE_ENDER = regex.compile(r"[။?!]$")


def _get_chapter_pairs(novel: str):
    """Yield (chapter_row, src_sents, tgt_sents) for aligned chapters."""
    from src.dataset_alignment.config import get_alignment_config
    from src.dataset_alignment.preprocessing import (
        clean_text, extract_title_and_body, normalize_text, segment_sentences,
    )

    cfg = get_alignment_config()
    with connect() as conn:
        chapters = conn.execute(
            """SELECT id, chapter_no, src_file_id, tgt_file_id
               FROM chapters WHERE novel=? AND src_file_id IS NOT NULL
               AND tgt_file_id IS NOT NULL ORDER BY chapter_no""",
            (novel,),
        ).fetchall()

    for r in chapters:
        src_raw = read_chapter_text(r["src_file_id"])
        tgt_raw = read_chapter_text(r["tgt_file_id"])
        _, src_body = extract_title_and_body(src_raw)
        _, tgt_body = extract_title_and_body(tgt_raw)
        src_body = clean_text(normalize_text(src_body)).text
        tgt_body = clean_text(normalize_text(tgt_body)).text
        src_sents = segment_sentences(src_body, cfg.src_lang)
        tgt_sents = segment_sentences(tgt_body, cfg.tgt_lang)
        yield r, src_sents, tgt_sents


@register
class OmissionValidator(Validator):
    name = "omission"

    def run(self, ctx: ValidatorContext) -> int:
        n = 0
        for r, src_sents, tgt_sents in _get_chapter_pairs(ctx.novel):
            src_ending = src_sents[-1] if src_sents else ""
            tgt_ending = tgt_sents[-1] if tgt_sents else ""
            if src_sents and not _SENTENCE_ENDER.search(src_ending):
                continue
            if tgt_sents and not _SENTENCE_ENDER.search(tgt_ending):
                with connect() as conn:
                    insert_issue(
                        conn,
                        chapter_id=r["id"],
                        category="content.incomplete_sentence",
                        severity="warn",
                        message=f"Chapter {r['chapter_no']}: target ends without sentence ender",
                        evidence=tgt_ending[:200],
                    )
                    n += 1

            ratio = len(tgt_sents) / max(len(src_sents), 1)
            if ratio < 0.3:
                with connect() as conn:
                    insert_issue(
                        conn,
                        chapter_id=r["id"],
                        category="content.omission_suspected",
                        severity="error",
                        message=f"Chapter {r['chapter_no']}: target has {len(tgt_sents)} sentences vs {len(src_sents)} source ({ratio:.0%})",
                    )
                    n += 1
        return n


@register
class HallucinationLiteValidator(Validator):
    name = "hallucination_lite"

    def run(self, ctx: ValidatorContext) -> int:
        n = 0
        DATE_PATTERN = regex.compile(
            r"(january|february|march|april|may|june|july|august|"
            r"september|october|november|december|\d{4}|"
            r"chapter \d|volume \d)", regex.IGNORECASE)
        URL_PATTERN = regex.compile(r"https?://\S+")

        for r, _, tgt_sents in _get_chapter_pairs(ctx.novel):
            for s in tgt_sents:
                if DATE_PATTERN.search(s):
                    with connect() as conn:
                        insert_issue(
                            conn,
                            chapter_id=r["id"],
                            category="content.hallucination_lite",
                            severity="warn",
                            message=f"Chapter {r['chapter_no']}: date/metadata pattern in target",
                            evidence=s[:200],
                        )
                        n += 1
                if URL_PATTERN.search(s):
                    with connect() as conn:
                        insert_issue(
                            conn,
                            chapter_id=r["id"],
                            category="content.hallucination_lite",
                            severity="error",
                            message=f"Chapter {r['chapter_no']}: URL found in target",
                            evidence=s[:200],
                        )
                        n += 1
        return n


@register
class TerminologyValidator(Validator):
    name = "terminology"

    def run(self, ctx: ValidatorContext) -> int:
        n = 0
        with connect() as conn:
            pairs = conn.execute(
                """SELECT a.id, a.chapter_id, a.src_ids, a.tgt_ids
                   FROM alignments a JOIN chapters c ON a.chapter_id = c.id
                   WHERE c.novel=? AND a.kind='1:1' LIMIT 50""",
                (ctx.novel,),
            ).fetchall()

            for r in pairs:
                import json as _json
                try:
                    src_ids = _json.loads(r["src_ids"])
                    tgt_ids = _json.loads(r["tgt_ids"])
                except Exception:
                    continue
                if not src_ids or not tgt_ids:
                    continue
                src = conn.execute(
                    "SELECT text FROM sentences WHERE chapter_id=? AND seq=?",
                    (r["chapter_id"], src_ids[0]),
                ).fetchone()
                tgt = conn.execute(
                    "SELECT text FROM sentences WHERE chapter_id=? AND seq=?",
                    (r["chapter_id"], tgt_ids[0]),
                ).fetchone()
                if not src or not tgt:
                    continue

                en_words_lower = set(src["text"].lower().split())
                non_stop_en = {w for w in en_words_lower if len(w) > 4 and w not in
                               {"about", "their", "there", "where", "which", "would", "could", "should"}}
                tgt_words = set(tgt["text"].lower().split())
                leaked = non_stop_en & tgt_words
                if leaked:
                    insert_issue(
                        conn,
                        chapter_id=r["chapter_id"],
                        category="content.terminology_english_leak",
                        severity="warn",
                        message=f"English word(s) found in Myanmar translation: {leaked}",
                        evidence=tgt["text"][:200],
                    )
                    n += 1
        return n
