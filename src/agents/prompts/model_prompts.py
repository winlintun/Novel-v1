"""
model_prompts.py
=================
Model-aware prompt layer for the CN/EN → Myanmar translation pipeline.

PLACE THIS FILE next to the existing modules, i.e.:
    src/agents/prompts/model_prompts.py
    src/agents/prompts/language_guards.py   (existing)
    src/agents/prompts/cn_mm_rules.py       (existing)
    src/agents/prompts/en_mm_rules.py       (existing)
    src/agents/prompts/system_prompts.py    (existing)

WHY THIS FILE EXISTS
--------------------
system_prompts.py already picks a base prompt by SOURCE LANGUAGE (Chinese vs
English) and has one special case for "padauk" in the model name. It does NOT
otherwise know which Ollama model is actually generating the translation.

In practice, each Ollama model family leaks non-Myanmar script or breaks
format in a DIFFERENT, predictable way:

    padauk-gemma      -> occasionally leaks Thai/Bengali script (known bug)
    translategemma    -> ignores long literary instructions; needs its own
                         fixed single-message template (per Google's prompt
                         guide), not the full system prompt
    qwen3.5 / qwen3.6 -> Chinese-centric base model; drifts back into
                         Chinese, and may emit <think>/reasoning blocks
                         when "thinking preservation" is enabled
    sailor2-20b-chat  -> ships with its OWN default persona/system prompt
                         that explicitly offers Thai/Lao/Khmer/Vietnamese/
                         etc. output — this must be overridden per call
    gemma4            -> native system-role + configurable thinking mode;
                         thinking traces must not leak into the final answer

This module adds a MODEL PROFILE layer on top of the existing prompt
builders so every model converges on the same goal: Myanmar Unicode ONLY,
zero leakage, zero preamble — instead of relying on one generic guard for
every model.

USAGE
-----
    from src.agents.prompts.model_prompts import build_prompt_for_model, validate_myanmar_output

    result = build_prompt_for_model(
        model_name="padauk-gemma:q8_0",
        source_lang="english",
        scene_type="dialogue",
        genre="xianxia",
        text=chunk_text,
        glossary=glossary_str,
    )
    # result["system_prompt"] -> str or None (TranslateGemma uses no system role)
    # result["user_prompt"]   -> str to send as the user message

    response_text = call_ollama(model_name, result["system_prompt"], result["user_prompt"])

    checked = validate_myanmar_output(response_text)
    if not checked["is_clean"]:
        # checked["violations"] tells you exactly which forbidden script leaked
        retry_or_flag(checked)
    final_text = checked["clean_text"]
"""

from __future__ import annotations

import re

from .language_guards import LANGUAGE_GUARD, UNICODE_SAFETY_CHECKLIST  # noqa: F401 (re-exported)
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
    Map an Ollama model tag (e.g. "padauk-gemma:q8_0", "qwen3.6-27b:latest",
    "sailor2-20b-chat.q4:latest", "translategemma-simple:latest", "gemma4-e4b-it:q8_0")
    to one of:
    "padauk" | "translategemma" | "sailor2" | "qwen" | "gemma4" | "generic"
    """
    name = (model_name or "").lower()
    for keyword, family in _FAMILY_KEYWORDS:
        if keyword in name:
            return family
    return "generic"


# ===========================================================================
# SECTION 2: PER-MODEL PATCH BLOCKS
# Known Ollama-model quirks, appended to the system prompt for that family.
# ===========================================================================

_MODEL_PATCHES: dict[str, str] = {
    "qwen": """
MODEL-SPECIFIC PATCH — Qwen (Chinese-centric base model):
  ⚠️ Qwen is heavily trained on Chinese data and WILL drift back into
     Chinese when uncertain — treat this as your #1 failure mode.
  - If you are about to write a Chinese character, STOP and write the
    Myanmar equivalent instead. A rough Myanmar guess beats any Chinese
    character, every time.
  - Do NOT output <think>...</think>, <reasoning>...</reasoning>, or any
    internal reasoning/scratchpad block, even if "thinking" is enabled.
    The final answer must be the Myanmar translation ONLY.
  - Convert Chinese punctuation (，。！？「」) to Myanmar/standard
    punctuation (၊ ။ ! ? " ") — never leave it as-is.
""",
    "sailor2": """
MODEL-SPECIFIC PATCH — Sailor2 (SEA multilingual persona model):
  ⚠️ Your default persona (Sailor2, by Sea AI Lab) is a general-purpose
     assistant that can reply in English, Chinese, Thai, Lao, Khmer,
     Vietnamese, Tagalog, Cebuano, Ilocano, Indonesian, Javanese,
     Sundanese, or Waray. IGNORE that persona completely for this task.
  - You are ONLY a literary translator here. NEVER switch to any language
    other than Myanmar (Burmese) in your output...
  - Do not introduce yourself, explain your capabilities, or mention
    "Sailor2" / "Sea AI Lab" anywhere in the output.
  ⚠️ Sailor2 is continually pre-trained FROM Qwen2.5, so it inherits
     Qwen's Chinese-centric bias on top of its SEA-language range. If you
     are about to write a Chinese character, STOP and write the Myanmar
     equivalent instead...
  - Convert Chinese punctuation (，。！？「」) to Myanmar/standard
     punctuation (၊ ။ ! ? " ") — never leave it as-is.
