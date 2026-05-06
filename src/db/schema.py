"""
SQLite schema DDL for novel translation project.
Based on sql_blueprint.md — 10 tables with foreign keys and indexes.
"""

import logging
from src.db.connection import DatabaseConnection

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1

CREATE_TABLES = """
-- novels
CREATE TABLE IF NOT EXISTS novels (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    source_language TEXT NOT NULL DEFAULT 'chinese',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- glossary_terms
CREATE TABLE IF NOT EXISTS glossary_terms (
    id TEXT PRIMARY KEY,
    novel_id TEXT NOT NULL,
    source_term TEXT NOT NULL,
    target_term TEXT NOT NULL,
    canonical_form TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'general',
    status TEXT NOT NULL DEFAULT 'pending',
    enforcement_level TEXT NOT NULL DEFAULT 'soft',
    context_condition TEXT,
    confidence REAL NOT NULL DEFAULT 0.0,
    usage_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    reviewed_at TEXT,
    FOREIGN KEY (novel_id) REFERENCES novels(id) ON DELETE CASCADE
);

-- term_variants
CREATE TABLE IF NOT EXISTS term_variants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    term_id TEXT NOT NULL,
    variant_text TEXT NOT NULL,
    match_type TEXT NOT NULL DEFAULT 'exact',
    case_sensitive INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (term_id) REFERENCES glossary_terms(id) ON DELETE CASCADE
);

-- chapters
CREATE TABLE IF NOT EXISTS chapters (
    id TEXT PRIMARY KEY,
    novel_id TEXT NOT NULL,
    chapter_num INTEGER NOT NULL,
    file_path TEXT NOT NULL,
    translation_status TEXT NOT NULL DEFAULT 'pending',
    last_processed_at TEXT,
    paragraph_count INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (novel_id) REFERENCES novels(id) ON DELETE CASCADE,
    UNIQUE(novel_id, chapter_num)
);

-- term_usage
CREATE TABLE IF NOT EXISTS term_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    term_id TEXT NOT NULL,
    chapter_id TEXT NOT NULL,
    paragraph_idx INTEGER NOT NULL,
    variant_used TEXT,
    confidence REAL NOT NULL DEFAULT 0.0,
    context_snippet TEXT,
    FOREIGN KEY (term_id) REFERENCES glossary_terms(id) ON DELETE CASCADE,
    FOREIGN KEY (chapter_id) REFERENCES chapters(id) ON DELETE CASCADE
);

-- context_snapshots
CREATE TABLE IF NOT EXISTS context_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_id TEXT NOT NULL,
    summary_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (chapter_id) REFERENCES chapters(id) ON DELETE CASCADE
);

-- sync_jobs
CREATE TABLE IF NOT EXISTS sync_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    term_id TEXT NOT NULL,
    old_value TEXT NOT NULL,
    new_value TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending_review',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    applied_at TEXT,
    FOREIGN KEY (term_id) REFERENCES glossary_terms(id) ON DELETE CASCADE
);

-- sync_job_chapters (junction table)
CREATE TABLE IF NOT EXISTS sync_job_chapters (
    job_id INTEGER NOT NULL,
    chapter_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    applied_at TEXT,
    PRIMARY KEY (job_id, chapter_id),
    FOREIGN KEY (job_id) REFERENCES sync_jobs(id) ON DELETE CASCADE,
    FOREIGN KEY (chapter_id) REFERENCES chapters(id) ON DELETE CASCADE
);

-- chapter_versions
CREATE TABLE IF NOT EXISTS chapter_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_id TEXT NOT NULL,
    version_num INTEGER NOT NULL,
    file_snapshot_path TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    reason TEXT NOT NULL,
    FOREIGN KEY (chapter_id) REFERENCES chapters(id) ON DELETE CASCADE,
    UNIQUE(chapter_id, version_num)
);

-- audit_log
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name TEXT NOT NULL,
    record_id TEXT NOT NULL,
    action TEXT NOT NULL,
    old_data TEXT,
    new_data TEXT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    source TEXT NOT NULL DEFAULT 'manual'
);
"""

CREATE_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_glossary_novel ON glossary_terms(novel_id);
CREATE INDEX IF NOT EXISTS idx_glossary_status ON glossary_terms(status);
CREATE INDEX IF NOT EXISTS idx_glossary_source ON glossary_terms(source_term);
CREATE INDEX IF NOT EXISTS idx_glossary_category ON glossary_terms(category);
CREATE INDEX IF NOT EXISTS idx_glossary_novel_status ON glossary_terms(novel_id, status);

CREATE INDEX IF NOT EXISTS idx_variants_term ON term_variants(term_id);

CREATE INDEX IF NOT EXISTS idx_chapters_novel ON chapters(novel_id);
CREATE INDEX IF NOT EXISTS idx_chapters_novel_num ON chapters(novel_id, chapter_num);

CREATE INDEX IF NOT EXISTS idx_term_usage_term ON term_usage(term_id);
CREATE INDEX IF NOT EXISTS idx_term_usage_chapter ON term_usage(chapter_id);

CREATE INDEX IF NOT EXISTS idx_context_chapter ON context_snapshots(chapter_id);

CREATE INDEX IF NOT EXISTS idx_sync_jobs_term ON sync_jobs(term_id);
CREATE INDEX IF NOT EXISTS idx_sync_jobs_status ON sync_jobs(status);

CREATE INDEX IF NOT EXISTS idx_sync_job_chapters_job ON sync_job_chapters(job_id);
CREATE INDEX IF NOT EXISTS idx_sync_job_chapters_chapter ON sync_job_chapters(chapter_id);

CREATE INDEX IF NOT EXISTS idx_chapter_versions_chapter ON chapter_versions(chapter_id);

CREATE INDEX IF NOT EXISTS idx_audit_table ON audit_log(table_name, record_id);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
"""


class SchemaManager:
    """Creates and manages the SQLite schema."""

    def __init__(self, db: DatabaseConnection):
        self.db = db

    def create_all(self) -> None:
        """Create all tables and indexes."""
        conn = self.db.connect()
        conn.executescript(CREATE_TABLES)
        conn.executescript(CREATE_INDEXES)
        logger.info("Schema created: all tables and indexes")

    def drop_all(self) -> None:
        """Drop all tables (DANGEROUS — for testing only)."""
        conn = self.db.connect()
        tables = [
            "audit_log", "chapter_versions", "sync_job_chapters", "sync_jobs",
            "context_snapshots", "term_usage", "chapters", "term_variants",
            "glossary_terms", "novels",
        ]
        for table in tables:
            conn.execute(f"DROP TABLE IF EXISTS {table}")
        conn.commit()
        logger.warning("All tables dropped")

    def get_schema_version(self) -> int:
        """Return current schema version (always SCHEMA_VERSION for now)."""
        return SCHEMA_VERSION

    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists."""
        result = self.db.fetchone(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        )
        return result is not None

    def get_table_count(self, table_name: str) -> int:
        """Get row count for a table."""
        result = self.db.fetchone(f"SELECT COUNT(*) as cnt FROM {table_name}")
        if result:
            return result["cnt"]
        return 0
