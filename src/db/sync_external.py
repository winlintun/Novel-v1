"""
Sync terms from the external Glossary System database into the local project DB.

Runs once at MemoryManager startup (when use_sql=True).
Copies novel-specific + global terms from the authoritative Glossary System DB
into the local SQLite, skipping terms that already exist (matched by source_term).

External DB path: configurable via GLOSSARY_SYSTEM_DB_PATH env var
Local DB path:    data/novel_translation.db
"""

import hashlib
import logging
import os
import sqlite3
from typing import Optional

logger = logging.getLogger(__name__)

EXTERNAL_DB_PATH = os.environ.get(
    "GLOSSARY_SYSTEM_DB_PATH",
    "/home/wangyi/Desktop/Glossary_System/db/glossary_system.db",
)
GLOBAL_NOVEL_ID = "novel_global_xianxia"

# Columns to copy from external DB (excludes extra columns local DB doesn't have)
SHARED_COLUMNS = [
    "novel_id", "source_term", "target_term", "canonical_form",
    "category", "status", "scope", "enforcement_level", "context_condition",
    "confidence", "usage_count", "created_at", "reviewed_at",
]


def make_novel_id(novel_name: str) -> str:
    """Generate a sanitized novel_id consistent across all modules."""
    safe = novel_name.replace('/', '_').replace('\\', '_').replace(' ', '_')
    return f"novel_{safe}"


def make_term_id(novel_id: str, source_term: str) -> str:
    """Generate a deterministic term ID matching GlossaryRepository convention."""
    md5_hash = hashlib.md5(source_term.encode()).hexdigest()[:8]
    return f"term_{novel_id}_{md5_hash}"


def sync_external_glossary(
    local_conn: sqlite3.Connection,
    novel_name: str,
    external_db_path: str = EXTERNAL_DB_PATH,
    status_filter: Optional[str] = "approved",
) -> dict:
    """Sync glossary terms from external DB into local DB.

    Args:
        local_conn: Active sqlite3.Connection to the local project DB.
        novel_name: Novel slug (e.g. 'we-agreed-on-experiencing-life...').
        external_db_path: Path to the external Glossary System DB.
        status_filter: If set, only sync terms with this status.
                       Default: "approved" — only sync approved terms.
                       None = sync all statuses.

    Returns:
        dict with keys: synced, skipped, global_synced, global_skipped, errors
    """
    result = {
        "synced": 0,
        "skipped": 0,
        "global_synced": 0,
        "global_skipped": 0,
        "errors": [],
    }

    # Check external DB exists
    if not os.path.exists(external_db_path):
        logger.warning(f"External glossary DB not found: {external_db_path}. Skipping sync.")
        return result

    try:
        ext_conn = sqlite3.connect(f"file:{external_db_path}?mode=ro", uri=True)
        ext_conn.row_factory = sqlite3.Row
    except Exception as e:
        logger.error(f"Failed to connect to external glossary DB: {e}")
        result["errors"].append(str(e))
        return result

    novel_id = make_novel_id(novel_name)

    # Check if sync already ran (skip if terms already exist)
    existing_novel = local_conn.execute(
        "SELECT COUNT(*) FROM glossary_terms WHERE novel_id = ?", (novel_id,)
    ).fetchone()[0]
    existing_global = local_conn.execute(
        "SELECT COUNT(*) FROM glossary_terms WHERE novel_id = ?", (GLOBAL_NOVEL_ID,)
    ).fetchone()[0]

    if existing_novel > 0 and existing_global > 0:
        logger.debug(
            f"External glossary sync skipped: {existing_novel} novel + "
            f"{existing_global} global terms already present"
        )
        ext_conn.close()
        return result

    try:
        # Ensure novel entries exist in local DB (FK requirement)
        local_conn.execute(
            "INSERT OR IGNORE INTO novels (id, name, source_language) VALUES (?, ?, 'chinese')",
            (novel_id, novel_name),
        )
        local_conn.execute(
            "INSERT OR IGNORE INTO novels (id, name, source_language) VALUES (?, ?, 'english')",
            (GLOBAL_NOVEL_ID, "Global Xianxia Terms"),
        )
        local_conn.commit()

        # Wrap entire sync in a transaction with rollback on failure
        # Use a savepoint so we can rollback without affecting outer transactions
        local_conn.execute("SAVEPOINT glossary_sync")
        try:
            local_conn.execute("PRAGMA foreign_keys=OFF")

            # ── Sync novel-specific terms ──────────────────────────────────
            result["synced"], result["skipped"] = _sync_terms_for_novel(
                ext_conn, local_conn, novel_id, status_filter,
            )

            # ── Sync global xianxia terms ─────────────────────────────────
            result["global_synced"], result["global_skipped"] = _sync_terms_for_novel(
                ext_conn, local_conn, GLOBAL_NOVEL_ID, status_filter,
            )

            local_conn.execute("PRAGMA foreign_keys=ON")
            local_conn.execute("RELEASE glossary_sync")
        except Exception as e:
            local_conn.execute("ROLLBACK TO glossary_sync")
            logger.error(f"External glossary sync rolled back: {e}")
            result["errors"].append(str(e))

    finally:
        ext_conn.close()

    total = result["synced"] + result["global_synced"]
    logger.info(
        f"External glossary sync complete: {total} terms imported "
        f"({result['synced']} novel + {result['global_synced']} global), "
        f"{result['skipped'] + result['global_skipped']} skipped (already exist)"
    )
    return result


def _sync_terms_for_novel(
    ext_conn: sqlite3.Connection,
    local_conn: sqlite3.Connection,
    novel_id: str,
    status_filter: Optional[str],
) -> tuple[int, int]:
    """Sync terms for a single novel_id. Returns (synced_count, skipped_count)."""

    # Build query
    if status_filter:
        query = "SELECT * FROM glossary_terms WHERE novel_id = ? AND status = ?"
        params: tuple = (novel_id, status_filter)
    else:
        query = "SELECT * FROM glossary_terms WHERE novel_id = ?"
        params = (novel_id,)

    ext_rows = ext_conn.execute(query, params).fetchall()
    if not ext_rows:
        logger.debug(f"No external terms found for novel_id={novel_id}")
        return 0, 0

    synced = 0
    skipped = 0

    # Get existing source_terms in local DB for this novel to avoid duplicates
    existing = set()
    cur = local_conn.execute(
        "SELECT source_term FROM glossary_terms WHERE novel_id = ?",
        (novel_id,),
    )
    for row in cur:
        existing.add(row[0])

    # Column list for INSERT (regenerate ID to match local repo convention)
    insert_cols = "id, " + ", ".join(SHARED_COLUMNS)
    placeholders = ", ".join(["?"] * (len(SHARED_COLUMNS) + 1))

    for row in ext_rows:
        source = row["source_term"]

        if source in existing:
            skipped += 1
            continue

        # Generate ID matching GlossaryRepository.add_term() convention
        term_id = make_term_id(novel_id, source)

        # Force scope='global' for global novel terms
        scope_val = 'global' if novel_id == GLOBAL_NOVEL_ID else row['scope']

        # Build values: (id, novel_id, source_term, ..., reviewed_at)
        values = (term_id,) + tuple(
            scope_val if col == 'scope' else row[col]
            for col in SHARED_COLUMNS
        )

        try:
            local_conn.execute(
                f"INSERT INTO glossary_terms ({insert_cols}) VALUES ({placeholders})",
                values,
            )
            synced += 1
            existing.add(source)
        except Exception as e:
            logger.warning(f"Failed to sync term '{source}': {e}")

    return synced, skipped
