"""Fleet monitoring / statistical process control (NEW_TODO.md §3A, §10).

A SQLite-backed time-series of per-chunk quality metrics shared across all
chapters of a novel.  The pipeline records a row per chunk *and* a per-chapter
rollup; ``window()`` aggregates the last ``N`` chapters and ``alerts()`` raises
an alert any time a metric crosses its threshold ("stop the line", §10).

Metrics recorded:
- average Auditor grade (weighted_total)
- verifier rejection rate
- fallback-model activation rate
- glossary auto-fix frequency
- overlap divergence rate
- model latency (per chunk, seconds)

SQLite is the stdlib choice already used elsewhere in the repo
(src/core/attendance_capacity.py) — no new dependency for scale-grade metrics.
"""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_SCHEMA = """
CREATE TABLE IF NOT EXISTS chunks (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ts            TEXT NOT NULL,
    novel         TEXT NOT NULL,
    chapter_id    TEXT NOT NULL,
    chunk_id      TEXT NOT NULL,
    quality_score REAL,
    rejected      INTEGER NOT NULL DEFAULT 0,
    fallback_used INTEGER NOT NULL DEFAULT 0,
    auto_fixed    INTEGER NOT NULL DEFAULT 0,
    overlap_diverged INTEGER NOT NULL DEFAULT 0,
    latency_ms    INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS chapters (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    ts             TEXT NOT NULL,
    novel          TEXT NOT NULL,
    chapter_id     TEXT NOT NULL,
    weighted_total REAL,
    grade          TEXT,
    chunks_total   INTEGER NOT NULL DEFAULT 0,
    chunks_failed  INTEGER NOT NULL DEFAULT 0,
    glossary_auto_fix_total INTEGER NOT NULL DEFAULT 0,
    fallback_total INTEGER NOT NULL DEFAULT 0,
    overlap_diverged_total INTEGER NOT NULL DEFAULT 0,
    latency_total_ms INTEGER NOT NULL DEFAULT 0,
    UNIQUE (novel, chapter_id)
);
CREATE INDEX IF NOT EXISTS idx_chunks_novel_chapter ON chunks (novel, chapter_id);
"""

# NEW_TODO §3A alert thresholds.
ALERT_THRESHOLDS = {
    "grade": 85.0,                 # avg grade < B(85) -> INVESTIGATE
    "reject_rate": 0.15,           # verifier rejection rate > 15% -> PAUSE
    "fallback_rate": 0.20,         # fallback > 20% -> DEGRADED
    "auto_fix_per_chunk": 3.0,     # auto-fix > 3 per chunk -> GLOSSARY GAP
    "overlap_divergence": 0.10,    # overlap divergence > 10% -> CHUNKER BUG
}


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


