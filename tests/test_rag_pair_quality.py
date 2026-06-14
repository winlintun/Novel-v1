"""Tests for rag_pair_quality — the EN→MY few-shot pair validator.

These guard against the two alignment defects that corrupt RAG few-shot
examples: omission (Myanmar far shorter than English) and Latin leakage.
"""

from src.dataset_alignment.pipeline import rag_pair_quality

# A real, well-aligned pair (Bai Xiaochun greeting). ~1:1 length.
GOOD_EN = "Junior is a sentimental and righteous person, he said."
GOOD_MY = "ကျွန်တော်က သံယောဇဉ်ကြီးပြီး အစွဲအလမ်းလည်းကြီးတဲ့ သူတစ်ယောက်ပါ။"


def test_good_pair_passes():
    ok, reason = rag_pair_quality(GOOD_EN, GOOD_MY)
    assert ok is True
    assert reason == "ok"


def test_omission_pair_rejected():
    # Long English compound sentence aligned to one short Myanmar clause.
    en = ("Both were heavily wounded, and despite the fact that the wounds "
          "weren't critical, it was still a serious situation for them.")
    my = "နှစ်ယောက်လုံး ဒဏ်ရာအကြီးအမားတွေရကုန်ကြလေသည်။"
    ok, reason = rag_pair_quality(en, my)
    assert ok is False
    assert reason == "my_too_short_omission"


def test_latin_leak_rejected():
    en = "He walked into the ancient sect hall slowly and looked around."
    my = "သူသည် ancient sect hall ထဲသို့ ဖြည်းညင်းစွာ လျှောက်ဝင်သွားသည်။ He looked."
    ok, reason = rag_pair_quality(en, my)
    assert ok is False
    assert reason == "latin_leak"


def test_too_short_rejected():
    ok, reason = rag_pair_quality("Go.", "သွား။")
    assert ok is False
    assert reason == "too_short_abs"


def test_short_english_high_ratio_still_passes():
    # "Days passed." legitimately expands ~3x in Myanmar — must NOT be penalised.
    en = "Days passed."
    my = "တရွေ့ရွေ့နှင့် နေ့ရက်များကုန်ဆုံးခဲ့သည်။"
    ok, reason = rag_pair_quality(en, my)
    assert ok is True
    assert reason == "ok"


def test_low_myanmar_ratio_rejected():
    en = "This is a fairly long English sentence with real content here."
    my = "12345 67890 !!!! ???? ----"  # no Myanmar script at all
    ok, reason = rag_pair_quality(en, my)
    assert ok is False
    assert reason in ("low_myanmar_ratio", "latin_leak")
