"""SQLite schema + DAO for the Dataset Alignment Pipeline."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from src.dataset_alignment.config import get_alignment_config

SCHEMA = """
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS files (
    id          INTEGER PRIMARY KEY,
    novel       TEXT    NOT NULL,
    lang        TEXT    NOT NULL,
    path        TEXT    NOT NULL UNIQUE,
    filename    TEXT    NOT NULL,
    chapter_no  INTEGER,
    sha256      TEXT    NOT NULL,
    encoding    TEXT,
    byte_size   INTEGER,
    char_count  INTEGER,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_dap_files_chapter ON files(novel, lang, chapter_no);
CREATE INDEX IF NOT EXISTS idx_dap_files_sha ON files(sha256);

CREATE TABLE IF NOT EXISTS chapters (
    id             INTEGER PRIMARY KEY,
    novel          TEXT    NOT NULL,
    chapter_no     INTEGER NOT NULL,
    src_file_id    INTEGER REFERENCES files(id),
    tgt_file_id    INTEGER REFERENCES files(id),
    src_title      TEXT,
    tgt_title      TEXT,
    src_char_count INTEGER,
    tgt_char_count INTEGER,
    UNIQUE(novel, chapter_no)
);

CREATE TABLE IF NOT EXISTS sentences (
    id          INTEGER PRIMARY KEY,
    file_id     INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    chapter_id  INTEGER REFERENCES chapters(id),
    lang        TEXT    NOT NULL,
    seq         INTEGER NOT NULL,
    text        TEXT    NOT NULL,
    text_norm   TEXT,
    char_count  INTEGER,
    is_dialogue INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_dap_sent_chapter ON sentences(chapter_id, lang, seq);

CREATE TABLE IF NOT EXISTS alignments (
    id          INTEGER PRIMARY KEY,
    chapter_id  INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    src_ids     TEXT    NOT NULL,
    tgt_ids     TEXT    NOT NULL,
    similarity  REAL,
    kind        TEXT,
    rating      INTEGER,
    reviewed    INTEGER DEFAULT 0,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_dap_align_chapter ON alignments(chapter_id);
CREATE INDEX IF NOT EXISTS idx_dap_align_rating ON alignments(rating);

CREATE TABLE IF NOT EXISTS issues (
    id           INTEGER PRIMARY KEY,
    chapter_id   INTEGER REFERENCES chapters(id),
    sentence_id  INTEGER REFERENCES sentences(id),
    file_id      INTEGER REFERENCES files(id),
    category     TEXT NOT NULL,
    severity     TEXT NOT NULL,
    message      TEXT NOT NULL,
    evidence     TEXT,
    auto_fixable INTEGER DEFAULT 0,
    fixed        INTEGER DEFAULT 0,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_dap_issues_cat ON issues(category, severity);
CREATE INDEX IF NOT EXISTS idx_dap_issues_chap ON issues(chapter_id);

CREATE TABLE IF NOT EXISTS embedding_handles (
    id           INTEGER PRIMARY KEY,
    sentence_id  INTEGER REFERENCES sentences(id),
    chroma_id    TEXT NOT NULL UNIQUE,
    model        TEXT NOT NULL,
    dim          INTEGER,
    sha256       TEXT,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_dap_embed_sent ON embedding_handles(sentence_id);
"""

ALIGNMENT_DB_NAME = "novel_alignment.db"


def init_db(db_path: Optional[Path] = None) -> Path:
    cfg = get_alignment_config()
    db_path = db_path or cfg.db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA)
    return db_path


@contextmanager
def connect(db_path: Optional[Path] = None) -> Iterator[sqlite3.Connection]:
    cfg = get_alignment_config()
    db_path = db_path or cfg.db_path
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def insert_issue(
    conn: sqlite3.Connection,
    *,
    category: str,
    severity: str,
    message: str,
    chapter_id: Optional[int] = None,
    sentence_id: Optional[int] = None,
    file_id: Optional[int] = None,
    evidence: Optional[str] = None,
    auto_fixable: bool = False,
) -> int:
    cur = conn.execute(
        """INSERT INTO issues
           (chapter_id, sentence_id, file_id, category, severity, message,
            evidence, auto_fixable)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (chapter_id, sentence_id, file_id, category, severity, message,
         evidence, int(auto_fixable)),
    )
    return cur.lastrowid


def fetch_issues_by_category(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute(
        "SELECT category, severity, COUNT(*) AS n "
        "FROM issues GROUP BY category, severity"
    ).fetchall()
    return {f"{r['category']}::{r['severity']}": r["n"] for r in rows}
