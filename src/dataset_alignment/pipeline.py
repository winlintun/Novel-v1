"""Pipeline orchestrator — coordinates ingestion, alignment, validation, and RAG population."""

import logging
from pathlib import Path
from typing import Optional

from rich.progress import track

from src.dataset_alignment.config import get_alignment_config
from src.dataset_alignment.database import connect, init_db, insert_issue
from src.dataset_alignment.loaders import ingest_files, scan_novel_dir, read_chapter_text
from src.dataset_alignment.preprocessing import (
    clean_text, extract_title_and_body, normalize_text, segment_sentences,
)
from src.dataset_alignment.embedder import BGEEmbedder
from src.dataset_alignment.alignment import (
    align_sentences,
    check_chapter_pairing,
    get_all_aligned_pairs,
    store_alignments,
)
from src.dataset_alignment.reporter import build_report

logger = logging.getLogger(__name__)


def run_alignment_pipeline(
    novel_name: Optional[str] = None,
    skip_validators: bool = False,
    populate_rag: bool = True,
    min_similarity: float = 0.65,
) -> dict:
    """Run the full dataset alignment pipeline for one or all novels.

    1. Init DB schema
    2. Scan + ingest chapter files
    3. Pair source/target chapters
    4. Align sentences with BGE-M3 embeddings
    5. Validate quality
    6. Populate RAG database
    7. Generate report

    Args:
        novel_name: Specific novel to process, or None for all.
        skip_validators: Skip validation steps.
        populate_rag: Ingest aligned pairs into RAG database.
        min_similarity: Minimum cosine similarity for 1:1 alignment.

    Returns:
        Summary dict with pipeline results.
    """
    cfg = get_alignment_config()
    summary: dict = {
        "novel": novel_name or "all",
        "files_ingested": 0,
        "chapters_paired": 0,
        "alignments_total": 0,
        "alignments_1to1": 0,
        "issues_found": 0,
        "rag_pairs_ingested": 0,
        "errors": [],
        "report_path": None,
    }

    logger.info("=" * 60)
    logger.info("  Dataset Alignment Pipeline — START")
    logger.info("=" * 60)

    logger.info(f"Phase 1: INIT — DB: {cfg.db_path}")
    init_db()

    if novel_name:
        novels_to_process = [novel_name]
    else:
        input_dir = cfg.input_dir
        novels_to_process = sorted(
            d.name for d in input_dir.iterdir() if d.is_dir()
        )
        if not novels_to_process:
            logger.warning(f"No novel directories found in {input_dir}")
            summary["errors"].append("No novels found")
            return summary

    for novel in novels_to_process:
        novel_dir = cfg.input_dir / novel
        if not novel_dir.exists():
            logger.warning(f"Novel directory not found: {novel_dir}")
            continue

        logger.info(f"\n--- Processing novel: {novel} ---")

        logger.info(f"Phase 2: INGEST — scanning {novel_dir}")
        records = scan_novel_dir(novel_dir)
        if not records:
            logger.warning(f"  No files found for novel: {novel}")
            continue

        counts = ingest_files(records)
        summary["files_ingested"] += counts.get("inserted", 0)
        logger.info(f"  Inserted: {counts}")

        logger.info("Phase 3: PAIR — matching chapters")
        pair_results = check_chapter_pairing(novel)
        summary["chapters_paired"] += pair_results.get("paired", 0)
        logger.info(f"  Paired: {pair_results}")

        embedder = BGEEmbedder()
        with connect() as conn:
            chapters = conn.execute(
                """SELECT id, chapter_no, src_file_id, tgt_file_id
                   FROM chapters
                   WHERE novel=? AND src_file_id IS NOT NULL
                                AND tgt_file_id IS NOT NULL
                   ORDER BY chapter_no""",
                (novel,),
            ).fetchall()

        if not chapters:
            logger.warning(f"  No paired chapters found for {novel}")
            continue

        logger.info(f"Phase 4: ALIGN — sentence alignment for {len(chapters)} chapters")
        for r in track(chapters, description=f"Aligning {novel}"):
            _align_chapter(
                chapter_id=r["id"],
                src_fid=r["src_file_id"],
                tgt_fid=r["tgt_file_id"],
                chapter_no=r["chapter_no"],
                embedder=embedder,
                min_sim=min_similarity,
            )

        with connect() as conn:
            align_total = conn.execute(
                "SELECT COUNT(*) AS c FROM alignments a "
                "JOIN chapters c ON a.chapter_id = c.id WHERE c.novel=?",
                (novel,),
            ).fetchone()["c"]
            align_1to1 = conn.execute(
                "SELECT COUNT(*) AS c FROM alignments a "
                "JOIN chapters c ON a.chapter_id = c.id "
                "WHERE c.novel=? AND a.kind='1:1'",
                (novel,),
            ).fetchone()["c"]
            summary["alignments_total"] += align_total
            summary["alignments_1to1"] += align_1to1
            logger.info(f"  Alignments: {align_total} total, {align_1to1} 1:1")

        if not skip_validators:
            logger.info("Phase 5: VALIDATE — running quality checks")
            issues = _run_validators(novel)
            summary["issues_found"] += issues
            logger.info(f"  Issues found: {issues}")

        if populate_rag:
            logger.info("Phase 6: RAG — ingesting aligned pairs into RAG database")
            rag_count = _populate_rag_database(novel, min_similarity=min_similarity)
            summary["rag_pairs_ingested"] += rag_count
            logger.info(f"  RAG pairs ingested: {rag_count}")

        logger.info("Phase 7: REPORT — generating report")
        report_path = build_report(novel)
        summary["report_path"] = str(report_path)
        logger.info(f"  Report: {report_path}")

    logger.info("=" * 60)
    logger.info("  Dataset Alignment Pipeline — COMPLETE")
    logger.info("=" * 60)

    return summary


