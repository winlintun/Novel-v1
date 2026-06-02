"""
Shared fixtures and CI detection for tests.
Heavy dependencies (sentence-transformers, chromadb, torch) are imported lazily
in src/ — tests should never trigger those code paths in CI.
"""

import os
import shutil
import tempfile
from pathlib import Path

import pytest


def is_ci() -> bool:
    """Detect if running in CI (GitHub Actions, GitLab CI, etc.)."""
    return any(os.environ.get(var) for var in
               ["CI", "GITHUB_ACTIONS", "GITLAB_CI", "JENKINS_HOME"])


@pytest.fixture(scope="session")
def tmp_db_path() -> Path:
    """Create a temporary SQLite DB with schema for tests that need a database."""
    db_dir = Path(tempfile.mkdtemp(prefix="novel_test_"))
    db_path = db_dir / "novel_translation.db"

    import sqlite3
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS novels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            novel_id TEXT UNIQUE NOT NULL,
            title TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS glossary_terms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            novel_id TEXT NOT NULL,
            source_term TEXT NOT NULL,
            target_term TEXT,
            category TEXT DEFAULT 'general',
            status TEXT DEFAULT 'pending',
            chapter_first_seen INTEGER DEFAULT 0,
            usage_count INTEGER DEFAULT 1,
            verified INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );
        INSERT OR IGNORE INTO novels (novel_id, title) VALUES ('test-novel', 'Test Novel');
    """)
    conn.commit()
    conn.close()
    yield db_path
    shutil.rmtree(db_dir, ignore_errors=True)
