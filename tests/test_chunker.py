"""Chunker tests (SPEC §2.2, R-STRUCT-01/02/03)."""

from __future__ import annotations

from src.pipeline.chunker import (
    ChunkerConfig,
    build_chunks,
    identify_speakers,
    is_dialogue_para,
    is_scene_break,
)
from src.pipeline.models import Chunk

CFG = ChunkerConfig(
    {
        "parameters": {
            "max_paragraphs_per_chunk": 3,
            "min_paragraphs_per_chunk": 1,
            "overlap_paragraphs": 1,
        },
        "dialogue_preservation": {"max_consecutive_dialogue": 4},
        "chunk_types": {
            "dialogue-heavy": {"dialogue_ratio": "> 0.6"},
            "narration-heavy": {"dialogue_ratio": "< 0.2"},
        },
    }
)


def test_scene_breaker():
    assert is_scene_break("---")
    assert is_scene_break("# Heading")
    assert not is_scene_break("ordinary paragraph")


def test_dialogue_detection():
    assert is_dialogue_para('"Hi"')
    assert is_dialogue_para("\u201cဟယ်\u201d")
    assert not is_dialogue_para("He walked inside.")


def test_build_chunks_scene_split():
    paras = [
        "Para one.",
        "Para two.",
        "---",
        "After the break.",
        "More after.",
    ]
    chunks = build_chunks("0001", paras, CFG)
    assert len(chunks) == 2
    assert chunks[0].scene_id != chunks[1].scene_id


def test_build_chunks_overlap_injected():
    paras = ["A.", "B.", "C.", "D.", "E.", "F."]
    chunks = build_chunks("0001", paras, CFG)
    assert len(chunks) > 1
    assert chunks[1].overlap_paras == ["C."]
    assert chunks[1].paragraphs[0] == "C."


def test_chunk_repr_properties():
    c = Chunk(id="x", chapter_id="0001", scene_id="sc01", sequence=0,
              paragraphs=["P0.", "P1.", "P2."], overlap_paras=["P0."])
    assert c.source_text == "P0.\n\nP1.\n\nP2."
    assert c.preceding_overlap == "P0."
    assert c.body_paragraphs == ["P1.", "P2."]


def test_identify_speakers_from_tags():
    names = identify_speakers('"Hey," Chen Ge said. "Stop," Xu Wan shouted.')
    assert "Chen Ge" in names
    assert "Xu Wan" in names


def test_mixed_paras_limit_enforced():
    paras = [f"P{i}. narration without quotes" for i in range(8)]
    chunks = build_chunks("0001", paras, CFG)
    for c in chunks:
        assert len(c.paragraphs) - len(c.overlap_paras) <= CFG.max_paragraphs
    assert len(chunks) >= 3