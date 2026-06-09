"""Quality validators — ChrF score, length ratio.

Note: BERTScore is disabled by default as it requires a GPU.
"""

import logging

import numpy as np

from src.dataset_alignment.database import connect, insert_issue
from . import Validator, ValidatorContext, register

logger = logging.getLogger(__name__)


@register
class ChrFValidator(Validator):
    name = "chrf"

    def run(self, ctx: ValidatorContext) -> int:
        n = 0
        try:
            import sacrebleu
        except ImportError:
            logger.info("sacrebleu not installed — skipping ChrF validation")
            return 0

        with connect() as conn:
            rows = conn.execute(
                """SELECT s.text AS src, t.text AS tgt, c.chapter_no
                   FROM sentences s
                   JOIN sentences t ON s.chapter_id = t.chapter_id
                   JOIN chapters c ON s.chapter_id = c.id
                   WHERE c.novel=? AND s.lang=? AND t.lang=?
                   AND s.seq = t.seq
                   LIMIT 500""",
                (ctx.novel, "en", "my"),
            ).fetchall()

            for r in rows:
                if len(r["tgt"]) < 20:
                    continue
                try:
                    score = sacrebleu.sentence_chrf(r["tgt"], [r["src"]]).score
                    if score < 15:
                        insert_issue(
                            conn,
                            category="quality.low_chrf",
                            severity="warn",
                            message=f"Chapter {r['chapter_no']}: ChrF score {score:.1f} < 15",
                        )
                        n += 1
                except Exception:
                    continue
        return n


@register
class BERTScoreValidator(Validator):
    name = "bertscore"

    def run(self, ctx: ValidatorContext) -> int:
        logger.info("BERTScore validator requires GPU — skipping")
        return 0
