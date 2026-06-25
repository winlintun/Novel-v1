"""Build a ChatML fine-tuning dataset from BGE-M3-aligned EN→MY pairs.

The alignment pipeline (``src/dataset_alignment``) already produces high-quality
1:1 sentence pairs and a quality filter (``rag_pair_quality``) that rejects
omission / misalignment. This module turns those pairs into the supervised
fine-tuning format and splits them **by chapter** so the held-out test set is
made of chapters the model never trained on — the only honest way to measure
"how close to the human translator" with chrF afterwards.

Pure data transformation (no DB / model access) so it is fully unit-testable;
the CLI driver in ``scripts/build_finetune_dataset.py`` supplies the real pairs.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Iterable, Optional

# Matches the system prompt used by the existing dataset so a continued run is
# consistent; also mirrors translator intent (preserve voice, not literal MT).
SYSTEM_PROMPT = (
    "You are an expert literary translator specializing in English to Myanmar "
    "translation. Preserve tone, atmosphere, emotions, dialogue style, and "
    "character voice naturally."
)

USER_TEMPLATE = "Translate to Myanmar:\n{en}"


def to_chatml(en_text: str, my_text: str, system: str = SYSTEM_PROMPT) -> dict:
    """Render one EN→MY pair as a ChatML training record."""
    return {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": USER_TEMPLATE.format(en=en_text.strip())},
            {"role": "assistant", "content": my_text.strip()},
        ]
    }


def _quality_ok(en: str, my: str) -> bool:
    """Apply the alignment pipeline's pair-quality filter when available.

    Falls back to a light length/Myanmar-ratio check if the import is missing,
    so the builder never hard-depends on the alignment package being importable.
    """
    try:
        from src.dataset_alignment.pipeline import rag_pair_quality
        ok, _ = rag_pair_quality(en, my)
        return ok
    except Exception:
        en, my = (en or "").strip(), (my or "").strip()
        if len(en) < 10 or len(my) < 12:
            return False
        return 0.55 <= len(my) / max(len(en), 1) <= 2.6


def build_splits(
    pairs: Iterable[dict],
    holdout_chapters: int = 20,
    val_fraction: float = 0.02,
    seed: int = 42,
    apply_quality_filter: bool = True,
) -> dict[str, list[dict]]:
    """Split aligned pairs into train/val/test ChatML records.

    Each input pair is a dict with ``en_text``, ``my_text``, ``novel`` and
    ``chapter_no``. The test set is the **last ``holdout_chapters`` chapter
    numbers of each novel** (held out as a whole so no sentence from a test
    chapter leaks into training). ``val_fraction`` of the remaining pairs is set
    aside as a validation split.

    Returns ``{'train': [...], 'val': [...], 'test': [...]}`` of ChatML dicts.
    """
    rng = random.Random(seed)

    cleaned = []
    for p in pairs:
        en = (p.get("en_text") or "").strip()
        my = (p.get("my_text") or "").strip()
        if not en or not my:
            continue
        if apply_quality_filter and not _quality_ok(en, my):
            continue
        cleaned.append(p)

    # Determine the held-out chapter set per novel (highest chapter numbers).
    chapters_by_novel: dict[str, set[int]] = {}
    for p in cleaned:
        ch = p.get("chapter_no")
        if ch is None:
            continue
        chapters_by_novel.setdefault(p.get("novel", ""), set()).add(int(ch))
    holdout: dict[str, set[int]] = {}
    for novel, chs in chapters_by_novel.items():
        ordered = sorted(chs, reverse=True)
        holdout[novel] = set(ordered[:holdout_chapters])

    train_pool: list[dict] = []
    test: list[dict] = []
    for p in cleaned:
        novel = p.get("novel", "")
        ch = p.get("chapter_no")
        rec = to_chatml(p["en_text"], p["my_text"])
        if ch is not None and int(ch) in holdout.get(novel, set()):
            test.append(rec)
        else:
            train_pool.append(rec)

    rng.shuffle(train_pool)
    n_val = int(len(train_pool) * val_fraction)
    val = train_pool[:n_val]
    train = train_pool[n_val:]

    return {"train": train, "val": val, "test": test}


def write_jsonl(records: list[dict], path: Path) -> int:
    """Write ChatML records as JSONL (UTF-8, ensure_ascii=False). Returns count."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return len(records)


def write_splits(splits: dict[str, list[dict]], out_dir: str,
                 prefix: Optional[str] = None) -> dict[str, int]:
    """Write train/val/test JSONL files to ``out_dir``. Returns counts per split."""
    out = Path(out_dir)
    stem = f"{prefix}_" if prefix else ""
    counts = {}
    for split in ("train", "val", "test"):
        counts[split] = write_jsonl(splits.get(split, []), out / f"{stem}{split}.jsonl")
    return counts
