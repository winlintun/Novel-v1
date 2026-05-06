"""
Context repository — CRUD for context_snapshots and term_usage tables.
"""

import logging
from datetime import datetime
from typing import Optional
from src.db.connection import DatabaseConnection

logger = logging.getLogger(__name__)


class ContextRepository:
    """Handles all database operations for context_snapshots and term_usage."""

    def __init__(self, db: DatabaseConnection):
        self.db = db

    # ── context_snapshots ───────────────────────────────────────────────

    def create_snapshot(self, chapter_id: str, summary_json: str) -> dict:
        """Insert a new context snapshot."""
        now = datetime.now().isoformat()
        cur = self.db.execute(
            "INSERT INTO context_snapshots (chapter_id, summary_json, created_at) VALUES (?, ?, ?)",
            (chapter_id, summary_json, now),
        )
        return self.get_snapshot(cur.lastrowid)

    def get_snapshot(self, snapshot_id: int) -> Optional[dict]:
        """Fetch a snapshot by ID."""
        row = self.db.fetchone(
            "SELECT * FROM context_snapshots WHERE id = ?", (snapshot_id,)
        )
        return dict(row) if row else None

    def get_snapshots_for_chapter(self, chapter_id: str) -> list[dict]:
        """Fetch all snapshots for a chapter."""
        rows = self.db.fetchall(
            "SELECT * FROM context_snapshots WHERE chapter_id = ? ORDER BY created_at DESC",
            (chapter_id,),
        )
        return [dict(r) for r in rows]

    def get_rolling_context(self, chapter_ids: list[str], limit: int = 3) -> list[dict]:
        """Get latest snapshots for a list of chapter IDs (rolling context)."""
        if not chapter_ids:
            return []
        placeholders = ",".join("?" for _ in chapter_ids)
        rows = self.db.fetchall(
            f"SELECT cs.* FROM context_snapshots cs "
            f"WHERE cs.chapter_id IN ({placeholders}) "
            f"AND cs.id = (SELECT MAX(cs2.id) FROM context_snapshots cs2 WHERE cs2.chapter_id = cs.chapter_id) "
            f"ORDER BY cs.created_at DESC LIMIT ?",
            (*chapter_ids, limit),
        )
        return [dict(r) for r in rows]

    def delete_snapshots(self, chapter_id: str) -> int:
        """Delete all snapshots for a chapter."""
        cur = self.db.execute("DELETE FROM context_snapshots WHERE chapter_id = ?", (chapter_id,))
        return cur.rowcount

    # ── term_usage ──────────────────────────────────────────────────────

    def record_usage(self, term_id: str, chapter_id: str, paragraph_idx: int,
                     variant_used: Optional[str] = None, confidence: float = 1.0,
                     context_snippet: Optional[str] = None) -> int:
        """Record a term usage occurrence. Returns usage ID."""
        cur = self.db.execute(
            """INSERT INTO term_usage (term_id, chapter_id, paragraph_idx,
               variant_used, confidence, context_snippet) VALUES (?, ?, ?, ?, ?, ?)""",
            (term_id, chapter_id, paragraph_idx, variant_used, confidence, context_snippet),
        )
        return cur.lastrowid

    def get_usage_by_term(self, term_id: str) -> list[dict]:
        """Fetch all usage records for a term."""
        rows = self.db.fetchall(
            "SELECT * FROM term_usage WHERE term_id = ? ORDER BY chapter_id, paragraph_idx",
            (term_id,),
        )
        return [dict(r) for r in rows]

    def get_usage_by_chapter(self, chapter_id: str) -> list[dict]:
        """Fetch all usage records for a chapter."""
        rows = self.db.fetchall(
            "SELECT * FROM term_usage WHERE chapter_id = ? ORDER BY paragraph_idx",
            (chapter_id,),
        )
        return [dict(r) for r in rows]

    def get_term_chapters(self, term_id: str) -> list[str]:
        """Get list of unique chapter IDs where a term was used."""
        rows = self.db.fetchall(
            "SELECT DISTINCT chapter_id FROM term_usage WHERE term_id = ? ORDER BY chapter_id",
            (term_id,),
        )
        return [r["chapter_id"] for r in rows]

    def delete_usage(self, chapter_id: str) -> int:
        """Delete all usage records for a chapter."""
        cur = self.db.execute("DELETE FROM term_usage WHERE chapter_id = ?", (chapter_id,))
        return cur.rowcount
