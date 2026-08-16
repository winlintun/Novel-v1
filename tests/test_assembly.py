"""Assembly-time gate tests (todo.md §2/§3)."""

from __future__ import annotations

from src.pipeline.assembly import (
    assembly_completeness,
    assembly_script_gate,
    check_naming_consistency,
    dedup_assembled_paras,
    normalize_hygiene,
    translate_loanwords,
)


# -- 2.1 script whitelist gate ------------------------------------------- #
def test_script_gate_passes_pure_myanmar():
    ok, reason = assembly_script_gate("ကျွန်တော်မှာ ကြောက်စရာ သရဲအိမ် ရှိတယ်။ ၅၀၀!")
    assert ok is True
    assert reason == ""


def test_script_gate_allows_approved_loanwords():
    ok, _ = assembly_script_gate("ဂိမ်း HP 20 NPC 5", loanword_allowlist=["HP", "NPC"])
    assert ok is True


def test_script_gate_rejects_unapproved_latin():
    ok, reason = assembly_script_gate("ဂိမ်း Level တက်ဖို့", loanword_allowlist=[])
    assert ok is False
    assert "Level" in reason


def test_script_gate_rejects_thai():
    ok, reason = assembly_script_gate("တကယ်မရှိဘူး หรอก", loanword_allowlist=[])
    assert ok is False
    assert "Foreign script" in reason


def test_script_gate_rejects_bengali():
    ok, _ = assembly_script_gate("ဖုန်မှုန့် কাঁচ", loanword_allowlist=[])
    assert ok is False


def test_script_gate_rejects_hangul():
    ok, _ = assembly_script_gate("မြန်မာ 한국어", loanword_allowlist=[])
    assert ok is False


# -- 2.2 near-duplicate suppression -------------------------------------- #
def test_dedup_drops_exact_duplicates():
    paras = ["ငါ သည်းခံနိုင်ဦးမလဲ မသိဘူး", "ငါ သည်းခံနိုင်ဦးမလဲ မသိဘူး", "တတိယစာ။"]
    cleaned, dropped = dedup_assembled_paras(paras)
    assert len(cleaned) == 2
    assert len(dropped) == 1
    assert dropped[0] == paras[0]


def test_dedup_keeps_distinct():
    paras = [
        "သရဲအိမ်ရှေ့မှာ ကျောင်းသားအုပ်စုတစ်စု ရပ်နေကြသည်။",
        "ချန်ဂီက ကြော်ငြာစာရွက်တွေကို ကိုင်ထားသည်။",
        "အမျိုးသမီးတစ်ယောက်က နောက်ကနေ ပြေးထွက်လာသည်။",
    ]
    cleaned, dropped = dedup_assembled_paras(paras)
    assert len(cleaned) == 3
    assert dropped == []


# -- 2.3 completeness gate ------------------------------------------------ #
def test_completeness_ok():
    ok, reason = assembly_completeness(["အကြောင်းအရာ တစ်ခု ဖြစ်လာလေသည်။"], source_paras=["A line."])
    assert ok is True
    assert reason == ""


def test_completeness_rejects_empty():
    ok, reason = assembly_completeness([], source_paras=["A line."])
    assert ok is False
    assert "empty" in reason


def test_completeness_rejects_non_burmese():
    ok, reason = assembly_completeness(["All english text here"], source_paras=["A line."])
    assert ok is False
    assert "incomplete" in reason


# -- §3 hygiene normalization --------------------------------------------- #
def test_hygiene_unifies_dashes():
    out = normalize_hygiene("တစ်ခု – နှစ်ခု — သုံးခု - လေးခု")
    assert "\u2014" in out and "\u2013" not in out


def test_hygiene_unifies_ellipsis():
    out = normalize_hygiene("သွားတော့... ပြီးတော့။...")
    assert "…" in out


def test_hygiene_strips_ascii_art():
    out = normalize_hygiene("အပေါ်စာပိုဒ်။\n\n_______________\n\nအောက်စာပိုဒ်။")
    assert "___" not in out
    assert "အပေါ်စာပိုဒ်" in out and "အောက်စာပိုဒ်" in out


def test_hygiene_normalizes_single_quotes():
    out = normalize_hygiene("\u2018ဟယ်လို\u2019")
    assert "\u2018" not in out and "\u201c" in out


# -- loanword transliteration --------------------------------------------- #
def test_translate_loanwords():
    out = translate_loanwords("ဂိမ်း Level တက်ဖို့")
    assert "Level" not in out
    assert "အဆင့်" in out


# -- §4 naming consistency ------------------------------------------------ #
def test_naming_consistency_flags_drift():
    text = "ရှုရှု က ပြောသည်။ ပန်းခြံတာဝန်ခံ က ပြုံးသည်။ အသက်ကြီးသူ က နောက်လိုက်သည်။"
    index = [
        {"en": "Shu Shu", "my": "ရှုရှု", "my_variants": ["ပန်းခြံတာဝန်ခံ", "အသက်ကြီးသူ"]}
    ]
    flags = check_naming_consistency(text, index, max_variants=2)
    assert any("Shu Shu" in f for f in flags)


def test_naming_consistency_ok():
    text = "ရှုရှု က ပြောသည်။"
    index = [{"en": "Shu Shu", "my": "ရှုရှု", "my_variants": []}]
    assert check_naming_consistency(text, index, max_variants=2) == []
