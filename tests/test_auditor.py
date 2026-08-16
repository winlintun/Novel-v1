"""Auditor tests (LLM path + deterministic fallback)."""

from __future__ import annotations

from src.pipeline.auditor import Auditor, heuristic_scores, verdict_from_grade

SOURCE = "Chen Ge walked into the Haunted House. Xu Wan smiled."
MY = "ချန်ဂီ သည် သရဲစံအိမ်သို့ ဝင်လာလေ၏။ ရှောင်ဝမ် က ပြုံးလိုက်သည်။"
GLOSSARY = [
    {"en": "Chen Ge", "my": "ချန်ဂီ", "aliases": ["Chen Ge"]},
    {"en": "Haunted House", "my": "သရဲစံအိမ်", "aliases": ["Haunted House"]},
    {"en": "Xu Wan", "my": "ရှောင်ဝမ်", "aliases": ["Xu Wan"]},
]


class FakeAuditClient:
    def __init__(self, raw):
        self.raw = raw

    def generate(self, prompt, **kwargs):
        return self.raw


def test_audit_uses_llm_json(mock_ollama):
    mock_ollama.responses = [
        '{"grade":"B","scores":{"flow":80,"voice_consistency":75,"terminology":90,"literary_quality":70},"weighted_total":78.0,"verdict":"pass","suggestions":["More variety"]}'
    ]
    auditor = Auditor(client=mock_ollama)
    report = auditor.audit(SOURCE, MY, glossary_index=GLOSSARY)
    assert report["llm_used"] is True
    # weighted = .25*80 + .25*75 + .20*90 + .30*70 = 77.75 -> B (>=70)
    assert report["grade"] == "B"
    assert report["verdict"] == "pass"


def test_audit_falls_back_to_heuristic_on_missing_client():
    auditor = Auditor(client=None)
    report = auditor.audit(SOURCE, MY, glossary_index=GLOSSARY)
    assert report["llm_used"] is False
    assert "scores" in report
    assert report["scores"]["terminology"] == 100
    assert report["verdict"] in ("pass", "needs_human_review", "fail")


def test_audit_falls_back_on_garbage_llm(mock_ollama):
    mock_ollama.responses = ["not json at all"]
    auditor = Auditor(client=mock_ollama)
    report = auditor.audit(SOURCE, MY, glossary_index=GLOSSARY)
    assert report["llm_used"] is False
    assert "scores" in report


def test_heuristic_scores_terminology_perfect():
    s = heuristic_scores(SOURCE, MY, GLOSSARY)
    assert s["terminology"] == 100


def test_heuristic_terminology_misses():
    s = heuristic_scores(SOURCE, "some burmese text သူ။", GLOSSARY)
    assert s["terminology"] < 100


def test_verdict_ranges():
    assert verdict_from_grade("A") == "pass"
    assert verdict_from_grade("B") == "pass"
    assert verdict_from_grade("C") == "needs_human_review"
    assert verdict_from_grade("F") == "fail"


def test_audit_comparison_with_human(mock_ollama):
    mock_ollama.responses = ["junk"]
    auditor = Auditor(client=mock_ollama)
    report = auditor.audit(SOURCE, MY, glossary_index=GLOSSARY, human_reference=MY, compare_with_human=True)
    assert "human_reference_similarity" in report["comparison"]