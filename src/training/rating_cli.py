"""
Interactive CLI for human rating of rejected translation chunks.

Usage:
    python -m src.main --rate-rejected --novel outside-of-time

Reads rejected chunks from data/training/rejected/{novel}/,
presents them interactively, and ingests accepted ones into
the dataset DB with human_score populated.
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

REJECTED_DIR = Path("data/training/rejected")
PROGRESS_FILE = Path("data/training/rating_progress.json")
DATASET_DB = Path("data/novel_v1_dataset.db")


def _load_progress(novel: str) -> Dict[str, int]:
    """Load rating progress from checkpoint file."""
    if not PROGRESS_FILE.exists():
        return {}
    try:
        data = json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
        return data.get(novel, {})
    except (json.JSONDecodeError, OSError):
        return {}


def _save_progress(novel: str, progress: Dict[str, int]) -> None:
    """Save rating progress to checkpoint file (atomic write)."""
    all_progress = {}
    if PROGRESS_FILE.exists():
        try:
            all_progress = json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            all_progress = {}
    all_progress[novel] = progress
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    # Atomic write: temp file → rename
    tmp = PROGRESS_FILE.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(all_progress, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    tmp.rename(PROGRESS_FILE)


def _load_chunks(novel: str) -> List[Dict[str, str]]:
    """Load all rejected chunks for a novel."""
    novel_dir = REJECTED_DIR / novel
    if not novel_dir.exists():
        logger.error(f"No rejected chunks found for novel '{novel}' at {novel_dir}")
        return []

    # Group files by chunk key (e.g., chunk_001_20260529_004305)
    groups: Dict[str, dict] = {}
    for f in sorted(novel_dir.iterdir()):
        if not f.is_file() or not f.name.endswith(".txt"):
            continue
        # Parse: chunk_NNN_YYYYMMDD_HHMMSS_{source,output,reason}.txt
        parts = f.name.rsplit("_", 1)
        if len(parts) != 2:
            continue
        chunk_key = parts[0]
        suffix = parts[1].replace(".txt", "")
        if chunk_key not in groups:
            groups[chunk_key] = {"key": chunk_key, "source": "", "output": "", "reason": ""}
        content = f.read_text(encoding="utf-8-sig").strip()
        if suffix == "source":
            groups[chunk_key]["source"] = content
        elif suffix == "output":
            groups[chunk_key]["output"] = content
        elif suffix == "reason":
            groups[chunk_key]["reason"] = content

    return [g for g in groups.values() if g["source"] and g["output"]]


def _ensure_human_reviewed_column(conn) -> None:
    """Add human_reviewed_at column if it doesn't exist."""
    try:
        conn.execute("ALTER TABLE translation_pairs ADD COLUMN human_reviewed_at TEXT")
    except Exception:
        pass  # Column already exists


def _ingest_rated_pair(
    source: str, translation: str, score: int,
    novel: str, reason: str = "",
) -> bool:
    """Insert or update a human-rated pair in the dataset DB.

    Returns True on success, False on failure.
    """
    try:
        from src.data.dataset_pipeline import init_db, pair_id, insert_pair

        conn = init_db(str(DATASET_DB))
        _ensure_human_reviewed_column(conn)

        validation = {
            "score": score,
            "myanmar_ratio": 1.0,
            "length_ratio": 1.0,
            "aligned": 1,
            "usable": 1 if score >= 3 else 0,
        }
        # Insert or replace (so re-rating updates the pair)
        insert_pair(
            conn, source, translation, validation,
            source_file=f"human_rating_{novel}",
            novel_slug=novel,
            chapter_num=0,
            skip_duplicates=False,
        )
        # Update human_score and timestamp
        pid = pair_id(source)
        conn.execute(
            "UPDATE translation_pairs SET human_score = ?, "
            "human_reviewed_at = ? WHERE id = ?",
            (score, datetime.now().isoformat(), pid),
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Failed to ingest rated pair: {e}")
        return False


def run_rating_cli(novel: str) -> int:
    """Interactive CLI: rate rejected chunks for a novel.

    Args:
        novel: Novel slug (e.g., "outside-of-time")

    Returns:
        0 on success, 1 on error
    """
    chunks = _load_chunks(novel)
    if not chunks:
        print(f"No rejected chunks found for '{novel}'.")
        return 0

    progress = _load_progress(novel)
    start_index = progress.get("last_index", 0)
    accepted = progress.get("accepted", 0)
    rejected = progress.get("rejected", 0)
    skipped = progress.get("skipped", 0)
    total = len(chunks)

    print(f"\n=== Human Rating: {novel} ===\n")
    print(f"Found {total} rejected chunks. Resuming from chunk {start_index + 1}.\n")

    for i in range(start_index, total):
        chunk = chunks[i]
        print(f"\n--- Chunk {i + 1}/{total} ---")
        print(f"\n[SOURCE]:\n{chunk['source'][:500]}")
        print(f"\n[TRANSLATION]:\n{chunk['output'][:500]}")
        if chunk["reason"]:
            print(f"\n[REJECTION REASON]: {chunk['reason'][:200]}")

        while True:
            try:
                choice = input(
                    "\n[1] Accept (score 4)\n"
                    "[2] Accept (score 3 — minor issues)\n"
                    "[3] Reject (score < 3 — garbage)\n"
                    "[s] Skip\n"
                    "[q] Quit (save progress)\n"
                    "Choice: "
                ).strip().lower()
            except (EOFError, KeyboardInterrupt):
                choice = "q"

            if choice == "1":
                _ingest_rated_pair(chunk["source"], chunk["output"], 4, novel, chunk["reason"])
                accepted += 1
                print("  ✓ Accepted (score 4)")
                break
            elif choice == "2":
                _ingest_rated_pair(chunk["source"], chunk["output"], 3, novel, chunk["reason"])
                accepted += 1
                print("  ✓ Accepted (score 3)")
                break
            elif choice == "3":
                rejected += 1
                print("  ✗ Rejected")
                break
            elif choice == "s":
                skipped += 1
                print("  — Skipped")
                break
            elif choice == "q":
                _save_progress(novel, {
                    "last_index": i, "accepted": accepted,
                    "rejected": rejected, "skipped": skipped,
                })
                print(f"\nProgress saved. Rated {accepted + rejected + skipped}/{total}.")
                return 0
            else:
                print("Invalid choice. Try again.")

        _save_progress(novel, {
            "last_index": i + 1, "accepted": accepted,
            "rejected": rejected, "skipped": skipped,
        })

    print(f"\n=== Rating Complete! ===")
    print(f"  Accepted: {accepted}")
    print(f"  Rejected: {rejected}")
    print(f"  Skipped:  {skipped}")
    print(f"  Total:    {total}")
    return 0