def _align_chapter(
    chapter_id: int,
    src_fid: int,
    tgt_fid: int,
    chapter_no: int,
    embedder: BGEEmbedder,
    min_sim: float,
) -> None:
    """Align sentences for a single chapter pair."""
    cfg = get_alignment_config()

    src_raw = read_chapter_text(src_fid)
    tgt_raw = read_chapter_text(tgt_fid)
    _, src_body = extract_title_and_body(src_raw)
    _, tgt_body = extract_title_and_body(tgt_raw)

    src_body = clean_text(normalize_text(src_body)).text
    tgt_body = clean_text(normalize_text(tgt_body)).text

    src_sents = segment_sentences(src_body, cfg.src_lang)
    tgt_sents = segment_sentences(tgt_body, cfg.tgt_lang)

    _upsert_sentences(chapter_id, src_fid, src_sents, cfg.src_lang)
    _upsert_sentences(chapter_id, tgt_fid, tgt_sents, cfg.tgt_lang)

    with connect() as conn:
        conn.execute(
            "UPDATE chapters SET src_char_count=?, tgt_char_count=? WHERE id=?",
            (sum(len(s) for s in src_sents),
             sum(len(s) for s in tgt_sents),
             chapter_id),
        )

    if not src_sents or not tgt_sents:
        return

    aligns = align_sentences(src_sents, tgt_sents, embedder, min_sim=min_sim)
    store_alignments(chapter_id, aligns)


