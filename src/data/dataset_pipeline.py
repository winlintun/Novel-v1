"""
Novel-v1 Dataset Pipeline
=========================
JSONL dataset ကို clean → validate → score → SQLite + ChromaDB ထဲ ingest လုပ်သည်။

Usage:
    python dataset_pipeline.py --input novel_dataset.jsonl [--db novel_v1.db] [--chroma ./chroma_db]

Requirements:
    pip install chromadb sentence-transformers tqdm
"""

import json
import sqlite3
import re
import argparse
import hashlib
from pathlib import Path
from typing import Optional
from tqdm import tqdm

# ── Optional imports (RAG) ──────────────────────────────────────────────────
try:
    import chromadb
    from chromadb.utils import embedding_functions
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False
    print("[WARN] chromadb not installed. SQLite-only mode.")

try:
    from sentence_transformers import SentenceTransformer
    ST_AVAILABLE = True
except ImportError:
    ST_AVAILABLE = False


# ═══════════════════════════════════════════════════════════════════════════
# STEP 1 — LOAD JSONL
# ═══════════════════════════════════════════════════════════════════════════

def load_jsonl(path: str) -> list[dict]:
    """Load JSONL file — skip malformed lines with a warning."""
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"[WARN] Line {i} skipped (JSON error): {e}")
    return records


# ═══════════════════════════════════════════════════════════════════════════
# STEP 2 — EXTRACT EN / MY TEXT FROM CHAT FORMAT
# ═══════════════════════════════════════════════════════════════════════════

def extract_pair(record: dict) -> Optional[tuple[str, str]]:
    """
    Extract (english_source, myanmar_translation) from JSONL records.
    Supports two formats:
      1. OpenAI-chat: {"messages": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}
      2. Flat src/tgt: {"src": "...", "tgt": "..."}
    Returns None if structure is wrong.
    """
    # ── Format 1: OpenAI-chat messages array ──
    messages = record.get("messages", [])
    if messages:
        user_text = None
        assistant_text = None

        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "").strip()

            if role == "user":
                # Remove the "Translate to Myanmar:\n" prefix
                cleaned = re.sub(r"^Translate to Myanmar:\s*", "", content, flags=re.IGNORECASE).strip()
                # Remove chapter header metadata lines (--- novel: ... ---)
                cleaned = re.sub(r"^---.*?---\s*", "", cleaned, flags=re.DOTALL).strip()
                # Remove markdown headings that are just chapter numbers
                cleaned = re.sub(r"^#+\s*Chapter\s+\d+.*$", "", cleaned, flags=re.MULTILINE).strip()
                if cleaned:
                    user_text = cleaned

            elif role == "assistant":
                assistant_text = content

        if user_text and assistant_text:
            return (user_text, assistant_text)
        return None

    # ── Format 2: Flat src/tgt keys ──
    src = record.get("src", "").strip()
    tgt = record.get("tgt", "").strip()
    if src and tgt:
        return (src, tgt)

    return None


# ═══════════════════════════════════════════════════════════════════════════
# STEP 3 — VALIDATE & QUALITY SCORE
# ═══════════════════════════════════════════════════════════════════════════

# Myanmar Unicode range: U+1000–U+109F
MYANMAR_RE = re.compile(r"[\u1000-\u109F]")
# Latin / ASCII letters (catches English, dates, etc. leaking into MY side)
LATIN_RE   = re.compile(r"[A-Za-z]")
# Metadata patterns that indicate garbage
GARBAGE_RE = re.compile(
    r"(january|february|march|april|may|june|july|august|"
    r"september|october|november|december|\d{4}|"
    r"chapter \d|volume \d)",
    re.IGNORECASE,
)


def myanmar_ratio(text: str) -> float:
    """Fraction of characters that are Myanmar script."""
    if not text:
        return 0.0
    my_chars = len(MYANMAR_RE.findall(text))
    return my_chars / len(text)


def length_ratio(en: str, my: str) -> float:
    """
    EN→MY length ratio heuristic.
    Myanmar text is typically 0.7–2.0x the English character length.
    Returns a score 0–1 based on how close to expected range.
    """
    if not en or not my:
        return 0.0
    ratio = len(my) / len(en)
    if 0.6 <= ratio <= 2.5:
        return 1.0
    elif 0.3 <= ratio <= 4.0:
        return 0.5
    return 0.0


