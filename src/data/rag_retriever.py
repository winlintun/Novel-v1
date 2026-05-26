"""
RAG Retriever for Novel Translation
====================================
Retrieves similar translation examples from ChromaDB/SQLite during translation
to inject as few-shot examples into the prompt.

Usage:
    retriever = RAGRetriever(chroma_path="data/chroma_db", db_path="data/novel_v1_dataset.db")
    examples = retriever.retrieve_similar("The young man walked into the tavern.", top_k=3)
"""

import sqlite3
import hashlib
import logging
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

try:
    import chromadb
    from chromadb.utils import embedding_functions
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False


@dataclass
class TranslationExample:
    """A single translation pair retrieved for RAG injection."""
    en_text: str
    my_text: str
    score: float
    source_file: str
    similarity: float = 0.0

    def format_for_prompt(self) -> str:
        """Format as few-shot example for prompt injection."""
        return f"EN: {self.en_text}\nMY: {self.my_text}"


class RAGRetriever:
    """
    Retrieves similar translation examples from ChromaDB + SQLite.
    
    ChromaDB is used for semantic similarity search.
    SQLite is used as fallback for exact/novel-specific retrieval.
    """

    def __init__(
        self,
        chroma_path: str = "data/chroma_db",
        db_path: str = "data/novel_v1_dataset.db",
        top_k: int = 3,
        min_score: float = 2.5,
        novel_filter: Optional[str] = None,
    ):
        self.chroma_path = chroma_path
        self.db_path = db_path
        self.top_k = top_k
        self.min_score = min_score
        self.novel_filter = novel_filter

        self._chroma_client = None
        self._chroma_collection = None
        self._sqlite_conn = None
        self.logger = logging.getLogger(__name__)

        self._init_chroma()
        self._init_sqlite()

    def _init_chroma(self) -> None:
        """Initialize ChromaDB connection with BGE-M3 embedding model."""
        if not CHROMA_AVAILABLE:
            self.logger.warning("chromadb not installed — Chroma RAG disabled")
            self._chroma_client = None
            self._chroma_collection = None
            return

        chroma_path = Path(self.chroma_path)
        if not chroma_path.exists():
            self.logger.warning(f"ChromaDB path not found: {self.chroma_path} — RAG will use SQLite fallback")
            self._chroma_client = None
            self._chroma_collection = None
            return

        try:
            self._chroma_client = chromadb.PersistentClient(path=str(chroma_path))
            # NOTE: Do NOT pass embedding_function to get_collection — the collection
            # was already created with one. Passing a different embedding_function
            # causes "embedding function already exists" conflict error (ERR-072).
            try:
                self._chroma_collection = self._chroma_client.get_collection(
                    name="alignment_pairs",
                )
            except ValueError:
                # Collection does not exist — this is the common case when RAG data
                # has not been ingested yet. Check what collections ARE available
                # and log a clear message so the user knows what to fix.
                self._chroma_collection = None
                try:
                    cols = self._chroma_client.list_collections()
                    if cols:
                        col_names = [c.name for c in cols]
                        self.logger.warning(
                            f"ChromaDB collection 'alignment_pairs' not found. "
                            f"Available collections: {col_names}. "
                            f"RAG will use SQLite fallback."
                        )
                    else:
                        self.logger.warning(
                            "⚠ RAG DATA EMPTY: ChromaDB collection 'alignment_pairs' does not exist "
                            "and no other collections found at %s. "
                            "RAG will return NO examples. "
                            "To fix: repopulate via dataset_alignment_project's ingest script.",
                            self.chroma_path,
                        )
                except Exception:
                    pass
                return
            count = self._chroma_collection.count()
            self.logger.info(f"ChromaDB initialized at {chroma_path} ({count} embeddings)")
            if count == 0:
                self.logger.warning("ChromaDB collection 'alignment_pairs' is empty — RAG will use SQLite fallback")
                self._chroma_collection = None
        except Exception as e:
            self.logger.warning(f"ChromaDB init failed: {e} — falling back to SQLite")
            # Try to list what collections exist for diagnostic info
            try:
                if self._chroma_client:
                    cols = self._chroma_client.list_collections()
                    if cols:
                        self.logger.warning(
                            "  ChromaDB collections found at %s: %s",
                            self.chroma_path,
                            [c.name for c in cols],
                        )
            except Exception:
                pass
            self._chroma_client = None
            self._chroma_collection = None

    def _init_sqlite(self) -> None:
        """Initialize SQLite connection."""
        if Path(self.db_path).exists():
            self._sqlite_conn = sqlite3.connect(self.db_path)
            self._sqlite_conn.row_factory = sqlite3.Row

            # Check if translation_pairs table has data
            try:
                row_count = self._sqlite_conn.execute(
                    "SELECT COUNT(*) FROM translation_pairs"
                ).fetchone()[0]
                if row_count == 0:
                    self.logger.warning(
                        "⚠ RAG DATA EMPTY: SQLite translation_pairs table at %s has 0 rows. "
                        "RAG fallback will return NO examples.",
                        self.db_path,
                    )
                else:
                    self.logger.info(
                        "SQLite RAG fallback ready: %d rows in translation_pairs",
                        row_count,
                    )
            except sqlite3.Error:
                self.logger.warning(
                    "SQLite table 'translation_pairs' not found in %s. "
                    "RAG fallback will return NO examples.",
                    self.db_path,
                )

    def retrieve_similar(
        self,
        query_text: str,
        top_k: Optional[int] = None,
        novel_filter: Optional[str] = None,
    ) -> list[TranslationExample]:
        """
        Retrieve similar translation examples for the given source text.
        
        Priority: ChromaDB semantic search > SQLite novel-specific > SQLite general
        
        Args:
            query_text: English source text to find similar examples for
            top_k: Number of examples to retrieve (overrides constructor default)
            novel_filter: Filter by novel slug (e.g., "eternal-sacred-king")
            
        Returns:
            List of TranslationExample objects sorted by relevance
        """
        k = top_k or self.top_k
        novel = novel_filter or self.novel_filter

        # Try ChromaDB first
        if self._chroma_collection is not None:
            examples = self._retrieve_from_chroma(query_text, k, novel)
            if examples:
                return examples

        # Fallback to SQLite
        return self._retrieve_from_sqlite(query_text, k, novel)

    def _retrieve_from_chroma(
        self,
        query_text: str,
        top_k: int,
        novel_filter: Optional[str] = None,
    ) -> list[TranslationExample]:
        """Retrieve from ChromaDB using semantic similarity."""
        try:
            where_clause = {"auto_score": {"$gte": self.min_score}}
            if novel_filter:
                where_clause["source_file"] = {"$regex": novel_filter}

            results = self._chroma_collection.query(
                query_texts=[query_text],
                n_results=top_k * 2,
                where=where_clause,
                include=["metadatas", "documents", "distances"],
            )

            examples = []
            if results["ids"] and results["ids"][0]:
                for i, doc_id in enumerate(results["ids"][0]):
                    metadata = results["metadatas"][0][i]
                    distance = results["distances"][0][i]
                    similarity = 1.0 - distance

                    examples.append(TranslationExample(
                        en_text=results["documents"][0][i],
                        my_text=metadata.get("my_text", ""),
                        score=metadata.get("auto_score", 0.0),
                        source_file=metadata.get("source_file", ""),
                        similarity=similarity,
                    ))

            return examples[:top_k]

        except Exception:
            return []

    def _retrieve_from_sqlite(
        self,
        query_text: str,
        top_k: int,
        novel_filter: Optional[str] = None,
    ) -> list[TranslationExample]:
        """Retrieve from SQLite using keyword overlap heuristic."""
        if self._sqlite_conn is None:
            return []

        try:
            # Extract key words from query for simple matching
            words = set(query_text.lower().split())
            words = {w for w in words if len(w) > 3}

            # Build base query
            sql = """
                SELECT en_text, my_text, auto_score, source_file, novel_slug
                FROM translation_pairs
                WHERE usable = 1 AND auto_score >= ?
            """
            params = [self.min_score]

            # Filter by novel_slug or source_file containing the novel name
            if novel_filter:
                sql += " AND (novel_slug = ? OR source_file LIKE ?)"
                params.append(novel_filter)
                params.append(f"%{novel_filter}%")

            # If we have query words, use LIKE with OR to widen candidate pool
            if words:
                like_conditions = " AND (" + " OR ".join(
                    [f"en_text LIKE ?" for _ in words]
                ) + ")"
                sql += like_conditions
                for w in words:
                    params.append(f"%{w}%")

            # Order by score then limit - we re-rank by overlap below
            sql += " ORDER BY auto_score DESC, length(en_text) ASC LIMIT ?"
            params.append(top_k * 50)

            cursor = self._sqlite_conn.execute(sql, params)
            rows = cursor.fetchall()

            if not rows:
                return []

            # Score by word overlap
            scored = []
            for row in rows:
                if words:
                    en_words = set(row["en_text"].lower().split())
                    overlap = len(words & en_words)
                    similarity = overlap / max(len(words), 1)
                else:
                    # No query words: use score as similarity proxy
                    similarity = row["auto_score"] / 5.0

                scored.append((similarity, TranslationExample(
                    en_text=row["en_text"],
                    my_text=row["my_text"],
                    score=row["auto_score"],
                    source_file=row["source_file"],
                    similarity=similarity,
                )))

            # Sort by similarity and return top_k
            scored.sort(key=lambda x: x[0], reverse=True)
            return [ex for _, ex in scored[:top_k]]

        except sqlite3.Error:
            return []

    def retrieve_by_novel(
        self,
        novel_slug: str,
        top_k: int = 5,
    ) -> list[TranslationExample]:
        """Retrieve top examples from a specific novel."""
        return self._retrieve_from_sqlite("", top_k, novel_slug)

    def close(self) -> None:
        """Close database connections."""
        if hasattr(self, '_sqlite_conn') and self._sqlite_conn:
            self._sqlite_conn.close()
            self._sqlite_conn = None
        if hasattr(self, '_chroma_client') and self._chroma_client:
            try:
                self._chroma_client.clear_system_cache()
            except Exception:
                pass

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass
