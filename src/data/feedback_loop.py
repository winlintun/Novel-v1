"""
Feedback Loop for Novel Translation
=====================================
Rates translation output and ingests high-quality pairs back into the database
to continuously improve the RAG retrieval pool.

Flow:
    Translation Output → Quality Score → If score >= threshold → Ingest to DB+Chroma
"""

import sqlite3
import hashlib
import re
from pathlib import Path
from typing import Optional
from datetime import datetime

try:
    import chromadb
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False

# Myanmar Unicode range
MYANMAR_RE = re.compile(r"[\u1000-\u109F]")
LATIN_RE = re.compile(r"[A-Za-z]")
GARBAGE_RE = re.compile(
    r"(january|february|march|april|may|june|july|august|"
    r"september|october|november|december|\d{4}|"
    r"chapter \d|volume \d)",
    re.IGNORECASE,
)


def myanmar_ratio(text: str) -> float:
    """Fraction of characters that are Myanmar script."""
    if not text:
        return 0.0
    my_chars = len(MYANMAR_RE.findall(text))
    return my_chars / len(text)


def length_ratio(en: str, my: str) -> float:
    """EN→MY length ratio heuristic."""
    if not en or not my:
        return 0.0
    ratio = len(my) / len(en)
    if 0.6 <= ratio <= 2.5:
        return 1.0
    elif 0.3 <= ratio <= 4.0:
        return 0.5
    return 0.0


def auto_quality_score(en: str, my: str) -> float:
    """Heuristic quality score 0–5."""
    score = 0.0
    my_ratio = myanmar_ratio(my)
    score += min(my_ratio * 2.5, 2.0)
    score += length_ratio(en, my) * 1.5
    if not GARBAGE_RE.search(my):
        score += 1.0
    latin_count = len(LATIN_RE.findall(my))
    if latin_count / max(len(my), 1) < 0.1:
        score += 0.5
    return round(min(score, 5.0), 2)


def is_misaligned(en: str, my: str) -> bool:
    """Detect obvious misalignment."""
    if len(my) < 5:
        return True
    if myanmar_ratio(my) < 0.20:
        return True
    if re.match(r"^(#|---|\*\*|အခန်း\s*\(\d+\)|Chapter\s+\d+)", my.strip()):
        if len(my) < 30:
            return True
    return False


def pair_id(en: str) -> str:
    """Generate SHA256-based ID for a translation pair."""
    return hashlib.sha256(en.encode()).hexdigest()[:16]