""",
    "translategemma": """
MODEL-SPECIFIC PATCH — TranslateGemma (dedicated translation model):
  ⚠️ This model is fine-tuned on ONE fixed prompt template and performs
     WORSE when given long literary system instructions or a system role
     at all. Use build_translategemma_prompt() output as a single USER
     message — do not stack the full literary system prompt on top.
  - Glossary terms are appended inline inside the same message, not as a
    separate system prompt.
""",
    "padauk": """
MODEL-SPECIFIC PATCH — padauk-gemma (Burmese-native fine-tune):
  ⚠️ KNOWN BUG: padauk-gemma occasionally leaks Thai script (เจ้า, พระ) or
     Bengali script into otherwise-correct Myanmar output, especially over
     long chapters. Re-scan every paragraph for U+0E00–U+0E7F and
     U+0980–U+09FF before finishing.
  - This model degrades with over-long instructions — prefer the concise
    CUSTOM_PADAUK_*_MM_PROMPT over the full literary system prompt.
""",
    "gemma4": """
MODEL-SPECIFIC PATCH — Gemma 4 (native system-role, configurable thinking):
  ⚠️ Gemma 4 supports a "thinking mode". For this pipeline thinking MUST
     be disabled at the API/Ollama-options level; if a trace still
     appears, treat it as a bug — the final answer must contain ONLY the
     Myanmar translation, no reasoning trace, no restated instructions.
""",
    "generic": "",
}


# ===========================================================================
# SECTION 3: TRANSLATEGEMMA — fixed single-message template
# (per the official TranslateGemma prompt guide: two blank lines before TEXT)
# ===========================================================================

_LANG_NAME_CODE = {
    "chinese": ("Chinese", "zh"),
    "zh": ("Chinese", "zh"),
    "zh-cn": ("Chinese", "zh"),
    "english": ("English", "en"),
    "en": ("English", "en"),
}


def build_translategemma_prompt(source_lang: str, text: str, glossary: str = "") -> str:
    """Build the single user message TranslateGemma expects."""
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


# ===========================================================================
# SECTION 4: MAIN BUILDER — model-aware system/user prompt pair
# ===========================================================================

def _build_en_mm_core_rules(scene_type: str = "narration") -> str:
    """Condensed EN→MM rules for models that degrade with long prompts (Qwen, Sailor2).
    
    Extracts only the critical rules from build_en_context() — SVO→SOV,
    dialogue format, pronouns, tense, unicode safety — without the verbose
    examples and cultural deep-dives that bloat the full prompt.
    """
    scene_rule = {
        "narration":    "Medium sentences (10-18 words). Literary style.",
        "dialogue":     "Short natural sentences. Real speech rhythm.",
        "action":       "SHORT sentences (3-7 words). Fast rhythm. Active verbs.",
        "confrontation": "SHORT punchy sentences. One accusation per sentence.",
    }.get(scene_type, "Adapt sentence length to match scene intensity.")

    return """
[EN→MM TRANSLATION RULES — CONDENSED]

1. SVO→SOV: English Subject+Verb+Object → Myanmar Subject+Object+Verb
   EN: He struck the enemy → MM: သူ ရန်သူကို ထိုးလိုက်တယ်
   Time/Location → sentence START. Negation (မ) before verb. Question markers (လား) at END.

2. DIALOGUE:
   ✅ "စကားပြော" လို့ [name] ပြောတယ်
   ❌ "စကားပြော" ဟု သူ မေးမြန်းလေသည် (NEVER USE archaic ဟု/လေသည်)
   Vary verbs: ပြောတယ်, မေးတယ်, အော်လိုက်တယ်, ပြန်ပြောတယ်

3. PRONOUNS:
   Enemy: နင် (NOT မင်း), ဒီကောင် (3rd contempt)
   Equal: မင်း / ခင်ဗျ (male) / ရှင် (female)
   Formal self: ကျွန်တော် (male), ကျွန်မ (female)

4. SENTENCE RHYTHM: {scene_rule}

5. TENSE: Past=ခဲ့တယ်, Present=တယ်/သည်, NEVER mix formal/casual in same block.

6. SHOW EMOTIONS PHYSICALLY:
   ❌ သူ ဝမ်းနည်းတယ် (abstract)
   ✅ သူ့ရင်ထဲမှာ တစ်ခုခု ကျိုးသွားသလို ဖြစ်မိတယ် (physical)

7. ARCHAIC FORBIDDEN: ဟု→လို့, ထို→အဲဒီ, ဤ→ဒီ, သင်သည်→မင်း, ဖြစ်၏→ဖြစ်တယ်

8. UNICODE: Myanmar ONLY (U+1000-U+109F). NO Chinese/Thai/Bengali/English in output.
   Use 【?term?】 for unknowns. Preserve Markdown formatting.
