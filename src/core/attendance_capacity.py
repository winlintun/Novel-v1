"""Race-safe attendance capacity registry backed by SQLite.

Purpose
-------
Guard any venue/event/class's attendance against exceeding its configured
capacity, even when registration requests are handled concurrently (threads,
separate processes, or multiple MCP clients).

Why it cannot race
------------------
The classic "attendance capacity check" bug is a *check-then-commit* window:

    1. read  count        < capacity   (both threads see 49)
    2. write count = count + 1          (both threads commit -> 51)

That window is eliminated here in two layers:

- ``BEGIN IMMEDIATE`` acquires SQLite's reserved (write) lock *before* the
  check, so the capacity read and the insert happen as one serialized step.
  Any other writer blocks until COMMIT/ROLLBACK.
- A ``UNIQUE(venue_id, member_id)`` constraint makes double-registering the
  same member impossible, whatever the interleaving.

The registry is self-contained (stdlib ``sqlite3`` only) and can be pointed at
the same DB file from many connections for true multi-thread / multi-process
safety.

Usage
-----
    from src.core.attendance_capacity import AttendanceRegistry

    reg = AttendanceRegistry("output/attendance.db")   # or ":memory:"
    reg.set_capacity("mall", capacity=50)

    ok, info = reg.try_register("mall", "member-001")
    # ok=True  -> info = {"attendance_id": 1, "count": 1}
    # ok=False -> info = {"reason": "capacity_full" | "already_registered"
    #                      | "venue_not_found", ...}

    count = reg.count("mall")
    reg.release("mall", "member-001")
    reg.close()
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

_SCHEMA = """
CREATE TABLE IF NOT EXISTS venues (
    venue_id   TEXT PRIMARY KEY,
    capacity   INTEGER NOT NULL CHECK (capacity >= 0)
);

CREATE TABLE IF NOT EXISTS attendance (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    venue_id      TEXT NOT NULL REFERENCES venues(venue_id),
    member_id     TEXT NOT NULL,
    registered_at TEXT NOT NULL,
    UNIQUE (venue_id, member_id)
);

CREATE INDEX IF NOT EXISTS idx_attendance_venue ON attendance (venue_id);
"""

_RESULTS = ("attendance_id", "count")


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


class AttendanceRegistry:
    """Atomic capacity-guarded attendance registry for many venues."""

    def __init__(self, db_path: object = ":memory:") -> None:
        if db_path == ":memory:":
            self._path: Optional[Path] = None
        else:
            path = Path(db_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            self._path = path
        # autocommit mode: we manage BEGIN IMMEDIATE/COMMIT ourselves
        conn = self._connect()
        conn.executescript(_SCHEMA)
        conn.commit()
        conn.close()

    def _connect(self) -> sqlite3.Connection:
        if self._path is None:
            conn = sqlite3.connect(":memory:")
        else:
            conn = sqlite3.connect(str(self._path), timeout=30.0)
        conn.isolation_level = None  # manual transactions
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    # -- public API -------------------------------------------------------- #

    def set_capacity(self, venue_id: str, capacity: int) -> None:
        """Create/update a venue and its attendance capacity."""
        if not venue_id:
            raise ValueError("venue_id must be non-empty")
        if not isinstance(capacity, int) or isinstance(capacity, bool):
            raise ValueError("capacity must be an int")
        if capacity < 0:
            raise ValueError("capacity must be >= 0")
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT INTO venues (venue_id, capacity) VALUES (?, ?) "
                "ON CONFLICT(venue_id) DO UPDATE SET capacity = excluded.capacity",
                (venue_id, capacity),
            )
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    def capacity(self, venue_id: str) -> Optional[int]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT capacity FROM venues WHERE venue_id = ?", (venue_id,)
            ).fetchone()
            return None if row is None else int(row[0])
        finally:
            conn.close()

    def try_register(self, venue_id: str, member_id: str) -> Tuple[bool, Dict[str, Any]]:
        """Atomically reserve a slot for ``member_id`` in ``venue_id``.

        Returns ``(True, {"attendance_id", "count"})`` on success or
        ``(False, {"reason", ...})`` when the venue is unknown, full, or the
        member already registered.
        """
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT capacity FROM venues WHERE venue_id = ?", (venue_id,)
            ).fetchone()
            if row is None:
                conn.execute("ROLLBACK")
                return False, {"reason": "venue_not_found", "venue_id": venue_id}

            occupied = conn.execute(
                "SELECT COUNT(*) FROM attendance WHERE venue_id = ?", (venue_id,)
            ).fetchone()[0]
            if occupied >= int(row[0]):
                conn.execute("ROLLBACK")
                return False, {
                    "reason": "capacity_full",
                    "venue_id": venue_id,
                    "count": int(occupied),
                    "capacity": int(row[0]),
                }

            cursor = conn.execute(
                "INSERT INTO attendance (venue_id, member_id, registered_at) "
                "VALUES (?, ?, ?)",
                (venue_id, member_id, _now()),
            )
            conn.execute("COMMIT")
        except sqlite3.IntegrityError:
            conn.execute("ROLLBACK")
            return False, {"reason": "already_registered", "venue_id": venue_id}
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        else:
            return True, {
                "attendance_id": int(cursor.lastrowid),
                "venue_id": venue_id,
                "count": int(occupied) + 1,
            }
        finally:
            conn.close()

    def release(self, venue_id: str, member_id: str) -> bool:
        """Remove a member's registration, freeing their slot."""
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            cursor = conn.execute(
                "DELETE FROM attendance WHERE venue_id = ? AND member_id = ?",
                (venue_id, member_id),
            )
            conn.execute("COMMIT")
            return cursor.rowcount > 0
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    def count(self, venue_id: str) -> int:
        conn = self._connect()
        try:
            return int(
                conn.execute(
                    "SELECT COUNT(*) FROM attendance WHERE venue_id = ?",
                    (venue_id,),
                ).fetchone()[0]
            )
        finally:
            conn.close()

    def member_ids(self, venue_id: str) -> list[str]:
        conn = self._connect()
        try:
            return [
                str(r[0])
                for r in conn.execute(
                    "SELECT member_id FROM attendance WHERE venue_id = ?",
                    (venue_id,),
                ).fetchall()
            ]
        finally:
            conn.close()

    def close(self) -> None:
        """No-op kept for symmetric lifecycle with connection-based registries."""