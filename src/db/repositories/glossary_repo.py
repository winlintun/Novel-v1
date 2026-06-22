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
                 confidence: float = 0.0, scope: str = "novel",
                 variants: Optional[list[str]] = None,
                 subtype: Optional[str] = None) -> dict:
        """Insert a new glossary term.

        Args:
            novel_id: Novel identifier (e.g., 'novel_wayfarer')
            source_term: Source text term
            target_term: Myanmar translation
            category: Term category (coarse). If a fine label is passed (e.g.
                "mountain") it is normalized to its coarse category and the fine
                label is stored as subtype automatically.
            status: pending/approved
            enforcement_level: soft/hard
            context_condition: Optional context condition
            confidence: Confidence score
            scope: 'novel' (novel-specific) or 'global' (all novels)
            variants: Optional list of alternate spellings/variants
            subtype: Fine-grained label under the coarse category (e.g.
                "mountain", "sect_master"). If None, derived from `category`.
        """
        from src.glossary_taxonomy import normalize_category

        # Resolve (category, subtype) through the taxonomy so callers can pass
        # either a coarse category, a fine subtype, or a natural-language label.
        norm_category, norm_subtype = normalize_category(category)
        if subtype:
            # An explicit subtype wins; re-anchor the coarse category to it.
            sub_cat, sub_sub = normalize_category(subtype)
            norm_subtype = sub_sub or norm_subtype
            if sub_cat != "general":
                norm_category = sub_cat
        category, subtype = norm_category, norm_subtype

        term_id = f"term_{novel_id}_{hashlib.md5(source_term.encode()).hexdigest()[:8]}"
        now = datetime.now().isoformat()
        self.db.execute(
            """INSERT INTO glossary_terms
               (id, novel_id, source_term, target_term, canonical_form, category, subtype,
                status, enforcement_level, context_condition, confidence, usage_count, scope, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)""",
            (term_id, novel_id, source_term, target_term, source_term, category, subtype,
             status, enforcement_level, context_condition, confidence, scope, now),
        )
        
        # Add variants if provided
        if variants:
            for variant in variants:
                self.add_variant(term_id, variant, match_type="exact")
        
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
        Also checks term_variants table for alternate spellings.
        """
        row = self.db.fetchone(
            "SELECT * FROM glossary_terms WHERE novel_id = ? AND source_term = ? AND scope = 'novel'",
            (novel_id, source_term),
        )
        if row:
            return dict(row)
        
        # Check variants table for alternate spellings
        variant_row = self.db.fetchone(
            """SELECT gt.* FROM term_variants tv
               JOIN glossary_terms gt ON tv.term_id = gt.id
               WHERE gt.novel_id = ? AND tv.variant_text = ? AND gt.scope = 'novel'""",
            (novel_id, source_term),
        )
        if variant_row:
            return dict(variant_row)
        
        # Fall back to global terms
        row = self.db.fetchone(
            "SELECT * FROM glossary_terms WHERE scope = 'global' AND source_term = ? AND status = 'approved'",
            (source_term,),
        )
        if row:
            return dict(row)
        
        # Check global variants
        variant_row = self.db.fetchone(
            """SELECT gt.* FROM term_variants tv
               JOIN glossary_terms gt ON tv.term_id = gt.id
               WHERE gt.scope = 'global' AND tv.variant_text = ? AND gt.status = 'approved'""",
            (source_term,),
        )
        return dict(variant_row) if variant_row else None

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
        
        Global terms first (up to half), then novel-specific terms.
        Deduplicates: novel-specific terms matching a global source_term are skipped.
        """
        global_limit = min(10, limit // 2)
        novel_limit = limit - global_limit
        
        global_rows = self.db.fetchall(
            "SELECT * FROM glossary_terms WHERE scope = 'global' AND status = 'approved' "
            "ORDER BY usage_count DESC, confidence DESC LIMIT ?",
            (global_limit,),
        )
        
        # Get novel-specific terms, excluding any already covered by global
        global_sources = set(r["source_term"] for r in global_rows)
        if global_sources:
            placeholders = ",".join("?" for _ in global_sources)
            params = [novel_id] + list(global_sources) + [novel_limit]
            novel_rows = self.db.fetchall(
                "SELECT * FROM glossary_terms WHERE novel_id = ? AND status = 'approved' "
                "AND source_term NOT IN ({}) "
                "ORDER BY usage_count DESC, confidence DESC LIMIT ?".format(placeholders),
                params,
            )
        else:
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

    def get_variant_map(self, novel_id: str) -> list[dict]:
        """All (variant_text → canonical target) pairs for a novel's approved terms.

        Used by the deterministic glossary enforcer to normalise known misspellings
        of a term (e.g. a model rendering Bai Xiaochun as ပိုင်ရှောင်ချီ instead of
        the canonical ပိုင်ရှောင်ချန်း) in the final output.
        """
        rows = self.db.fetchall(
            """SELECT tv.variant_text, gt.target_term, gt.source_term, gt.category
               FROM term_variants tv
               JOIN glossary_terms gt ON tv.term_id = gt.id
               WHERE (gt.novel_id = ? OR gt.scope = 'global')
                 AND gt.status = 'approved'""",
            (novel_id,),
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

    # ── term_relationships ──────────────────────────────────────────────

    def add_relationship(self, novel_id: str, src_term_id: str, dst_term_id: str,
                         relation_type: str, confidence: float = 1.0,
                         add_inverse: bool = False) -> Optional[int]:
        """Create a directed edge (src) --relation--> (dst) between two terms.

        Idempotent: the UNIQUE(src,dst,relation) constraint means re-inserting the
        same edge is ignored. Returns the new row id, or None if it already existed
        or the relation_type is unknown.

        Args:
            add_inverse: also insert the inverse edge (e.g. master_of ⇄ disciple_of)
                so the graph is queryable from both ends. See RELATION_INVERSE.
        """
        from src.glossary_taxonomy import is_valid_relation, RELATION_INVERSE

        if not is_valid_relation(relation_type):
            logger.warning(f"Unknown relation_type '{relation_type}' — skipped")
            return None

        cur = self.db.execute(
            """INSERT OR IGNORE INTO term_relationships
               (novel_id, src_term_id, dst_term_id, relation_type, confidence)
               VALUES (?, ?, ?, ?, ?)""",
            (novel_id, src_term_id, dst_term_id, relation_type, confidence),
        )
        new_id = cur.lastrowid if cur.rowcount > 0 else None

        if add_inverse and relation_type in RELATION_INVERSE:
            inv = RELATION_INVERSE[relation_type]
            self.db.execute(
                """INSERT OR IGNORE INTO term_relationships
                   (novel_id, src_term_id, dst_term_id, relation_type, confidence)
                   VALUES (?, ?, ?, ?, ?)""",
                (novel_id, dst_term_id, src_term_id, inv, confidence),
            )

        logger.debug(f"Relationship: {src_term_id} --{relation_type}--> {dst_term_id}")
        return new_id

    def get_relationships(self, term_id: str, direction: str = "out") -> list[dict]:
        """Fetch relationship edges for a term.

        Args:
            direction: 'out' (term is src), 'in' (term is dst), or 'both'.
        """
        if direction == "out":
            rows = self.db.fetchall(
                "SELECT * FROM term_relationships WHERE src_term_id = ?", (term_id,)
            )
        elif direction == "in":
            rows = self.db.fetchall(
                "SELECT * FROM term_relationships WHERE dst_term_id = ?", (term_id,)
            )
        else:
            rows = self.db.fetchall(
                "SELECT * FROM term_relationships WHERE src_term_id = ? OR dst_term_id = ?",
                (term_id, term_id),
            )
        return [dict(r) for r in rows]

    def get_related_terms(self, term_id: str, relation_type: Optional[str] = None) -> list[dict]:
        """Fetch the full glossary rows of terms directly related to `term_id`.

        Returns each neighbour term joined with the edge's relation_type and
        direction, so callers can render e.g. "Greenwood Village (located_in) →
        Yan State" for relationship-aware glossary injection.
        """
        sql = """
            SELECT gt.*, r.relation_type AS relation_type, 'out' AS direction
              FROM term_relationships r
              JOIN glossary_terms gt ON gt.id = r.dst_term_id
             WHERE r.src_term_id = ?
            UNION ALL
            SELECT gt.*, r.relation_type AS relation_type, 'in' AS direction
              FROM term_relationships r
              JOIN glossary_terms gt ON gt.id = r.src_term_id
             WHERE r.dst_term_id = ?
        """
        params: list = [term_id, term_id]
        if relation_type:
            sql = f"SELECT * FROM ({sql}) WHERE relation_type = ?"
            params.append(relation_type)
        return [dict(r) for r in self.db.fetchall(sql, tuple(params))]

    def delete_relationships(self, term_id: str) -> int:
        """Delete all edges touching a term. Returns rows removed."""
        cur = self.db.execute(
            "DELETE FROM term_relationships WHERE src_term_id = ? OR dst_term_id = ?",
            (term_id, term_id),
        )
        return cur.rowcount
