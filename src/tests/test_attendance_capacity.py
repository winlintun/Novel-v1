"""Unit + concurrency tests for the race-safe attendance capacity registry.

Spec: TDD.md — "If it cannot be tested, it cannot be merged."

Slow-connection tests use a real file-backed SQLite DB (not ``:memory:``) so
separate connections truly contend on the same data.
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from src.core.attendance_capacity import AttendanceRegistry


@pytest.fixture
def reg(tmp_path: Path) -> AttendanceRegistry:
    """File-backed registry so concurrent connections share one DB."""
    r = AttendanceRegistry(tmp_path / "attendance.db")
    yield r
    r.close()


def test_att_001_capacity_enforced_sequential(reg: AttendanceRegistry) -> None:
    """Register up to capacity; each success becomes visible immediately."""
    reg.set_capacity("mall", 3)
    ok_a, info_a = reg.try_register("mall", "m1")
    ok_b, info_b = reg.try_register("mall", "m2")
    ok_c, info_c = reg.try_register("mall", "m3")

    assert ok_a is True and ok_c is True
    assert info_a["attendance_id"] != info_b["attendance_id"]
    assert info_b["count"] == 2
    assert info_c["count"] == 3
    assert reg.count("mall") == 3


def test_att_002_capacity_full_rejects(reg: AttendanceRegistry) -> None:
    """Once full, further registrations fail with reason capacity_full."""
    reg.set_capacity("theater", 2)
    reg.try_register("theater", "m1")
    reg.try_register("theater", "m2")

    ok, info = reg.try_register("theater", "m3")

    assert ok is False
    assert info["reason"] == "capacity_full"
    assert info["count"] == 2
    assert info["capacity"] == 2
    assert reg.count("theater") == 2


def test_att_003_concurrent_registration_never_over_capacity(reg: AttendanceRegistry) -> None:
    """Race check: 200 threads race for 50 slots — exactly 50 win.

    Without atomic check-and-reserve (e.g. plain read-then-insert) many more
    than 50 would pass. With BEGIN IMMEDIATE the count never exceeds capacity.
    """
    capacity = 50
    n_threads = 200
    reg.set_capacity("stadium", capacity)

    barrier = threading.Barrier(n_threads)
    results: list[bool] = [False] * n_threads
    errors: list[Exception] = []

    def worker(i: int) -> None:
        try:
            barrier.wait(timeout=10)
            ok, _ = reg.try_register("stadium", f"fan-{i}")
            results[i] = ok
        except Exception as exc:  # pragma: no cover - barrier thread failure
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert not errors
    assert sum(results) == capacity
    assert reg.count("stadium") == capacity


def test_att_004_concurrent_duplicate_member_exactly_one(reg: AttendanceRegistry) -> None:
    """Two threads register the same member — exactly one succeeds via the
    (venue, member) unique constraint, never two."""
    reg.set_capacity("gala", 100)

    barrier = threading.Barrier(2)
    winner: list[bool] = []
    lock = threading.Lock()

    def worker(i: int) -> None:
        barrier.wait(timeout=10)
        ok, info = reg.try_register("gala", "single-member")
        if ok:
            with lock:
                winner.append(info["attendance_id"])

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert len(winner) == 1
    assert len(reg.member_ids("gala")) == 1


def test_att_005_release_frees_a_slot(reg: AttendanceRegistry) -> None:
    """After release a freed slot can be reused by another member."""
    reg.set_capacity("dojo", 1)
    ok_a, _ = reg.try_register("dojo", "a")
    assert ok_a is True
    ok_full, _ = reg.try_register("dojo", "b")
    assert ok_full is False

    assert reg.release("dojo", "a") is True
    assert reg.release("dojo", "a") is False  # already gone
    ok_b, _ = reg.try_register("dojo", "b")

    assert ok_b is True
    assert reg.count("dojo") == 1


def test_att_006_venue_isolation(reg: AttendanceRegistry) -> None:
    """Each venue has independent capacity and attendance counts."""
    reg.set_capacity("venue-a", 1)
    reg.set_capacity("venue-b", 5)

    ok_a, _ = reg.try_register("venue-a", "x")
    ok_b, _ = reg.try_register("venue-a", "y")  # full

    assert ok_a is True and ok_b is False
    assert reg.count("venue-a") == 1
    assert reg.count("venue-b") == 0

    for i in range(5):
        assert reg.try_register("venue-b", f"g{i}")[0] is True
    assert reg.try_register("venue-b", "g5")[0] is False
    assert reg.count("venue-b") == 5


def test_att_007_venue_not_found_rejected(reg: AttendanceRegistry) -> None:
    """Registering to an unknown venue is rejected, not silently stored."""
    ok, info = reg.try_register("ghost-town", "m1")

    assert ok is False
    assert info["reason"] == "venue_not_found"
    assert reg.count("ghost-town") == 0


def test_att_008_capacity_change_takes_effect(reg: AttendanceRegistry) -> None:
    """Raising capacity allows more; lowering rejects existing occupancy."""
    reg.set_capacity("club", 2)
    reg.try_register("club", "m1")
    reg.try_register("club", "m2")

    reg.set_capacity("club", 5)  # raise — one more accepted
    assert reg.try_register("club", "m3")[0] is True

    reg.set_capacity("club", 1)  # lower below occupancy
    assert reg.try_register("club", "m4")[0] is False
    assert reg.count("club") == 3  # existing rows kept
    assert reg.capacity("club") == 1


def test_att_009_invalid_capacity_rejected(reg: AttendanceRegistry) -> None:
    """Negative capacity is rejected at set time."""
    with pytest.raises(ValueError):
        reg.set_capacity("club", -1)
    with pytest.raises(ValueError):
        reg.set_capacity("", 5)