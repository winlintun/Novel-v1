"""
Sync repository — CRUD for sync_jobs, sync_job_chapters, and audit_log tables.
"""

import logging
from datetime import datetime
from typing import Optional
from src.db.connection import DatabaseConnection

logger = logging.getLogger(__name__)


class SyncRepository:
    """Handles all database operations for sync_jobs, sync_job_chapters, and audit_log."""

    def __init__(self, db: DatabaseConnection):
        self.db = db

    # ── sync_jobs ───────────────────────────────────────────────────────

    def create_job(self, term_id: str, old_value: str, new_value: str,
                   status: str = "pending_review") -> dict:
        """Create a new sync job."""
        now = datetime.now().isoformat()
        cur = self.db.execute(
            """INSERT INTO sync_jobs (term_id, old_value, new_value, status, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (term_id, old_value, new_value, status, now),
        )
        return self.get_job(cur.lastrowid)

    def get_job(self, job_id: int) -> Optional[dict]:
        """Fetch a sync job by ID."""
        row = self.db.fetchone("SELECT * FROM sync_jobs WHERE id = ?", (job_id,))
        return dict(row) if row else None

    def get_jobs_by_term(self, term_id: str, status: Optional[str] = None) -> list[dict]:
        """Fetch jobs for a term, optionally filtered by status."""
        if status:
            rows = self.db.fetchall(
                "SELECT * FROM sync_jobs WHERE term_id = ? AND status = ? ORDER BY created_at DESC",
                (term_id, status),
            )
        else:
            rows = self.db.fetchall(
                "SELECT * FROM sync_jobs WHERE term_id = ? ORDER BY created_at DESC",
                (term_id,),
            )
        return [dict(r) for r in rows]

    def get_pending_jobs(self) -> list[dict]:
        """Fetch all pending jobs."""
        rows = self.db.fetchall(
            "SELECT * FROM sync_jobs WHERE status = 'pending_review' ORDER BY created_at"
        )
        return [dict(r) for r in rows]

    def update_job_status(self, job_id: int, status: str) -> Optional[dict]:
        """Update job status. If 'applied', set applied_at."""
        if status == "applied":
            now = datetime.now().isoformat()
            self.db.execute(
                "UPDATE sync_jobs SET status = ?, applied_at = ? WHERE id = ?",
                (status, now, job_id),
            )
        else:
            self.db.execute("UPDATE sync_jobs SET status = ? WHERE id = ?", (status, job_id))
        return self.get_job(job_id)

    # ── sync_job_chapters ───────────────────────────────────────────────

    def add_job_chapter(self, job_id: int, chapter_id: str,
                        status: str = "pending") -> None:
        """Link a chapter to a sync job."""
        self.db.execute(
            """INSERT INTO sync_job_chapters (job_id, chapter_id, status)
               VALUES (?, ?, ?)""",
            (job_id, chapter_id, status),
        )

    def add_job_chapters(self, job_id: int, chapter_ids: list[str]) -> None:
        """Link multiple chapters to a sync job."""
        for cid in chapter_ids:
            self.add_job_chapter(job_id, cid)

    def get_job_chapters(self, job_id: int) -> list[dict]:
        """Fetch all chapter links for a job."""
        rows = self.db.fetchall(
            "SELECT * FROM sync_job_chapters WHERE job_id = ? ORDER BY chapter_id",
            (job_id,),
        )
        return [dict(r) for r in rows]

    def update_chapter_status(self, job_id: int, chapter_id: str,
                               status: str) -> None:
        """Update the status of a chapter within a job."""
        if status == "applied":
            now = datetime.now().isoformat()
            self.db.execute(
                """UPDATE sync_job_chapters SET status = ?, applied_at = ?
                   WHERE job_id = ? AND chapter_id = ?""",
                (status, now, job_id, chapter_id),
            )
        else:
            self.db.execute(
                """UPDATE sync_job_chapters SET status = ?
                   WHERE job_id = ? AND chapter_id = ?""",
                (status, job_id, chapter_id),
            )

    def get_chapters_by_status(self, job_id: int, status: str) -> list[str]:
        """Get chapter IDs for a job with a specific status."""
        rows = self.db.fetchall(
            "SELECT chapter_id FROM sync_job_chapters WHERE job_id = ? AND status = ?",
            (job_id, status),
        )
        return [r["chapter_id"] for r in rows]

    def is_job_complete(self, job_id: int) -> bool:
        """Check if all chapters in a job are applied, failed, or skipped."""
        row = self.db.fetchone(
            "SELECT COUNT(*) as cnt FROM sync_job_chapters "
            "WHERE job_id = ? AND status = 'pending'",
            (job_id,),
        )
        return row["cnt"] == 0

    # ── audit_log ───────────────────────────────────────────────────────

    def log_action(self, table_name: str, record_id: str, action: str,
                   old_data: Optional[str] = None, new_data: Optional[str] = None,
                   source: str = "manual") -> int:
        """Write an audit log entry. Returns log ID."""
        now = datetime.now().isoformat()
        cur = self.db.execute(
            """INSERT INTO audit_log (table_name, record_id, action, old_data, new_data, timestamp, source)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (table_name, record_id, action, old_data, new_data, now, source),
        )
        return cur.lastrowid

    def get_audit_log(self, table_name: Optional[str] = None,
                      record_id: Optional[str] = None,
                      limit: int = 100) -> list[dict]:
        """Fetch audit log entries with optional filters."""
        conditions = []
        params: list = []
        if table_name:
            conditions.append("table_name = ?")
            params.append(table_name)
        if record_id:
            conditions.append("record_id = ?")
            params.append(record_id)

        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        rows = self.db.fetchall(
            f"SELECT * FROM audit_log{where} ORDER BY timestamp DESC LIMIT ?",
            (*params, limit),
        )
        return [dict(r) for r in rows]
