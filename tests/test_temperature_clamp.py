"""Regression test for the padauk-gemma temperature hard ceiling.

Bug: TranslationPipeline._create_ollama_client read temperature from
processing.temperature (0.35), so padauk-gemma:q8_0 ran at 0.35 — above the
documented ≤0.2 ceiling that "corrupts Myanmar output" (CLAUDE.md / AGENTS.md).
The padauk_gemma config block's 0.2 was dead. _effective_temperature() now
clamps it structurally.
"""
import logging
import types

from src.pipeline.orchestrator import TranslationPipeline


def _stub(temp):
    s = types.SimpleNamespace()
    s.config = types.SimpleNamespace(processing=types.SimpleNamespace(temperature=temp))
    s.logger = logging.getLogger("test")
    s._MODEL_MAX_TEMPERATURE = TranslationPipeline._MODEL_MAX_TEMPERATURE
    return s


def _temp(stub, model):
    return TranslationPipeline._effective_temperature.__get__(stub)(model)


def test_padauk_clamped_to_ceiling():
    assert _temp(_stub(0.35), "padauk-gemma:q8_0") == 0.2


def test_non_padauk_model_keeps_configured_temp():
    assert _temp(_stub(0.35), "gemma-4-e4b-it:q8_0") == 0.35


def test_padauk_already_compliant_unchanged():
    assert _temp(_stub(0.2), "padauk-gemma:q8_0") == 0.2
    assert _temp(_stub(0.15), "padauk-gemma:q8_0") == 0.15


def test_padauk_match_is_case_insensitive_and_substring():
    assert _temp(_stub(0.5), "PADAUK-GEMMA:Q8_0") == 0.2
    assert _temp(_stub(0.5), "myorg/padauk-gemma-custom") == 0.2