class FleetMonitor:
    """Append-only quality time-series for one novel."""

    def __init__(self, db_path: object = ":memory:"):
        if db_path == ":memory:":
            self._path: Optional[Path] = None
            self._memory_conn: Optional[sqlite3.Connection] = None
        else:
            p = Path(db_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            self._path = p
            self._memory_conn = None
        conn = self._connect()
        try:
            conn.executescript(_SCHEMA)
            conn.commit()
        finally:
            if self._memory_conn is None:
                self._close(conn)
            else:
                self._memory_conn = conn

    def _connect(self) -> sqlite3.Connection:
        if self._path is None:
            # :memory: must reuse ONE connection or every query sees an empty DB
            if self._memory_conn is None:
                self._memory_conn = sqlite3.connect(":memory:")
                self._memory_conn.row_factory = sqlite3.Row
            return self._memory_conn
        conn = sqlite3.connect(str(self._path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _close(self, conn: sqlite3.Connection) -> None:
        if self._path is not None:
            conn.close()

    # -- write path -------------------------------------------------------- #
    def record_chunk(
        self,
        novel: str,
        chapter_id: str,
        chunk_id: str,
        *,
        quality_score: Optional[float] = None,
        rejected: bool = False,
        fallback_used: bool = False,
        auto_fixed: int = 0,
        overlap_diverged: bool = False,
        latency_ms: int = 0,
    ) -> None:
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO chunks (ts, novel, chapter_id, chunk_id, quality_score, "
                "rejected, fallback_used, auto_fixed, overlap_diverged, latency_ms) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    _now(), novel, chapter_id, chunk_id, quality_score,
                    int(bool(rejected)), int(bool(fallback_used)), int(auto_fixed),
                    int(bool(overlap_diverged)), int(latency_ms),
                ),
            )
            conn.commit()
        finally:
            self._close(conn)

    def record_chapter(
        self,
        novel: str,
        chapter_id: str,
        *,
        weighted_total: Optional[float] = None,
        grade: str = "",
        chunks_total: int = 0,
        chunks_failed: int = 0,
        glossary_auto_fix_total: int = 0,
        fallback_total: int = 0,
        overlap_diverged_total: int = 0,
        latency_total_ms: int = 0,
    ) -> None:
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO chapters (ts, novel, chapter_id, weighted_total, grade, "
                "chunks_total, chunks_failed, glossary_auto_fix_total, fallback_total, "
                "overlap_diverged_total, latency_total_ms) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(novel, chapter_id) DO UPDATE SET "
                "weighted_total=excluded.weighted_total, grade=excluded.grade, "
                "chunks_total=excluded.chunks_total, chunks_failed=excluded.chunks_failed, "
                "glossary_auto_fix_total=excluded.glossary_auto_fix_total, "
                "fallback_total=excluded.fallback_total, "
                "overlap_diverged_total=excluded.overlap_diverged_total, "
                "latency_total_ms=excluded.latency_total_ms",
                (
                    _now(), novel, chapter_id, weighted_total, grade,
                    chunks_total, chunks_failed, glossary_auto_fix_total,
                    fallback_total, overlap_diverged_total, latency_total_ms,
                ),
            )
            conn.commit()
        finally:
            self._close(conn)

    # -- read path --------------------------------------------------------- #
    def recent_chapters(self, novel: str, n: int = 10) -> List[Dict[str, Any]]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM chapters WHERE novel=? ORDER BY id DESC LIMIT ?",
                (novel, n),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            self._close(conn)

    def window(self, novel: str, n_chapters: int = 10) -> Dict[str, Any]:
        """Aggregate the last ``n_chapters`` chapter rollups + raw chunk rows."""
        chapters = self.recent_chapters(novel, n=n_chapters)
        n = len(chapters)
        if n == 0:
            return {
                "novel": novel,
                "chapters": 0,
                "avg_grade": None,
                "reject_rate": 0.0,
                "fallback_rate": 0.0,
                "auto_fix_per_chunk": 0.0,
                "overlap_divergence": 0.0,
                "avg_latency_ms": 0.0,
                "avg_quality_score": None,
            }

        grades = [float(c["weighted_total"]) for c in chapters if c["weighted_total"] is not None]
        chunk_total = sum(int(c["chunks_total"]) for c in chapters)
        chunk_failed = sum(int(c["chunks_failed"]) for c in chapters)
        fallback_total = sum(int(c["fallback_total"]) for c in chapters)
        af_total = sum(int(c["glossary_auto_fix_total"]) for c in chapters)
        overlap_tot = sum(int(c["overlap_diverged_total"]) for c in chapters)
        latency_ms = sum(int(c["latency_total_ms"]) for c in chapters)

        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT AVG(quality_score) AS q FROM chunks WHERE novel=? "
                "AND chapter_id IN (SELECT chapter_id FROM chapters WHERE novel=? "
                "ORDER BY id DESC LIMIT ?)",
                (novel, novel, n),
            ).fetchone()
            avg_q = row["q"] if row and row["q"] is not None else None
        finally:
            self._close(conn)

        return {
            "novel": novel,
            "chapters": n,
            "avg_grade": round(sum(grades) / len(grades), 1) if grades else None,
            "reject_rate": round(chunk_failed / chunk_total, 4) if chunk_total else 0.0,
            "fallback_rate": round(fallback_total / chunk_total, 4) if chunk_total else 0.0,
            "auto_fix_per_chunk": round(af_total / chunk_total, 3) if chunk_total else 0.0,
            "overlap_divergence": round(overlap_tot / chunk_total, 4) if chunk_total else 0.0,
            "avg_latency_ms": round(latency_ms / chunk_total, 1) if chunk_total else 0.0,
            "avg_quality_score": round(float(avg_q), 1) if avg_q is not None else None,
        }

    # -- alerts ------------------------------------------------------------ #
    def alerts(
        self,
        novel: str,
        n_chapters: int = 10,
        thresholds: Optional[Dict[str, float]] = None,
    ) -> List[Dict[str, Any]]:
        """Return a list of alerts raised by the last ``n_chapters`` window."""
        th = dict(thresholds or ALERT_THRESHOLDS)
        w = self.window(novel, n_chapters=n_chapters)
        out: List[Dict[str, Any]] = []

        if w["avg_grade"] is not None and w["avg_grade"] < th["grade"]:
            out.append({
                "rule": "SPC-GRADE",
                "level": "INVESTIGATE",
                "level_code": 1,
                "metric": "avg_grade",
                "value": w["avg_grade"],
                "threshold": th["grade"],
                "message": f"Auditor avg grade {w['avg_grade']} < {th['grade']} (B)",
            })
        if w["reject_rate"] > th["reject_rate"]:
            out.append({
                "rule": "SPC-REJECT",
                "level": "PAUSE",
                "level_code": 3,
                "metric": "reject_rate",
                "value": w["reject_rate"],
                "threshold": th["reject_rate"],
                "message": f"Verifier reject rate {w['reject_rate']:.1%} > "
                           f"{th['reject_rate']:.0%} — pause pipeline",
            })
        if w["fallback_rate"] > th["fallback_rate"]:
            out.append({
                "rule": "SPC-FALLBACK",
                "level": "DEGRADED",
                "level_code": 2,
                "metric": "fallback_rate",
                "value": w["fallback_rate"],
                "threshold": th["fallback_rate"],
                "message": f"Fallback activation {w['fallback_rate']:.1%} > "
                           f"{th['fallback_rate']:.0%} — model degraded",
            })
        if w["auto_fix_per_chunk"] > th["auto_fix_per_chunk"]:
            out.append({
                "rule": "SPC-GLOSS",
                "level": "GLOSSARY_GAP",
                "level_code": 1,
                "metric": "auto_fix_per_chunk",
                "value": w["auto_fix_per_chunk"],
                "threshold": th["auto_fix_per_chunk"],
                "message": f"Glossary auto-fix {w['auto_fix_per_chunk']:.2f}/chunk > "
                           f"{th['auto_fix_per_chunk']:.0f} — glossary gap",
            })
        if w["overlap_divergence"] > th["overlap_divergence"]:
            out.append({
                "rule": "SPC-OVERLAP",
                "level": "CHUNKER_BUG",
                "level_code": 2,
                "metric": "overlap_divergence",
                "value": w["overlap_divergence"],
                "threshold": th["overlap_divergence"],
                "message": f"Overlap divergence {w['overlap_divergence']:.1%} > "
                           f"{th['overlap_divergence']:.0%} — chunker bug",
            })
        out.sort(key=lambda a: a["level_code"], reverse=True)
        return out

    def stop_the_line(self, novel: str, n_chapters: int = 10) -> bool:
        """§10 rule: any PAUSE-level alert stops the pipeline."""
        return any(a["level"] == "PAUSE" for a in self.alerts(novel, n_chapters=n_chapters))

    def report(self, novel: str, n_chapters: int = 10) -> Dict[str, Any]:
        return {
            "novel": novel,
            "window": self.window(novel, n_chapters=n_chapters),
            "alerts": self.alerts(novel, n_chapters=n_chapters),
            "stop_the_line": self.stop_the_line(novel, n_chapters=n_chapters),
        }

    def close(self) -> None:
        """No-op reserved for symmetric lifecycle with connection-backed monitors."""
