"""
model_prompts.py
=================
Model-aware prompt layer for the CN/EN → Myanmar translation pipeline.

Each Ollama model has different capabilities and failure modes. This module
builds the OPTIMAL prompt for each model when translating EN→MM or CN→MM.

Model details sourced from model_detail.md:
    - Gemma 4:         Native system-role, 128K/256K context, thinking mode
    - TranslateGemma:  Single user message only, NO system role
    - Padauk:          Burmese-native, concise prompts, Thai/Bengali leak bug
    - Qwen3.5/3.6:     Chinese-centric, drifts to Chinese, needs SHORT prompts
    - Sailor2:         Built on Qwen2.5, 15-language persona, must override

USAGE
-----
    from src.agents.prompts.model_prompts import build_prompt_for_model

    result = build_prompt_for_model(
        model_name="qwen3.5-9b:latest",
        source_lang="english",
        scene_type="dialogue",
        genre="xianxia",
        text=chunk_text,
        glossary=glossary_str,
    )
    # result["system_prompt"] -> str or None (TranslateGemma = None)
    # result["user_prompt"]   -> str to send as user message
"""

from __future__ import annotations

import re

from .language_guards import LANGUAGE_GUARD, UNICODE_SAFETY_CHECKLIST  # noqa: F401
from .cn_mm_rules import build_linguistic_context as build_cn_context
from .en_mm_rules import build_linguistic_context as build_en_context
from .system_prompts import (
    TRANSLATOR_SYSTEM_PROMPT,
    ENGLISH_TRANSLATOR_SYSTEM_PROMPT,
    CUSTOM_PADAUK_EN_MM_PROMPT,
    _GENRE_RULES,
)

# ===========================================================================
# SECTION 1: MODEL FAMILY DETECTION
# ===========================================================================

_FAMILY_KEYWORDS = (
    ("padauk", "padauk"),
    ("translategemma", "translategemma"),
    ("translate-gemma", "translategemma"),
    ("translate_gemma", "translategemma"),
    ("sailor", "sailor2"),
    ("qwen", "qwen"),
    ("gemma", "gemma4"),
)


def detect_model_family(model_name: str) -> str:
    """
    Map an Ollama model tag to its family:
    "padauk" | "translategemma" | "sailor2" | "qwen" | "gemma4" | "generic"
    """
    name = (model_name or "").lower()
    for keyword, family in _FAMILY_KEYWORDS:
        if keyword in name:
            return family
    return "generic"


# ===========================================================================
# SECTION 2: PER-MODEL PROMPTS (EN → Myanmar)
# Each model gets a prompt tuned to its architecture and context window.
# ===========================================================================

