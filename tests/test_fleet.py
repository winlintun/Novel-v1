"""Fleet monitor tests (NEW_TODO.md §3A SPC + §10 stop-the-line)."""

from __future__ import annotations

import sqlite3

from src.pipeline.fleet import FleetMonitor


def _seed_ok_chapters(mon: FleetMonitor, n: int = 3) -> None:
    for i in range(n):
        cid = f"ch{i:03d}"
        for j in range(4):
            mon.record_chunk(
                "novel-a", cid, f"{cid}_ck{j:02d}",
                quality_score=90.0, rejected=False, auto_fixed=0, latency_ms=1200,
            )
        mon.record_chapter(
            "novel-a", cid, weighted_total=88.0, grade="B+",
            chunks_total=4, chunks_failed=0,
            glossary_auto_fix_total=0, fallback_total=0,
            overlap_diverged_total=0, latency_total_ms=4800,
        )


def test_record_and_window_aggregates():
    mon = FleetMonitor(":memory:")
    _seed_ok_chapters(mon)
    w = mon.window("novel-a", n_chapters=3)
    assert w["chapters"] == 3
    assert w["avg_grade"] == 88.0
    assert w["reject_rate"] == 0.0
    assert w["fallback_rate"] == 0.0
    assert w["overlap_divergence"] == 0.0
    assert w["avg_quality_score"] == 90.0
    assert w["auto_fix_per_chunk"] == 0.0


def test_window_limits_to_n_chapters():
    mon = FleetMonitor(":memory:")
    _seed_ok_chapters(mon, n=10)
    assert mon.window("novel-a", n_chapters=3)["chapters"] == 3
    assert mon.window("novel-a", n_chapters=10)["chapters"] == 10


def test_no_data_is_neutral():
    mon = FleetMonitor(":memory:")
    w = mon.window("novel-a")
    assert w["chapters"] == 0
    assert w["avg_grade"] is None
    assert mon.stop_the_line("novel-a") is False


def test_reject_rate_raises_pause_alert():
    mon = FleetMonitor(":memory:")
    cid = "ch001"
    for j in range(4):
        rejected = j == 0
        mon.record_chunk("novel-a", cid, f"{cid}_ck{j:02d}",
                         quality_score=70.0, rejected=rejected)
    mon.record_chapter("novel-a", cid, weighted_total=70.0, grade="B",
                       chunks_total=4, chunks_failed=1)
    alerts = mon.alerts("novel-a", n_chapters=1)
    assert any(a["rule"] == "SPC-REJECT" and a["level"] == "PAUSE" for a in alerts)
    assert mon.stop_the_line("novel-a") is True


def test_glossary_auto_fix_alert():
    mon = FleetMonitor(":memory:")
    cid = "ch001"
    for j in range(4):
        mon.record_chunk("novel-a", cid, f"{cid}_ck{j:02d}", auto_fixed=5)
    mon.record_chapter("novel-a", cid, weighted_total=85.0, grade="B+",
                       chunks_total=4, chunks_failed=0, glossary_auto_fix_total=20)
    alerts = mon.alerts("novel-a", n_chapters=1)
    assert any(a["rule"] == "SPC-GLOSS" for a in alerts)


def test_overlap_divergence_alert():
    mon = FleetMonitor(":memory:")
    cid = "ch001"
    for j in range(4):
        mon.record_chunk("novel-a", cid, f"{cid}_ck{j:02d}",
                         overlap_diverged=(j == 0))
    mon.record_chapter("novel-a", cid, weighted_total=85.0, grade="B+",
                       chunks_total=4, chunks_failed=0, overlap_diverged_total=1)
    alerts = mon.alerts("novel-a", n_chapters=1)
    assert any(a["rule"] == "SPC-OVERLAP" and a["level"] == "CHUNKER_BUG" for a in alerts)


def test_low_grade_investigate_alert():
    mon = FleetMonitor(":memory:")
    _seed_ok_chapters(mon)
    # add one failing chapter to pull the average below 85
    cid = "ch999"
    mon.record_chunk("novel-a", cid, f"{cid}_ck00", quality_score=40.0)
    mon.record_chapter("novel-a", cid, weighted_total=50.0, grade="C",
                       chunks_total=1, chunks_failed=0)
    alerts = mon.alerts("novel-a", n_chapters=4)
    assert any(a["rule"] == "SPC-GRADE" and a["level"] == "INVESTIGATE" for a in alerts)


def test_fallback_rate_degraded_alert():
    mon = FleetMonitor(":memory:")
    cid = "ch001"
    for j in range(4):
        mon.record_chunk("novel-a", cid, f"{cid}_ck{j:02d}", fallback_used=(j < 2))
    mon.record_chapter("novel-a", cid, weighted_total=85.0, grade="B+",
                       chunks_total=4, chunks_failed=0, fallback_total=2)
    alerts = mon.alerts("novel-a", n_chapters=1)
    assert any(a["rule"] == "SPC-FALLBACK" and a["level"] == "DEGRADED" for a in alerts)


def test_healthy_window_no_alerts():
    mon = FleetMonitor(":memory:")
    _seed_ok_chapters(mon, n=5)
    assert mon.alerts("novel-a", n_chapters=5) == []
    assert mon.stop_the_line("novel-a") is False


def test_report_shape_and_file_backed_db(tmp_path):
    db = tmp_path / "fleet.db"
    mon = FleetMonitor(db)
    _seed_ok_chapters(mon, n=2)
    r = mon.report("novel-a", n_chapters=2)
    assert set(r) == {"novel", "window", "alerts", "stop_the_line"}
    assert db.is_file()
    # reopen reads persisted data
    mon2 = FleetMonitor(db)
    assert mon2.window("novel-a")["chapters"] == 2


def test_record_chapter_upsert_dedupes():
    mon = FleetMonitor(":memory:")
    mon.record_chapter("novel-a", "ch001", weighted_total=80.0, grade="B",
                       chunks_total=4, chunks_failed=0)
    mon.record_chapter("novel-a", "ch001", weighted_total=90.0, grade="A",
                       chunks_total=4, chunks_failed=0)
    rows = mon.recent_chapters("novel-a")
    assert len(rows) == 1
    assert rows[0]["weighted_total"] == 90.0


def test_schema_has_expected_tables(tmp_path):
    db = tmp_path / "schema.db"
    mon = FleetMonitor(db)
    mon.record_chunk("novel-a", "ch001", "ch001_ck00")
    conn = sqlite3.connect(str(db))
    rows = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    conn.close()
    assert "chunks" in rows and "chapters" in rows