"""Translator micro-prompt orchestration tests."""

from __future__ import annotations

import pytest

from src.pipeline.models import Chunk
from src.pipeline.translator import Translator

GOOD_MY = "ချန်ဂီ က ခေါင်းညိတ်လိုက်လေသည်။"


@pytest.fixture
def chunk() -> Chunk:
    return Chunk(
        id="0001_sc01_ck00",
        chapter_id="0001",
        scene_id="sc01",
        sequence=0,
        type="mixed",
        paragraphs=["Chen Ge nodded.", '"Sure," he said.'],
    )


def test_translate_single_pass(mock_ollama, chunk):
    mock_ollama.responses = [GOOD_MY]
    t = Translator(mock_ollama, two_pass=False)
    text, used = t.translate_chunk(chunk)
    assert text == GOOD_MY
    assert "polish" not in used


def test_translate_two_pass_uses_polish(mock_ollama, chunk):
    mock_ollama.responses = [GOOD_MY, GOOD_MY + "\n\n(extra)"]
    t = Translator(mock_ollama, two_pass=True)
    text, used = t.translate_chunk(chunk)
    assert "polish" in used
    assert text  # clean text kept even if polish returned empty
    assert len(mock_ollama.calls) == 2


def test_translate_cleans_raw_output(mock_ollama, chunk):
    mock_ollama.responses = ["<thinking>hmm</thinking>" + GOOD_MY]
    t = Translator(mock_ollama, two_pass=False)
    text, _ = t.translate_chunk(chunk)
    assert "<thinking>" not in text


def test_translate_fix_mode_appends_issues(mock_ollama, chunk):
    mock_ollama.responses = [GOOD_MY]
    t = Translator(mock_ollama, two_pass=False)
    text, used = t.translate_chunk(chunk, fix_issues=["Wrong variant for Chen Ge"])
    assert "fix" in used
    assert "Wrong variant for Chen Ge" in mock_ollama.calls[0]["prompt"]


def test_translate_analyze_extra_call(mock_ollama, chunk):
    mock_ollama.responses = ['{"speakers":["Chen Ge"]}', GOOD_MY]
    t = Translator(mock_ollama, two_pass=False)
    _, used = t.translate_chunk(chunk, analyze=True)
    assert "analyze" in used
    assert len(mock_ollama.calls) == 2