def _build_gemma4_en_mm_prompt(scene_type: str = "narration", genre: str = "") -> str:
    """Gemma 4 prompt — native system-role, 128K+ context, thinking mode.
    
    Per model_detail.md:
    - Supports system role natively
    - Configurable thinking mode (must be disabled for translation)
    - 128K (small) / 256K (medium) context window
    - Strong reasoning capabilities
    
    Strategy: Full detailed prompt. Gemma4 can handle it.
    """
    genre_block = _GENRE_RULES.get((genre or "").lower().strip(), "")

    prompt = LANGUAGE_GUARD + """

# ROLE
You are a master literary translator who turns English-language novels into rich, idiomatic Myanmar (Burmese). You are not a machine; you are a linguistic artist.

# CONTEXT
You translate for native Myanmar readers who do not read English. The text is one chunk of a continuous, multi-chapter novel, so names, terms, pronouns, and tone MUST stay consistent with the GLOSSARY and PREVIOUS CONTEXT supplied below.

# TASK
Produce a complete, polished literary Burmese translation of the SOURCE TEXT that reads as if it were originally written in Burmese — capturing the spirit and tone of the original, not just the literal words.

# CONSTRAINTS

COMPLETENESS RULE (CRITICAL):
1. Translate EVERY sentence and paragraph from the source.
2. NEVER summarize, compress, or skip content.
3. Source paragraph count MUST equal output paragraph count.

ANTI-REPETITION RULES (CRITICAL):
1. NEVER repeat the same sentence pattern more than once in a row.
2. VARY sentence structure — use different grammatical patterns.
3. PARTICLE MAX: Each particle (က/ကို/မှာ/အတွက်/သည်) may appear AT MOST 2 times per paragraph.

LINGUISTIC RULES — English → Myanmar:

0. TRANSCREATE, DON'T TRANSLATE (MOST IMPORTANT):
   Do NOT mirror the English clause structure. COMPRESS and REORDER:
   several English clauses collapse into ONE flowing Myanmar sentence.
   Convey the MEANING and FEELING in natural literary Burmese.
   EN (3 clauses): "He seemed thin and weak, but had a healthy, fair complexion, and an overall charming appearance."
   ✅ TRANSCREATED: ပိန်ပါးသော်လည်း ကျန်းမာ၍ အသားလတ်သောကြောင့် ခြုံကြည့်လျှင် ခန့်ညားသူဟု ဆိုနိုင်သည်။

1. SYNTAX: English SVO → Myanmar SOV
   EN: He struck the enemy → MM: သူ ရန်သူကို ထိုးလိုက်တယ်
   Time/Location → sentence START. Negation (မ) before verb. Question markers (လား) at END.

2. DIALOGUE:
   ✅ "စကားပြော" လို့ [name] ပြောတယ်
   ❌ "စကားပြော" ဟု သူ မေးမြန်းလေသည် (NEVER USE archaic ဟု/လေသည်)
   Vary verbs: ပြောတယ်, မေးတယ်, အော်လိုက်တယ်, ပြန်ပြောတယ်

3. PRONOUNS:
   Enemy: နင် (NOT မင်း), ဒီကောင် (3rd contempt)
   Equal: မင်း / ခင်ဗျ (male) / ရှင် (female)
   Formal: ကျွန်တော် (male), ကျွန်မ (female)

4. TENSE: Past=ခဲ့တယ်, Present=တယ်/သည်. NEVER mix formal/casual in same block.

5. SHOW EMOTIONS PHYSICALLY:
   ❌ သူ ဝမ်းနည်းတယ် (abstract label)
   ✅ သူ့ရင်ထဲမှာ တစ်ခုခု ကျိုးသွားသလို ဖြစ်မိတယ် (physical sensation)

6. ARCHAIC FORBIDDEN: ဟု→လို့, ထို→အဲဒီ, ဤ→ဒီ, သင်သည်→မင်း, ဖြစ်၏→ဖြစ်တယ်

7. GLOSSARY: Use glossary terms EXACTLY. Unknown terms → 【?term?】 placeholder.

8. OUTPUT: Myanmar Unicode ONLY (U+1000-U+109F). NO Chinese/Thai/Bengali/English.
   NO preamble, NO explanation. Start directly with the translation.
"""
    if genre_block:
        prompt += "\n" + genre_block

    prompt += """

MODEL NOTE — Gemma 4:
  ⚠️ Thinking mode MUST be disabled at the API/Ollama-options level.
     If a <think> trace appears, treat it as a bug.
     The final answer must contain ONLY the Myanmar translation.
"""
    return prompt


def _build_padauk_en_mm_prompt(scene_type: str = "narration", genre: str = "") -> str:
    """Padauk prompt — Burmese-native fine-tune, concise instructions.
    
    Per model_detail.md:
    - Burmese-first assistant built for daily tasks
    - Degrades with over-long instructions
    - Known Thai/Bengali script leak bug
    
    Strategy: Use the existing CUSTOM_PADAUK_EN_MM_PROMPT which is already
    optimized for this model. Do NOT add extra rules on top.
    """
    return CUSTOM_PADAUK_EN_MM_PROMPT


def _build_translategemma_prompt(source_lang: str, text: str, glossary: str = "") -> str:
    """TranslateGemma prompt — single user message, NO system role.
    
    Per model_detail.md:
    - Built on Gemma 3, dedicated translation model
    - Expects EXACTLY one user message with this structure:
      "You are a professional {SOURCE} to {TARGET} translator..."
      Two blank lines before the text.
    - Performs WORSE with long system instructions
    
    Strategy: Follow Google's prompt guide EXACTLY. No system role.
    """
    _LANG_NAME_CODE = {
        "chinese": ("Chinese", "zh"),
        "zh": ("Chinese", "zh"),
        "zh-cn": ("Chinese", "zh"),
        "english": ("English", "en"),
        "en": ("English", "en"),
    }
    src_name, src_code = _LANG_NAME_CODE.get(
        (source_lang or "english").lower(), (source_lang.title(), (source_lang or "en")[:2])
    )
    tgt_name, tgt_code = "Myanmar (Burmese)", "my"

    glossary_line = f"\nUse these exact terms where they appear: {glossary}\n" if glossary else ""

    return (
        f"You are a professional {src_name} ({src_code}) to {tgt_name} ({tgt_code}) translator. "
        f"Your goal is to accurately convey the meaning and nuances of the original {src_name} text "
        f"while adhering to {tgt_name} grammar, vocabulary, and cultural sensitivities.\n"
        f"Produce only the {tgt_name} translation, without any additional explanations or commentary. "
        f"Output using Myanmar Unicode (U+1000-U+109F) ONLY — no Chinese, no English, no Thai, no Bengali."
        f"{glossary_line}"
        f"Please translate the following {src_name} text into {tgt_name}:\n\n\n"
        f"{text}"
    )


