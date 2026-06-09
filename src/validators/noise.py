"""Noise artifact validators — translator notes, ads, formatting artifacts."""

import regex

from src.dataset_alignment.config import get_alignment_config
from src.dataset_alignment.database import connect, insert_issue
from src.dataset_alignment.loaders import read_chapter_text
from . import Validator, ValidatorContext, register


@register
class NoiseArtifactsValidator(Validator):
    name = "noise_artifacts"

    def run(self, ctx: ValidatorContext) -> int:
        cfg = get_alignment_config()
        n = 0
        with connect() as conn:
            files = conn.execute(
                "SELECT id, filename, lang FROM files WHERE novel=?",
                (ctx.novel,),
            ).fetchall()

            for f in files:
                try:
                    text = read_chapter_text(f["id"])
                except Exception:
                    continue

                for cat in ("translator_notes", "ads", "formatting_artifacts", "ocr_errors"):
                    for pat in cfg.rule("noise_patterns", cat, default=[]) or []:
                        matches = regex.findall(pat, text)
                        if matches:
                            insert_issue(
                                conn,
                                file_id=f["id"],
                                category=f"noise.{cat}",
                                severity="warn" if cat == "formatting_artifacts" else "info",
                                message=f"'{f['filename']}' has {len(matches)} '{cat}' pattern(s)",
                                evidence=str(matches[:3]),
                            )
                            n += 1
        return n
