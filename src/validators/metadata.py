"""Metadata validators — chapter alignment completeness."""

from src.dataset_alignment.database import connect, insert_issue
from . import Validator, ValidatorContext, register


@register
class ChapterAlignmentCheckValidator(Validator):
    name = "chapter_alignment_check"

    def run(self, ctx: ValidatorContext) -> int:
        n = 0
        with connect() as conn:
            rows = conn.execute(
                """SELECT id, chapter_no, src_file_id, tgt_file_id,
                          src_char_count, tgt_char_count
                   FROM chapters WHERE novel=?""",
                (ctx.novel,),
            ).fetchall()

            for r in rows:
                if r["src_file_id"] and not r["tgt_file_id"]:
                    insert_issue(
                        conn,
                        chapter_id=r["id"],
                        category="metadata.missing_target",
                        severity="error",
                        message=f"Chapter {r['chapter_no']}: source exists but no target file",
                    )
                    n += 1
                elif r["tgt_file_id"] and not r["src_file_id"]:
                    insert_issue(
                        conn,
                        chapter_id=r["id"],
                        category="metadata.missing_source",
                        severity="error",
                        message=f"Chapter {r['chapter_no']}: target exists but no source file",
                    )
                    n += 1
                elif r["src_file_id"] and r["tgt_file_id"]:
                    if not r["src_char_count"] or not r["tgt_char_count"]:
                        insert_issue(
                            conn,
                            chapter_id=r["id"],
                            category="metadata.no_char_count",
                            severity="info",
                            message=f"Chapter {r['chapter_no']}: char counts not computed",
                        )
                        n += 1
        return n
