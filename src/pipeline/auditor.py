"""Auditor (SKILL_auditor.md, SPEC §2.7).

Primary path calls Ollama with the audit prompt (PROMPTS.md §3.2) and parses
the JSON report.  If the LLM call fails (offline / malformed) a deterministic
heuristic scorer produces the same shape so the pipeline never crashes.

Grades: A >=90, B+ >=80, B >=70, C+ >=60, C >=50, D >=40, else F.
Weights: flow .25, voice .25, terminology .20, literary .30.
"""
from __future__ import annotations

import time
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

from . import jsonparse, postprocessor

GRADE_WEIGHTS = {"flow": 0.25, "voice_consistency": 0.25, "terminology": 0.20, "literary_quality": 0.30}

AUDIT_PROMPT_TEMPLATE = """Audit the following translated chapter as a complete work of fiction.

SOURCE (English):
\"\"\"
{source}
\"\"\"

TRANSLATION (Burmese):
\"\"\"
{translation}
\"\"\"

Evaluate on 0-100: FLOW, VOICE CONSISTENCY, TERMINOLOGY, LITERARY QUALITY.
Provide a weighted total, grade (A/B+/B/C+/C/D/F), verdict (pass/fail/needs_human_review),
and 3-5 specific suggestions.
Return ONLY JSON: {{"grade":"","scores":{{"flow":0,"voice_consistency":0,"terminology":0,"literary_quality":0}},"weighted_total":0.0,"verdict":"","suggestions":[]}}
"""


def _grade_from_total(total: float) -> str:
    if total >= 90:
        return "A"
    if total >= 80:
        return "B+"
    if total >= 70:
        return "B"
    if total >= 60:
        return "C+"
    if total >= 50:
        return "C"
    if total >= 40:
        return "D"
    return "F"


def verdict_from_grade(grade: str) -> str:
    if grade in ("A", "B+", "B"):
        return "pass"
    if grade in ("C+", "C"):
        return "needs_human_review"
    return "fail"


def heuristic_scores(
    source: str,
    translation: str,
    glossary_index: List[dict],
) -> Dict[str, int]:
    """Deterministic fallback scoring when Ollama is unavailable."""
    # terminology
    hits = misses = 0
    for entry in glossary_index:
        aliases = list(entry.get("aliases") or [entry.get("en") or ""])
        canonical = entry.get("my") or ""
        if not canonical:
            continue
        if any(a and a in source for a in aliases):
            if canonical in translation:
                hits += 1
            else:
                misses += 1
    term = int(100 * hits / (hits + misses)) if (hits + misses) else 100
    if misses == 0:
        term = 100

    # flow: scene breaks preserved + paragraph balance
    src_paras = len([p for p in source.split("\n\n") if p.strip()])
    out_paras = len([p for p in translation.split("\n\n") if p.strip()])
    para_balance = 1 - min(1.0, abs(src_paras - out_paras) / max(1, src_paras))
    has_breaks = "---" in translation or "\n\n\n" in translation
    flow = int(round(55 + 25 * para_balance + (15 if has_breaks else 0)))

    # voice: distinct particles + consistent endings variety
    literary_variety = len({e for e in ("လေသည်", "ရလေသည်", "ကြလေသည်") if e in translation})
    spoken = sum(1 for p in ("တယ်", "လား", "ကွာ", "နော်", "ဗျာ") if p in translation)
    voice = int(round(50 + 20 * min(1.0, literary_variety) + 10 * min(1.0, spoken / 3)))

    # literary quality: sentence-length variety + narration endings + Myanmar ratio
    sentences = [s for s in translation.replace("\n", " ").split("।") if s.strip()]
    lengths = [len(s) for s in sentences]
    variety = (max(lengths) - min(lengths)) / max(1, max(lengths)) if lengths else 0.3
    literary = int(round(40 + 30 * min(1.0, variety * 2) + (15 if any(e in translation for e in ("လေသည်", "ရလေသည်")) else 0) + (15 if postprocessor.has_myanmar(translation) else 0)))
    return {"flow": min(100, flow), "voice_consistency": min(100, voice), "terminology": term, "literary_quality": min(100, literary)}


class Auditor:
    def __init__(self, client=None, *, roles: Optional[Dict[str, Any]] = None):
        self.client = client
        role = (roles or {}).get("auditor") or {}
        self.model = role.get("model")
        self.temperature = role.get("temperature")

    def audit(
        self,
        source: str,
        translation: str,
        glossary_index: Optional[List[dict]] = None,
        human_reference: str = "",
        compare_with_human: bool = False,
    ) -> Dict[str, Any]:
        scores: Dict[str, int]
        suggestions: List[str] = []
        llm_ok = False

        if self.client is not None:
            try:
                prompt = AUDIT_PROMPT_TEMPLATE.format(
                    source=_truncate(source, 9000), translation=_truncate(translation, 9000)
                )
                kwargs: Dict[str, Any] = {"num_predict": 2048}
                if self.model and self.model != self.client.model:
                    kwargs["model"] = self.model
                if self.temperature is not None:
                    kwargs["temperature"] = self.temperature
                raw = self.client.generate(prompt, **kwargs)
                parsed = self._parse(raw)
                if parsed is not None:
                    import itertools

                    scores, suggestions, llm_ok = parsed
            except Exception:  # noqa: BLE001 — never crash the pipeline
                llm_ok = False

        if not llm_ok:
            scores = heuristic_scores(source, translation, list(glossary_index or []))
            suggestions = [
                "Run audit with a live Ollama model for LLM-based literary scoring",
                "Verify dialogue particles match each character's profile",
            ]

        weighted = sum(scores.get(k, 0) * w for k, w in GRADE_WEIGHTS.items())
        grade = _grade_from_total(weighted)
        report = {
            "grade": grade,
            "scores": scores,
            "weighted_total": round(weighted, 1),
            "verdict": verdict_from_grade(grade),
            "suggestions": suggestions,
            "llm_used": llm_ok,
            "audited_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        if compare_with_human and human_reference:
            sim = SequenceMatcher(None, translation, human_reference, autojunk=False).ratio()
            diff_head = []
            if translation and human_reference and translation[:200] != human_reference[:200]:
                diff_head = ["Opens differently from the human reference"]
            report["comparison"] = {
                "human_reference_similarity": round(sim, 3),
                "key_differences": diff_head,
            }
        return report

    @staticmethod
    def _parse(raw: str):
        """Return (scores, suggestions) or None from an LLM audit JSON blob."""
        parsed = jsonparse.load_json(raw.strip())
        if not isinstance(parsed, dict):
            return None
        scores = parsed.get("scores")
        if not isinstance(scores, dict):
            return None
        cleaned_scores = {}
        for k in ("flow", "voice_consistency", "terminology", "literary_quality"):
            cleaned_scores[k] = int(min(100, max(0, float(scores.get(k, 0)))))
        suggestions = [str(s) for s in (parsed.get("suggestions") or [])]
        return cleaned_scores, suggestions, True


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"