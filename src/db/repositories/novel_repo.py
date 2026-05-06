"""
Novel repository — CRUD for novels table.
"""

import logging
from datetime import datetime
from typing import Optional
from src.db.connection import DatabaseConnection

logger = logging.getLogger(__name__)


class NovelRepository:
    """Handles all database operations for the novels table."""

    def __init__(self, db: DatabaseConnection):
        self.db = db

    def create(self, novel_id: str, name: str, source_language: str = "chinese") -> dict:
        """Insert a new novel record."""
        now = datetime.now().isoformat()
        self.db.execute(
            "INSERT INTO novels (id, name, source_language, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (novel_id, name, source_language, now, now),
        )
        logger.info(f"Novel created: {novel_id} ({name})")
        return self.get_by_id(novel_id)

    def get_by_id(self, novel_id: str) -> Optional[dict]:
        """Fetch a novel by ID."""
        row = self.db.fetchone("SELECT * FROM novels WHERE id = ?", (novel_id,))
        return dict(row) if row else None

    def get_all(self) -> list[dict]:
        """Fetch all novels."""
        rows = self.db.fetchall("SELECT * FROM novels ORDER BY created_at DESC")
        return [dict(r) for r in rows]

    def update(self, novel_id: str, **kwargs) -> Optional[dict]:
        """Update novel fields."""
        allowed = {"name", "source_language"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return self.get_by_id(novel_id)

        updates["updated_at"] = datetime.now().isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [novel_id]
        self.db.execute(f"UPDATE novels SET {set_clause} WHERE id = ?", tuple(values))
        return self.get_by_id(novel_id)

    def delete(self, novel_id: str) -> bool:
        """Delete a novel (cascades to all related tables)."""
        self.db.execute("DELETE FROM novels WHERE id = ?", (novel_id,))
        logger.info(f"Novel deleted: {novel_id}")
        return True

    def exists(self, novel_id: str) -> bool:
        """Check if a novel exists."""
        return self.db.row_exists("SELECT 1 FROM novels WHERE id = ?", (novel_id,))
