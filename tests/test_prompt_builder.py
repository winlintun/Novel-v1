"""Prompt builder tests (TEST-PROMPT-001/002/003)."""

from __future__ import annotations

from src.pipeline.models import Chunk, FewShotPair
from src.pipeline.prompt_builder import (
    assembled_prompt,
    build_draft_prompt,
    build_polish_prompt,
    estimate_tokens,
    fit_context,
    render_context,
    render_few_shots,
    select_few_shots,
)


def make_chunk() -> Chunk:
    return Chunk(
        id="0001_sc01_ck00",
        chapter_id="0001",
        scene_id="sc01",
        sequence=0,
        type="dialogue-heavy",
        paragraphs=['"Chen Ge," Xu Wan said.', "Chen Ge nodded."],
        overlap_paras=['"Chen Ge," Xu Wan said.'],
    )


def test_estimate_tokens_nonzero():
    assert estimate_tokens("") == 1
    assert estimate_tokens("abc") >= 1


def test_build_draft_prompt_includes_glossary_and_source():
    c = make_chunk()
    p = build_draft_prompt(c, glossary_section="GLOSSARY:\n- Chen Ge = ချန်ဂီ")
    assert "GLOSSARY:" in p
    assert "Chen Ge" in p
    assert "SOURCE TEXT" in p
    assert '"Chen Ge," Xu Wan said.' in p


def test_build_draft_prompt_repeats_overlap():
    c = make_chunk()
    p = build_draft_prompt(c)
    assert c.preceding_overlap in p
    assert "OVERLAP" in p


def test_build_polish_prompt_keeps_draft():
    p = build_polish_prompt(make_chunk(), "ဒီဟာ မြန်မာ။")
    assert "ဒီဟာ မြန်မာ။" in p
    assert "LITERARY POLISH" in p


def test_select_few_shots_prefers_category():
    fs = [
        FewShotPair(id="1", category="dialogue", source='"a"', translation="အ"),
        FewShotPair(id="2", category="narration", source="b", translation="ဘီ"),
        FewShotPair(id="3", category="dialogue", source='"c"', translation="စီ"),
    ]
    sel = select_few_shots(fs, "dialogue-heavy", n=2)
    assert all(s.category == "dialogue" for s in sel)


def test_fit_context_trims_to_budget():
    ctx = "x" * 3000
    out = fit_context([ctx], 100)
    assert estimate_tokens(out) <= 105


def test_render_context_parts():
    context = {
        "preceding_summary": "Chen Ge runs.",
        "active_speakers": {"Chen Ge": {"pronoun": "ငါ", "mood": ""}},
        "preceding_chunks": [{"translated_text": "ချန်ဂီ သွားသည်။"}],
        "max_preceding_chunks": 2,
    }
    out = render_context(context)
    assert "Scene summary: Chen Ge runs." in out
    assert "pronoun=ငါ" in out
    assert "ချန်ဂီ သွားသည်။" in out


def test_render_few_shots_header():
    out = render_few_shots([FewShotPair(id="1", category="mixed", source="en", translation="my")])
    assert "HUMAN-WRITTEN reference" in out
    assert "ref EN: en" in out


def test_assembled_prompt_fits_budget():
    c = make_chunk()
    p = assembled_prompt(
        c,
        glossary_section="GLOSSARY:\n- Chen Ge = ချန်ဂီ\n- Xu Wan = ရှောင်ဝမ်",
        context_section="x" * 3000,
        few_shot_section="few shots here",
        max_ctx=2048,
    )
    assert estimate_tokens(p) <= 2048 - 512 + 20