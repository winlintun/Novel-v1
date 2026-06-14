"""
SQLite schema DDL for novel translation project.
Based on sql_blueprint.md — 10 tables with foreign keys and indexes.
"""

import logging
from src.db.connection import DatabaseConnection

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 3

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
    subtype TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    enforcement_level TEXT NOT NULL DEFAULT 'soft',
    context_condition TEXT,
    confidence REAL NOT NULL DEFAULT 0.0,
    usage_count INTEGER NOT NULL DEFAULT 0,
    scope TEXT NOT NULL DEFAULT 'novel',
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

-- term_relationships (directed graph edges between glossary terms)
CREATE TABLE IF NOT EXISTS term_relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id TEXT NOT NULL,
    src_term_id TEXT NOT NULL,
    dst_term_id TEXT NOT NULL,
    relation_type TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 1.0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (src_term_id) REFERENCES glossary_terms(id) ON DELETE CASCADE,
    FOREIGN KEY (dst_term_id) REFERENCES glossary_terms(id) ON DELETE CASCADE,
    UNIQUE (src_term_id, dst_term_id, relation_type)
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
CREATE INDEX IF NOT EXISTS idx_glossary_scope ON glossary_terms(scope);
CREATE INDEX IF NOT EXISTS idx_glossary_scope_status ON glossary_terms(scope, status);

CREATE INDEX IF NOT EXISTS idx_glossary_subtype ON glossary_terms(subtype);

CREATE INDEX IF NOT EXISTS idx_variants_term ON term_variants(term_id);

CREATE INDEX IF NOT EXISTS idx_term_rel_novel ON term_relationships(novel_id);
CREATE INDEX IF NOT EXISTS idx_term_rel_src ON term_relationships(src_term_id);
CREATE INDEX IF NOT EXISTS idx_term_rel_dst ON term_relationships(dst_term_id);
CREATE INDEX IF NOT EXISTS idx_term_rel_type ON term_relationships(relation_type);

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
        """Create all tables and indexes, then run migrations."""
        conn = self.db.connect()
        conn.executescript(CREATE_TABLES)
        conn.executescript(CREATE_INDEXES)
        logger.info("Schema created: all tables and indexes")
        
        # Run migrations for existing databases
        self.migrate_to_v2()
        self.migrate_to_v3()

    def drop_all(self) -> None:
        """Drop all tables (DANGEROUS — for testing only)."""
        conn = self.db.connect()
        tables = [
            "audit_log", "chapter_versions", "sync_job_chapters", "sync_jobs",
            "context_snapshots", "term_usage", "chapters", "term_relationships",
            "term_variants", "glossary_terms", "novels",
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
        """Get row count for a table.

        table_name is interpolated into SQL (identifiers can't be bound as
        params), so it MUST be a real existing table — verify against
        sqlite_master first to prevent SQL injection via a crafted name.
        """
        if not self.table_exists(table_name):
            raise ValueError(f"Unknown table: {table_name!r}")
        result = self.db.fetchone(f"SELECT COUNT(*) as cnt FROM {table_name}")
        if result:
            return result["cnt"]
        return 0

    def migrate_to_v2(self) -> bool:
        """Add scope column to glossary_terms for v1→v2 migration.
        
        Returns True if migration was applied, False if already done.
        """
        # Check if column already exists
        columns = self.db.fetchall("PRAGMA table_info(glossary_terms)")
        has_scope = any(c["name"] == "scope" for c in columns)
        
        if has_scope:
            logger.info("Schema v2: scope column already exists")
            return False
        
        # Add scope column with default 'novel'
        self.db.execute(
            "ALTER TABLE glossary_terms ADD COLUMN scope TEXT NOT NULL DEFAULT 'novel'"
        )
        
        # Create new indexes
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_glossary_scope ON glossary_terms(scope)")
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_glossary_scope_status ON glossary_terms(scope, status)")
        
        logger.info("Schema v2 migration complete: added scope column")
        return True

    def migrate_to_v3(self) -> bool:
        """Add subtype column and term_relationships table (v2→v3).

        - glossary_terms.subtype: fine-grained label under the coarse category
          (e.g. category='place', subtype='mountain'). See src/glossary_taxonomy.py.
        - term_relationships: directed edges between terms (located_in, member_of,
          heads, master_of, ...).

        Idempotent: returns True if anything was applied, False if already at v3.
        """
        applied = False

        # If glossary_terms doesn't exist yet, create_all's CREATE TABLE IF NOT
        # EXISTS already built it WITH the subtype column — nothing to ALTER.
        if not self.table_exists("glossary_terms"):
            columns = []
        else:
            columns = self.db.fetchall("PRAGMA table_info(glossary_terms)")
        has_subtype = any(c["name"] == "subtype" for c in columns)
        if columns and not has_subtype:
            # NOTE: no NOT NULL — existing rows must back-fill to NULL cleanly.
            self.db.execute("ALTER TABLE glossary_terms ADD COLUMN subtype TEXT")
            self.db.execute(
                "CREATE INDEX IF NOT EXISTS idx_glossary_subtype ON glossary_terms(subtype)"
            )
            applied = True
            logger.info("Schema v3: added glossary_terms.subtype column")

        if not self.table_exists("term_relationships"):
            self.db.execute(
                """CREATE TABLE IF NOT EXISTS term_relationships (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    novel_id TEXT NOT NULL,
                    src_term_id TEXT NOT NULL,
                    dst_term_id TEXT NOT NULL,
                    relation_type TEXT NOT NULL,
                    confidence REAL NOT NULL DEFAULT 1.0,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    FOREIGN KEY (src_term_id) REFERENCES glossary_terms(id) ON DELETE CASCADE,
                    FOREIGN KEY (dst_term_id) REFERENCES glossary_terms(id) ON DELETE CASCADE,
                    UNIQUE (src_term_id, dst_term_id, relation_type)
                )"""
            )
            for stmt in (
                "CREATE INDEX IF NOT EXISTS idx_term_rel_novel ON term_relationships(novel_id)",
                "CREATE INDEX IF NOT EXISTS idx_term_rel_src ON term_relationships(src_term_id)",
                "CREATE INDEX IF NOT EXISTS idx_term_rel_dst ON term_relationships(dst_term_id)",
                "CREATE INDEX IF NOT EXISTS idx_term_rel_type ON term_relationships(relation_type)",
            ):
                self.db.execute(stmt)
            applied = True
            logger.info("Schema v3: created term_relationships table")

        if not applied:
            logger.info("Schema v3: subtype + term_relationships already present")
        return applied
