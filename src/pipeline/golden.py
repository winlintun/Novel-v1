"""Golden test suite for model drift detection (NEW_TODO.md §6A/§6B).

A fixed set of small representative chunks — dialogue-heavy, narration-heavy,
internal monologue, new-character intro, idiomatic, and an overlap edge case —
is translated with the current models and compared against a stored baseline.
Any chunk whose output differs more than ``DRIFT_THRESHOLD`` from its baseline
raises an alert; the suite is meant to run weekly and before every production
batch (canary check).

Baselines live in ``config/golden_baseline.json``::

    {
      "model": "padauk-gemma:q8_0",
      "created": "2026-08-11T00:00:00",
      "chunks": {
        "dialogue_heavy": "ချန်ဂီ ...",
        "narration_heavy": "...",
        ...
      }
    }

Usage::

    from src.pipeline.golden import run_golden_suite
    report = run_golden_suite(client, model, baseline_path, two_pass=False)

Deterministic (no LLM in the scorer — only difflib character similarity), so
it can be unit-tested with the mock clients already used in the test suite.
"""
from __future__ import annotations

import difflib
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

DRIFT_THRESHOLD = 0.95     # SequenceMatcher ratio below this = >5% output change
DRIFT_FAIL_MESSAGE = "golden chunk output changed more than 5% from baseline"

GOLDEN_CHUNKS: Dict[str, str] = {
    "dialogue_heavy": (
        '"Chen Ge, are you really going in alone?" Xu Wan asked.\n'
        '"Someone has to. Stay here and keep the flashlight."'
    ),
    "narration_heavy": (
        "The corridor stretched endlessly before him, each door identical "
        "to the last. Dust drifted through the dim light like falling snow."
    ),
    "internal_monologue": (
        "So this is the room. He had pictured it a hundred times, but the "
        "reality felt heavier, darker than any imagining."
    ),
    "new_character": (
        'A thin man stepped into the hall, tilting his head. "You must be '
        'the new arranger. I am Uncle Xu. Welcome."'
    ),
    "idiomatic": (
        '"Easy for you to say. The dead are good company compared to some '
        "landlords I have met.\""
    ),
    "overlap_edge": (
        "He pressed the door open an inch. The darkness inside waited, "
        "patient and cold, and then it whispered his name."
    ),
}


def load_baseline(path: Optional[Path | str]) -> Dict[str, Any]:
    if not path:
        return {"model": "", "chunks": {}}
    p = Path(path)
    if not p.is_file():
        return {"model": "", "chunks": {}}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"model": "", "chunks": {}}
    if not isinstance(data, dict):
        return {"model": "", "chunks": {}}
    chunks = data.get("chunks")
    if not isinstance(chunks, dict):
        chunks = {}
    return {"model": str(data.get("model", "")), "chunks": chunks}


def save_baseline(path: Path | str, model: str, chunks: Dict[str, str]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "model": model,
        "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "chunks": chunks,
    }
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def similarity(a: str, b: str) -> float:
    """Character-level SequenceMatcher ratio (0..1); identical text = 1.0."""
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def run_golden_suite(
    client,
    model: str,
    baseline_path: Optional[Path | str] = None,
    *,
    two_pass: bool = False,
    threshold: float = DRIFT_THRESHOLD,
    chunk_subset: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Translate the golden chunks and compare against the baseline.

    ``client`` is any object exposing ``generate(prompt, **kwargs) -> str``
    (OllamaClient, or a mock).  Uses the MP2 draft prompt so the suite measures
    raw translation quality, not polish-model noise.

    Returns::

        {
          "model": model,
          "threshold": 0.95,
          "chunks": [{name, baseline_similarity, drifted, output}...],
          "drift_count": int,
          "all_golden": bool,
        }
    """
    from . import postprocessor, prompt_builder

    baseline = load_baseline(baseline_path)
    names = chunk_subset or list(GOLDEN_CHUNKS.keys())
    results: List[Dict[str, Any]] = []
    drift_count = 0

    for name in names:
        src = GOLDEN_CHUNKS[name]
        base = baseline["chunks"].get(name, "")
        try:
            raw = client.generate(
                prompt_builder.build_draft_prompt(__dummy_chunk(src)),
                system=prompt_builder.TRANSLATOR_SYSTEM,
                temperature=0.2,
            )
        except Exception as exc:  # noqa: BLE001 - report, never crash the suite
            results.append({
                "name": name,
                "baseline_similarity": 0.0,
                "drifted": True,
                "output": "",
                "error": str(exc),
            })
            drift_count += 1
            continue

        output = postprocessor.clean_my_text(raw)
        sim = similarity(output, base) if base else 1.0
        drifted = bool(base) and sim < threshold
        if drifted:
            drift_count += 1
        results.append({
            "name": name,
            "baseline_similarity": round(sim, 4),
            "drifted": drifted,
            "output": output,
        })

    return {
        "model": model,
        "threshold": threshold,
        "chunks": results,
        "drift_count": drift_count,
        "all_golden": drift_count == 0,
    }


def __dummy_chunk(source: str):
    """A minimal Chunk for prompt building without chunker bookkeeping."""
    from .models import Chunk

    return Chunk(
        id="golden", chapter_id="golden", scene_id="sc00", sequence=0,
        type="mixed", paragraphs=[source],
    )


def review_golden_report(report: Dict[str, Any]) -> str:
    """§6A verdict: ALERT on any drift, else 'GOLDEN OK'."""
    if report["drift_count"]:
        names = ", ".join(
            c["name"] for c in report["chunks"] if c.get("drifted")
        )
        return f"ALERT: golden drift on [{names}] — model quality changed" + \
               f" ({(1 - report['threshold']) * 100:.0f}% threshold)"
    return "GOLDEN OK"