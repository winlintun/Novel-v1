"""File ingestion & text loading from novel chapter directories."""

import hashlib
import re
from pathlib import Path

from src.dataset_alignment.config import get_alignment_config
from src.dataset_alignment.database import connect


def scan_novel_dir(novel_dir: Path) -> list[dict]:
    """Scan a novel directory for parallel source/target chapter files.

    Expects structure:
        {novel_dir}/
            {novel}_chapter_XXXX.md  (source language)
            (also checks data/output/{novel}/{novel}_chapter_XXXX.mm.md for target)
    """
    cfg = get_alignment_config()
    novel = novel_dir.name

    src_dir = novel_dir
    tgt_dir = novel_dir.parent.parent / "output" / novel_dir.name

    records = []
    # Check both novel_dir directly and novel_dir/en/ subdirectory
    md_files = sorted(src_dir.glob("*.md"))
    if not md_files:
        en_dir = src_dir / "en"
        if en_dir.exists():
            md_files = sorted(en_dir.glob("*.md"))
    for fp in md_files:
        if fp.name.endswith(".mm.md"):
            continue
        record = {
            "novel": novel,
            "lang": cfg.src_lang,
            "path": str(fp),
            "filename": fp.name,
            "sha256": _sha256_file(fp),
            "byte_size": fp.stat().st_size,
        }
        match = re.search(r"chapter_(\d+)", fp.name)
        if match:
            record["chapter_no"] = int(match.group(1))
        records.append(record)

        tgt_fp = tgt_dir / fp.name.replace(".md", ".mm.md")
        if tgt_fp.exists():
            records.append({
                "novel": novel,
                "lang": cfg.tgt_lang,
                "path": str(tgt_fp),
                "filename": tgt_fp.name,
                "sha256": _sha256_file(tgt_fp),
                "byte_size": tgt_fp.stat().st_size,
                "chapter_no": record.get("chapter_no"),
            })

    # Also scan for target files in novel_dir/mm/ subdirectory
    mm_dir = src_dir / "mm"
    if mm_dir.exists():
        for mm_fp in sorted(mm_dir.glob("*.md")):
            if mm_fp.name.endswith(".mm.md"):
                continue
            match = re.search(r"chapter_(\d+)", mm_fp.name)
            records.append({
                "novel": novel,
                "lang": cfg.tgt_lang,
                "path": str(mm_fp),
                "filename": mm_fp.name,
                "sha256": _sha256_file(mm_fp),
                "byte_size": mm_fp.stat().st_size,
                "chapter_no": int(match.group(1)) if match else None,
            })

    return records


def ingest_files(records: list[dict]) -> dict[str, int]:
    """Insert or update file records in the database."""
    counts = {"inserted": 0, "skipped": 0, "updated": 0}

    with connect() as conn:
        for rec in records:
            existing = conn.execute(
                "SELECT id, sha256 FROM files WHERE path = ?",
                (rec["path"],),
            ).fetchone()

            if existing:
                if existing["sha256"] != rec["sha256"]:
                    conn.execute(
                        """UPDATE files SET filename=?, sha256=?, byte_size=?
                           WHERE id=?""",
                        (rec["filename"], rec["sha256"],
                         rec["byte_size"], existing["id"]),
                    )
                    counts["updated"] += 1
                else:
                    counts["skipped"] += 1
                continue

            conn.execute(
                """INSERT INTO files
                   (novel, lang, path, filename, chapter_no, sha256, byte_size)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (rec["novel"], rec["lang"], rec["path"], rec["filename"],
                 rec.get("chapter_no"), rec["sha256"], rec["byte_size"]),
            )
            counts["inserted"] += 1

    return counts


def read_chapter_text(file_id: int, raw: bool = False) -> str:
    """Read chapter text from a file record by its database ID."""
    with connect() as conn:
        row = conn.execute(
            "SELECT path FROM files WHERE id = ?", (file_id,)
        ).fetchone()
        if not row:
            raise ValueError(f"File ID {file_id} not found")

    text = Path(row["path"]).read_text(encoding="utf-8", errors="replace")

    if not raw:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = text.strip()

    return text


def _sha256_file(fp: Path) -> str:
    h = hashlib.sha256()
    with open(fp, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()
