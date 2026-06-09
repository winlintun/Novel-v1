"""Structural validators — chapter pairing, file naming, encoding, duplicates."""

import logging
from pathlib import Path

from src.dataset_alignment.config import get_alignment_config
from src.dataset_alignment.database import connect, insert_issue
from . import Validator, ValidatorContext, register

logger = logging.getLogger(__name__)


@register
class ChapterAlignmentValidator(Validator):
    name = "chapter_alignment"

    def run(self, ctx: ValidatorContext) -> int:
        n = 0
        with connect() as conn:
            unpaired = conn.execute(
                """SELECT COUNT(*) AS c FROM chapters
                   WHERE novel=? AND (src_file_id IS NULL OR tgt_file_id IS NULL)""",
                (ctx.novel,),
            ).fetchone()["c"]
            if unpaired:
                insert_issue(
                    conn,
                    category="structural.unpaired_chapters",
                    severity="warn",
                    message=f"{unpaired} chapters missing source or target file",
                )
                n += 1
        return n


@register
class MissingChaptersValidator(Validator):
    name = "missing_chapters"

    def run(self, ctx: ValidatorContext) -> int:
        n = 0
        with connect() as conn:
            src = {
                r["chapter_no"]
                for r in conn.execute(
                    "SELECT chapter_no FROM files WHERE novel=? AND lang=?",
                    (ctx.novel, get_alignment_config().src_lang),
                )
            }
            tgt = {
                r["chapter_no"]
                for r in conn.execute(
                    "SELECT chapter_no FROM files WHERE novel=? AND lang=?",
                    (ctx.novel, get_alignment_config().tgt_lang),
                )
            }
            missing_src = tgt - src
            missing_tgt = src - tgt
            for ch in sorted(missing_src):
                insert_issue(
                    conn,
                    category="structural.missing_source",
                    severity="error",
                    message=f"Chapter {ch}: source file not found (target exists)",
                    auto_fixable=False,
                )
                n += 1
            for ch in sorted(missing_tgt):
                insert_issue(
                    conn,
                    category="structural.missing_target",
                    severity="error",
                    message=f"Chapter {ch}: target file not found (source exists)",
                    auto_fixable=False,
                )
                n += 1
        return n


@register
class FileNamingValidator(Validator):
    name = "file_naming"

    def run(self, ctx: ValidatorContext) -> int:
        n = 0
        with connect() as conn:
            rows = conn.execute(
                "SELECT id, filename, chapter_no FROM files WHERE novel=?",
                (ctx.novel,),
            ).fetchall()
            for r in rows:
                if r["chapter_no"] is None:
                    insert_issue(
                        conn,
                        file_id=r["id"],
                        category="structural.file_naming",
                        severity="warn",
                        message=f"Filename '{r['filename']}' has no extractable chapter number",
                        auto_fixable=False,
                    )
                    n += 1
        return n


@register
class EncodingValidator(Validator):
    name = "encoding"

    def run(self, ctx: ValidatorContext) -> int:
        n = 0
        with connect() as conn:
            rows = conn.execute(
                "SELECT id, path FROM files WHERE novel=?",
                (ctx.novel,),
            ).fetchall()
            for r in rows:
                try:
                    with open(r["path"], "rb") as f:
                        raw = f.read()
                    raw.decode("utf-8")
                except UnicodeDecodeError:
                    insert_issue(
                        conn,
                        file_id=r["id"],
                        category="structural.encoding",
                        severity="error",
                        message=f"File is not valid UTF-8: {Path(r['path']).name}",
                        auto_fixable=False,
                    )
                    n += 1
        return n


@register
class DuplicateFilesValidator(Validator):
    name = "duplicate_files"

    def run(self, ctx: ValidatorContext) -> int:
        n = 0
        with connect() as conn:
            rows = conn.execute(
                """SELECT sha256, COUNT(*) AS c, GROUP_CONCAT(filename) AS files
                   FROM files WHERE novel=?
                   GROUP BY sha256 HAVING c > 1""",
                (ctx.novel,),
            ).fetchall()
            for r in rows:
                insert_issue(
                    conn,
                    category="structural.duplicate_files",
                    severity="warn",
                    message=f"Duplicate SHA256: {r['files']} ({r['c']} copies)",
                    evidence=r["sha256"],
                    auto_fixable=True,
                )
                n += 1
        return n