def _build_qwen_en_mm_prompt(scene_type: str = "narration", genre: str = "") -> str:
    """Qwen prompt — Chinese-centric base, needs SHORT prompt.
    
    Per model_detail.md:
    - Qwen3.5: 201 languages, hybrid architecture, strong reasoning
    - Qwen3.6: Agentic coding, thinking preservation
    - BOTH drift back into Chinese when uncertain
    - BOTH emit <think> blocks when thinking is enabled
    
    Strategy: SHORT prompt (~3K chars). The full 10K+ char prompt
    overwhelms Qwen causing truncated output, English leakage, and crashes.
    """
    scene_rule = {
        "narration":    "Medium sentences (10-18 words). Literary style.",
        "dialogue":     "Short natural sentences. Real speech rhythm.",
        "action":       "SHORT sentences (3-7 words). Fast rhythm. Active verbs.",
        "confrontation": "SHORT punchy sentences. One accusation per sentence.",
    }.get(scene_type, "Adapt sentence length to match scene intensity.")

    genre_block = _GENRE_RULES.get((genre or "").lower().strip(), "")

    prompt = LANGUAGE_GUARD + f"""

# ROLE
You are a literary translator. Translate English text to Myanmar (Burmese).

# RULES (follow EXACTLY)

1. SYNTAX: English SVO → Myanmar SOV
   EN: He struck the enemy → MM: သူ ရန်သူကို ထိုးလိုက်တယ်
   Time/Location → sentence START. Negation (မ) before verb. Question markers (လား) at END.

2. DIALOGUE:
   ✅ "စကားပြော" လို့ [name] ပြောတယ်
   ❌ "စကားပြော" ဟု သူ မေးမြန်းလေသည် (NEVER USE archaic forms)
   Vary verbs: ပြောတယ်, မေးတယ်, အော်လိုက်တယ်, ပြန်ပြောတယ်

3. PRONOUNS:
   Enemy: နင် (NOT မင်း), ဒီကောင် (3rd contempt)
   Equal: မင်း / ခင်ဗျ (male) / ရှင် (female)
   Formal: ကျွန်တော် (male), ကျွန်မ (female)

4. SENTENCE RHYTHM: {scene_rule}

5. TENSE: Past=ခဲ့တယ်, Present=တယ်/သည်. NEVER mix formal/casual in same block.

6. ARCHAIC FORBIDDEN: ဟု→လို့, ထို→အဲဒီ, ဤ→ဒီ, သင်သည်→မင်း, ဖြစ်၏→ဖြစ်တယ်

7. COMPLETENESS: Translate EVERY sentence. NEVER summarize or skip content.

8. GLOSSARY: Use glossary terms EXACTLY. Unknown terms → 【?term?】 placeholder.

9. OUTPUT: Myanmar Unicode ONLY (U+1000-U+109F). NO Chinese/Thai/Bengali/English.
   NO preamble, NO explanation. Start directly with the translation.
"""
    if genre_block:
        prompt += "\n" + genre_block

    prompt += """

MODEL NOTE — Qwen:
  ⚠️ Qwen is Chinese-centric and WILL drift back into Chinese when uncertain.
     If you are about to write a Chinese character, STOP and write Myanmar instead.
  - Do NOT output <think>...</think> or <reasoning> blocks.
  - Convert Chinese punctuation (，。！？「」) to Myanmar (၊ ။ ! ? " ").
"""
    return prompt


