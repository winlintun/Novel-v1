"""Quality soft-gate scorer tests (NEW_TODO.md §2B)."""

from __future__ import annotations

from src.pipeline.quality import (
    glossary_coverage,
    lexical_diversity,
    quality_score,
    register_consistency,
    sentence_length_stddev,
    sov_order,
)

GLOSSARY = [
    {"en": "Chen Ge", "my": "ချန်ဂီ", "aliases": ["Chen Ge"], "locked": True},
    {"en": "Xu Wan", "my": "ရှောင်ဝမ်", "aliases": ["Xu Wan"], "locked": True},
]


def test_lexical_diversity_identical_words_low():
    text = "ဒီ စာကြောင်း ဒီ စာကြောင်း ဒီ စာကြောင်း"
    assert lexical_diversity(text) < 0.6


def test_lexical_diversity_varied_words_high():
    text = "ချန်ဂီ သည် တံခါးကို တိတ်တဆိတ် ဖွင့်လိုက်လေသည်။ သူ သည် အခန်းထဲသို့ ဝင်သွားလေသည်။"
    assert lexical_diversity(text) > 0.6


def test_sentence_length_stddev():
    # One long, many short -> meaningful spread
    text = "ဤသည်မှာ အလွန်ရှည်လျားသော စာကြောင်းတစ်ကြောင်း ဖြစ်လေသည်။ ဒါ ကြောင်း တို။"
    assert sentence_length_stddev(text) > 0


def test_sentence_length_stddev_single_sentence_zero():
    assert sentence_length_stddev("တစ်ကြောင်းတည်းသာ စာကြောင်း ဖြစ်သည်။") == 0.0


def test_glossary_coverage_full():
    src = "Chen Ge looked at Xu Wan."
    tr = "ချန်ဂီ က ရှောင်ဝမ် ကို ကြည့်လေသည်။"
    assert glossary_coverage(src, tr, GLOSSARY) == 1.0


def test_glossary_coverage_missing_term():
    src = "Chen Ge looked at Xu Wan."
    tr = "ချန်ဂီ က သူမ ကို ကြည့်လေသည်။"
    assert glossary_coverage(src, tr, GLOSSARY) < 1.0


def test_glossary_coverage_empty_source_is_neutral():
    assert glossary_coverage("", "မြန်မာ", GLOSSARY) == 1.0


def test_register_consistency_pure_narration():
    assert register_consistency("ချန်ဂီ သည် တံခါးကို ဖွင့်လိုက်လေသည်။") == 1.0


def test_register_consistency_mixed_paragraph_fails():
    text = "ချန်ဂီ သည် တံခါးကို ဖွင့်လိုက်လေသည် တယ်။"
    assert register_consistency(text) < 1.0


def test_sov_order_burmese_ends():
    text = "ချန်ဂီ သည် အိမ်သို့ ပြန်သွားလေသည်။ သူ သည် မောပန်းနေလေသည်။"
    assert sov_order(text) >= 0.8


def test_sov_order_latin_tail_penalized():
    # English-fragment tail (untranslated) is not SOV-natural
    text = "ချန်ဂီ သည် အိမ်သို့ ပြန်သွားလေသည်။ He walked here"
    assert sov_order(text) < 1.0


def test_quality_score_shape_and_pass():
    src = "Chen Ge walked into Xu Wan's haunted house."
    tr = ("ချန်ဂီ သည် ရှောင်ဝမ် ၏ သရဲအိမ်သို့ ဝင်သွားလေသည်။ "
          "သူ သည် အခန်းထဲတွင် ရပ်တန့်၍ ပတ်ဝန်းကျင်ကို ကြည့်ရှုလေသည်။")
    res = quality_score(src, tr, GLOSSARY)
    assert 0 <= res["score"] <= 100
    assert set(res["gates"]) == {
        "lexical_diversity", "sentence_length_variance",
        "glossary_coverage", "register_consistency", "sov_order",
    }
    assert isinstance(res["soft_gate_pass"], bool)
    assert res["gates"]["glossary_coverage"] is True


def test_quality_score_soft_gate_rejects_missing_glossary():
    src = "Chen Ge nodded at Xu Wan."
    tr = "ချန်ဂီ က ခေါင်းညိတ်သည်။"  # Xu Wan missing
    res = quality_score(src, tr, GLOSSARY)
    assert res["soft_gate_pass"] is False
    assert res["gates"]["glossary_coverage"] is False


def test_quality_score_custom_thresholds():
    src = "Chen Ge."
    tr = "ချန်ဂီ သည်။"
    # raise the glossary bar so even the short case must be scored
    res = quality_score(src, tr, GLOSSARY, thresholds={"glossary_coverage": 1.0})
    assert res["score"] >= 0


def test_quality_score_always_returns_score_even_on_empty():
    res = quality_score("", "", [])
    assert res["score"] >= 0
    assert res["soft_gate_pass"] is True