def auto_quality_score(en: str, my: str) -> float:
    """
    Heuristic quality score 0–5.
    Based on: Myanmar script ratio, length ratio, no garbage patterns.
    This is NOT a substitute for human review — use as a filter only.
    """
    score = 0.0
    
    # Myanmar script coverage (0–2 points)
    my_ratio = myanmar_ratio(my)
    score += min(my_ratio * 2.5, 2.0)
    
    # Length ratio (0–1.5 points)
    score += length_ratio(en, my) * 1.5
    
    # No date/metadata garbage in MY (0–1 point)
    if not GARBAGE_RE.search(my):
        score += 1.0
    
    # No English words leaking into MY translation (0–0.5 points)
    latin_count = len(LATIN_RE.findall(my))
    if latin_count / max(len(my), 1) < 0.1:
        score += 0.5
    
    return round(min(score, 5.0), 2)


def is_misaligned(en: str, my: str) -> bool:
    """
    Detect obvious misalignment:
    - MY text is just a chapter header / title
    - MY text is shorter than 5 chars
    - MY text has less than 20% Myanmar characters
    """
    if len(my) < 5:
        return True
    if myanmar_ratio(my) < 0.20:
        return True
    # Chapter-header only patterns
    if re.match(r"^(#|---|\*\*|အခန်း\s*\(\d+\)|Chapter\s+\d+)", my.strip()):
        if len(my) < 30:
            return True
    return False


def validate_pair(en: str, my: str) -> dict:
    """Full validation. Returns a dict with flags and score."""
    score   = auto_quality_score(en, my)
    aligned = not is_misaligned(en, my)
    return {
        "score":          score,
        "aligned":        aligned,
        "myanmar_ratio":  round(myanmar_ratio(my), 3),
        "length_ratio":   round(len(my) / max(len(en), 1), 3),
        "usable":         aligned and score >= 2.5,
    }


# ═══════════════════════════════════════════════════════════════════════════
# STEP 4 — SQLITE STORAGE
# ═══════════════════════════════════════════════════════════════════════════

SCHEMA = """
CREATE TABLE IF NOT EXISTS translation_pairs (
    id              TEXT PRIMARY KEY,   -- SHA256 of en_text
    en_text         TEXT NOT NULL,
    my_text         TEXT NOT NULL,
    novel_slug      TEXT,
    chapter_num     INTEGER,
    auto_score      REAL,
    human_score     REAL,               -- NULL until reviewed
    myanmar_ratio   REAL,
    length_ratio    REAL,
    aligned         INTEGER,
    usable          INTEGER,
    source_file     TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS ingestion_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file TEXT,
    total       INTEGER,
    clean       INTEGER,
    rejected    INTEGER,
    duplicates  INTEGER DEFAULT 0,
    ingested_at TEXT DEFAULT (datetime('now'))
);
"""


def init_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def pair_id(en: str) -> str:
    return hashlib.sha256(en.encode()).hexdigest()[:16]


