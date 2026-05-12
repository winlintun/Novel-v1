"""
Glossary repository — CRUD for glossary_terms and term_variants tables.
"""

import logging
import hashlib
from datetime import datetime
from typing import Optional
from src.db.connection import DatabaseConnection

logger = logging.getLogger(__name__)


GLOBAL_NOVEL_ID = "novel_global_xianxia"


class GlossaryRepository:
    """Handles all database operations for glossary_terms and term_variants."""

    def __init__(self, db: DatabaseConnection):
        self.db = db

    # ── glossary_terms ──────────────────────────────────────────────────

    def add_term(self, novel_id: str, source_term: str, target_term: str,
                 category: str = "general", status: str = "pending",
                 enforcement_level: str = "soft", context_condition: Optional[str] = None,
                 confidence: float = 0.0, scope: str = "novel") -> dict:
        """Insert a new glossary term.
        
        Args:
            novel_id: Novel identifier (e.g., 'novel_wayfarer')
            source_term: Source text term
            target_term: Myanmar translation
            category: Term category
            status: pending/approved
            enforcement_level: soft/hard
            context_condition: Optional context condition
            confidence: Confidence score
            scope: 'novel' (novel-specific) or 'global' (all novels)
        """
        term_id = f"term_{novel_id}_{hashlib.md5(source_term.encode()).hexdigest()[:8]}"
        now = datetime.now().isoformat()
        self.db.execute(
            """INSERT INTO glossary_terms
               (id, novel_id, source_term, target_term, canonical_form, category,
                status, enforcement_level, context_condition, confidence, usage_count, scope, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)""",
            (term_id, novel_id, source_term, target_term, source_term, category,
             status, enforcement_level, context_condition, confidence, scope, now),
        )
        logger.debug(f"Glossary term added: {source_term} -> {target_term} (scope={scope})")
        return self.get_term(term_id)

    def add_global_term(self, source_term: str, target_term: str,
                        category: str = "general", status: str = "approved",
                        enforcement_level: str = "hard",
                        confidence: float = 0.95) -> dict:
        """Add a global xianxia term available to ALL novels.
        
        Global terms use novel_id='novel_global_xianxia' and scope='global'.
        They are automatically included in every novel's glossary prompt.
        """
        return self.add_term(
            novel_id=GLOBAL_NOVEL_ID,
            source_term=source_term,
            target_term=target_term,
            category=category,
            status=status,
            enforcement_level=enforcement_level,
            confidence=confidence,
            scope="global",
        )

    def get_term(self, term_id: str) -> Optional[dict]:
        """Fetch a term by ID."""
        row = self.db.fetchone("SELECT * FROM glossary_terms WHERE id = ?", (term_id,))
        return dict(row) if row else None

    def get_term_by_source(self, novel_id: str, source_term: str) -> Optional[dict]:
        """Fetch a term by novel_id and source_term.
        
        Checks novel-specific terms first, then falls back to global terms.
        """
        row = self.db.fetchone(
            "SELECT * FROM glossary_terms WHERE novel_id = ? AND source_term = ? AND scope = 'novel'",
            (novel_id, source_term),
        )
        if row:
            return dict(row)
        
        # Fall back to global terms
        row = self.db.fetchone(
            "SELECT * FROM glossary_terms WHERE scope = 'global' AND source_term = ? AND status = 'approved'",
            (source_term,),
        )
        return dict(row) if row else None

    def get_terms_by_novel(self, novel_id: str, status: Optional[str] = None,
                           limit: int = 100, include_global: bool = True) -> list[dict]:
        """Fetch terms for a novel, optionally filtered by status.
        
        Includes global xianxia terms automatically unless include_global=False.
        """
        if include_global:
            if status:
                rows = self.db.fetchall(
                    """SELECT * FROM glossary_terms
                       WHERE (novel_id = ? OR scope = 'global') AND status = ?
                       ORDER BY scope ASC, usage_count DESC LIMIT ?""",
                    (novel_id, status, limit),
                )
            else:
                rows = self.db.fetchall(
                    """SELECT * FROM glossary_terms
                       WHERE novel_id = ? OR scope = 'global'
                       ORDER BY scope ASC, usage_count DESC LIMIT ?""",
                    (novel_id, limit),
                )
        else:
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

    def get_global_terms(self, status: Optional[str] = None, limit: int = 200) -> list[dict]:
        """Get all global xianxia terms."""
        if status:
            rows = self.db.fetchall(
                "SELECT * FROM glossary_terms WHERE scope = 'global' AND status = ? ORDER BY source_term",
                (status,),
            )
        else:
            rows = self.db.fetchall(
                "SELECT * FROM glossary_terms WHERE scope = 'global' ORDER BY source_term LIMIT ?",
                (limit,),
            )
        return [dict(r) for r in rows]

    def get_terms_for_prompt(self, novel_id: str, limit: int = 20) -> list[dict]:
        """Get terms sorted by usage recency (usage_count) for prompt injection.
        
        Includes global terms first (always), then novel-specific terms.
        Global terms take ~5 slots, remaining go to novel-specific.
        """
        global_limit = min(5, limit // 4)
        novel_limit = limit - global_limit
        
        global_rows = self.db.fetchall(
            "SELECT * FROM glossary_terms WHERE scope = 'global' AND status = 'approved' "
            "ORDER BY usage_count DESC, confidence DESC LIMIT ?",
            (global_limit,),
        )
        
        novel_rows = self.db.fetchall(
            "SELECT * FROM glossary_terms WHERE novel_id = ? AND status = 'approved' "
            "ORDER BY usage_count DESC, confidence DESC LIMIT ?",
            (novel_id, novel_limit),
        )
        
        return [dict(r) for r in global_rows] + [dict(r) for r in novel_rows]

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
        """Get all term IDs for a novel (including global)."""
        rows = self.db.fetchall(
            "SELECT id FROM glossary_terms WHERE novel_id = ? OR scope = 'global'",
            (novel_id,),
        )
        return [r["id"] for r in rows]

    def search_terms(self, novel_id: str, query: str) -> list[dict]:
        """Search terms by source_term or target_term (LIKE match).
        
        Includes global terms in search results.
        """
        pattern = f"%{query}%"
        rows = self.db.fetchall(
            "SELECT * FROM glossary_terms WHERE (novel_id = ? OR scope = 'global') "
            "AND (source_term LIKE ? OR target_term LIKE ?) ORDER BY scope ASC, usage_count DESC",
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

    # ── term_usage ──────────────────────────────────────────────────────

    def log_term_usage(self, term_id: str, chapter_id: str,
                       paragraph_idx: int = 0, variant_used: Optional[str] = None,
                       confidence: float = 1.0, context_snippet: Optional[str] = None) -> int:
        """Log a glossary term usage in a specific chapter/paragraph."""
        cur = self.db.execute(
            """INSERT INTO term_usage
               (term_id, chapter_id, paragraph_idx, variant_used, confidence, context_snippet)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (term_id, chapter_id, paragraph_idx, variant_used, confidence, context_snippet),
        )
        return cur.lastrowid

    def get_term_usage(self, term_id: str) -> list[dict]:
        """Get all usage records for a term."""
        rows = self.db.fetchall(
            "SELECT * FROM term_usage WHERE term_id = ? ORDER BY chapter_id, paragraph_idx",
            (term_id,),
        )
        return [dict(r) for r in rows]

    def get_chapter_terms(self, chapter_id: str) -> list[dict]:
        """Get all terms used in a specific chapter."""
        rows = self.db.fetchall(
            """SELECT tu.*, gt.source_term, gt.target_term, gt.category
               FROM term_usage tu
               JOIN glossary_terms gt ON tu.term_id = gt.id
               WHERE tu.chapter_id = ?
               ORDER BY tu.paragraph_idx""",
            (chapter_id,),
        )
        return [dict(r) for r in rows]

    def get_term_first_chapter(self, term_id: str) -> Optional[str]:
        """Get the first chapter where a term appeared."""
        row = self.db.fetchone(
            "SELECT chapter_id FROM term_usage WHERE term_id = ? ORDER BY chapter_id LIMIT 1",
            (term_id,),
        )
        return row["chapter_id"] if row else None

    def get_terms_by_chapter_count(self, novel_id: str, min_chapters: int = 1) -> list[dict]:
        """Get terms that appeared in at least N different chapters."""
        rows = self.db.fetchall(
            """SELECT gt.*, COUNT(DISTINCT tu.chapter_id) as chapter_count
               FROM glossary_terms gt
               JOIN term_usage tu ON gt.id = tu.term_id
               WHERE gt.novel_id = ?
               GROUP BY gt.id
               HAVING chapter_count >= ?
               ORDER BY chapter_count DESC""",
            (novel_id, min_chapters),
        )
        return [dict(r) for r in rows]
