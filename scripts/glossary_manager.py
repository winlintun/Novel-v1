"""
Runtime glossary manager — reads/writes SQLite directly.

Used by the translation pipeline to:
  - Load approved terms for prompt injection
  - Add newly-discovered names during translation (as status='pending')
  - Record term usage per chapter
"""
from __future__ import annotations

import hashlib
import logging
import sys
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterator, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

import sqlite3

log = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path("data/novel_translation.db")


def _term_id(novel_id: str, source_term: str) -> str:
    """Deterministic term ID — same source always produces same ID."""
    h = hashlib.md5(source_term.lower().encode("utf-8")).hexdigest()[:8]
    return f"term_{novel_id}_{h}"


@dataclass
class Term:
    id: str
    source_term: str
    target_term: str
    category: str
    status: str
    confidence: float
    variants: List[str] = field(default_factory=list)


class GlossaryManager:
    """Runtime glossary access — DB-only, no JSON files.

    Lightweight interface for the translation pipeline:
        gm = GlossaryManager()
        glossary = gm.load_for_translation("novel_wayfarer")
    """

    def __init__(self, db_path: Path = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError(f"DB not found: {self.db_path}")

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ── Read API ──────────────────────────────────────────────────────────

    def load_for_translation(self, novel_id: str,
                              include_universal: bool = True) -> Dict[str, str]:
        """Return {source_term: target_term} for APPROVED terms only.

        Used to build the glossary section injected into LLM prompts.
        Includes global xianxia terms when include_universal=True.
        """
        with self._conn() as c:
            if include_universal:
                rows = c.execute("""
                    SELECT source_term, target_term FROM glossary_terms
                    WHERE (novel_id = ? OR novel_id = 'novel_global_xianxia')
                      AND status = 'approved'
                    ORDER BY usage_count DESC
                """, (novel_id,)).fetchall()
            else:
                rows = c.execute("""
                    SELECT source_term, target_term FROM glossary_terms
                    WHERE novel_id = ? AND status = 'approved'
                    ORDER BY usage_count DESC
                """, (novel_id,)).fetchall()
        return {r["source_term"]: r["target_term"] for r in rows}

    def load_full(self, novel_id: str,
                  status: Optional[str] = None) -> List[Term]:
        """Return full Term objects with variants attached."""
        with self._conn() as c:
            if status:
                rows = c.execute("""
                    SELECT id, source_term, target_term, category, status, confidence
                    FROM glossary_terms WHERE novel_id = ? AND status = ?
                """, (novel_id, status)).fetchall()
            else:
                rows = c.execute("""
                    SELECT id, source_term, target_term, category, status, confidence
                    FROM glossary_terms WHERE novel_id = ?
                """, (novel_id,)).fetchall()

            terms: List[Term] = []
            for r in rows:
                variants = c.execute(
                    "SELECT variant_text FROM term_variants WHERE term_id = ?",
                    (r["id"],),
                ).fetchall()
                terms.append(Term(
                    id=r["id"],
                    source_term=r["source_term"],
                    target_term=r["target_term"],
                    category=r["category"],
                    status=r["status"],
                    confidence=r["confidence"],
                    variants=[v["variant_text"] for v in variants],
                ))
        return terms

    def get_term(self, novel_id: str, source_term: str) -> Optional[Term]:
        """Lookup a single term by source_term (case-insensitive)."""
        with self._conn() as c:
            r = c.execute("""
                SELECT id, source_term, target_term, category, status, confidence
                FROM glossary_terms
                WHERE novel_id = ? AND LOWER(source_term) = LOWER(?)
            """, (novel_id, source_term)).fetchone()
            if not r:
                return None
            variants = c.execute(
                "SELECT variant_text FROM term_variants WHERE term_id = ?",
                (r["id"],),
            ).fetchall()
            return Term(
                id=r["id"],
                source_term=r["source_term"],
                target_term=r["target_term"],
                category=r["category"],
                status=r["status"],
                confidence=r["confidence"],
                variants=[v["variant_text"] for v in variants],
            )

    # ── Write API ─────────────────────────────────────────────────────────

    def add_term_pending(self, novel_id: str, source_term: str,
                         target_term: str, category: str = "general",
                         confidence: float = 0.5,
                         source: str = "runtime_translation") -> Optional[str]:
        """Add a new term with status='pending'. Idempotent (no-op if exists)."""
        term_id = _term_id(novel_id, source_term)
        with self._conn() as c:
            existing = c.execute(
                "SELECT id FROM glossary_terms WHERE id = ?", (term_id,)
            ).fetchone()
            if existing:
                return None

            now = datetime.now(timezone.utc).isoformat()
            c.execute("""
                INSERT INTO glossary_terms
                    (id, novel_id, source_term, target_term, canonical_form,
                     category, status, enforcement_level, confidence,
                     usage_count, scope, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 'pending', 'soft', ?, 0, 'novel', ?)
            """, (term_id, novel_id, source_term, target_term,
                  source_term, category, confidence, now))

            try:
                import json
                c.execute("""
                    INSERT INTO audit_log
                        (table_name, record_id, action, new_data, source)
                    VALUES ('glossary_terms', ?, 'insert',
                            json_object('source', ?, 'target', ?, 'category', ?),
                            ?)
                """, (term_id, source_term, target_term, category, source))
            except Exception:
                pass  # audit_log is best-effort

            log.info("Added pending term: %s → %s", source_term, target_term)
            return term_id

    def record_usage(self, term_id: str, chapter_id: str,
                     paragraph_idx: int, variant_used: str,
                     context: str, confidence: float = 1.0) -> None:
        """Record a usage occurrence and bump usage_count."""
        with self._conn() as c:
            c.execute("""
                INSERT INTO term_usage
                    (term_id, chapter_id, paragraph_idx, variant_used,
                     confidence, context_snippet)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (term_id, chapter_id, paragraph_idx, variant_used,
                  confidence, context[:500]))
            c.execute(
                "UPDATE glossary_terms SET usage_count = usage_count + 1 WHERE id = ?",
                (term_id,),
            )

    # ── Stats ─────────────────────────────────────────────────────────────

    def stats(self, novel_id: str) -> Dict:
        """Return status counts for a novel's glossary."""
        with self._conn() as c:
            r = c.execute("""
                SELECT
                    SUM(CASE WHEN status='approved' THEN 1 ELSE 0 END) AS approved,
                    SUM(CASE WHEN status='pending'  THEN 1 ELSE 0 END) AS pending,
                    SUM(CASE WHEN status='rejected' THEN 1 ELSE 0 END) AS rejected,
                    COUNT(*) AS total
                FROM glossary_terms WHERE novel_id = ?
            """, (novel_id,)).fetchone()
            return dict(r)


if __name__ == "__main__":
    import json
    gm = GlossaryManager()
    novel_id = sys.argv[1] if len(sys.argv) > 1 else "novel_wayfarer"
    s = gm.stats(novel_id)
    print(json.dumps(s, indent=2))
    terms = list(gm.load_for_translation(novel_id).items())[:5]
    print(f"\nFirst 5 approved terms for {novel_id}:")
    for src, tgt in terms:
        print(f"  {src} → {tgt}")
