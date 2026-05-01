"""
Prompt Rules Modules for CN→MM and EN→MM translation.

Exports:
- cn_mm_rules: Chinese-to-Myanmar linguistic transformation rules
- en_mm_rules: English-to-Myanmar linguistic transformation rules
"""

from src.agents.prompts.cn_mm_rules import (
    SVO_TO_SOV_RULES,
    PARTICLE_GUIDELINES,
    PRONOUN_HIERARCHY,
    CULTURAL_RULES,
    build_linguistic_context as build_cn_context,
)

from src.agents.prompts.en_mm_rules import (
    SVO_TO_SOV_RULES as EN_SVO_TO_SOV_RULES,
    TENSE_TO_PARTICLE,
    PRONOUN_HIERARCHY as EN_PRONOUN_HIERARCHY,
    DIALOGUE_RULES,
    NARRATION_RULES,
    PARTICLE_GUIDELINES as EN_PARTICLE_GUIDELINES,
    UNICODE_SAFETY_RULES,
    CULTURAL_RULES as EN_CULTURAL_RULES,
    FORMATTING_RULES,
    VOCABULARY_PRECISION,
    CONFRONTATION_SPEECH_PATTERN,
    PIPELINE_SETTINGS,
    build_linguistic_context as build_en_context,
    build_rewriter_prompt,
)

__all__ = [
    "build_cn_context",
    "build_en_context",
    "build_rewriter_prompt",
]
