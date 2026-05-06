# src/database/db_manager.py
"""
Database Manager for Novel Translation Project.
Provides high-level interface for database operations.

Based on sql_blueprint.md schema.
"""

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    High-level database interface for novel translation.
    
    Handles:
    - Novel management
    - Glossary terms CRUD
    - Term variants
    - Chapter tracking
    - Context snapshots
    - Sync jobs
    - Audit logging
    """
    
    def __init__(self, db_path: Optional[Path] = None):
        """Initialize database manager."""
        from src.database.init_db import init_database, SCHEMA_PATH
        
        if db_path is None:
            db_path = SCHEMA_PATH
        
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        
        # Initialize if not exists
        if not db_path.exists():
            init_database(db_path)
    
    @property
    def conn(self) -> sqlite3.Connection:
        """Get database connection (lazy init)."""
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON")
        return self._conn
    
    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    # ─────────────────────────────────────────────────────────────
    # Novel operations
    # ─────────────────────────────────────────────────────────────
    
    def create_novel(self, novel_id: str, name: str, source_language: str) -> None:
        """Create a new novel."""
        now = datetime.now().isoformat()
        self.conn.execute(
            """INSERT OR REPLACE INTO novels 
               (id, name, source_language, created_at, updated_at) 
               VALUES (?, ?, ?, ?, ?)""",
            (novel_id, name, source_language, now, now)
        )
        self.conn.commit()
        self._log_audit('novels', novel_id, 'insert', None, {'name': name, 'source_language': source_language})
    
    def get_novels(self) -> list[dict]:
        """Get all novels."""
        cursor = self.conn.execute("SELECT * FROM novels ORDER BY name")
        return [dict(row) for row in cursor.fetchall()]
    
    def get_novel(self, novel_id: str) -> Optional[dict]:
        """Get a specific novel."""
        cursor = self.conn.execute("SELECT * FROM novels WHERE id = ?", (novel_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    # ─────────────────────────────────────────────────────────────
    # Glossary operations
    # ─────────────────────────────────────────────────────────────
    
    def add_glossary_term(
        self,
        term_id: str,
        novel_id: str,
        source_term: str,
        target_term: str,
        canonical_form: str,
        category: str,
        status: str = 'pending',
        enforcement_level: str = 'soft',
        context_condition: Optional[str] = None,
    ) -> None:
        """Add a new glossary term."""
        now = datetime.now().isoformat()
        self.conn.execute(
            """INSERT OR REPLACE INTO glossary_terms 
               (id, novel_id, source_term, target_term, canonical_form, category, 
                status, enforcement_level, context_condition, confidence, usage_count, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0.0, 0, ?)""",
            (term_id, novel_id, source_term, target_term, canonical_form, category,
             status, enforcement_level, context_condition, now)
        )
        self.conn.commit()
        self._log_audit('glossary_terms', term_id, 'insert', None, {'source_term': source_term, 'target_term': target_term})
    
    def get_glossary_terms(self, novel_id: str, status: Optional[str] = None) -> list[dict]:
        """Get glossary terms for a novel."""
        if status:
            cursor = self.conn.execute(
                "SELECT * FROM glossary_terms WHERE novel_id = ? AND status = ? ORDER BY source_term",
                (novel_id, status)
            )
        else:
            cursor = self.conn.execute(
                "SELECT * FROM glossary_terms WHERE novel_id = ? ORDER BY source_term",
                (novel_id,)
            )
        return [dict(row) for row in cursor.fetchall()]
    
    def get_term(self, novel_id: str, source_term: str) -> Optional[dict]:
        """Get a specific glossary term."""
        cursor = self.conn.execute(
            "SELECT * FROM glossary_terms WHERE novel_id = ? AND source_term = ?",
            (novel_id, source_term)
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def update_term_status(self, term_id: str, status: str) -> None:
        """Update term status."""
        now = datetime.now().isoformat()
        self.conn.execute(
            "UPDATE glossary_terms SET status = ?, reviewed_at = ? WHERE id = ?",
            (status, now, term_id)
        )
        self.conn.commit()
        self._log_audit('glossary_terms', term_id, 'update', None, {'status': status})
    
    def add_term_variant(self, term_id: str, variant_text: str, match_type: str = 'exact', case_sensitive: bool = False) -> None:
        """Add a variant to a glossary term."""
        self.conn.execute(
            """INSERT OR IGNORE INTO term_variants 
               (term_id, variant_text, match_type, case_sensitive) 
               VALUES (?, ?, ?, ?)""",
            (term_id, variant_text, match_type, case_sensitive)
        )
        self.conn.commit()
    
    def get_term_variants(self, term_id: str) -> list[dict]:
        """Get all variants for a term."""
        cursor = self.conn.execute(
            "SELECT * FROM term_variants WHERE term_id = ?",
            (term_id,)
        )
        return [dict(row) for row in cursor.fetchall()]
    
    # ─────────────────────────────────────────────────────────────
    # Chapter operations
    # ─────────────────────────────────────────────────────────────
    
    def create_chapter(self, novel_id: str, chapter_num: int, file_path: str) -> str:
        """Create a new chapter. Returns chapter ID."""
        chapter_id = f"chapter_{novel_id}_{chapter_num}"
        now = datetime.now().isoformat()
        self.conn.execute(
            """INSERT OR REPLACE INTO chapters 
               (id, novel_id, chapter_num, file_path, translation_status, last_processed_at)
               VALUES (?, ?, ?, ?, 'pending', ?)""",
            (chapter_id, novel_id, chapter_num, file_path, now)
        )
        self.conn.commit()
        return chapter_id
    
    def get_chapters(self, novel_id: str, status: Optional[str] = None) -> list[dict]:
        """Get chapters for a novel."""
        if status:
            cursor = self.conn.execute(
                "SELECT * FROM chapters WHERE novel_id = ? AND translation_status = ? ORDER BY chapter_num",
                (novel_id, status)
            )
        else:
            cursor = self.conn.execute(
                "SELECT * FROM chapters WHERE novel_id = ? ORDER BY chapter_num",
                (novel_id,)
            )
        return [dict(row) for row in cursor.fetchall()]
    
    def update_chapter_status(self, chapter_id: str, status: str) -> None:
        """Update chapter translation status."""
        now = datetime.now().isoformat()
        self.conn.execute(
            "UPDATE chapters SET translation_status = ?, last_processed_at = ? WHERE id = ?",
            (status, now, chapter_id)
        )
        self.conn.commit()
        self._log_audit('chapters', chapter_id, 'update', None, {'translation_status': status})
    
    # ─────────────────────────────────────────────────────────────
    # Term usage tracking
    # ─────────────────────────────────────────────────────────────
    
    def record_term_usage(
        self,
        term_id: str,
        chapter_id: str,
        paragraph_idx: int,
        variant_used: Optional[str] = None,
        confidence: float = 0.0,
        context_snippet: Optional[str] = None,
    ) -> None:
        """Record term usage in a chapter."""
        self.conn.execute(
            """INSERT OR REPLACE INTO term_usage 
               (term_id, chapter_id, paragraph_idx, variant_used, confidence, context_snippet)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (term_id, chapter_id, paragraph_idx, variant_used, confidence, context_snippet)
        )
        # Update usage count
        self.conn.execute(
            "UPDATE glossary_terms SET usage_count = usage_count + 1 WHERE id = ?",
            (term_id,)
        )
        self.conn.commit()
    
    def get_term_usage(self, term_id: str) -> list[dict]:
        """Get all usage records for a term."""
        cursor = self.conn.execute(
            "SELECT * FROM term_usage WHERE term_id = ? ORDER BY chapter_id, paragraph_idx",
            (term_id,)
        )
        return [dict(row) for row in cursor.fetchall()]
    
    # ─────────────────────────────────────────────────────────────
    # Context snapshots
    # ─────────────────────────────────────────────────────────────
    
    def save_context_snapshot(self, chapter_id: str, summary: dict) -> None:
        """Save context snapshot for a chapter."""
        now = datetime.now().isoformat()
        self.conn.execute(
            """INSERT INTO context_snapshots (chapter_id, summary_json, created_at) VALUES (?, ?, ?)""",
            (chapter_id, json.dumps(summary), now)
        )
        self.conn.commit()
    
    def get_context_snapshots(self, chapter_ids: list[str]) -> list[dict]:
        """Get context snapshots for multiple chapters."""
        if not chapter_ids:
            return []
        placeholders = ','.join(['?' for _ in chapter_ids])
        cursor = self.conn.execute(
            f"SELECT * FROM context_snapshots WHERE chapter_id IN ({placeholders}) ORDER BY created_at DESC",
            chapter_ids
        )
        return [dict(row) for row in cursor.fetchall()]
    
    # ─────────────────────────────────────────────────────────────
    # Sync jobs
    # ─────────────────────────────────────────────────────────────
    
    def create_sync_job(self, term_id: str, old_value: str, new_value: str) -> int:
        """Create a sync job. Returns job ID."""
        now = datetime.now().isoformat()
        cursor = self.conn.execute(
            """INSERT INTO sync_jobs (term_id, old_value, new_value, status, created_at) 
               VALUES (?, ?, ?, 'pending_review', ?)""",
            (term_id, old_value, new_value, now)
        )
        self.conn.commit()
        return cursor.lastrowid
    
    def add_sync_job_chapter(self, job_id: int, chapter_id: str) -> None:
        """Add chapter to sync job."""
        self.conn.execute(
            "INSERT INTO sync_job_chapters (job_id, chapter_id, status) VALUES (?, ?, 'pending')",
            (job_id, chapter_id)
        )
        self.conn.commit()
    
    def get_sync_job_chapters(self, job_id: int) -> list[dict]:
        """Get all chapters in a sync job."""
        cursor = self.conn.execute(
            "SELECT * FROM sync_job_chapters WHERE job_id = ?",
            (job_id,)
        )
        return [dict(row) for row in cursor.fetchall()]
    
    def update_sync_job_status(self, job_id: int, status: str) -> None:
        """Update sync job status."""
        now = datetime.now().isoformat() if status == 'applied' else None
        self.conn.execute(
            "UPDATE sync_jobs SET status = ?, applied_at = ? WHERE id = ?",
            (status, now, job_id)
        )
        self.conn.commit()
    
    def update_sync_chapter_status(self, job_id: int, chapter_id: str, status: str) -> None:
        """Update status of a chapter in sync job."""
        now = datetime.now().isoformat() if status == 'applied' else None
        self.conn.execute(
            "UPDATE sync_job_chapters SET status = ?, applied_at = ? WHERE job_id = ? AND chapter_id = ?",
            (status, now, job_id, chapter_id)
        )
        self.conn.commit()
    
    # ─────────────────────────────────────────────────────────────
    # Chapter versions
    # ─────────────────────────────────────────────────────────────
    
    def create_chapter_version(self, chapter_id: str, version_num: int, file_path: str, reason: str) -> None:
        """Create a chapter version snapshot."""
        now = datetime.now().isoformat()
        self.conn.execute(
            """INSERT INTO chapter_versions (chapter_id, version_num, file_snapshot_path, created_at, reason)
               VALUES (?, ?, ?, ?, ?)""",
            (chapter_id, version_num, file_path, now, reason)
        )
        self.conn.commit()
    
    # ─────────────────────────────────────────────────────────────
    # Audit logging
    # ─────────────────────────────────────────────────────────────
    
    def _log_audit(self, table_name: str, record_id: str, action: str, old_data: Optional[dict], new_data: Optional[dict]) -> None:
        """Log an audit entry."""
        now = datetime.now().isoformat()
        self.conn.execute(
            """INSERT INTO audit_log (table_name, record_id, action, old_data, new_data, timestamp, source)
               VALUES (?, ?, ?, ?, ?, ?, 'pipeline')""",
            (table_name, record_id, action, json.dumps(old_data) if old_data else None,
             json.dumps(new_data) if new_data else None, now)
        )
        self.conn.commit()
    
    def get_audit_log(self, table_name: Optional[str] = None, limit: int = 100) -> list[dict]:
        """Get audit log entries."""
        if table_name:
            cursor = self.conn.execute(
                "SELECT * FROM audit_log WHERE table_name = ? ORDER BY timestamp DESC LIMIT ?",
                (table_name, limit)
            )
        else:
            cursor = self.conn.execute(
                "SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            )
        return [dict(row) for row in cursor.fetchall()]