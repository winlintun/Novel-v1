"""
Feedback Loop for Novel Translation
=====================================
Rates translation output and ingests high-quality pairs back into the database
to continuously improve the RAG retrieval pool.

Flow:
    Translation Output → Quality Score + Adequacy Gate → If both pass → Ingest to SQLite + ChromaDB

The adequacy gate (BGE-M3 cross-lingual cosine) rejects pairs that are
fluently-Myanmar but meaning-incomplete (dropped sentences, hallucinations)
— the fluency-only heuristic cannot catch these (long_term_memory lesson #2).
"""

import sqlite3
import hashlib
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

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

    This creates a virtuous cycle: better translations → better RAG examples →
    better translations.

    Quality gate (F2): a pair is only ingested if it passes BOTH:
      1. Heuristic score >= min_score (fluency + Myanmar ratio + length)
      2. BGE-M3 adequacy >= min_adequacy (cross-lingual meaning similarity)
    The adequacy gate catches meaning-incomplete pairs that the fluency heuristic
    cannot (dropped sentences, hallucinations) — preventing corpus pollution.
    """

    def __init__(
        self,
        db_path: str = "data/novel_v1_dataset.db",
        chroma_path: str = "data/chroma_db",
        chroma_collection: str = "alignment_paragraphs",
        embedding_model: str = "models/bge-m3",
        embedding_device: str = "cpu",
        min_score: float = 3.0,
        min_myanmar_ratio: float = 0.70,
        min_adequacy: float = 0.45,
    ):
        self.db_path = db_path
        self.chroma_path = chroma_path
        self.chroma_collection_name = chroma_collection
        self.embedding_model = embedding_model
        self.embedding_device = embedding_device
        self.min_score = min_score
        self.min_myanmar_ratio = min_myanmar_ratio
        self.min_adequacy = min_adequacy

        self._sqlite_conn = None
        self._chroma_client = None
        self._chroma_collection = None
        self._embedder = None
        self._embedder_loaded = False

        self._init_sqlite()
        self._init_chroma()

        # Stats tracking
        self.stats = {
            "total_processed": 0,
            "ingested": 0,
            "rejected_low_score": 0,
            "rejected_low_myanmar": 0,
            "rejected_low_adequacy": 0,
            "rejected_duplicate": 0,
            "chroma_upserts": 0,
            "chroma_errors": 0,
        }

    def _init_sqlite(self) -> None:
        """Initialize SQLite connection and ensure schema exists.

        Also adds the adequacy_score column to existing tables (additive,
        idempotent migration — existing rows back-fill to NULL).
        """
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

        # Additive migration: adequacy_score column (idempotent)
        try:
            cols = self._sqlite_conn.execute("PRAGMA table_info(translation_pairs)").fetchall()
            col_names = {c[1] for c in cols}
            if "adequacy_score" not in col_names:
                self._sqlite_conn.execute(
                    "ALTER TABLE translation_pairs ADD COLUMN adequacy_score REAL"
                )
                self._sqlite_conn.commit()
                logger.info("Feedback DB: added adequacy_score column to translation_pairs")
        except sqlite3.Error as e:
            logger.debug(f"Feedback DB adequacy_score migration skipped: {e}")

    def _init_chroma(self) -> None:
        """Initialize ChromaDB connection (F1 — re-enabled).

        Connects to the same collection the RAG retriever uses so ingested
        pairs are immediately available to semantic retrieval. ChromaDB does
        NOT persist the embedding function, so ingestion embeds EN text with
        BGE-M3 explicitly (same model used to build the index) — passing a
        different/default embedding function causes dimension mismatch.
        """
        try:
            import chromadb
        except ImportError:
            logger.warning("chromadb not installed — feedback ChromaDB ingestion disabled")
            self._chroma_client = None
            self._chroma_collection = None
            return

        from pathlib import Path
        if not Path(self.chroma_path).exists():
            logger.warning(f"ChromaDB path not found: {self.chroma_path} — feedback ChromaDB ingestion disabled")
            return

        try:
            self._chroma_client = chromadb.PersistentClient(path=str(self.chroma_path))
            # get_or_create so feedback works even if the collection doesn't exist yet
            self._chroma_collection = self._chroma_client.get_or_create_collection(
                name=self.chroma_collection_name,
            )
            count = self._chroma_collection.count()
            logger.info(
                f"FeedbackLoop ChromaDB ready: collection '{self.chroma_collection_name}' "
                f"({count} embeddings) — ingestion enabled"
            )
        except Exception as e:
            logger.warning(f"ChromaDB init failed: {e} — feedback ChromaDB ingestion disabled")
            self._chroma_client = None
            self._chroma_collection = None

    def _get_embedder(self):
        """Lazily load the BGE-M3 embedder for both adequacy scoring + Chroma upsert.

        Reuses the RAG retriever's process-wide embedder cache so the ~2GB
        model is loaded exactly once per process.
        """
        if self._embedder_loaded:
            return self._embedder
        self._embedder_loaded = True
        try:
            from src.data.rag_retriever import _get_query_embedder
            self._embedder = _get_query_embedder(self.embedding_model, self.embedding_device)
            if self._embedder is None:
                logger.warning(
                    "BGE-M3 embedder unavailable — adequacy gate + Chroma embedding disabled. "
                    "Feedback will ingest to SQLite only (no semantic retrieval for these pairs)."
                )
        except Exception as e:
            logger.warning(f"Embedder load failed: {e} — adequacy gate disabled")
            self._embedder = None
        return self._embedder

    def _check_adequacy(self, en_text: str, my_text: str) -> float:
        """Cross-lingual adequacy score via BGE-M3 (F2).

        Embeds EN + MM sentences, computes the mean of per-source-sentence
        best cosine matches → 0.0-1.0. A low score means the Myanmar rendering
        dropped or mistranslated content that the fluency heuristic cannot see.

        Returns 1.0 (pass) when the embedder is unavailable so the gate never
        blocks ingestion solely because BGE-M3 isn't installed — but logs a
        warning so the operator knows the gate is inactive.
        """
        embedder = self._get_embedder()
        if embedder is None:
            return 1.0  # gate degrades to no-op (don't block on missing model)

        # Split into sentences (same logic as checker.py:411-422)
        en_sents = [s.strip() for s in re.split(r'(?<=[.!?])\s+|\n{2}', en_text or "") if len(s.strip()) >= 12]
        my_sents = [s.strip() for s in re.split(r'(?<=။)\s*|\n{2}', my_text or "") if len(s.strip()) >= 6]
        if not en_sents or not my_sents:
            return 1.0

        try:
            import numpy as np
            en_emb = np.asarray(embedder.encode(en_sents, normalize_embeddings=True, show_progress_bar=False))
            my_emb = np.asarray(embedder.encode(my_sents, normalize_embeddings=True, show_progress_bar=False))
            if en_emb.size == 0 or my_emb.size == 0:
                return 1.0
            sim = en_emb @ my_emb.T  # [n_en, n_my] cosine (normalized)
            # Mean of per-source-sentence best matches = how well EN is covered
            return round(float(sim.max(axis=1).mean()), 3)
        except Exception as e:
            logger.debug(f"Adequacy check failed (non-fatal): {e}")
            return 1.0  # don't block on a runtime error

    def _embed_for_ingest(self, en_text: str) -> Optional[list]:
        """Embed EN text for ChromaDB upsert (BGE-M3, 1024-dim normalized)."""
        embedder = self._get_embedder()
        if embedder is None:
            return None
        try:
            vec = embedder.encode([en_text], normalize_embeddings=True, show_progress_bar=False)
            return vec[0].tolist()
        except Exception as e:
            logger.debug(f"Chroma ingest embedding failed: {e}")
            return None

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

        Quality gate (F2): both the heuristic score AND the BGE-M3 adequacy
        score must pass. This rejects fluently-Myanmar but meaning-incomplete
        pairs (dropped sentences, hallucinations) that pollute the RAG corpus.
        """
        self.stats["total_processed"] += 1

        # Calculate heuristic quality metrics
        score = auto_quality_score(en_text, my_text)
        aligned = not is_misaligned(en_text, my_text)
        my_ratio = myanmar_ratio(my_text)
        len_ratio = length_ratio(en_text, my_text)

        result = {
            "en_text": en_text[:100],
            "my_text": my_text[:100],
            "score": score,
            "aligned": aligned,
            "myanmar_ratio": my_ratio,
            "length_ratio": len_ratio,
            "adequacy_score": None,
            "usable": False,
            "ingested": False,
            "reason": "",
        }

        # Gate 1: heuristic score
        if score < self.min_score:
            result["reason"] = f"low_score ({score} < {self.min_score})"
            self.stats["rejected_low_score"] += 1
            return result

        # Gate 2: Myanmar ratio
        if my_ratio < self.min_myanmar_ratio:
            result["reason"] = f"low_myanmar_ratio ({my_ratio:.2f} < {self.min_myanmar_ratio})"
            self.stats["rejected_low_myanmar"] += 1
            return result

        # Gate 3 (F2): BGE-M3 adequacy — meaning completeness
        adequacy = self._check_adequacy(en_text, my_text)
        result["adequacy_score"] = adequacy
        if adequacy < self.min_adequacy:
            result["reason"] = f"low_adequacy ({adequacy:.2f} < {self.min_adequacy})"
            self.stats["rejected_low_adequacy"] += 1
            return result

        usable = True
        result["usable"] = usable

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
                         aligned, usable, source_file, adequacy_score)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    pid, en_text, my_text, novel_slug, chapter_num,
                    score, my_ratio, len_ratio,
                    int(aligned), int(usable), source_file or "feedback_loop",
                    adequacy,
                ))
                self._sqlite_conn.commit()
            except sqlite3.Error as e:
                result["reason"] = f"sqlite_error: {e}"
                return result

        # Ingest to ChromaDB (F1 — re-enabled)
        if self._chroma_collection and usable:
            en_vec = self._embed_for_ingest(en_text)
            if en_vec is not None:
                try:
                    self._chroma_collection.upsert(
                        ids=[pid],
                        embeddings=[en_vec],
                        documents=[en_text],
                        metadatas=[{
                            "my_text": my_text[:500],
                            "auto_score": score,
                            "adequacy_score": adequacy,
                            "source_file": source_file or "feedback_loop",
                            "novel": novel_slug or "",
                        }],
                    )
                    self.stats["chroma_upserts"] += 1
                except Exception as e:
                    self.stats["chroma_errors"] += 1
                    logger.debug(f"ChromaDB upsert failed (non-fatal, SQLite ingest still succeeded): {e}")
                    # Don't overwrite a successful SQLite ingest — Chroma is additive

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
        if self._chroma_client:
            try:
                self._chroma_client.clear_system_cache()
            except Exception:
                pass

    def __del__(self) -> None:
        self.close()
