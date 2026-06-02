"""
Prompt Rules and System Prompts for Translation Pipeline

This module contains:
- Language guards (safety rules)
- System prompts for all agents
- Linguistic transformation rules for CN→MM and EN→MM

Exports:
- language_guards: Unicode safety and language prevention rules
- system_prompts: Complete system prompts for translator, editor, etc.
- cn_mm_rules: Chinese-to-Myanmar linguistic transformation rules
- en_mm_rules: English-to-Myanmar linguistic transformation rules
"""

# Language guards and safety constants
from src.agents.prompts.language_guards import (
    LANGUAGE_GUARD,
    UNICODE_SAFETY_CHECKLIST,
)

# System prompts for all agents
from src.agents.prompts.system_prompts import (
    TRANSLATOR_SYSTEM_PROMPT,
    ENGLISH_TRANSLATOR_SYSTEM_PROMPT,
    EDITOR_SYSTEM_PROMPT,
    EXTRACTOR_SYSTEM_PROMPT,
    FAST_EN_MM_PROMPT,
    CUSTOM_PADAUK_EN_MM_PROMPT,
    FALLBACK_CN_RULES,
    FALLBACK_EN_RULES,
    build_translator_prompt,
    get_fallback_rules,
)

# Linguistic rules modules
from src.agents.prompts.cn_mm_rules import (
    SVO_TO_SOV_RULES,
    PARTICLE_GUIDELINES,
    PRONOUN_HIERARCHY,
    CULTURAL_RULES,
    UNICODE_SAFETY_RULES,
    CONFRONTATION_SPEECH_PATTERN,
    build_linguistic_context as build_cn_context,
)

from src.agents.prompts.en_mm_rules import (
    SVO_TO_SOV_RULES as EN_SVO_TO_SOV_RULES,
    TENSE_TO_PARTICLE,
    PRONOUN_HIERARCHY as EN_PRONOUN_HIERARCHY,
    DIALOGUE_RULES,
    NARRATION_RULES,
    PARTICLE_GUIDELINES as EN_PARTICLE_GUIDELINES,
    UNICODE_SAFETY_RULES as EN_UNICODE_SAFETY,
    CULTURAL_RULES as EN_CULTURAL_RULES,
    FORMATTING_RULES,
    VOCABULARY_PRECISION,
    CONFRONTATION_SPEECH_PATTERN as EN_CONFRONTATION,
    PIPELINE_SETTINGS,
    build_linguistic_context as build_en_context,
    build_rewriter_prompt,
)

__all__ = [
    # Language guards
    "LANGUAGE_GUARD",
    "UNICODE_SAFETY_CHECKLIST",
    # System prompts
    "TRANSLATOR_SYSTEM_PROMPT",
    "ENGLISH_TRANSLATOR_SYSTEM_PROMPT",
    "EDITOR_SYSTEM_PROMPT",
    "EXTRACTOR_SYSTEM_PROMPT",
    "FAST_EN_MM_PROMPT",
    "CUSTOM_PADAUK_EN_MM_PROMPT",
    "FALLBACK_CN_RULES",
    "FALLBACK_EN_RULES",
    # CN→MM rules
    "SVO_TO_SOV_RULES",
    "PARTICLE_GUIDELINES",
    "PRONOUN_HIERARCHY",
    "CULTURAL_RULES",
    "UNICODE_SAFETY_RULES",
    "CONFRONTATION_SPEECH_PATTERN",
    # EN→MM rules
    "EN_SVO_TO_SOV_RULES",
    "TENSE_TO_PARTICLE",
    "EN_PRONOUN_HIERARCHY",
    "DIALOGUE_RULES",
    "NARRATION_RULES",
    "EN_PARTICLE_GUIDELINES",
    "EN_UNICODE_SAFETY",
    "EN_CULTURAL_RULES",
    "FORMATTING_RULES",
    "VOCABULARY_PRECISION",
    "EN_CONFRONTATION",
    "PIPELINE_SETTINGS",
    # Builder functions
    "build_translator_prompt",
    "build_cn_context",
    "build_en_context",
    "build_rewriter_prompt",
    "get_fallback_rules",
]