def _build_sailor2_en_mm_prompt(scene_type: str = "narration", genre: str = "") -> str:
    """Sailor2 prompt — built on Qwen2.5, 15-language persona, must override.
    
    Per model_detail.md:
    - Built on Qwen2.5, pre-trained on 500B tokens
    - Supports 15 languages (English, Chinese, Burmese, Thai, etc.)
    - Ships with default persona: "You are an AI assistant named Sailor2..."
    - Must override to Myanmar-only translator
    
    Strategy: SHORT prompt (inherits Qwen bias) + STRONG persona override.
    """
    scene_rule = {
        "narration":    "Medium sentences (10-18 words). Literary style.",
        "dialogue":     "Short natural sentences. Real speech rhythm.",
        "action":       "SHORT sentences (3-7 words). Fast rhythm. Active verbs.",
        "confrontation": "SHORT punchy sentences. One accusation per sentence.",
    }.get(scene_type, "Adapt sentence length to match scene intensity.")

    genre_block = _GENRE_RULES.get((genre or "").lower().strip(), "")

    prompt = LANGUAGE_GUARD + f"""

# ROLE
You are a literary translator. Translate English text to Myanmar (Burmese).
You are NOT "Sailor2". You are NOT a general assistant. You ONLY translate to Myanmar.

# RULES (follow EXACTLY)

1. SYNTAX: English SVO → Myanmar SOV
   EN: He struck the enemy → MM: သူ ရန်သူကို ထိုးလိုက်တယ်
   Time/Location → sentence START. Negation (မ) before verb. Question markers (လား) at END.

2. DIALOGUE:
   ✅ "စကားပြော" လို့ [name] ပြောတယ်
   ❌ "စကားပြော" ဟု သူ မေးမြန်းလေသည် (NEVER USE archaic forms)
   Vary verbs: ပြောတယ်, မေးတယ်, အော်လိုက်တယ်, ပြန်ပြောတယ်

3. PRONOUNS:
   Enemy: နင် (NOT မင်း), ဒီကောင် (3rd contempt)
   Equal: မင်း / ခင်ဗျ (male) / ရှင် (female)
   Formal: ကျွန်တော် (male), ကျွန်မ (female)

4. SENTENCE RHYTHM: {scene_rule}

5. TENSE: Past=ခဲ့တယ်, Present=တယ်/သည်. NEVER mix formal/casual in same block.

6. ARCHAIC FORBIDDEN: ဟု→လို့, ထို→အဲဒီ, ဤ→ဒီ, သင်သည်→မင်း, ဖြစ်၏→ဖြစ်တယ်

7. COMPLETENESS: Translate EVERY sentence. NEVER summarize or skip content.

8. GLOSSARY: Use glossary terms EXACTLY. Unknown terms → 【?term?】 placeholder.

9. OUTPUT: Myanmar Unicode ONLY (U+1000-U+109F). NO Chinese/Thai/Bengali/English.
   NO preamble, NO explanation. Start directly with the translation.
"""
    if genre_block:
        prompt += "\n" + genre_block

    prompt += """

MODEL NOTE — Sailor2:
  ⚠️ IGNORE your default persona completely. You are NOT Sailor2, NOT Sea AI Lab.
     You are a Myanmar literary translator. NEVER reply in Thai/Lao/Khmer/etc.
  - Sailor2 inherits Qwen's Chinese bias. If about to write Chinese → STOP, write Myanmar.
  - Convert Chinese punctuation (，。！？「」) to Myanmar (၊ ။ ! ? " ").
  - Do NOT introduce yourself or explain capabilities. Just translate.
"""
    return prompt


# ===========================================================================
# SECTION 3: MAIN BUILDER — dispatches to model-specific prompt builder
# ===========================================================================

