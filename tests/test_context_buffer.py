"""Context buffer tests (sliding window, scene flush, speaker continuity)."""

from __future__ import annotations

import json

from src.pipeline.context_buffer import ContextBuffer
from src.pipeline.models import Chunk


def _chunk(tid: str, text: str, speakers=None) -> Chunk:
    return Chunk(id=tid, chapter_id="0001", scene_id="sc01", sequence=0, translated_text=text, speakers=speakers or [])


def test_append_and_snapshot(tmp_path):
    cb = ContextBuffer(tmp_path / "ctx.json")
    cb.start_scene("0001", "sc01", flush=True)
    cb.append_chunk(_chunk("ck00", "ပထမစာပိုဒ်။"))
    cb.append_chunk(_chunk("ck01", "ဒုတိယစာပိုဒ်။"))

    snap = cb.snapshot()
    assert len(snap["preceding_chunks"]) == 2
    assert snap["preceding_chunks"][0]["chunk_id"] == "ck00"


def test_sliding_window_folds_oldest_into_summary(tmp_path):
    cb = ContextBuffer(tmp_path / "ctx.json")
    cb.data["max_preceding_chunks"] = 2
    cb.start_scene("0001", "sc01", flush=True, summary="start")
    cb.append_chunk(_chunk("ck00", "ပထမ"))
    cb.append_chunk(_chunk("ck01", "ဒုတိယ"))
    cb.append_chunk(_chunk("ck02", "တတိယ"))
    snap = cb.snapshot()
    assert len(snap["preceding_chunks"]) == 2
    assert snap["preceding_chunks"][-1]["chunk_id"] == "ck02"
    assert "ပထမ" in snap["preceding_summary"]


def test_scene_flush_clears_chunks(tmp_path):
    cb = ContextBuffer(tmp_path / "ctx.json")
    cb.start_scene("0001", "sc01", flush=True)
    cb.append_chunk(_chunk("ck00", "ပထမ"))
    cb.start_scene("0001", "sc02", flush=True, summary="new scene")
    snap = cb.snapshot()
    assert snap["preceding_chunks"] == []
    assert "new scene" in snap["preceding_summary"]


def test_speaker_pronoun_persistence(tmp_path):
    cb = ContextBuffer(tmp_path / "ctx.json")
    cb.update_active_speakers({"Chen Ge": {"pronoun": "ငါ", "mood": "calm"}})
    cb.update_active_speakers({"Chen Ge": {"mood": "angry"}})
    snap = cb.snapshot()
    assert snap["active_speakers"]["Chen Ge"]["pronoun"] == "ငါ"
    assert snap["active_speakers"]["Chen Ge"]["mood"] == "angry"


def test_loads_from_disk(tmp_path):
    path = tmp_path / "ctx.json"
    path.write_text(
        json.dumps(
            {"chapter_id": "0001", "scene_id": "sc02", "active_speakers": {"A": {"pronoun": "ငါ"}}}
        ),
        encoding="utf-8",
    )
    cb = ContextBuffer(path)
    assert cb.get("scene_id") == "sc02"
    assert cb.snapshot()["active_speakers"]["A"]["pronoun"] == "ငါ"


def test_archive_creates_file_and_resets(tmp_path):
    cb = ContextBuffer(tmp_path / "ctx.json")
    cb.start_scene("0001", "sc01", flush=True)
    cb.append_chunk(_chunk("ck00", "ပထမ"))
    cb.archive(tmp_path / "archive", "0001")
    assert (tmp_path / "archive" / "0001.json").is_file()
    assert cb.snapshot()["preceding_chunks"] == []