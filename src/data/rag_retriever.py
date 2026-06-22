"""
RAG Retriever for Novel Translation
====================================
Retrieves similar translation examples from ChromaDB/SQLite during translation
to inject as few-shot examples into the prompt.

Usage:
    retriever = RAGRetriever(chroma_path="data/chroma", db_path="data/novel_v1_dataset.db")
    examples = retriever.retrieve_similar("The young man walked into the tavern.", top_k=3)
"""

import sqlite3
import logging
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

try:
    import chromadb
    from chromadb.errors import NotFoundError as ChromaNotFoundError
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False


# The ChromaDB collection 'alignment_pairs' was ingested with BGE-M3 (1024-dim,
# normalized) embeddings. ChromaDB does NOT persist the embedding function, so
# query_texts=... would silently fall back to Chroma's default model
# (all-MiniLM-L6-v2, 384-dim) and every query fails with a dimension mismatch.
# We must embed queries ourselves with the SAME model and pass query_embeddings.
# The model is heavy (~2GB), so cache one instance per (model, device) process-wide.
_EMBEDDER_CACHE: dict = {}


def _get_query_embedder(model_name: str, device: str):
    """Lazily load and cache a SentenceTransformer for query embedding.

    Returns None if sentence-transformers or the model cannot be loaded, in
    which case the caller should fall back to SQLite retrieval.
    """
    key = (model_name, device)
    if key in _EMBEDDER_CACHE:
        return _EMBEDDER_CACHE[key]
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(model_name, device=device, local_files_only=True)
    except Exception as e:
        logging.getLogger(__name__).warning(
            "Could not load query embedding model '%s' on %s: %s — "
            "Chroma semantic RAG disabled, using SQLite fallback.",
            model_name, device, e,
        )
        model = None
    _EMBEDDER_CACHE[key] = model
    return model


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
        chroma_path: str = "data/chroma",
        db_path: str = "data/novel_v1_dataset.db",
        top_k: int = 3,
        min_score: float = 2.5,
        novel_filter: Optional[str] = None,
        embedding_model: str = "models/bge-m3",
        embedding_device: str = "cpu",
        min_similarity: float = 0.3,
        collection_name: str = "alignment_pairs",
    ):
        self.chroma_path = chroma_path
        self.db_path = db_path
        self.top_k = top_k
        self.min_score = min_score
        self.novel_filter = novel_filter
        # Chroma collection to query. The paragraph-level index
        # ('alignment_paragraphs') matches translation chunk granularity far
        # better than the original sentence-level 'alignment_pairs'.
        self.collection_name = collection_name
        # If Chroma's best semantic match is below this, fall back to SQLite
        # keyword retrieval. The corpus is sentence-level while translation
        # queries are paragraph-chunks, so Chroma cosine is often weak — SQLite
        # word-overlap then provides more useful, entity-matched examples.
        self.min_similarity = min_similarity
        self.embedding_model = embedding_model
        self.embedding_device = embedding_device

        self._chroma_client = None
        self._chroma_collection = None
        self._chroma_verified = False
        self._sqlite_conn = None
        self.logger = logging.getLogger(__name__)

        self._init_chroma()
        self._init_sqlite()

    def _embed_query(self, text: str) -> Optional[list]:
        """Embed a query string with the BGE-M3 model used to build the index.

        Returns a single 1024-dim normalized embedding (list of floats), or None
        if the embedding model is unavailable.
        """
        model = _get_query_embedder(self.embedding_model, self.embedding_device)
        if model is None:
            return None
        try:
            vec = model.encode(
                [text], normalize_embeddings=True, show_progress_bar=False
            )
            return vec[0].tolist()
        except Exception as e:
            self.logger.warning("Query embedding failed: %s — using SQLite fallback", e)
            return None

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
                    name=self.collection_name,
                )
            except (ValueError, ChromaNotFoundError):
                # Try fallback collection names
                fallback_names = ["alignment_pairs", "translations"]
                for fb_name in fallback_names:
                    try:
                        self._chroma_collection = self._chroma_client.get_collection(
                            name=fb_name,
                        )
                        self.logger.info(
                            f"ChromaDB: using collection '{fb_name}' (alignment_pairs not found)"
                        )
                        break
                    except (ValueError, ChromaNotFoundError):
                        continue
                else:
                    # No collection found — log available collections for diagnosis
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
                self.logger.warning(f"ChromaDB collection '{self._chroma_collection.name}' is empty — RAG will use SQLite fallback")
                self._chroma_collection = None
            elif self._chroma_collection is not None:
                self.logger.info(
                    "ChromaDB collection '%s' found with %d embeddings "
                    "(BGE-M3 verifier deferred to first query).",
                    self._chroma_collection.name, count,
                )
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

        # Try ChromaDB semantic search first.
        chroma_examples: list[TranslationExample] = []
        if self._chroma_collection is not None:
            chroma_examples = self._retrieve_from_chroma(query_text, k, novel)
            # Keep Chroma results only if at least one clears the usefulness bar.
            # Otherwise fall through to SQLite — sentence-level corpus vs
            # paragraph-chunk queries makes Chroma cosine weak, and SQLite
            # keyword/entity overlap often yields more relevant examples.
            if chroma_examples and max(e.similarity for e in chroma_examples) >= self.min_similarity:
                return chroma_examples

        # Fallback to SQLite keyword retrieval. Prefer it when Chroma was weak;
        # only fall back to the weak Chroma results if SQLite finds nothing.
        sqlite_examples = self._retrieve_from_sqlite(query_text, k, novel)
        return sqlite_examples or chroma_examples

    def _verify_chroma(self) -> bool:
        """One-time BGE-M3 verification: load embedder, run health query.

        Called on first actual retrieval, not during __init__, so the ~2GB
        embedding model load does not delay pipeline startup.

        Returns True if Chroma is usable, False to fall back to SQLite.
        """
        if self._chroma_verified:
            return True
        self.logger.info(
            "Loading BGE-M3 query embedder (first use, may take a minute)..."
        )
        health_vec = self._embed_query("health check")
        if health_vec is None:
            self.logger.warning(
                "BGE-M3 embedder unavailable — Chroma disabled, using SQLite fallback."
            )
            self._chroma_collection = None
            return False
        try:
            self._chroma_collection.query(
                query_embeddings=[health_vec],
                n_results=1,
                include=[],
            )
            self._chroma_verified = True
            self.logger.info(
                "ChromaDB semantic RAG ready (BGE-M3, %d-dim) for collection '%s'.",
                len(health_vec), self._chroma_collection.name,
            )
            return True
        except Exception as e:
            self.logger.warning(
                "ChromaDB query health check failed for collection '%s': %s — "
                "disabling Chroma, using SQLite fallback.",
                self._chroma_collection.name, e,
            )
            self._chroma_collection = None
            return False

    def _retrieve_from_chroma(
        self,
        query_text: str,
        top_k: int,
        novel_filter: Optional[str] = None,
    ) -> list[TranslationExample]:
        """Retrieve from ChromaDB using semantic similarity."""
        if not self._verify_chroma():
            return []
        try:
            query_vec = self._embed_query(query_text)
            if query_vec is None:
                return []

            # NOTE: auto_score is stored as a STRING ('4.356') in metadata.
            # ChromaDB does NOT coerce strings for numeric ops, so a
            # `{"auto_score": {"$gte": 2.5}}` filter silently matches ZERO docs
            # and disables Chroma entirely (every query fell back to SQLite).
            # We therefore filter by score in Python below, after parsing it to
            # float, and keep only the string-equality `novel` filter in `where`.
            where_clause = {"novel": {"$eq": novel_filter}} if novel_filter else None

            # Over-fetch so the post-query min_score filter still leaves top_k.
            results = self._chroma_collection.query(
                query_embeddings=[query_vec],
                n_results=top_k * 4,
                where=where_clause,
                include=["metadatas", "documents", "distances"],
            )

            examples = []
            if results["ids"] and results["ids"][0]:
                for i, doc_id in enumerate(results["ids"][0]):
                    metadata = results["metadatas"][0][i]
                    distance = results["distances"][0][i]
                    # The 'alignment_pairs' collection uses Chroma's DEFAULT
                    # distance space (squared-L2), not cosine. For the
                    # normalized BGE-M3 vectors, squared-L2 = 2 - 2*cos, so the
                    # true cosine similarity is 1 - distance/2. The old
                    # `1 - distance` halved every score, so genuinely-similar
                    # pairs (cos ~0.6) fell below min_similarity (0.30) and RAG
                    # injected nothing. (If the collection is ever recreated with
                    # hnsw:space=cosine, change this back to 1 - distance.)
                    similarity = max(0.0, 1.0 - distance / 2.0)

                    try:
                        score = float(metadata.get("auto_score", 0.0))
                    except (TypeError, ValueError):
                        score = 0.0
                    # Quality gate, applied in Python because the metadata value
                    # is a string (see note above).
                    if score < self.min_score:
                        continue
                    examples.append(TranslationExample(
                        en_text=results["documents"][0][i],
                        my_text=metadata.get("my_text", ""),
                        score=score,
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
            _STOP_WORDS = {
                "with", "that", "this", "from", "have", "what", "were",
                "been", "your", "they", "their", "would", "could", "should",
                "about", "which", "there", "where", "when", "than", "then",
                "some", "into", "also", "just", "like", "more", "very",
                "such", "each", "than", "them", "these", "those", "because",
            }
            words = set(query_text.lower().split())
            words = {w for w in words if len(w) > 3 and w not in _STOP_WORDS}

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
                    ["en_text LIKE ?" for _ in words]
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
