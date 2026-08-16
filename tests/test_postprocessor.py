"""Post-processor tests (MP4, R-FORMAT-*, R-GLOSS-*, Myanmar invariants)."""

from __future__ import annotations

from src.pipeline import postprocessor
from src.pipeline.postprocessor import (
    apply_all,
    clean_my_text,
    enforce_glossary,
    enforce_overlap,
    has_foreign_script,
    has_myanmar,
    looks_incomplete,
    normalize_quotes,
    remove_zwsp,
    strip_thinking,
    to_myanmar_numbers,
)


def test_strip_thinking_tags():
    raw = "<thinking>hmm</thinking>ဒီအကြောင်း ဖြစ်သည်။"
    assert strip_thinking(raw) == "ဒီအကြောင်း ဖြစ်သည်။"


def test_normalize_quotes():
    assert normalize_quotes('"hello"') == "\u201chello\u201d"


def test_remove_zwsp():
    assert remove_zwsp("a\u200bb") == "ab"


def test_to_myanmar_numbers():
    assert to_myanmar_numbers("500 books") == "၅၀၀ books"


def test_clean_my_text_paragraph_normalization():
    out = clean_my_text("  One.  \n \n  Two.  ")
    assert out == "One.\n\nTwo."


def test_clean_my_text_strips_fences():
    out = clean_my_text("```json\nအဖြေ\n```")
    assert out == "အဖြေ"


def test_enforce_glossary_replaces_variant():
    fixed, n = enforce_glossary(
        "ချန်ဂေါ် နှင့် သရဲအိမ် သို့",
        [
            {"en": "Chen Ge", "my": "ချန်ဂီ", "my_variants": ["ချန်ဂေါ်"], "aliases": ["Chen Ge"]},
            {"en": "Haunted House", "my": "သရဲစံအိမ်", "my_variants": ["သရဲအိမ်"], "aliases": []},
        ],
    )
    assert "ချန်ဂေါ်" not in fixed
    assert "သရဲအိမ်" not in fixed
    assert "ချန်ဂီ" in fixed and "သရဲစံအိမ်" in fixed
    assert n > 0


def test_enforce_glossary_fixes_leaked_english():
    fixed, _ = enforce_glossary(
        "Chen Ge walked into the haunted house.",
        [{"en": "Chen Ge", "my": "ချန်ဂီ", "my_variants": [], "aliases": ["Chen Ge"]}],
    )
    assert "Chen Ge" not in fixed
    assert "ချန်ဂီ" in fixed


def test_enforce_overlap_prepends():
    text = "ပထမစာပိုဒ်။"
    expected = "အရင်စာပိုဒ်။"
    out = enforce_overlap(text, expected)
    assert out.startswith(expected)
    assert expected in out


def test_enforce_overlap_idempotent_when_present():
    expected = "အရင်စာပိုဒ်။"
    out = enforce_overlap("အရင်စာပိုဒ်။\n\nဒုတိယ။", expected)
    assert out == "အရင်စာပိုဒ်။\n\nဒုတိယ။"


def test_has_myanmar_and_foreign():
    assert has_myanmar("မြန်မာ") is True
    assert has_myanmar("english") is False
    assert has_foreign_script("ภาษาไทย") is True
    assert has_foreign_script("မြန်မာ") is False


def test_looks_incomplete_rules():
    assert looks_incomplete("", "source") is True
    assert looks_incomplete("raw english echo", "raw english echo") is True
    assert looks_incomplete("NoBurmeseHere", "source text") is True
    assert looks_incomplete("ဒီဟာ မြန်မာစာ ဖြစ်သည်။", "source text") is False


def test_apply_all_pipeline():
    raw = '<thinking>x</thinking>"ချန်ဂေါ်" သွားသည်\u200b ။\n\n500 ခု။'
    idx = [{"en": "Chen Ge", "my": "ချန်ဂီ", "my_variants": ["ချန်ဂေါ်"], "aliases": ["Chen Ge"]}]
    text, n = apply_all(raw, index=idx, max_auto_fix=5, myanmar_numbers=True)
    assert "ချန်ဂေါ်" not in text
    assert "\u200b" not in text
    assert '"' not in text
    assert "၅၀၀" in text
    assert "ချန်ဂီ" in text