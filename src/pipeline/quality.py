"""Soft-gate quality scorer (NEW_TODO.md §2B, §3A).

Deterministic, no-LLM metrics that turn a translated chunk into a single
0-100 quality score plus per-metric pass/fail flags.  The Verifier enforces
*hard* gates (glossary exactness, overlap identity, register purity, encoding);
this module measures the *softer* stylistic signals that Verifier deliberately
does not block on:

- lexical diversity (avoid word repetition)      threshold >= 0.60
- sentence-length variance (std-dev of words)    threshold >= 5.0
- glossary coverage of locked terms              threshold == 1.0
- register consistency per paragraph             threshold == 1.0
- SOV word-order naturalness                     threshold >= 0.80

Every measurement is defensive: empty/short input yields neutral metrics,
never an exception, so the pipeline can always record a score.
"""
from __future__ import annotations

import re
import statistics
from typing import Any, Dict, List, Optional, Sequence

from .postprocessor import has_myanmar

LEXICAL_DIVERSITY_THRESHOLD = 0.60
SENTENCE_STDDEV_THRESHOLD = 5.0
GLOSSARY_COVERAGE_THRESHOLD = 1.0
REGISTER_CONSISTENCY_THRESHOLD = 1.0
SOV_SCORE_THRESHOLD = 0.80

WEIGHTS: Dict[str, float] = {
    "lexical_diversity": 0.15,
    "sentence_length_variance": 0.15,
    "glossary_coverage": 0.30,
    "register_consistency": 0.25,
    "sov_order": 0.15,
}

LITERARY_ENDINGS = ("လေသည်", "ရလေသည်", "ကြလေသည်")
SPOKEN_PARTICLES = ("တယ်", "လား", "ပဲ", "ကွာ", "နော်", "ဗျာ")

# Approximate sentence-final verb suffixes for the SOV naturalness heuristic.
# A sentence is "SOV-natural" when its final content token carries one of these
# verb endings, or the sentence is entirely Myanmar script.
_VERB_SUFFIXES = (
    "လေသည်", "ရလေသည်", "ကြလေသည်", "ဖြစ်သည်", "သည်", "၏",
    "တယ်", "ပါတယ်", "မယ်", "မည်", "ပါ", "လား", "နော်", "ကွာ", "ဗျာ",
    "လိုက်သည်", "ခဲ့သည်", "နေသည်", "လျက်", "ပေသည်", "လိမ့်မည်",
)

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[။.!?…])\s+|\n+")
_TOKEN_RE = re.compile(r"\S+")


def _sentences(text: str) -> List[str]:
    if not text:
        return []
    out = []
    for frag in _SENTENCE_SPLIT_RE.split(text):
        frag = frag.strip()
        if frag:
            out.append(frag)
    if not out and text.strip():
        out = [text.strip()]
    return out


def lexical_diversity(text: str) -> float:
    tokens = _TOKEN_RE.findall(text or "")
    if len(tokens) < 2:
        return 1.0
    lowered = [t.lower().strip("“”\"'။,.") for t in tokens]
    lowered = [t for t in lowered if t]
    if not lowered:
        return 1.0
    return round(len(set(lowered)) / len(lowered), 4)


def sentence_length_stddev(text: str) -> float:
    sentences = _sentences(text)
    lengths = [len(_TOKEN_RE.findall(s)) for s in sentences]
    if not lengths:
        return 0.0
    if len(lengths) == 1:
        return 0.0
    return round(statistics.pstdev(lengths), 3)


def glossary_coverage(
    source: str,
    translation: str,
    glossary_index: Sequence[dict],
    *,
    locked_only: bool = True,
) -> float:
    hits = 0
    total = 0
    for entry in glossary_index or []:
        if locked_only and entry.get("locked") is not True:
            continue
        aliases = list(entry.get("aliases") or [entry.get("en") or ""])
        if not any(a and a in (source or "") for a in aliases):
            continue
        total += 1
        canonical = entry.get("my") or ""
        if canonical and canonical in (translation or ""):
            hits += 1
    if total == 0:
        return 1.0
    return round(hits / total, 4)