def _upsert_sentences(
    chapter_id: int,
    file_id: int,
    sents: list[str],
    lang: str,
) -> None:
    """Insert sentences for a chapter if not already present."""
    with connect() as conn:
        existing = conn.execute(
            "SELECT COUNT(*) AS c FROM sentences "
            "WHERE chapter_id=? AND lang=?",
            (chapter_id, lang),
        ).fetchone()["c"]
        if existing:
            return
        for seq, s in enumerate(sents):
            conn.execute(
                """INSERT INTO sentences
                   (file_id, chapter_id, lang, seq, text, char_count)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (file_id, chapter_id, lang, seq, s, len(s)),
            )


def _run_validators(novel: str) -> int:
    """Run registered validators and return total issue count."""
    total = 0
    with connect() as conn:
        for r in conn.execute(
            "SELECT id, chapter_no, src_char_count, tgt_char_count "
            "FROM chapters WHERE novel=? AND src_char_count IS NOT NULL "
            "AND tgt_char_count IS NOT NULL",
            (novel,),
        ):
            if r["src_char_count"] == 0:
                continue
            ratio = r["tgt_char_count"] / r["src_char_count"]
            if ratio < 0.55:
                insert_issue(
                    conn,
                    chapter_id=r["id"],
                    category="content.omission_suspected",
                    severity="error",
                    message=f"Chapter {r['chapter_no']} target is {ratio:.0%} of source length",
                    evidence=str({"src": r["src_char_count"], "tgt": r["tgt_char_count"], "ratio": ratio}),
                )
                total += 1
            elif ratio > 2.5:
                insert_issue(
                    conn,
                    chapter_id=r["id"],
                    category="content.length_inflation",
                    severity="warn",
                    message=f"Chapter {r['chapter_no']} target is {ratio:.0%} of source length",
                    evidence=str({"src": r["src_char_count"], "tgt": r["tgt_char_count"], "ratio": ratio}),
                )
                total += 1
    return total


def _populate_rag_database(novel: str, min_similarity: float = 0.65) -> int:
    """Ingest aligned 1:1 pairs into the RAG database (novel_v1_dataset.db).

    Inserts into translation_pairs table used by RAGRetriever (SQLite fallback)
    AND into the ChromaDB ``alignment_pairs`` collection (semantic retrieval).
    Without the ChromaDB half, RAGRetriever silently degrades to keyword-overlap
    matching and the human few-shot examples it surfaces are usually irrelevant.
    """
    pairs = get_all_aligned_pairs(novel, min_similarity=min_similarity)
    if not pairs:
        logger.info(f"  No aligned pairs to ingest for {novel}")
        return 0

    rag_db_path = Path("data/novel_v1_dataset.db")
    rag_db_path.parent.mkdir(parents=True, exist_ok=True)

    import sqlite3
    conn = sqlite3.connect(str(rag_db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("""
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
        )
    """)
    conn.commit()

    import hashlib
    imported = 0
    usable_pairs: list[dict] = []  # collected for ChromaDB semantic ingestion
    for pair in pairs:
        en_text = pair["en_text"]
        my_text = pair["my_text"]
        score = pair["score"]

        # Reject omission / misalignment pairs so they never become few-shot
        # examples (they teach the model to drop or fabricate content).
        ok, reason = rag_pair_quality(en_text, my_text)
        if not ok:
            logger.debug(f"  Rejecting pair ({reason}): {en_text[:50]!r}")
            continue

        # `score` from alignment is a cosine SIMILARITY (0.65–1.0), but the
        # auto_score column / RAGRetriever filter use a 0–5 QUALITY scale. Storing
        # the raw similarity makes every aligned pair fall below the retriever's
        # default min_score=2.5 gate, so it never surfaces. Map onto 0–5 here:
        # a 1:1 human-aligned pair is high quality, so 0.65→~4.1, 1.0→5.0.
        quality_score = round(min(2.5 + score * 2.5, 5.0), 3)

        pair_id = hashlib.sha256(en_text.encode()).hexdigest()[:16]

        try:
            cur = conn.execute(
                """INSERT OR IGNORE INTO translation_pairs
                   (id, en_text, my_text, novel_slug, auto_score,
                    myanmar_ratio, length_ratio, aligned, usable,
                    chapter_num)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 1, 1, ?)""",
                (pair_id, en_text, my_text, novel, quality_score,
                 _myanmar_ratio(my_text),
                 len(my_text) / max(len(en_text), 1),
                 pair.get("chapter_id", 0)),
            )
            if cur.rowcount > 0:
                imported += 1
        except Exception as e:
            logger.debug(f"Skipping pair ingestion: {e}")

        usable_pairs.append({
            "id": pair_id,
            "en_text": en_text,
            "my_text": my_text,
            "score": quality_score,
            "chapter_id": pair.get("chapter_id", 0),
        })

    conn.commit()
    conn.close()

    logger.info(f"  Ingested {imported} new pairs into RAG database for {novel}")

    # Semantic half: embed + upsert into ChromaDB so RAGRetriever can do true
    # similarity search. Best-effort — a missing chromadb/sentence-transformers
    # install must never break the alignment run (Stability Rule 1: no crashes).
    chroma_count = _ingest_pairs_to_chroma(novel, usable_pairs)
    if chroma_count:
        logger.info(f"  Embedded {chroma_count} pairs into ChromaDB for {novel}")

    return imported


def _ingest_pairs_to_chroma(novel: str, pairs: list[dict]) -> int:
    """Embed and upsert usable pairs into the ChromaDB ``alignment_pairs`` collection.

    RAGRetriever queries this collection with BGE-M3 query embeddings and reads
    ``my_text``/``auto_score``/``source_file``/``novel`` from each pair's
    metadata, so we write exactly those keys. Returns the number of pairs
    upserted, or 0 if ChromaDB or the embedder is unavailable.
    """
    if not pairs:
        return 0

    try:
        import chromadb
    except ImportError:
        logger.warning(
            "  chromadb not installed — semantic RAG skipped. "
            "Install chromadb to enable similarity-based few-shot retrieval."
        )
        return 0

    try:
        embedder = BGEEmbedder()
        chroma_path = Path("data/chroma")
        chroma_path.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(chroma_path))
        collection = client.get_or_create_collection(name="alignment_pairs")

        # Batch both the embed and the upsert. A full novel yields tens of
        # thousands of sentence pairs — embedding them all at once risks OOM, and
        # ChromaDB rejects any single upsert larger than its max batch size
        # (5461 in chroma 1.x). Stay well under that.
        try:
            max_batch = min(client.get_max_batch_size(), 2000)
        except Exception:
            max_batch = 2000

        ingested = 0
        for start in range(0, len(pairs), max_batch):
            batch = pairs[start:start + max_batch]
            texts = [p["en_text"] for p in batch]
            embeddings = embedder.encode(texts)
            if embeddings is None or getattr(embeddings, "size", 0) == 0:
                logger.warning(
                    "  BGE-M3 produced no embeddings for batch at offset %d — skipping it.",
                    start,
                )
                continue
            collection.upsert(
                ids=[p["id"] for p in batch],
                embeddings=[e.tolist() for e in embeddings],
                documents=texts,
                metadatas=[{
                    "my_text": p["my_text"][:1000],
                    "auto_score": str(p["score"]),
                    "source_file": f"{novel}_chapter_{p['chapter_id']}",
                    "novel": novel,
                } for p in batch],
            )
            ingested += len(batch)
        return ingested
    except Exception as e:
        logger.warning(f"  ChromaDB ingestion failed ({e}) — semantic RAG skipped.")
        return 0


def _myanmar_ratio(text: str) -> float:
    import re
    mm = re.compile(r"[\u1000-\u109F\uAA60-\uAA7F\uA9E0-\uA9FF]")
    matches = mm.findall(text)
    return len(matches) / max(len(text), 1)


def rag_pair_quality(en_text: str, my_text: str) -> tuple[bool, str]:
    """Decide whether an EN\u2192MY pair is clean enough to use as a RAG few-shot example.

    BGE-M3 sentence alignment produces two recurring kinds of bad pairs, both of
    which actively teach the model the wrong behaviour if shown as examples:

    1. **Omission** \u2014 a long English compound sentence aligned to a single short
       Myanmar clause that only renders the first part (the rest of the EN is
       dropped). Signal: Myanmar far shorter than English (length_ratio < 0.55).
    2. **Misalignment** \u2014 the Myanmar sentence is about entirely different content
       than the English (the aligner matched the wrong neighbour). These usually
       ALSO show up as a length mismatch, and are caught by the same band.

    Returns (is_usable, reason). reason == "ok" when the pair passes.
    """
    en_text = (en_text or "").strip()
    my_text = (my_text or "").strip()
    el, ml = len(en_text), len(my_text)

    if el < 10 or ml < 12:
        return False, "too_short_abs"

    if _myanmar_ratio(my_text) < 0.50:
        return False, "low_myanmar_ratio"

    # Latin leakage on the Myanmar side \u2014 a real human translation has almost none.
    latin = sum(1 for c in my_text if c.isascii() and c.isalpha())
    if latin / ml > 0.10:
        return False, "latin_leak"

    length_ratio = ml / max(el, 1)
    # Omission: Myanmar far shorter than English. This is the dominant defect.
    if length_ratio < 0.55:
        return False, "my_too_short_omission"
    # Runaway merge: Myanmar much longer, but ONLY suspicious when the English is
    # itself long. Short EN ("Days passed.") legitimately expands a lot in Myanmar,
    # so we do not penalise high ratios on short sources.
    if el > 60 and length_ratio > 2.6:
        return False, "my_too_long_merge"

    return True, "ok"
