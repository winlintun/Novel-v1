"""Reference-based translation quality evaluation against human Myanmar.

The fluency/adequacy checks elsewhere are *reference-free* — they judge an output
on its own. But you have something better: the actual human translation. This
module measures how close the model's output is to that human reference using
**chrF** (character n-gram F-score), the metric of choice for Myanmar because it
needs no word segmentation — Burmese has no reliable word boundaries, which breaks
BLEU and chrF++ (their word n-grams), while chrF works on characters directly.

chrF is reported 0–100 (higher = closer to human). It is the yardstick for the
whole "translate like the human translator" effort: measure the current gap, then
prove each change (RAG, fine-tuning, re-ranking) actually narrows it.

Usage (CLI):
    python -m src.utils.translation_eval --hyp data/output/a-will-eternal \\
        --ref data/input/a-will-eternal/mm
    python -m src.utils.translation_eval --hyp out.mm.md --ref human.md
"""

from __future__ import annotations

import re
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_HEADING_RE = re.compile(r"(?m)^\s*#.*$")
_CHAPTER_RE = re.compile(r"chapter[_\-]?(\d+)", re.IGNORECASE)


def _get_chrf(word_order: int = 0):
    """Return a sacrebleu CHRF scorer, or None if sacrebleu is unavailable.

    word_order=0 → plain chrF (character n-grams only) — correct for Myanmar.
    word_order=2 → chrF++ (adds word n-grams; only meaningful if the text is
    reliably word-tokenized, which Myanmar is not).
    """
    try:
        from sacrebleu.metrics import CHRF
        return CHRF(word_order=word_order, char_order=6, beta=2)
    except Exception as e:  # pragma: no cover - optional dep
        logger.debug("sacrebleu unavailable: %s", e)
        return None


def strip_for_eval(text: str) -> str:
    """Remove markdown headings and normalize whitespace for fair comparison."""
    text = (text or "").replace("﻿", "")
    text = _HEADING_RE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def compute_chrf(hypothesis: str, reference: str, word_order: int = 0) -> Optional[float]:
    """chrF score (0–100) of one hypothesis against one reference.

    Returns None if sacrebleu is not installed (so callers degrade gracefully).
    """
    chrf = _get_chrf(word_order)
    if chrf is None:
        return None
    h = strip_for_eval(hypothesis)
    r = strip_for_eval(reference)
    if not h or not r:
        return 0.0
    return round(chrf.sentence_score(h, [r]).score, 2)


def evaluate_corpus(hypotheses: list[str], references: list[str],
                    word_order: int = 0) -> dict:
    """Corpus-level chrF plus per-item scores.

    Returns ``{'checked', 'corpus_chrf', 'mean_chrf', 'n', 'per_item'}``.
    ``corpus_chrf`` aggregates statistics across all items (the headline number);
    ``mean_chrf`` is the simple average of per-chapter scores.
    """
    result = {"checked": False, "corpus_chrf": None, "mean_chrf": None,
              "n": 0, "per_item": []}
    chrf = _get_chrf(word_order)
    if chrf is None or not hypotheses:
        return result

    hyps = [strip_for_eval(h) for h in hypotheses]
    refs = [strip_for_eval(r) for r in references]

    per_item = [round(chrf.sentence_score(h, [r]).score, 2) for h, r in zip(hyps, refs)]
    corpus = chrf.corpus_score(hyps, [refs]).score
    result.update(
        checked=True,
        corpus_chrf=round(corpus, 2),
        mean_chrf=round(sum(per_item) / len(per_item), 2) if per_item else 0.0,
        n=len(per_item),
        per_item=per_item,
    )
    return result


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def _chapter_no(name: str) -> Optional[int]:
    m = _CHAPTER_RE.search(name)
    return int(m.group(1)) if m else None


def pair_files(hyp_path: Path, ref_path: Path) -> list[tuple[int, Path, Path]]:
    """Match hypothesis and reference files by chapter number.

    Both single-file and directory inputs are supported. Directories are matched
    by the integer in ``chapter_NNN`` — so EN-style ``chapter_001`` aligns with
    MM-style ``chapter_0001``, and partially-translated novels simply yield fewer
    pairs (unmatched chapters are skipped).
    """
    if hyp_path.is_file() and ref_path.is_file():
        return [(_chapter_no(hyp_path.name) or 0, hyp_path, ref_path)]

    hyp_by_ch: dict[int, Path] = {}
    for fp in sorted(hyp_path.glob("*.md")):
        ch = _chapter_no(fp.name)
        if ch is not None and ch not in hyp_by_ch:
            hyp_by_ch[ch] = fp
    ref_by_ch: dict[int, Path] = {}
    for fp in sorted(ref_path.glob("*.md")):
        ch = _chapter_no(fp.name)
        if ch is not None and ch not in ref_by_ch:
            ref_by_ch[ch] = fp

    common = sorted(set(hyp_by_ch) & set(ref_by_ch))
    return [(ch, hyp_by_ch[ch], ref_by_ch[ch]) for ch in common]


def evaluate_paths(hyp: str, ref: str, word_order: int = 0) -> dict:
    """Evaluate a hypothesis file/dir against a reference file/dir by chapter."""
    pairs = pair_files(Path(hyp), Path(ref))
    if not pairs:
        return {"checked": False, "n": 0, "corpus_chrf": None, "per_item": [],
                "message": "No chapter-aligned file pairs found."}
    chapters = [ch for ch, _, _ in pairs]
    hyps = [_read(h) for _, h, _ in pairs]
    refs = [_read(r) for _, _, r in pairs]
    out = evaluate_corpus(hyps, refs, word_order)
    out["chapters"] = chapters
    out["per_chapter"] = list(zip(chapters, out.get("per_item", [])))
    return out


def _main() -> None:  # pragma: no cover - CLI
    import argparse
    parser = argparse.ArgumentParser(description="chrF evaluation vs human Myanmar reference")
    parser.add_argument("--hyp", required=True, help="Hypothesis file or directory (model output)")
    parser.add_argument("--ref", required=True, help="Reference file or directory (human MM)")
    parser.add_argument("--chrf-plus", action="store_true", help="Use chrF++ (word_order=2)")
    args = parser.parse_args()

    out = evaluate_paths(args.hyp, args.ref, word_order=2 if args.chrf_plus else 0)
    if not out.get("checked"):
        print(out.get("message", "Evaluation unavailable (is sacrebleu installed?)"))
        return
    print(f"Pairs evaluated : {out['n']}")
    print(f"Corpus chrF     : {out['corpus_chrf']}")
    print(f"Mean chapter chrF: {out['mean_chrf']}")
    worst = sorted(out["per_chapter"], key=lambda x: x[1])[:5]
    if worst:
        print("Lowest-scoring chapters (likely needing attention):")
        for ch, sc in worst:
            print(f"  ch.{ch}: {sc}")


if __name__ == "__main__":  # pragma: no cover
    _main()
