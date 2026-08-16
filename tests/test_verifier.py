"""Verifier tests (R-GLOSS-01, R-STRUCT-04, R-FORBID-03/04, paragraph parity)."""

from __future__ import annotations

from src.pipeline import verifier
from src.pipeline.verifier import verify


GLOSSARY = [
    {"en": "Chen Ge", "my": "ချန်ဂီ", "aliases": ["Chen Ge", "Boss"], "my_variants": ["ချန်ဂေါ်"]},
    {"en": "Xu Wan", "my": "ရှောင်ဝမ်", "aliases": ["Xu Wan", "Xiao Wan"], "my_variants": []},
]


def test_verify_passes_clean_translation():
    src = '"Chen Ge" said. Xu Wan nodded.'
    out = "“ချန်ဂီ” က ပြောသည်။ ရှောင်ဝမ် က ခေါင်းညိတ်သည်။"
    result = verify(src, out, GLOSSARY)
    assert result.passv is True
    assert result.glossary_misses == 0


def test_verify_catches_wrong_variant_fatal():
    src = "Chen Ge nodded."
    out = "ချန်ဂေါ် က ခေါင်းညိတ်သည်။"  # variant, not canonical
    result = verify(src, out, GLOSSARY, auto_fix_enabled=False)
    assert result.passv is False
    assert any(i.rule_id == "R-GLOSS-01" and i.severity == "fatal" for i in result.issues)


def test_verify_catches_missing_term_error():
    src = "Chen Ge smiled."
    out = "သူ က ပြုံးသည်။"
    result = verify(src, out, GLOSSARY)
    assert result.passv is False
    assert any(i.rule_id == "R-GLOSS-01" and i.severity == "error" for i in result.issues)


def test_verify_auto_fixes_variant_when_enabled():
    src = "Chen Ge nodded."
    out = "ချန်ဂေါ် က ခေါင်းညိတ်သည်။"
    result = verify(src, out, GLOSSARY, auto_fix_enabled=True, max_auto_fix=10)
    assert result.auto_fixed >= 1
    assert "ချန်ဂီ" in result.corrected_text
    assert result.glossary_misses == 0


def test_verify_overlap_identity():
    src = "P1.\n\nP2."
    out = "ဒုတိယစာပိုဒ် ဖြစ်သည်။"  # missing the overlap P1 translation
    result = verify(src, out, [], preceding_overlap="ပထမစာပိုဒ်။")
    assert not result.passv
    assert any(i.rule_id == "R-STRUCT-04" for i in result.issues)


def test_verify_rejects_untranslated_english():
    src = "Chen Ge opened the door."
    out = "ချန်ဂီ က the door ကို ဖွင့်သည်။"
    result = verify(src, out, GLOSSARY)
    assert not result.passv
    assert any(i.rule_id == "R-FORBID-03" for i in result.issues)


def test_verify_rejects_foreign_script():
    src = "Chen Ge looked at the glass."
    out = "ချန်ဂီ က ဖန်ခွက် ကို ကြည့်သည်။ มอง ကြည့်သည်"
    result = verify(src, out, GLOSSARY, auto_fix_enabled=False)
    assert not result.passv
    assert any(i.rule_id == "R-FORBID-05" and i.severity == "fatal" for i in result.issues)


def test_verify_register_mix_error():
    src = "He thought about it."
    out = "သူ က အကြောင်းကို စဉ်းစားလေသည် ကွာ။"
    result = verify(src, out, [])
    assert not result.passv
    assert any(i.rule_id == "R-FORBID-04" for i in result.issues)


def test_verify_paragraph_parity_warning():
    src = "A.\n\nB.\n\nC."
    out = "အေ။\n\nဘီ။"
    result = verify(src, out, [])
    assert any(i.rule_id == "R-STRUCT-02" for i in result.issues)


def test_verify_detects_new_terms():
    src = "Marco opened the door. Chen Ge waited."
    result = verify(src, "ချန်ဂီ စောင့်နေသည်။", GLOSSARY)
    assert "Marco" in result.new_terms


def test_verify_context_voice_continuity():
    src = "Xu Wan spoke."
    out = "“ငါ သွားမယ်” ဟု ပြောသည်။"
    context = {"active_speakers": {"Xu Wan": {"pronoun": "ကျွန်မ"}, "Chen Ge": {"pronoun": "ငါ"}}}
    result = verify(src, out, GLOSSARY, context=context)
    # Xu Wan's dialogue uses Chen Ge's pronoun ငါ instead of ကျွန်မ
    assert any(i.rule_id == "R-CTX-01" for i in result.issues)