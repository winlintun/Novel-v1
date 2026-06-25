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


# Production database that must never be written to during a test run.
_PRODUCTION_DB = "data/novel_translation.db"


@pytest.fixture(scope="session", autouse=True)
def _guard_production_db():
    """Redirect the production DB to a throwaway temp DB for the whole test run.

    Any test that builds a ``DatabaseConnection`` (directly, or indirectly via
    ``MemoryManager`` / the repositories) without passing an explicit path falls
    back to the default ``data/novel_translation.db``. That persists test novels
    and auto-seeds the global xianxia glossary into the *real* database. This
    autouse fixture transparently rewrites that one production path to a
    per-session temp DB, so running the suite never saves glossary terms (or
    anything else) into the real file. Tests that pass their own db_path — e.g.
    the ``tmp_db_path`` fixture — are unaffected.
    """
    from src.db import connection as _conn_mod

    real = Path(_PRODUCTION_DB).resolve()
    tmp_dir = Path(tempfile.mkdtemp(prefix="novel_test_db_"))
    redirect = tmp_dir / "novel_translation.db"

    original_init = _conn_mod.DatabaseConnection.__init__

    def guarded_init(self, db_path: str = _PRODUCTION_DB):
        if Path(db_path).resolve() == real:
            db_path = str(redirect)
        original_init(self, db_path)

    _conn_mod.DatabaseConnection.__init__ = guarded_init
    try:
        yield redirect
    finally:
        _conn_mod.DatabaseConnection.__init__ = original_init
        shutil.rmtree(tmp_dir, ignore_errors=True)


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
