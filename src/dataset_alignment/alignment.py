"""Chapter & sentence alignment — DP-based sentence matching using BGE-M3 embeddings."""

import json
import logging

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from src.dataset_alignment.config import get_alignment_config
from src.dataset_alignment.database import connect
from src.dataset_alignment.embedder import BGEEmbedder

logger = logging.getLogger(__name__)


def check_chapter_pairing(novel: str) -> dict[str, int]:
    """Match source/target files into chapter pairs in the database."""
    cfg = get_alignment_config()
    results = {"paired": 0, "unpaired_src": 0, "unpaired_tgt": 0, "missing": 0}

    with connect() as conn:
        src_files = {
            r["chapter_no"]: r["id"]
            for r in conn.execute(
                "SELECT id, chapter_no FROM files WHERE novel=? AND lang=?",
                (novel, cfg.src_lang),
            ).fetchall()
        }
        tgt_files = {
            r["chapter_no"]: r["id"]
            for r in conn.execute(
                "SELECT id, chapter_no FROM files WHERE novel=? AND lang=?",
                (novel, cfg.tgt_lang),
            ).fetchall()
        }

        all_chapters = set(src_files.keys()) | set(tgt_files.keys())
        for ch in sorted(all_chapters):
            if ch is None:
                continue
            src_id = src_files.get(ch)
            tgt_id = tgt_files.get(ch)

            if src_id and tgt_id:
                existing = conn.execute(
                    "SELECT id FROM chapters WHERE novel=? AND chapter_no=?",
                    (novel, ch),
                ).fetchone()
                if existing:
                    conn.execute(
                        "UPDATE chapters SET src_file_id=?, tgt_file_id=? WHERE id=?",
                        (src_id, tgt_id, existing["id"]),
                    )
                else:
                    conn.execute(
                        """INSERT INTO chapters
                           (novel, chapter_no, src_file_id, tgt_file_id)
                           VALUES (?, ?, ?, ?)""",
                        (novel, ch, src_id, tgt_id),
                    )
                results["paired"] += 1
            elif src_id and not tgt_id:
                results["unpaired_src"] += 1
            elif tgt_id and not src_id:
                results["unpaired_tgt"] += 1
                results["missing"] += 1

    return results


def align_sentences(
    src_sents: list[str],
    tgt_sents: list[str],
    embedder: BGEEmbedder,
    min_sim: float = 0.50,
) -> list[dict]:
    """DP-based sentence alignment using cosine similarity of BGE-M3 embeddings.

    Uses a minimum-cost path through the similarity matrix to find 1:1, 1:NULL,
    and NULL:1 alignments.
    """
    if not src_sents or not tgt_sents:
        return []

    src_embs = embedder.encode(src_sents)
    tgt_embs = embedder.encode(tgt_sents)

    sim_matrix = cosine_similarity(src_embs, tgt_embs)

    m, n = len(src_sents), len(tgt_sents)
    INF = float("inf")
    dp = [[INF] * (n + 1) for _ in range(m + 1)]
    dp[0][0] = 0
    parent = {}

    for i in range(m + 1):
        for j in range(n + 1):
            if dp[i][j] == INF:
                continue
            if i < m and j < n and sim_matrix[i][j] >= min_sim:
                cost = 1 - sim_matrix[i][j]
                if dp[i + 1][j + 1] > dp[i][j] + cost:
                    dp[i + 1][j + 1] = dp[i][j] + cost
                    parent[(i + 1, j + 1)] = (i, j, "1:1", sim_matrix[i][j])
            if i < m:
                if dp[i + 1][j] > dp[i][j] + 2.0:
                    dp[i + 1][j] = dp[i][j] + 2.0
                    parent[(i + 1, j)] = (i, j, "1:NULL", None)
            if j < n:
                if dp[i][j + 1] > dp[i][j] + 2.0:
                    dp[i][j + 1] = dp[i][j] + 2.0
                    parent[(i, j + 1)] = (i, j, "NULL:1", None)

    alignments = []
    i, j = m, n
    while (i, j) in parent:
        pi, pj, kind, sim = parent[(i, j)]
        src_ids = list(range(pi, i))
        tgt_ids = list(range(pj, j))
        alignments.append({
            "src_ids": src_ids,
            "tgt_ids": tgt_ids,
            "kind": kind,
            "similarity": float(sim) if sim is not None else 0.0,
        })
        i, j = pi, pj

    alignments.reverse()
    return alignments


def store_alignments(chapter_id: int, alignments: list[dict]) -> None:
    """Store alignments to database, replacing any existing ones."""
    with connect() as conn:
        conn.execute("DELETE FROM alignments WHERE chapter_id=?", (chapter_id,))
        for a in alignments:
            conn.execute(
                """INSERT INTO alignments
                   (chapter_id, src_ids, tgt_ids, kind, similarity)
                   VALUES (?, ?, ?, ?, ?)""",
                (chapter_id, json.dumps(a["src_ids"]),
                 json.dumps(a["tgt_ids"]),
                 a["kind"], a["similarity"]),
            )


def get_all_aligned_pairs(novel: str, min_similarity: float = 0.55) -> list[dict]:
    """Get all 1:1 aligned sentence pairs for a novel with similarity above threshold.

    Returns pairs ready for RAG ingestion:
        {"en_text": "...", "my_text": "...", "score": similarity}
    """
    pairs = []
    with connect() as conn:
        rows = conn.execute(
            """SELECT a.id, a.chapter_id, a.src_ids, a.tgt_ids, a.similarity
               FROM alignments a
               JOIN chapters c ON a.chapter_id = c.id
               WHERE c.novel=? AND a.kind='1:1' AND a.similarity >= ?
               ORDER BY a.similarity DESC""",
            (novel, min_similarity),
        ).fetchall()

        for r in rows:
            try:
                src_ids = json.loads(r["src_ids"])
                tgt_ids = json.loads(r["tgt_ids"])
            except (json.JSONDecodeError, TypeError):
                continue
            if not src_ids or not tgt_ids:
                continue

            src = conn.execute(
                "SELECT text FROM sentences WHERE chapter_id=? AND seq=?",
                (r["chapter_id"], src_ids[0]),
            ).fetchone()
            tgt = conn.execute(
                "SELECT text FROM sentences WHERE chapter_id=? AND seq=?",
                (r["chapter_id"], tgt_ids[0]),
            ).fetchone()
            if src and tgt:
                pairs.append({
                    "en_text": src["text"],
                    "my_text": tgt["text"],
                    "score": r["similarity"],
                    "chapter_id": r["chapter_id"],
                })

    return pairs
