"""Golden test suite tests (NEW_TODO.md §6A drift detection)."""

from __future__ import annotations

import json

from src.pipeline.golden import (
    GOLDEN_CHUNKS,
    load_baseline,
    review_golden_report,
    run_golden_suite,
    save_baseline,
    similarity,
)


class GoldenClient:
    """Fake client returning stored per-chunk translations by output marker in the prompt."""

    def __init__(self, outputs: dict):
        self.outputs = outputs
        self.calls = 0

    def generate(self, prompt, system="", temperature=None, num_predict=None, **kwargs):
        self.calls += 1
        # find which golden source chunk is embedded
        for name, src in GOLDEN_CHUNKS.items():
            if src[:80] in prompt:
                return self.outputs.get(name, src)
        return ""


def test_golden_chunks_suite_is_fixed():
    assert set(GOLDEN_CHUNKS) >= {
        "dialogue_heavy", "narration_heavy", "internal_monologue",
        "new_character", "idiomatic", "overlap_edge",
    }
    for src in GOLDEN_CHUNKS.values():
        assert isinstance(src, str) and len(src) > 20


def test_similarity_identical_text():
    assert similarity("မြန်မာ စာသား", "မြန်မာ စာသား") == 1.0


def test_similarity_different_text_low():
    assert similarity("mmmm", "nnnn") < 0.5


def test_save_and_load_baseline(tmp_path):
    p = tmp_path / "golden.json"
    save_baseline(p, "model-x", {"dialogue_heavy": "ချန်ဂီ ..."})
    data = load_baseline(p)
    assert data["model"] == "model-x"
    assert data["chunks"]["dialogue_heavy"] == "ချန်ဂီ ..."


def test_load_baseline_missing_file():
    assert load_baseline("nope.json") == {"model": "", "chunks": {}}


def test_run_golden_matches_baseline_no_drift(tmp_path):
    p = tmp_path / "golden.json"
    # baseline equals the client output -> no drift
    outputs = {name: ("ချန်ဂီ သည် " + name) for name in GOLDEN_CHUNKS}
    save_baseline(p, "mock", {name: ("ချန်ဂီ သည် " + name) for name in GOLDEN_CHUNKS})
    client = GoldenClient(outputs)
    report = run_golden_suite(client, "mock", p)
    assert report["drift_count"] == 0
    assert report["all_golden"] is True
    assert review_golden_report(report) == "GOLDEN OK"
    assert client.calls == len(GOLDEN_CHUNKS)


def test_run_golden_detects_drift(tmp_path):
    p = tmp_path / "golden.json"
    outputs = {name: ("ချန်ဂီ သည် " + name) for name in GOLDEN_CHUNKS}
    # baseline stored a DIFFERENT string for one chunk
    baseline_chunks = {name: ("ချန်ဂီ သည် " + name) for name in GOLDEN_CHUNKS}
    baseline_chunks["narration_heavy"] = "လုံးဝကို ကွဲပြားသော စာသား"
    save_baseline(p, "mock", baseline_chunks)
    client = GoldenClient(outputs)
    report = run_golden_suite(client, "mock", p)
    assert report["drift_count"] == 1
    drifted = [c for c in report["chunks"] if c.get("drifted")]
    assert drifted[0]["name"] == "narration_heavy"
    assert "ALERT" in review_golden_report(report)


def test_run_golden_no_baseline_is_golden():
    # no baseline file -> nothing to compare -> no drift
    client = GoldenClient({})
    report = run_golden_suite(client, "mock", "missing.json")
    assert report["drift_count"] == 0
    assert report["all_golden"] is True


def test_run_golden_reports_error_as_drift(tmp_path):
    class BoomClient:
        def generate(self, prompt, **kwargs):
            raise RuntimeError("server down")

    report = run_golden_suite(BoomClient(), "mock", "missing.json")
    assert report["drift_count"] == len(GOLDEN_CHUNKS)
    assert all(c.get("error") for c in report["chunks"])


def test_chunk_subset(tmp_path):
    p = tmp_path / "golden.json"
    save_baseline(p, "mock", {})
    client = GoldenClient({})
    report = run_golden_suite(client, "mock", p, chunk_subset=["dialogue_heavy"])
    assert len(report["chunks"]) == 1
    assert report["chunks"][0]["name"] == "dialogue_heavy"


def test_baseline_json_is_valid(tmp_path):
    p = tmp_path / "g.json"
    save_baseline(p, "m", {"a": "ဦး"})
    parsed = json.loads(p.read_text(encoding="utf-8"))
    assert isinstance(parsed["chunks"], dict)