def insert_pair(conn: sqlite3.Connection, en: str, my: str,
                validation: dict, source_file: str,
                novel_slug: str = None, chapter_num: int = None,
                skip_duplicates: bool = False) -> bool:
    """Insert or update a translation pair. Returns True if new insert, False if duplicate replaced/skipped."""
    pid = pair_id(en)
    try:
        # Check if already exists
        cursor = conn.execute("SELECT 1 FROM translation_pairs WHERE id = ?", (pid,))
        is_duplicate = cursor.fetchone() is not None
        
        if is_duplicate and skip_duplicates:
            # Skip duplicates entirely - don't update
            return False
        
        if is_duplicate and not skip_duplicates:
            # Replace (default behavior)
            conn.execute("""
                INSERT OR REPLACE INTO translation_pairs
                (id, en_text, my_text, novel_slug, chapter_num,
                 auto_score, myanmar_ratio, length_ratio,
                 aligned, usable, source_file)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (
                pid, en, my, novel_slug, chapter_num,
                validation["score"],
                validation["myanmar_ratio"],
                validation["length_ratio"],
                int(validation["aligned"]),
                int(validation["usable"]),
                source_file,
            ))
        else:
            # New insert
            conn.execute("""
                INSERT INTO translation_pairs
                (id, en_text, my_text, novel_slug, chapter_num,
                 auto_score, myanmar_ratio, length_ratio,
                 aligned, usable, source_file)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (
                pid, en, my, novel_slug, chapter_num,
                validation["score"],
                validation["myanmar_ratio"],
                validation["length_ratio"],
                int(validation["aligned"]),
                int(validation["usable"]),
                source_file,
            ))
        return not is_duplicate
    except sqlite3.Error as e:
        print(f"[DB ERROR] {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════
# STEP 5 — CHROMADB RAG INGESTION  (usable pairs only)
# ═══════════════════════════════════════════════════════════════════════════

def init_chroma(chroma_path: str, enable_chroma: bool = False):
    """Initialize ChromaDB. Returns (client, collection) or (None, None) if unavailable.
    
    Note: ChromaDB requires embedding models which may need downloads.
    Use --enable-chroma flag to enable.
    """
    if not enable_chroma:
        print("[INFO] ChromaDB skipped (use --enable-chroma to enable)")
        print("[INFO] Using SQLite for RAG retrieval")
        return None, None
    
    # Try to initialize ChromaDB
    try:
        client = chromadb.PersistentClient(path=chroma_path)
        collection = client.get_or_create_collection(
            name="translations",
            metadata={"description": "EN→MM translation pairs"}
        )
        print(f"[INFO] ChromaDB initialized: {chroma_path}")
        return client, collection
    except Exception as e:
        print(f"[WARN] ChromaDB init failed: {e}")
        print("[INFO] Falling back to SQLite for RAG retrieval")
        return None, None


def ingest_to_chroma(collection, en: str, my: str,
                     validation: dict, source_file: str):
    pid = pair_id(en)
    try:
        collection.upsert(
            ids=[pid],
            documents=[en],          # embed the English source
            metadatas=[{
                "my_text":      my[:500],   # ChromaDB metadata size limit
                "auto_score":   validation["score"],
                "source_file":  source_file,
            }],
        )
    except Exception as e:
        print(f"[CHROMA ERROR] {e}")


# ═══════════════════════════════════════════════════════════════════════════
# STEP 6 — MAIN PIPELINE
# ═══════════════════════════════════════════════════════════════════════════

def infer_novel_slug(source_file: str) -> str:
    """Guess novel slug from directory name (e.g., data/datasets_novels/eternal-sacred-king/novel_dataset.jsonl → eternal-sacred-king)."""
    parent = Path(source_file).parent.name
    if parent and parent != "datasets_novels":
        return parent
    # Fallback to filename stem
    stem = Path(source_file).stem
    return stem.replace("_dataset", "").replace("dataset_", "")


def run_pipeline(
    input_file: str,
    db_path:    str = "data/novel_v1_dataset.db",
    chroma_path: str = "data/chroma_db",
    min_score:  float = 2.5,
    verbose:    bool = True,
    skip_duplicates: bool = False,
    enable_chroma: bool = False,
):
    print(f"\n{'='*60}")
    print(f"  Novel-v1 Dataset Pipeline")
    print(f"  Input:   {input_file}")
    print(f"  DB:      {db_path}")
    print(f"  Chroma: {chroma_path}")
    print(f"  Skip duplicates: {skip_duplicates}")
    print(f"  Enable ChromaDB: {enable_chroma}")
    print(f"{'='*60}\n")

    # Load
    records = load_jsonl(input_file)
    print(f"[1/5] Loaded {len(records)} records from JSONL\n")

    # DB init
    conn = init_db(db_path)
    print(f"[2/5] SQLite initialized: {db_path}")

    # Chroma init
    _, collection = init_chroma(chroma_path, enable_chroma)
    if collection:
        print(f"[3/5] ChromaDB enabled: {chroma_path}")
    else:
        print(f"[3/5] ChromaDB skipped (not installed)")

    novel_slug = infer_novel_slug(input_file)

    # Process
    stats = {"total": 0, "extracted": 0, "usable": 0, "rejected": 0, "duplicates": 0}
    rejected_samples = []

    print(f"\n[4/5] Processing pairs...\n")
    for i, record in enumerate(tqdm(records, desc="Pairs"), 1):
        stats["total"] += 1
        pair = extract_pair(record)
        if not pair:
            stats["rejected"] += 1
            continue

        en, my = pair
        stats["extracted"] += 1
        validation = validate_pair(en, my)

        is_new = insert_pair(conn, en, my, validation, input_file,
                    novel_slug=novel_slug, skip_duplicates=skip_duplicates)
        if not is_new:
            stats["duplicates"] += 1

        if validation["usable"]:
            stats["usable"] += 1
            if collection:
                ingest_to_chroma(collection, en, my, validation, input_file)
        else:
            stats["rejected"] += 1
            if verbose and len(rejected_samples) < 3:
                rejected_samples.append({
                    "en":    en[:80],
                    "my":    my[:80],
                    "score": validation["score"],
                    "reason": "misaligned" if not validation["aligned"] else "low_score",
                })

    # Log
    conn.execute("""
        INSERT INTO ingestion_log (source_file, total, clean, rejected, duplicates)
        VALUES (?,?,?,?,?)
    """, (input_file, stats["total"], stats["usable"], stats["rejected"], stats["duplicates"]))
    conn.commit()
    conn.close()

    # Report
    print(f"\n{'='*60}")
    print(f"  PIPELINE COMPLETE")
    print(f"{'='*60}")
    print(f"  Total records loaded  : {stats['total']}")
    print(f"  Pairs extracted       : {stats['extracted']}")
    print(f"  ✅ Usable (→ RAG)     : {stats['usable']}")
    print(f"  ❌ Rejected           : {stats['rejected']}")
    print(f"  🔄 Duplicates updated : {stats['duplicates']}")
    print(f"  Usable rate           : {stats['usable']/max(stats['extracted'],1)*100:.1f}%")

    if rejected_samples:
        print(f"\n  Sample rejected pairs:")
        for s in rejected_samples:
            print(f"    EN: {s['en']}")
            print(f"    MY: {s['my']}")
            print(f"    Score: {s['score']} | Reason: {s['reason']}\n")

    print(f"\n  Next steps:")
    print(f"  1. Review rejected pairs manually → fix alignment")
    print(f"  2. Human-rate usable pairs (UPDATE translation_pairs SET human_score=4 WHERE id=?)")
    print(f"  3. Use only human_score >= 4 pairs for RAG retrieval")
    print(f"  4. Add more JSONL files: python dataset_pipeline.py --input novel2_dataset.jsonl")


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

def run_batch_ingest(
    datasets_dir: str = "data/datasets_novels",
    db_path: str = "data/novel_v1_dataset.db",
    chroma_path: str = "data/chroma_db",
    min_score: float = 2.5,
    verbose: bool = True,
    skip_duplicates: bool = False,
    enable_chroma: bool = False,
    skip_existing: bool = False,
):
    """
    Batch ingest all JSONL files from data/datasets_novels/novelname/*.
    
    Directory structure expected:
        data/datasets_novels/
        ├── novel-name-1/
        │   └── novel_dataset.jsonl
        ├── novel-name-2/
        │   └── novel_dataset.jsonl
        └── ...
    """
    datasets_path = Path(datasets_dir)
    if not datasets_path.exists():
        print(f"[ERROR] Datasets directory not found: {datasets_dir}")
        return

    # Find all JSONL files
    jsonl_files = list(datasets_path.rglob("*.jsonl"))
    if not jsonl_files:
        print(f"[WARN] No JSONL files found in {datasets_dir}")
        return

    print(f"\n{'='*60}")
    print(f"  Batch Ingestion — {len(jsonl_files)} files found")
    print(f"{'='*60}\n")

    total_stats = {"total": 0, "extracted": 0, "usable": 0, "rejected": 0, "duplicates": 0}

    for jsonl_file in jsonl_files:
        novel_slug = jsonl_file.parent.name
        
        # Check if novel already has data in DB
        if skip_existing:
            conn_check = sqlite3.connect(db_path)
            # Check if table exists
            table_exists = conn_check.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='translation_pairs'"
            ).fetchone()
            if not table_exists:
                conn_check.close()
                # No table yet, will create on first ingest
                print(f"\n{'─'*40}")
                print(f"  Processing: {novel_slug} (DB empty, will create)")
                print(f"{'─'*40}")
            else:
                cursor = conn_check.execute(
                    "SELECT COUNT(*) FROM translation_pairs WHERE novel_slug = ?",
                    (novel_slug,)
                )
                existing_count = cursor.fetchone()[0]
                conn_check.close()
                
                if existing_count > 0:
                    print(f"\n{'─'*40}")
                    print(f"  ⏭ Skipping: {novel_slug} (already has {existing_count} pairs in DB)")
                    print(f"{'─'*40}")
                    continue
                print(f"\n{'─'*40}")
                print(f"  Processing: {novel_slug}")
                print(f"{'─'*40}")
        print(f"  Processing: {novel_slug}")
        print(f"  File: {jsonl_file}")
        print(f"  Skip duplicates: {skip_duplicates}")
        print(f"  Enable ChromaDB: {enable_chroma}")
        print(f"{'─'*40}")

        try:
            # Run pipeline for this file
            run_pipeline(
                input_file=str(jsonl_file),
                db_path=db_path,
                chroma_path=chroma_path,
                min_score=min_score,
                verbose=verbose,
                skip_duplicates=skip_duplicates,
                enable_chroma=enable_chroma,
            )

            # Accumulate stats (approximate — from ingestion_log)
            conn = sqlite3.connect(db_path)
            cursor = conn.execute("""
                SELECT total, clean, rejected, duplicates 
                FROM ingestion_log 
                WHERE source_file = ? 
                ORDER BY ingested_at DESC LIMIT 1
            """, (str(jsonl_file),))
            row = cursor.fetchone()
            if row:
                total_stats["total"] += row[0]
                total_stats["usable"] += row[1]
                total_stats["rejected"] += row[2]
                total_stats["duplicates"] += row[3]
                total_stats["extracted"] += row[1] + row[2]
            conn.close()

        except Exception as e:
            print(f"[ERROR] Failed to process {jsonl_file}: {e}")

    # Summary
    print(f"\n{'='*60}")
    print(f"  BATCH INGESTION COMPLETE")
    print(f"{'='*60}")
    print(f"  Files processed       : {len(jsonl_files)}")
    print(f"  Total records         : {total_stats['total']}")
    print(f"  Usable pairs          : {total_stats['usable']}")
    print(f"  Rejected              : {total_stats['rejected']}")
    print(f"  Duplicates updated    : {total_stats['duplicates']}")
    print(f"  Usable rate           : {total_stats['usable']/max(total_stats['extracted'],1)*100:.1f}%")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Novel-v1 Dataset Pipeline")
    parser.add_argument("--input",    required=False, help="Path to JSONL file (single file mode)")
    parser.add_argument("--batch",    action="store_true", help="Batch mode: ingest all files from data/datasets_novels/")
    parser.add_argument("--datasets-dir", default="data/datasets_novels", help="Datasets directory (batch mode)")
    parser.add_argument("--db",       default="data/novel_v1_dataset.db", help="SQLite DB path")
    parser.add_argument("--chroma",   default="data/chroma_db", help="ChromaDB directory")
    parser.add_argument("--min-score",type=float, default=2.5, help="Min auto score to accept")
    parser.add_argument("--skip",     action="store_true", help="Skip novels that already have data in DB")
    parser.add_argument("--skip-duplicates", action="store_true", help="Skip duplicates instead of replacing")
    parser.add_argument("--enable-chroma", action="store_true", help="Enable ChromaDB for semantic RAG (requires sentence-transformers)")
    parser.add_argument("--quiet",    action="store_true", help="Less verbose output")
    args = parser.parse_args()

    if args.batch:
        run_batch_ingest(
            datasets_dir=args.datasets_dir,
            db_path=args.db,
            chroma_path=args.chroma,
            min_score=args.min_score,
            verbose=not args.quiet,
            skip_existing=args.skip,
            skip_duplicates=args.skip_duplicates,
            enable_chroma=args.enable_chroma,
        )
    elif args.input:
        run_pipeline(
            input_file  = args.input,
            db_path     = args.db,
            chroma_path = args.chroma,
            min_score   = args.min_score,
            verbose     = not args.quiet,
            skip_duplicates=args.skip_duplicates,
            enable_chroma=args.enable_chroma,
        )
    else:
        parser.print_help()