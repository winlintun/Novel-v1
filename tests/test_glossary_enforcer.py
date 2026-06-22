"""Tests for deterministic glossary enforcement."""

from src.utils.glossary_enforcer import enforce_glossary, enforce_variants


class TestEnforceGlossary:
    def test_replaces_latin_leakage_present_in_source(self):
        terms = [{"source_term": "village gate", "target_term": "ရွာတံခါး"}]
        out, n = enforce_glossary(
            "သူသည် village gate သို့ သွားသည်။",
            "He walked to the village gate.",
            terms,
        )
        assert n == 1
        assert "village gate" not in out
        assert "ရွာတံခါး" in out

    def test_skips_term_not_in_source(self):
        # Relevance guard: term absent from source must not be replaced.
        terms = [{"source_term": "Bai Xiaochun", "target_term": "ပိုင်ရှောင်ချန်း"}]
        out, n = enforce_glossary("Bai Xiaochun ဖြစ်သည်။", "no name here", terms)
        assert n == 0
        assert "Bai Xiaochun" in out

    def test_longest_term_first(self):
        terms = [
            {"source_term": "Inner Sect", "target_term": "အတွင်းဂိုဏ်း"},
            {"source_term": "Inner Sect disciples", "target_term": "အတွင်းဂိုဏ်းသားများ"},
        ]
        out, n = enforce_glossary(
            "Inner Sect disciples များ",
            "The Inner Sect disciples gathered.",
            terms,
        )
        assert "အတွင်းဂိုဏ်းသားများ" in out

    def test_ignores_placeholder_target(self):
        terms = [{"source_term": "qi", "target_term": "【?qi?】"}]
        out, n = enforce_glossary("qi ပါ", "the qi flows", terms)
        assert n == 0


class TestEnforceVariants:
    def test_normalises_misspelling(self):
        variants = [{"variant_text": "ရှောင်ချွန်", "target": "ရှောင်ချန်း"}]
        out, n = enforce_variants("ရှောင်ချွန် က ပြောသည်။", variants)
        assert n == 1
        assert "ရှောင်ချွန်" not in out
        assert "ရှောင်ချန်း" in out

    def test_longest_variant_first(self):
        variants = [
            {"variant_text": "ရှောင်ချီ", "target": "ရှောင်ချန်း"},
            {"variant_text": "ပိုင်ရှောင်ချီ", "target": "ပိုင်ရှောင်ချန်း"},
        ]
        out, n = enforce_variants("ပိုင်ရှောင်ချီ ထွက်သွားသည်။", variants)
        assert "ပိုင်ရှောင်ချန်း" in out
        # the long form must not be half-replaced into a broken token
        assert "ပိုင်ရှောင်ချန်းချီ" not in out

    def test_noop_when_variant_equals_target(self):
        variants = [{"variant_text": "ပိုင်", "target": "ပိုင်"}]
        out, n = enforce_variants("ပိုင် ပါ", variants)
        assert n == 0