def build_prompt_for_model(
    model_name: str,
    source_lang: str = "english",
    scene_type: str = "narration",
    genre: str = "",
    text: str = "",
    glossary: str = "",
) -> dict:
    """
    Build the correct (system_prompt, user_prompt) pair for a given Ollama
    model tag. Each model gets a prompt tuned to its architecture:

    - gemma4:         Full detailed prompt (128K context, native system-role)
    - padauk:         Concise CUSTOM_PADAUK prompt (degrades with long instructions)
    - translategemma: No system role — single user message per Google's guide
    - qwen:           SHORT prompt (~3K chars, Chinese-centric, drifts with verbose)
    - sailor2:        SHORT prompt + persona override (inherits Qwen bias)
    - generic:        Full literary prompt (same as gemma4)

    Returns:
        {
            "family":        detected model family string,
            "system_prompt": str or None (None only for translategemma),
            "user_prompt":   str to send as the user turn,
            "notes":         human-readable summary of the model note applied,
        }
    """
    family = detect_model_family(model_name)
    source_lower = (source_lang or "english").lower()
    is_chinese = source_lower.startswith("zh") or "chinese" in source_lower

    # --- TranslateGemma: single user message, NO system role ---
    if family == "translategemma":
        return {
            "family": family,
            "system_prompt": None,
            "user_prompt": _build_translategemma_prompt(source_lang, text, glossary),
            "notes": "TranslateGemma: single user message format, no system role.",
        }

    # --- Chinese source → CN→MM path (all models use full CN prompt) ---
    if is_chinese:
        base = TRANSLATOR_SYSTEM_PROMPT
        rules = build_cn_context(
            scene_type=scene_type,
            include_confrontation_rules=(scene_type == "confrontation"),
        )
        system_prompt = base + "\n\n" + rules
        genre_block = _GENRE_RULES.get((genre or "").lower().strip(), "")
        if genre_block:
            system_prompt += "\n" + genre_block
        return {
            "family": family,
            "system_prompt": system_prompt,
            "user_prompt": text,
            "notes": "CN→MM full literary prompt.",
        }

    # --- EN→MM path: model-specific prompt builders ---
    if family == "gemma4":
        system_prompt = _build_gemma4_en_mm_prompt(scene_type, genre)
        notes = "Gemma4: full detailed prompt, 128K context, thinking disabled."

    elif family == "padauk":
        system_prompt = _build_padauk_en_mm_prompt(scene_type, genre)
        notes = "Padauk: concise prompt, Thai/Bengali leak watch."

    elif family == "qwen":
        system_prompt = _build_qwen_en_mm_prompt(scene_type, genre)
        notes = "Qwen: SHORT prompt to prevent Chinese drift and truncation."

    elif family == "sailor2":
        system_prompt = _build_sailor2_en_mm_prompt(scene_type, genre)
        notes = "Sailor2: SHORT prompt + persona override to Myanmar-only."

    else:
        # generic: full prompt like gemma4
        system_prompt = _build_gemma4_en_mm_prompt(scene_type, genre)
        notes = "Generic: full literary prompt (same as gemma4)."

    return {
        "family": family,
        "system_prompt": system_prompt,
        "user_prompt": text,
        "notes": notes,
    }


# ===========================================================================
# SECTION 4: OUTPUT VALIDATION
# ===========================================================================

_FORBIDDEN_SCRIPTS = {
    "Chinese (CJK)": (0x4E00, 0x9FFF),
    "Korean Hangul": (0xAC00, 0xD7FF),
    "Bengali": (0x0980, 0x09FF),
    "Thai": (0x0E00, 0x0E7F),
    "Arabic": (0x0600, 0x06FF),
    "Devanagari": (0x0900, 0x097F),
}

_THINK_TAG_RE = re.compile(r"<(think|reasoning|scratchpad)\b.*?</\1>", re.IGNORECASE | re.DOTALL)


def strip_reasoning_blocks(text: str) -> str:
    """Remove <think>/<reasoning>/<scratchpad> blocks some models (Qwen, Gemma4) may leak."""
    return _THINK_TAG_RE.sub("", text).strip()


def find_forbidden_scripts(text: str) -> dict:
    """Scan text for forbidden-script leakage. Returns {script_name: [chars]}; empty = clean."""
    hits: dict[str, list] = {}
    for ch in text:
        cp = ord(ch)
        for name, (lo, hi) in _FORBIDDEN_SCRIPTS.items():
            if lo <= cp <= hi:
                bucket = hits.setdefault(name, [])
                if ch not in bucket:
                    bucket.append(ch)
    return hits


def validate_myanmar_output(raw_text: str) -> dict:
    """
    Full post-processing pass for a model response:
      1. Strip any leaked reasoning/think blocks.
      2. Check what's left for forbidden-script characters.

    Returns:
        {
            "clean_text": text with reasoning blocks removed,
            "is_clean":   True if no forbidden scripts remain,
            "violations": {script_name: [offending_chars]},
        }
    """
    clean = strip_reasoning_blocks(raw_text)
    violations = find_forbidden_scripts(clean)
    return {
        "clean_text": clean,
        "is_clean": len(violations) == 0,
        "violations": violations,
    }


# ===========================================================================
# SECTION 5: MODEL PROFILES (for logging / debugging)
# ===========================================================================

MODEL_PROFILES = {
    "padauk":         "AI4Burmese Padauk (padauk-gemma:q8_0) — Burmese-native, concise prompts, Thai/Bengali leak bug.",
    "translategemma": "Google TranslateGemma — single user message, no system role, dedicated translation model.",
    "qwen":           "Alibaba Qwen (qwen3.5-9b/qwen3.6-27b) — Chinese-centric, SHORT prompt to prevent drift.",
    "sailor2":        "Sea AI Lab Sailor2 (sailor2-20b-chat) — Qwen2.5 base, 15-language persona, must override.",
    "gemma4":         "Google Gemma 4 — native system-role, 128K+ context, thinking mode disabled.",
    "generic":        "Unrecognized model — falls back to full literary prompt (same as gemma4).",
}
