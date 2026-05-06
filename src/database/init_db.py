# src/database/init_db.py
"""
Database schema initialization based on sql_blueprint.md.

Tables:
- novels
- glossary_terms
- term_variants
- chapters
- term_usage
- context_snapshots
- sync_jobs
- sync_job_chapters
- chapter_versions
- audit_log

Author: Novel Translation Project
"""

import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "1.0.0"
SCHEMA_PATH = Path(__file__).parent / "novel_translation.db"


def get_schema_sql() -> list[str]:
    """Return list of CREATE TABLE statements."""
    return [
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            version TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            description TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS novels (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            source_language TEXT NOT NULL CHECK(source_language IN ('chinese', 'english', 'japanese')),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS glossary_terms (
            id TEXT PRIMARY KEY,
            novel_id TEXT NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
            source_term TEXT NOT NULL,
            target_term TEXT NOT NULL,
            canonical_form TEXT NOT NULL,
            category TEXT NOT NULL CHECK(category IN ('character', 'location', 'artifact', 'concept')),
            status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'approved', 'locked', 'deprecated')),
            enforcement_level TEXT NOT NULL DEFAULT 'soft' CHECK(enforcement_level IN ('strict', 'soft', 'suggestion')),
            context_condition TEXT,
            confidence REAL NOT NULL DEFAULT 0.0,
            usage_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            reviewed_at TEXT,
            UNIQUE(novel_id, source_term)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS term_variants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            term_id TEXT NOT NULL REFERENCES glossary_terms(id) ON DELETE CASCADE,
            variant_text TEXT NOT NULL,
            match_type TEXT NOT NULL CHECK(match_type IN ('exact', 'pattern', 'contextual')),
            case_sensitive BOOLEAN NOT NULL DEFAULT 0,
            UNIQUE(term_id, variant_text)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS chapters (
            id TEXT PRIMARY KEY,
            novel_id TEXT NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
            chapter_num INTEGER NOT NULL,
            file_path TEXT NOT NULL,
            translation_status TEXT NOT NULL DEFAULT 'pending' CHECK(translation_status IN ('pending', 'translated', 'reviewed', 'synced')),
            last_processed_at TEXT,
            paragraph_count INTEGER,
            UNIQUE(novel_id, chapter_num)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS term_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            term_id TEXT NOT NULL REFERENCES glossary_terms(id) ON DELETE CASCADE,
            chapter_id TEXT NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
            paragraph_idx INTEGER NOT NULL,
            variant_used TEXT,
            confidence REAL NOT NULL DEFAULT 0.0,
            context_snippet TEXT,
            UNIQUE(term_id, chapter_id, paragraph_idx)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS context_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chapter_id TEXT NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
            summary_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS sync_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            term_id TEXT NOT NULL REFERENCES glossary_terms(id) ON DELETE CASCADE,
            old_value TEXT NOT NULL,
            new_value TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending_review' CHECK(status IN ('pending_review', 'applied', 'rolled_back', 'cancelled')),
            created_at TEXT NOT NULL,
            applied_at TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS sync_job_chapters (
            job_id INTEGER NOT NULL REFERENCES sync_jobs(id) ON DELETE CASCADE,
            chapter_id TEXT NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
            status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'applied', 'failed', 'skipped')),
            applied_at TEXT,
            PRIMARY KEY (job_id, chapter_id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS chapter_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chapter_id TEXT NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
            version_num INTEGER NOT NULL,
            file_snapshot_path TEXT NOT NULL,
            created_at TEXT NOT NULL,
            reason TEXT NOT NULL,
            UNIQUE(chapter_id, version_num)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_name TEXT NOT NULL,
            record_id TEXT NOT NULL,
            action TEXT NOT NULL CHECK(action IN ('insert', 'update', 'delete')),
            old_data TEXT,
            new_data TEXT,
            timestamp TEXT NOT NULL,
            source TEXT NOT NULL CHECK(source IN ('cli', 'pipeline', 'manual'))
        )
        """,
    ]


def get_indexes_sql() -> list[str]:
    """Return list of CREATE INDEX statements for performance."""
    return [
        "CREATE INDEX IF NOT EXISTS idx_glossary_novel ON glossary_terms(novel_id)",
        "CREATE INDEX IF NOT EXISTS idx_glossary_status ON glossary_terms(status)",
        "CREATE INDEX IF NOT EXISTS idx_terms_usage_term ON term_usage(term_id)",
        "CREATE INDEX IF NOT EXISTS idx_terms_usage_chapter ON term_usage(chapter_id)",
        "CREATE INDEX IF NOT EXISTS idx_context_chapter ON context_snapshots(chapter_id)",
        "CREATE INDEX IF NOT EXISTS idx_sync_jobs_status ON sync_jobs(status)",
        "CREATE INDEX IF NOT EXISTS idx_sync_job_chapters_status ON sync_job_chapters(status)",
        "CREATE INDEX IF NOT EXISTS idx_chapter_versions_chapter ON chapter_versions(chapter_id)",
        "CREATE INDEX IF NOT EXISTS idx_audit_table ON audit_log(table_name)",
        "CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp)",
    ]


def init_database(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """
    Initialize database with schema from sql_blueprint.md.
    
    Args:
        db_path: Path to SQLite database file. Defaults to project root.
        
    Returns:
        sqlite3.Connection: Database connection
        
    Raises:
        sqlite3.Error: If database initialization fails
    """
    if db_path is None:
        db_path = SCHEMA_PATH
    
    logger.info(f"Initializing database at {db_path}")
    
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    
    try:
        cursor = conn.cursor()
        
        # Enable foreign keys
        cursor.execute("PRAGMA foreign_keys = ON")
        
        # Create schema version table first
        cursor.execute(get_schema_sql()[0])
        
        # Check if schema already exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='novels'")
        if cursor.fetchone():
            logger.info("Database already initialized, skipping schema creation")
            conn.close()
            return sqlite3.connect(str(db_path))
        
        # Create all tables
        for sql in get_schema_sql():
            cursor.execute(sql)
        
        # Create indexes
        for sql in get_indexes_sql():
            cursor.execute(sql)
        
        # Insert schema version
        from datetime import datetime
        cursor.execute(
            "INSERT INTO schema_version (version, created_at, description) VALUES (?, ?, ?)",
            (SCHEMA_VERSION, datetime.now().isoformat(), "Initial schema from sql_blueprint.md")
        )
        
        conn.commit()
        logger.info(f"Database initialized successfully with schema version {SCHEMA_VERSION}")
        
    except sqlite3.Error as e:
        conn.close()
        logger.error(f"Database initialization failed: {e}")
        raise
    
    return conn


def get_schema_version(db_path: Optional[Path] = None) -> Optional[str]:
    """Get the current schema version."""
    if db_path is None:
        db_path = SCHEMA_PATH
    
    if not db_path.exists():
        return None
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT version FROM schema_version ORDER BY ROWID DESC LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None
    except sqlite3.Error:
        return None


def create_novel(conn: sqlite3.Connection, novel_id: str, name: str, source_language: str) -> None:
    """Create a new novel entry."""
    from datetime import datetime
    now = datetime.now().isoformat()
    conn.execute(
        "INSERT OR REPLACE INTO novels (id, name, source_language, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (novel_id, name, source_language, now, now)
    )
    conn.commit()


def create_chapter(conn: sqlite3.Connection, novel_id: str, chapter_num: int, file_path: str) -> str:
    """Create a new chapter entry. Returns chapter ID."""
    chapter_id = f"chapter_{novel_id}_{chapter_num}"
    conn.execute(
        """INSERT OR REPLACE INTO chapters 
           (id, novel_id, chapter_num, file_path, translation_status, last_processed_at) 
           VALUES (?, ?, ?, ?, 'pending', ?)""",
        (chapter_id, novel_id, chapter_num, file_path, datetime.now().isoformat())
    )
    conn.commit()
    return chapter_id