class FeedbackLoop:
    """
    Rates translation output and ingests high-quality pairs back into the database.
    
    This creates a virtuous cycle: better translations → better RAG examples → better translations.
    """

    def __init__(
        self,
        db_path: str = "data/novel_v1_dataset.db",
        chroma_path: str = "data/chroma_db",
        min_score: float = 3.0,
        min_myanmar_ratio: float = 0.70,
    ):
        self.db_path = db_path
        self.chroma_path = chroma_path
        self.min_score = min_score
        self.min_myanmar_ratio = min_myanmar_ratio

        self._sqlite_conn = None
        self._chroma_collection = None

        self._init_sqlite()
        self._init_chroma()

        # Stats tracking
        self.stats = {
            "total_processed": 0,
            "ingested": 0,
            "rejected_low_score": 0,
            "rejected_low_myanmar": 0,
            "rejected_duplicate": 0,
        }

    def _init_sqlite(self) -> None:
        """Initialize SQLite connection and ensure schema exists."""
        self._sqlite_conn = sqlite3.connect(self.db_path)

        # Ensure schema exists (same as dataset_pipeline.py)
        self._sqlite_conn.executescript("""
            CREATE TABLE IF NOT EXISTS translation_pairs (
                id              TEXT PRIMARY KEY,
                en_text         TEXT NOT NULL,
                my_text         TEXT NOT NULL,
                novel_slug      TEXT,
                chapter_num     INTEGER,
                auto_score      REAL,
                human_score     REAL,
                myanmar_ratio   REAL,
                length_ratio    REAL,
                aligned         INTEGER,
                usable          INTEGER,
                source_file     TEXT,
                created_at      TEXT DEFAULT (datetime('now'))
            );
        """)
        self._sqlite_conn.commit()

    def _init_chroma(self) -> None:
        """Initialize ChromaDB connection. Skipped to avoid model downloads."""
        # Skip ChromaDB to avoid model downloads during feedback ingestion
        # SQLite-only mode is sufficient for the feedback loop
        self._chroma_collection = None

    def rate_and_ingest(
        self,
        en_text: str,
        my_text: str,
        novel_slug: Optional[str] = None,
        chapter_num: Optional[int] = None,
        source_file: Optional[str] = None,
    ) -> dict:
        """
        Rate a translation pair and ingest if quality is sufficient.
        
        Args:
            en_text: English source text
            my_text: Myanmar translation output
            novel_slug: Novel identifier (e.g., "eternal-sacred-king")
            chapter_num: Chapter number
            source_file: Source file path
            
        Returns:
            Dict with rating results and ingestion status
        """
        self.stats["total_processed"] += 1

        # Calculate quality metrics
        score = auto_quality_score(en_text, my_text)
        aligned = not is_misaligned(en_text, my_text)
        my_ratio = myanmar_ratio(my_text)
        len_ratio = length_ratio(en_text, my_text)
        usable = aligned and score >= self.min_score

        result = {
            "en_text": en_text[:100],
            "my_text": my_text[:100],
            "score": score,
            "aligned": aligned,
            "myanmar_ratio": my_ratio,
            "length_ratio": len_ratio,
            "usable": usable,
            "ingested": False,
            "reason": "",
        }

        # Check quality thresholds
        if score < self.min_score:
            result["reason"] = f"low_score ({score} < {self.min_score})"
            self.stats["rejected_low_score"] += 1
            return result

        if my_ratio < self.min_myanmar_ratio:
            result["reason"] = f"low_myanmar_ratio ({my_ratio:.2f} < {self.min_myanmar_ratio})"
            self.stats["rejected_low_myanmar"] += 1
            return result

        # Check for duplicates
        pid = pair_id(en_text)
        if self._sqlite_conn:
            try:
                cursor = self._sqlite_conn.execute(
                    "SELECT 1 FROM translation_pairs WHERE id = ?", (pid,)
                )
                if cursor.fetchone():
                    result["reason"] = "duplicate"
                    self.stats["rejected_duplicate"] += 1
                    return result
            except sqlite3.Error:
                pass

        # Ingest to SQLite
        if self._sqlite_conn:
            try:
                self._sqlite_conn.execute("""
                    INSERT INTO translation_pairs
                        (id, en_text, my_text, novel_slug, chapter_num,
                         auto_score, myanmar_ratio, length_ratio,
                         aligned, usable, source_file)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    pid, en_text, my_text, novel_slug, chapter_num,
                    score, my_ratio, len_ratio,
                    int(aligned), int(usable), source_file or "feedback_loop",
                ))
                self._sqlite_conn.commit()
            except sqlite3.Error as e:
                result["reason"] = f"sqlite_error: {e}"
                return result

        # Ingest to ChromaDB
        if self._chroma_collection and usable:
            try:
                self._chroma_collection.upsert(
                    ids=[pid],
                    documents=[en_text],
                    metadatas=[{
                        "my_text": my_text[:500],
                        "auto_score": score,
                        "source_file": source_file or "feedback_loop",
                    }],
                )
            except Exception as e:
                result["reason"] = f"chroma_error: {e}"

        result["ingested"] = True
        self.stats["ingested"] += 1
        return result

    def get_stats(self) -> dict:
        """Return ingestion statistics."""
        return self.stats.copy()

    def close(self) -> None:
        """Close database connections."""
        if self._sqlite_conn:
            self._sqlite_conn.close()
            self._sqlite_conn = None

    def __del__(self) -> None:
        self.close()
