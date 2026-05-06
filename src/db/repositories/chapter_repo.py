"""
Chapter repository — CRUD for chapters and chapter_versions tables.
"""

import logging
from datetime import datetime
from typing import Optional
from src.db.connection import DatabaseConnection

logger = logging.getLogger(__name__)


class ChapterRepository:
    """Handles all database operations for chapters and chapter_versions."""

    def __init__(self, db: DatabaseConnection):
        self.db = db

    # ── chapters ────────────────────────────────────────────────────────

    def create(self, novel_id: str, chapter_num: int, file_path: str,
               translation_status: str = "pending", paragraph_count: int = 0) -> dict:
        """Insert a new chapter record."""
        chapter_id = f"chapter_{novel_id}_{chapter_num:04d}"
        self.db.execute(
            """INSERT INTO chapters (id, novel_id, chapter_num, file_path,
               translation_status, paragraph_count) VALUES (?, ?, ?, ?, ?, ?)""",
            (chapter_id, novel_id, chapter_num, file_path, translation_status, paragraph_count),
        )
        logger.debug(f"Chapter created: {chapter_id}")
        return self.get_by_id(chapter_id)

    def get_by_id(self, chapter_id: str) -> Optional[dict]:
        """Fetch a chapter by ID."""
        row = self.db.fetchone("SELECT * FROM chapters WHERE id = ?", (chapter_id,))
        return dict(row) if row else None

    def get_by_number(self, novel_id: str, chapter_num: int) -> Optional[dict]:
        """Fetch a chapter by novel_id and chapter number."""
        row = self.db.fetchone(
            "SELECT * FROM chapters WHERE novel_id = ? AND chapter_num = ?",
            (novel_id, chapter_num),
        )
        return dict(row) if row else None

    def get_chapters_by_novel(self, novel_id: str, status: Optional[str] = None) -> list[dict]:
        """Fetch all chapters for a novel, optionally filtered by status."""
        if status:
            rows = self.db.fetchall(
                "SELECT * FROM chapters WHERE novel_id = ? AND translation_status = ? ORDER BY chapter_num",
                (novel_id, status),
            )
        else:
            rows = self.db.fetchall(
                "SELECT * FROM chapters WHERE novel_id = ? ORDER BY chapter_num",
                (novel_id,),
            )
        return [dict(r) for r in rows]

    def update_status(self, chapter_id: str, status: str) -> Optional[dict]:
        """Update translation status and last_processed_at."""
        now = datetime.now().isoformat()
        self.db.execute(
            "UPDATE chapters SET translation_status = ?, last_processed_at = ? WHERE id = ?",
            (status, now, chapter_id),
        )
        return self.get_by_id(chapter_id)

    def update_paragraph_count(self, chapter_id: str, count: int) -> Optional[dict]:
        """Update paragraph count."""
        self.db.execute(
            "UPDATE chapters SET paragraph_count = ? WHERE id = ?",
            (count, chapter_id),
        )
        return self.get_by_id(chapter_id)

    def delete(self, chapter_id: str) -> bool:
        """Delete a chapter (cascades to snapshots, usage, versions)."""
        self.db.execute("DELETE FROM chapters WHERE id = ?", (chapter_id,))
        logger.info(f"Chapter deleted: {chapter_id}")
        return True

    # ── chapter_versions ────────────────────────────────────────────────

    def create_version(self, chapter_id: str, file_snapshot_path: str,
                       reason: str) -> dict:
        """Create a new chapter version."""
        existing = self.get_latest_version(chapter_id)
        version_num = (existing["version_num"] + 1) if existing else 1
        now = datetime.now().isoformat()
        self.db.execute(
            """INSERT INTO chapter_versions (chapter_id, version_num, file_snapshot_path, reason, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (chapter_id, version_num, file_snapshot_path, reason, now),
        )
        logger.debug(f"Chapter version {version_num} created: {chapter_id}")
        return self.get_version(chapter_id, version_num)

    def get_version(self, chapter_id: str, version_num: int) -> Optional[dict]:
        """Fetch a specific version."""
        row = self.db.fetchone(
            "SELECT * FROM chapter_versions WHERE chapter_id = ? AND version_num = ?",
            (chapter_id, version_num),
        )
        return dict(row) if row else None

    def get_latest_version(self, chapter_id: str) -> Optional[dict]:
        """Fetch the latest version for a chapter."""
        row = self.db.fetchone(
            "SELECT * FROM chapter_versions WHERE chapter_id = ? ORDER BY version_num DESC LIMIT 1",
            (chapter_id,),
        )
        return dict(row) if row else None

    def get_all_versions(self, chapter_id: str) -> list[dict]:
        """Fetch all versions for a chapter."""
        rows = self.db.fetchall(
            "SELECT * FROM chapter_versions WHERE chapter_id = ? ORDER BY version_num",
            (chapter_id,),
        )
        return [dict(r) for r in rows]

    def delete_versions(self, chapter_id: str) -> int:
        """Delete all versions for a chapter. Returns count deleted."""
        cur = self.db.execute("DELETE FROM chapter_versions WHERE chapter_id = ?", (chapter_id,))
        return cur.rowcount