def register_consistency(text: str) -> float:
    paragraphs = [p for p in (text or "").split("\n\n") if p.strip()]
    if not paragraphs:
        return 1.0
    consistent = 0
    for para in paragraphs:
        has_lit = any(e in para for e in LITERARY_ENDINGS)
        has_spk = any(p in para for p in SPOKEN_PARTICLES)
        if not (has_lit and has_spk):
            consistent += 1
    return round(consistent / len(paragraphs), 4)


def sov_order(text: str) -> float:
    sentences = _sentences(text)
    if not sentences:
        return 1.0
    natural = 0
    for s in sentences:
        if re.search(r"[A-Za-z]{2,}", s):
            continue
        tail = re.sub(r"[။.!?…\u201c\u201d“”\s]+$", "", s)
        if any(suffix and tail.endswith(suffix) for suffix in _VERB_SUFFIXES):
            natural += 1
        elif has_myanmar(tail):
            natural += 1
    return round(natural / len(sentences), 4)


METRIC_FUNCS = {
    "lexical_diversity": lambda src, tr, g: lexical_diversity(tr),
    "sentence_length_variance": lambda src, tr, g: sentence_length_stddev(tr),
    "glossary_coverage": lambda src, tr, g: glossary_coverage(src, tr, g),
    "register_consistency": lambda src, tr, g: register_consistency(tr),
    "sov_order": lambda src, tr, g: sov_order(tr),
}

THRESHOLDS: Dict[str, float] = {
    "lexical_diversity": LEXICAL_DIVERSITY_THRESHOLD,
    "sentence_length_variance": SENTENCE_STDDEV_THRESHOLD,
    "glossary_coverage": GLOSSARY_COVERAGE_THRESHOLD,
    "register_consistency": REGISTER_CONSISTENCY_THRESHOLD,
    "sov_order": SOV_SCORE_THRESHOLD,
}


def quality_score(
    source: str,
    translation: str,
    glossary_index: Optional[Sequence[dict]] = None,
    *,
    weights: Optional[Dict[str, float]] = None,
    thresholds: Optional[Dict[str, float]] = None,
    return_metrics: bool = True,
) -> Dict[str, Any]:
    """Score a chunk 0-100 from the five soft gates.

    Returns::

        {
          "score": float,          # 0-100 weighted
          "metrics": {metric: value, ...},
          "gates":   {metric: pass_bool, ...},
          "soft_gate_pass": bool,  # all gates pass
        }
    """
    w = dict(weights or WEIGHTS)
    th = dict(thresholds or THRESHOLDS)
    idx = list(glossary_index or [])
    metrics: Dict[str, float] = {}
    for name, func in METRIC_FUNCS.items():
        value = float(func(source, translation, idx))
        if name == "sentence_length_variance":
            value = min(value, 100.0)
        metrics[name] = value

    gates: Dict[str, bool] = {}
    sentence_count = len(_sentences(translation or ""))
    for name, raw in metrics.items():
        gt = th.get(name, 0.0)
        if name == "glossary_coverage":
            gates[name] = raw >= gt - 1e-9
        elif name == "register_consistency":
            gates[name] = raw >= gt - 1e-9
        elif name == "sentence_length_variance":
            # variance is undefined below 2 sentences -> treat as neutral/pass
            if sentence_count < 2:
                gates[name] = True
            else:
                gates[name] = raw >= gt
        else:
            gates[name] = raw >= gt

    score = 0.0
    for name, frac in w.items():
        norm = 1.0
        if name == "sentence_length_variance":
            norm = min(1.0, metrics.get(name, 0.0) / 10.0)
        elif name == "glossary_coverage":
            norm = metrics.get(name, 1.0)
        elif name == "register_consistency":
            norm = metrics.get(name, 1.0)
        else:
            norm = min(1.0, metrics.get(name, 0.0) / 1.0)
        score += frac * norm * 100.0
    score = round(min(100.0, max(0.0, score)), 1)

    result: Dict[str, Any] = {
        "score": score,
        "soft_gate_pass": all(gates.values()),
    }
    if return_metrics:
        result["metrics"] = metrics
        result["gates"] = gates
    return result