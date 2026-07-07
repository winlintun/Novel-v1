"""
Prompt Rules and System Prompts for Translation Pipeline
"""

# Language guards
from src.agents.prompts.language_guards import LANGUAGE_GUARD

# System prompts (used directly by agents)
from src.agents.prompts.system_prompts import (
    TRANSLATOR_SYSTEM_PROMPT,
    ENGLISH_TRANSLATOR_SYSTEM_PROMPT,
    EDITOR_SYSTEM_PROMPT,
    EXTRACTOR_SYSTEM_PROMPT,
    CUSTOM_PADAUK_EN_MM_PROMPT,
    FALLBACK_CN_RULES,
    FALLBACK_EN_RULES,
    build_translator_prompt,
    get_fallback_rules,
)

# Builder functions (used by agents to generate dynamic prompts)
from src.agents.prompts.cn_mm_rules import (
    CULTURAL_RULES,
    build_linguistic_context as build_cn_context,
)
from src.agents.prompts.en_mm_rules import (
    VOCABULARY_PRECISION,
    CULTURAL_RULES as EN_CULTURAL_RULES,
    build_linguistic_context as build_en_context,
    build_rewriter_prompt,
)

# Model-aware prompt builder — per-model optimized prompts
from src.agents.prompts.model_prompts import (
    build_prompt_for_model,
    detect_model_family,
)

# Re-export surface for `from src.agents.prompts import ...`. Listed in __all__
# so the re-exports above are not flagged as unused imports (F401).
__all__ = [
    "LANGUAGE_GUARD",
    "TRANSLATOR_SYSTEM_PROMPT",
    "ENGLISH_TRANSLATOR_SYSTEM_PROMPT",
    "EDITOR_SYSTEM_PROMPT",
    "EXTRACTOR_SYSTEM_PROMPT",
    "CUSTOM_PADAUK_EN_MM_PROMPT",
    "FALLBACK_CN_RULES",
    "FALLBACK_EN_RULES",
    "build_translator_prompt",
    "get_fallback_rules",
    "CULTURAL_RULES",
    "build_cn_context",
    "VOCABULARY_PRECISION",
    "EN_CULTURAL_RULES",
    "build_en_context",
    "build_rewriter_prompt",
    "build_prompt_for_model",
    "detect_model_family",
]
