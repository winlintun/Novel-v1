#!/usr/bin/env python3
"""One-time reconciliation of `novel_id` drift in `data/novel_translation.db`.

Idempotent. Safe to re-run. By default prints a dry-run report; apply changes
only with ``--apply``.

What it fixes (the 6-row drift found 2026-06):
  1. Phantom row ``novel_.versions`` — created when a tool treated the
     infrastructure folder ``data/output/.versions`` as a novel. Delete it and
     its orphaned child rows.
  2. Canonicalize every novel row's ``id`` to
     ``src.utils.novel_slug.novel_id_from_name(name)`` so MemoryManager,
     VersionManager and the web UI all agree on one key.
  3. Merge legacy/orphaned novel rows whose on-disk input folder no longer
     exists into the sibling row whose folder DOES exist. Concretely the
     ``a-will-eternal`` (legacy, rich glossary) + ``a-will-eternal1`` (on-disk
     folder, was reading an empty glossary — AGENTS.md lesson #3) pair: the
     legacy glossary is reparented to the on-disk id so the pipeline finally
     sees it.

Child rows in glossary_terms / term_relationships / chapters / term_usage /
chapter_versions / sync_jobs are reparented. ``chapters`` has a
UNIQUE(novel_id, chapter_num); reparenting deletes source rows that would
collide with an existing destination chapter (the destination copy wins).
``glossary_terms`` has no novel+term unique constraint, so no terms are lost —
the legacy terms simply become visible under the on-disk novel.

Usage:
    python scripts/reconcile_novel_ids.py            # dry-run
    python scripts/reconcile_novel_ids.py --apply    # commit changes
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.utils.novel_slug import novel_id_from_name  # noqa: E402

DB_PATH = "data/novel_translation.db"
INPUT_DIR = "data/input"

# Child tables that carry a `novel_id` foreign key.
CHILD_TABLES = [
    "glossary_terms",
    "term_relationships",
    "chapters",
    "term_usage",
    "chapter_versions",
    "sync_jobs",
]


def _on_disk_novel_ids() -> set[str]:
    ids: set[str] = set()
    root = Path(INPUT_DIR)
    if not root.is_dir():
        return ids
    for d in root.iterdir():
        if d.is_dir() and not d.name.startswith("."):
            ids.add(novel_id_from_name(d.name))
    return ids


def _is_phantom(nid: str, name: str) -> bool:
    return (name or "").startswith(".") or nid.startswith("novel_.")


def _reparent_children(conn: sqlite3.Connection, old_id: str, new_id: str) -> int:
    """Move all child rows from old_id to new_id. Returns count reparented.

    Handles tables with a UNIQUE(novel_id, ...) constraint by deleting source
    rows that would collide with an existing destination row (destination copy
    wins). glossary_terms has no such unique constraint, so terms are kept.
    """
    total = 0
    for table in CHILD_TABLES:
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
        if "novel_id" not in cols:
            continue
        # Detect UNIQUE constraints that include novel_id; if so, delete
        # conflicting source rows first (destination copy wins).
        unique_groups = _unique_groups(conn, table)
        for group in unique_groups:
            if "novel_id" in group:
                # build a collision filter on the non-novel_id columns
                others = [c for c in group if c != "novel_id"]
                if others:
                    coll = " AND ".join(
                        f"src.{c} = dst.{c}" for c in others
                    )
                    conn.execute(
                        f"DELETE FROM {table} AS src WHERE src.novel_id = ? "
                        f"AND EXISTS (SELECT 1 FROM {table} dst "
                        f"WHERE dst.novel_id = ? AND {coll})",
                        (old_id, new_id),
                    )
        cur = conn.execute(
            f"UPDATE {table} SET novel_id = ? WHERE novel_id = ?", (new_id, old_id)
        )
        if cur.rowcount > 0:
            total += cur.rowcount
    return total


def _unique_groups(conn: sqlite3.Connection, table: str) -> list[list[str]]:
    """Return lists of column names for each UNIQUE constraint on `table`."""
    groups: list[list[str]] = []
    for row in conn.execute(f"PRAGMA index_list({table})"):
        idx_name = row[1]
        origin = row[3]  # 'u' for unique, 'pk' for primary, 'c' for created
        if origin != "u":
            continue
        cols = [r[2] for r in conn.execute(f"PRAGMA index_info({idx_name})")]
        groups.append(cols)
    # Also implicit unique on (novel_id, ...) declared inline? chapters has
    # UNIQUE(novel_id, chapter_num) which creates an auto-index; covered above.
    return groups


def _delete_children(conn: sqlite3.Connection, novel_id: str) -> int:
    total = 0
    for table in CHILD_TABLES:
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
        if "novel_id" not in cols:
            continue
        cur = conn.execute(f"DELETE FROM {table} WHERE novel_id = ?", (novel_id,))
        if cur.rowcount > 0:
            total += cur.rowcount
    return total


def _plan(rows: list[tuple[str, str]], on_disk: set[str]) -> list[str]:
    plan: list[str] = []
    live = [(nid, name) for nid, name in rows if not _is_phantom(nid, name)]

    # 1. phantoms
    for nid, name in rows:
        if _is_phantom(nid, name):
            plan.append(f"DELETE phantom novel {nid!r} (name={name!r})")

    # 2. canonicalize: any row whose id != canonical id derived from its own name
    canon_to_rows: dict[str, list[tuple[str, str]]] = {}
    for nid, name in live:
        canon_to_rows.setdefault(novel_id_from_name(name), []).append((nid, name))
    for canon, members in canon_to_rows.items():
        if len(members) == 1 and members[0][0] == canon:
            continue
        survivors = [m for m in members if m[0] == canon]
        if survivors:
            target = survivors[0][0]
            for nid, _name in members:
                if nid != target:
                    plan.append(
                        f"MERGE {nid!r} -> {target!r} (same canonical id; reparent children, drop novel row)"
                    )
        else:
            first_id, first_name = members[0]
            plan.append(
                f"RENAME {first_id!r} -> {canon!r} (name={first_name!r}); reparent children"
            )

    # 3. orphan merge: live rows whose canonical id is NOT on disk merge into
    #    an on-disk sibling row (prefix-name match).
    on_disk_rows = [(nid, name) for nid, name in live if novel_id_from_name(name) in on_disk]
    for nid, name in live:
        canon = novel_id_from_name(name)
        if canon in on_disk:
            continue
        # find an on-disk survivor whose name is a prefix-extension of this
        # row's name (e.g. "a-will-eternal" -> "a-will-eternal1")
        partner = None
        for s_nid, s_name in on_disk_rows:
            base = s_name.rstrip("0123456789")
            if s_name.startswith(name) or name.startswith(base):
                partner = s_nid
                break
        if partner:
            plan.append(
                f"MERGE orphan {nid!r} (name={name!r}, no input folder) -> {partner!r} (on-disk sibling)"
            )
    return plan


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconcile novel_id drift in the glossary DB")
    parser.add_argument("--db", default=DB_PATH, help="Path to novel_translation.db")
    parser.add_argument("--apply", action="store_true", help="Commit changes (default: dry-run)")
    args = parser.parse_args()

    if not Path(args.db).exists():
        print(f"[error] DB not found: {args.db}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(args.db)
    conn.execute("PRAGMA foreign_keys = OFF")

    rows = list(conn.execute("SELECT id, name FROM novels ORDER BY id"))
    on_disk = _on_disk_novel_ids()

    print(f"Found {len(rows)} novel row(s) in {args.db}:")
    for nid, name in rows:
        canon = novel_id_from_name(name)
        flags = []
        if nid != canon:
            flags.append(f"canon={canon}")
        if canon not in on_disk and not _is_phantom(nid, name):
            flags.append("NO input folder (orphan)")
        flag = f"  [{', '.join(flags)}]" if flags else ""
        print(f"  id={nid:<40} name={name!r}{flag}")
    print(f"\nOn-disk input folders -> canonical ids: {sorted(on_disk)}\n")

    plan = _plan(rows, on_disk)
    if not plan:
        print("Nothing to reconcile — DB already canonical.")
        conn.close()
        return 0

    print("Planned changes:")
    for step in plan:
        print(f"  - {step}")

    if not args.apply:
        print("\nDRY RUN — no changes made. Re-run with --apply to commit.")
        conn.close()
        return 0

    print("\nApplying...")

    # 1. delete phantoms
    for nid, name in rows:
        if _is_phantom(nid, name):
            n = _delete_children(conn, nid)
            conn.execute("DELETE FROM novels WHERE id = ?", (nid,))
            print(f"  deleted phantom {nid!r} (+{n} child rows deleted)")

    rows = list(conn.execute("SELECT id, name FROM novels"))
    live = [(nid, name) for nid, name in rows if not _is_phantom(nid, name)]

    # 2. canonicalize
    canon_to_rows: dict[str, list[tuple[str, str]]] = {}
    for nid, name in live:
        canon_to_rows.setdefault(novel_id_from_name(name), []).append((nid, name))
    for canon, members in canon_to_rows.items():
        survivors = [m for m in members if m[0] == canon]
        survivor_id = survivors[0][0] if survivors else None
        if survivor_id is None:
            first_id, _ = members[0]
            _reparent_children(conn, first_id, canon)
            conn.execute("UPDATE novels SET id = ? WHERE id = ?", (canon, first_id))
            print(f"  renamed {first_id!r} -> {canon!r}")
            survivor_id = canon
        for nid, _name in members:
            if nid == survivor_id:
                continue
            n = _reparent_children(conn, nid, survivor_id)
            conn.execute("DELETE FROM novels WHERE id = ?", (nid,))
            print(f"  merged {nid!r} -> {survivor_id!r} (+{n} child rows reparented)")

    # 3. orphan merge
    rows = list(conn.execute("SELECT id, name FROM novels"))
    live = [(nid, name) for nid, name in rows if not _is_phantom(nid, name)]
    on_disk_rows = [(nid, name) for nid, name in live if novel_id_from_name(name) in on_disk]
    for nid, name in live:
        canon = novel_id_from_name(name)
        if canon in on_disk:
            continue
        partner = None
        for s_nid, s_name in on_disk_rows:
            base = s_name.rstrip("0123456789")
            if s_name.startswith(name) or name.startswith(base):
                partner = s_nid
                break
        if partner:
            n = _reparent_children(conn, nid, partner)
            conn.execute("DELETE FROM novels WHERE id = ?", (nid,))
            print(f"  merged orphan {nid!r} -> {partner!r} (+{n} child rows reparented)")

    conn.commit()
    conn.close()
    print("\nDone. Final novel rows:")
    conn = sqlite3.connect(args.db)
    for nid, name in conn.execute("SELECT id, name FROM novels ORDER BY id"):
        print(f"  id={nid:<40} name={name!r}")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())