"""


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
    model tag, source language, scene, and genre, with known per-model
    failure modes patched in.

    Each model family gets a differently-sized prompt tuned to its strengths:

    - padauk:         Concise CUSTOM_PADAUK prompt only (degrades with long instructions)
    - translategemma: No system role — single user message per Google's prompt guide
    - qwen:           Condensed core rules (Chinese-centric base, drifts with verbose prompts)
    - sailor2:        Condensed rules + strong persona override (inherits Qwen bias)
    - gemma4:         Full literary prompt (native system-role, 128K+ context)
    - generic:        Full literary prompt + full rules

    Returns a dict:
        {
            "family":        detected model family string,
            "system_prompt": str or None (None only for translategemma),
            "user_prompt":   str to send as the user turn,
            "notes":         human-readable summary of the patch applied,
        }
    """
    family = detect_model_family(model_name)
    source_lower = (source_lang or "english").lower()
    is_chinese = source_lower.startswith("zh") or "chinese" in source_lower

    # --- TranslateGemma: fixed single-message template, no system role ---
    # Per model_detail.md: expects EXACTLY one user message with two blank
    # lines before the text. No system role at all.
    if family == "translategemma":
        return {
            "family": family,
            "system_prompt": None,
            "user_prompt": build_translategemma_prompt(source_lang, text, glossary),
            "notes": _MODEL_PATCHES["translategemma"],
        }

    genre_block = _GENRE_RULES.get((genre or "").lower().strip(), "")
    patch = _MODEL_PATCHES.get(family, "")

    # --- Chinese source → CN→MM path (unchanged) ---
    if is_chinese:
        base = TRANSLATOR_SYSTEM_PROMPT
        rules = build_cn_context(
            scene_type=scene_type,
            include_confrontation_rules=(scene_type == "confrontation"),
        )
        system_prompt = base + "\n\n" + rules
        if genre_block:
            system_prompt += "\n" + genre_block
        if patch:
            system_prompt += "\n" + patch
        return {
            "family": family,
            "system_prompt": system_prompt,
            "user_prompt": text,
            "notes": patch or "No model-specific patch needed for this family.",
        }

    # --- EN→MM path: model-specific prompt sizing ---

    if family == "padauk":
        # Padauk: Burmese-native fine-tune. Use ONLY the concise custom prompt.
        # Per model_detail.md: "designed for daily questions and quick answers"
        # It degrades with over-long instructions. No extra rules appended.
        system_prompt = CUSTOM_PADAUK_EN_MM_PROMPT

    elif family in ("qwen", "sailor2"):
        # Qwen/Sailor2: Chinese-centric base models. Use condensed core rules
        # only — the full 15K-char prompt causes drift and confusion.
        # Sailor2 inherits Qwen2.5 bias, so same treatment.
        condensed_rules = _build_en_mm_core_rules(scene_type=scene_type)
        system_prompt = ENGLISH_TRANSLATOR_SYSTEM_PROMPT + "\n\n" + condensed_rules

    else:
        # gemma4 / generic: Full literary prompt + full linguistic rules.
        # Gemma4 has native system-role support and 128K+ context window.
        full_rules = build_en_context(source_lang=source_lang, scene_type=scene_type)
        system_prompt = ENGLISH_TRANSLATOR_SYSTEM_PROMPT + "\n\n" + full_rules

    if genre_block:
        system_prompt += "\n" + genre_block
    if patch:
        system_prompt += "\n" + patch

    return {
        "family": family,
        "system_prompt": system_prompt,
        "user_prompt": text,
        "notes": patch or "No model-specific patch needed for this family.",
    }


# ===========================================================================
# SECTION 5: OUTPUT VALIDATION
# Operationalizes UNICODE_SAFETY_CHECKLIST instead of relying on the prompt
# alone — run this on every model response before accepting it.
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
# SECTION 6: QUICK MODEL PROFILE REFERENCE (for logging / debugging)
# ===========================================================================

MODEL_PROFILES = {
    "padauk":         "AI4Burmese Padauk (padauk-gemma:q8_0) — Burmese-native Gemma finetune (8.0 GB). Fast, but has a known Thai/Bengali leak bug on long chapters. Use concise CUSTOM_PADAUK_* prompts.",
    "translategemma": "Google TranslateGemma (translategemma-simple:latest) — dedicated translation model (7.3 GB). Needs its OWN fixed single-message template, no system role, no long literary instructions.",
    "qwen":           "Alibaba Qwen (qwen3.5-9b:latest / qwen3.6-27b:latest) — Chinese-centric base, strong agentic/coding skills. Prone to drifting back into Chinese and to leaking <think> blocks when 'thinking preservation' is on.",
    "sailor2":        "Sea AI Lab Sailor2 (sailor2-20b-chat.q4:latest) — SEA multilingual, built on Qwen2.5 (11 GB). Ships with a default persona that can answer in 15 languages; must be explicitly overridden to Myanmar-only.",
    "gemma4":         "Google Gemma 4 (gemma4-e4b-it:q8_0) — native system-role support, configurable thinking mode, 128K/256K context (8.2 GB). Thinking traces must not leak into final output.",
    "generic":        "Unrecognized model tag — falls back to the standard literary system prompt with no model-specific patch.",
}