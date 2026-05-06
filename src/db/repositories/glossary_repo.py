"""
Glossary repository — CRUD for glossary_terms and term_variants tables.
"""

import logging
import hashlib
from datetime import datetime
from typing import Optional
from src.db.connection import DatabaseConnection

logger = logging.getLogger(__name__)


class GlossaryRepository:
    """Handles all database operations for glossary_terms and term_variants."""

    def __init__(self, db: DatabaseConnection):
        self.db = db

    # ── glossary_terms ──────────────────────────────────────────────────

    def add_term(self, novel_id: str, source_term: str, target_term: str,
                 category: str = "general", status: str = "pending",
                 enforcement_level: str = "soft", context_condition: Optional[str] = None,
                 confidence: float = 0.0) -> dict:
        """Insert a new glossary term."""
        term_id = f"term_{novel_id}_{hashlib.md5(source_term.encode()).hexdigest()[:8]}"
        now = datetime.now().isoformat()
        self.db.execute(
            """INSERT INTO glossary_terms
               (id, novel_id, source_term, target_term, canonical_form, category,
                status, enforcement_level, context_condition, confidence, usage_count, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)""",
            (term_id, novel_id, source_term, target_term, source_term, category,
             status, enforcement_level, context_condition, confidence, now),
        )
        logger.debug(f"Glossary term added: {source_term} -> {target_term}")
        return self.get_term(term_id)

    def get_term(self, term_id: str) -> Optional[dict]:
        """Fetch a term by ID."""
        row = self.db.fetchone("SELECT * FROM glossary_terms WHERE id = ?", (term_id,))
        return dict(row) if row else None

    def get_term_by_source(self, novel_id: str, source_term: str) -> Optional[dict]:
        """Fetch a term by novel_id and source_term."""
        row = self.db.fetchone(
            "SELECT * FROM glossary_terms WHERE novel_id = ? AND source_term = ?",
            (novel_id, source_term),
        )
        return dict(row) if row else None

    def get_terms_by_novel(self, novel_id: str, status: Optional[str] = None,
                           limit: int = 100) -> list[dict]:
        """Fetch terms for a novel, optionally filtered by status."""
        if status:
            rows = self.db.fetchall(
                "SELECT * FROM glossary_terms WHERE novel_id = ? AND status = ? ORDER BY usage_count DESC LIMIT ?",
                (novel_id, status, limit),
            )
        else:
            rows = self.db.fetchall(
                "SELECT * FROM glossary_terms WHERE novel_id = ? ORDER BY usage_count DESC LIMIT ?",
                (novel_id, limit),
            )
        return [dict(r) for r in rows]

    def get_terms_for_prompt(self, novel_id: str, limit: int = 20) -> list[dict]:
        """Get terms sorted by usage recency (usage_count) for prompt injection."""
        rows = self.db.fetchall(
            "SELECT * FROM glossary_terms WHERE novel_id = ? AND status = 'approved' "
            "ORDER BY usage_count DESC, confidence DESC LIMIT ?",
            (novel_id, limit),
        )
        return [dict(r) for r in rows]

    def update_term(self, term_id: str, **kwargs) -> Optional[dict]:
        """Update term fields."""
        allowed = {"target_term", "canonical_form", "category", "status",
                   "enforcement_level", "context_condition", "confidence", "usage_count", "reviewed_at"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return self.get_term(term_id)

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [term_id]
        self.db.execute(f"UPDATE glossary_terms SET {set_clause} WHERE id = ?", tuple(values))
        return self.get_term(term_id)

    def increment_usage(self, term_id: str) -> None:
        """Increment usage_count for a term."""
        self.db.execute(
            "UPDATE glossary_terms SET usage_count = usage_count + 1 WHERE id = ?",
            (term_id,),
        )

    def delete_term(self, term_id: str) -> bool:
        """Delete a term (cascades to variants and usage)."""
        self.db.execute("DELETE FROM glossary_terms WHERE id = ?", (term_id,))
        logger.info(f"Glossary term deleted: {term_id}")
        return True

    def get_all_term_ids(self, novel_id: str) -> list[str]:
        """Get all term IDs for a novel."""
        rows = self.db.fetchall(
            "SELECT id FROM glossary_terms WHERE novel_id = ?",
            (novel_id,),
        )
        return [r["id"] for r in rows]

    def search_terms(self, novel_id: str, query: str) -> list[dict]:
        """Search terms by source_term or target_term (LIKE match)."""
        pattern = f"%{query}%"
        rows = self.db.fetchall(
            "SELECT * FROM glossary_terms WHERE novel_id = ? "
            "AND (source_term LIKE ? OR target_term LIKE ?) ORDER BY usage_count DESC",
            (novel_id, pattern, pattern),
        )
        return [dict(r) for r in rows]

    # ── term_variants ───────────────────────────────────────────────────

    def add_variant(self, term_id: str, variant_text: str,
                    match_type: str = "exact", case_sensitive: bool = False) -> int:
        """Insert a term variant. Returns variant ID."""
        cur = self.db.execute(
            "INSERT INTO term_variants (term_id, variant_text, match_type, case_sensitive) VALUES (?, ?, ?, ?)",
            (term_id, variant_text, match_type, int(case_sensitive)),
        )
        return cur.lastrowid

    def get_variants(self, term_id: str) -> list[dict]:
        """Fetch all variants for a term."""
        rows = self.db.fetchall(
            "SELECT * FROM term_variants WHERE term_id = ?", (term_id,)
        )
        return [dict(r) for r in rows]

    def delete_variants(self, term_id: str) -> int:
        """Delete all variants for a term. Returns count deleted."""
        cur = self.db.execute("DELETE FROM term_variants WHERE term_id = ?", (term_id,))
        return cur.rowcount
