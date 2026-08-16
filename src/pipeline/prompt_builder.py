"""Prompt assembly (SPEC.md §2.3, PROMPTS.md §2/§6).

Micro-prompts:
- MP1 analyze/tag (JSON)
- MP2 draft translate
- MP3 literary polish
- MP4 format normalize (handled deterministically by postprocessor)

Constraints:
- glossary terms injected longest-first (TEST-PROMPT-001)
- total prompt tokens <= ``max_ctx - reserve`` (TEST-PROMPT-002)
- few-shot examples for the chunk category win (TEST-PROMPT-003)
"""
from __future__ import annotations

from typing import List, Optional, Sequence

from .models import Chunk, FewShotPair

RESERVE_FOR_OUTPUT = 512
MAX_CTX_DEFAULT = 8192

TRANSLATOR_SYSTEM = """You are a master literary translator translating Chinese web novels from English source into Burmese.
You preserve character voices distinctly. You adapt cultural references naturally. You never produce machine-like text.
FIDELITY: Capture exact meaning, including subtext and emotion.
FLUENCY: Write as a Burmese novelist would write.
VOICE: Each character has a unique speech fingerprint.
REGISTER: Dialogue is spoken; narration is literary.
You work in micro-steps. You never output thinking tags or meta-commentary. You only output the final Burmese text."""


def estimate_tokens(text: str) -> int:
    """Rough token estimate (EN+MY chars are roughly 3-4 per token)."""
    return max(1, len(text or "") // 3)


def fit_context(
    sections: Sequence[str],
    budget_tokens: int,
) -> str:
    """Join sections, then trim the *context* portion to fit ``budget_tokens``."""
    joined = "\n\n".join(s for s in sections if s)
    if estimate_tokens(joined) <= budget_tokens:
        return joined
    # Drop from the tail (context is least critical near the source text).
    kept: List[str] = []
    used = 0
    for section in sections:
        if not section:
            continue
        est = estimate_tokens(section)
        if used + est > budget_tokens:
            leftovers = budget_tokens - used
            if leftovers > 20:
                kept.append(section[: leftovers * 3])
            break
        kept.append(section)
        used += est
    return "\n\n".join(kept)


def select_few_shots(
    few_shots: Sequence[FewShotPair],
    chunk_type: str,
    n: int = 3,
) -> List[FewShotPair]:
    """Prefer few-shots whose category matches the chunk type (TEST-PROMPT-003)."""
    if not few_shots:
        return []
    category = "dialogue" if chunk_type == "dialogue-heavy" else "narration" if chunk_type == "narration-heavy" else "mixed"
    priority = [
        fs for fs in few_shots if category in fs.category or fs.category == chunk_type
    ]
    if len(priority) < n:
        seen = {id(fs) for fs in priority}
        priority += [fs for fs in few_shots if id(fs) not in seen]
    return priority[:n]


def render_few_shots(few_shots: Sequence[FewShotPair]) -> str:
    if not few_shots:
        return ""
    lines = [
        "Below are HUMAN-WRITTEN reference examples (English -> natural literary Myanmar) "
        "from the same novel. Match the style, register and terminology; do NOT copy verbatim."
    ]
    for i, fs in enumerate(few_shots, 1):
        lines.append(f"({i}) ref EN: {fs.source}")
        lines.append(f"    ref MY: {fs.translation}")
    return "\n".join(lines)


def render_context(context: Optional[dict]) -> str:
    """ContextBuffer -> prompt section (SPEC §3.4)."""
    if not context:
        return ""
    parts = []
    if context.get("preceding_summary"):
        parts.append(f"Scene summary: {context['preceding_summary']}")
    if context.get("active_speakers"):
        speakers_lines = []
        for name, info in context["active_speakers"].items():
            pronoun = info.get("pronoun") or info.get("last_used_pronoun") or ""
            mood = info.get("mood") or ""
            speakers_lines.append(f"- {name}: pronoun={pronoun or '?'}{', mood=' + mood if mood else ''}")
        if speakers_lines:
            parts.append("Active speakers:" + "\n" + "\n".join(speakers_lines))
    if context.get("preceding_chunks"):
        parts.append("Recent translated text:")
        for pc in context["preceding_chunks"][-context.get("max_preceding_chunks", 2):]:
            text = pc.get("translated_text") or ""
            if text:
                parts.append(text)
    return "\n\n".join(parts)


# --------------------------------------------------------------------------- #
# Micro-prompt builders
# --------------------------------------------------------------------------- #
def build_analyze_prompt(chunk: Chunk) -> str:
    return (
        "Analyze the following English text chunk from a horror novel. Provide a JSON response.\n"
        'Text:\n"""\n' + chunk.source_text + '\n"""\n'
        'Return ONLY JSON: {"speakers":[],"scene_type":"","emotional_tone":"","setting":"","key_terms":[],"translation_notes":""}'
    )


def build_draft_prompt(
    chunk: Chunk,
    glossary_section: str = "",
    context_section: str = "",
    few_shot_section: str = "",
    rules_section: str = "",
) -> str:
    parts = [
        "DRAFT PHASE: Translate the following English text into Burmese. Focus on accuracy - do not worry about literary polish yet.",
    ]
    if glossary_section:
        parts.append(glossary_section)
    if context_section:
        parts.append("CONTEXT (what happened before):\n" + context_section)
    if few_shot_section:
        parts.append("FEW-SHOT EXAMPLES:\n" + few_shot_section)
    if rules_section:
        parts.append(rules_section)
    parts.append("Preserve paragraph structure. For dialogue, keep the speaking voice natural.")
    if chunk.preceding_overlap:
        parts.append(
            'The chunk STARTS with an OVERLAP paragraph from the previous chunk. '
            'Reproduce it EXACTLY at the start:\n"""\n' + chunk.preceding_overlap + '\n"""'
        )
    parts.append('SOURCE TEXT:\n"""\n' + chunk.source_text + '\n"""')
    parts.append("Output ONLY the Burmese translation. No explanations, no thinking tags.")
    return "\n\n".join(parts)


def build_polish_prompt(chunk: Chunk, draft: str, style_guide: str = "", voice_guide: str = "") -> str:
    parts = [
        "LITERARY POLISH phase. Turn the Burmese draft below into literary prose.",
        'DRAFT TEXT:\n"""\n' + (draft or "") + '\n"""',
    ]
    if voice_guide:
        parts.append("CHARACTER VOICE GUIDE:\n" + voice_guide)
    if style_guide:
        parts.append("STYLE RULES:\n" + style_guide)
    else:
        parts.append(
            "STYLE RULES: Narration uses literary endings (လေသည်, ရလေသည်, ခြင်း ဖြစ်သည်) and varies them. "
            "Dialogue uses spoken Burmese (တယ်, လား, ပဲ, ကွာ, နော်, ဗျာ). NEVER mix literary and spoken endings in the same sentence. "
            "Preserve all meaning. Keep paragraph structure identical to the draft."
        )
    parts.append("Output ONLY the polished Burmese text. No explanations.")
    return "\n\n".join(parts)


def normalize_prompt_marker() -> str:
    """Marker used to detect the (optional) MP4 pass."""
    return "FORMAT NORMALIZE phase"


def build_normalize_prompt(polished: str, expected_overlap: str = "") -> str:
    parts = [
        "FORMAT NORMALIZE phase: normalize the following Burmese text for technical compliance.",
        'TEXT:\n"""\n' + (polished or "") + '\n"""',
        "Rules: use Burmese quotes only; remove zero-width spaces; no thinking tags; "
        "keep paragraphs separated by blank lines; no English words except glossary terms.",
    ]
    if expected_overlap:
        parts.append("The start must match EXACTLY:\n" + expected_overlap)
    parts.append("Output ONLY the normalized text.")
    return "\n\n".join(parts)


def assembled_prompt(
    chunk: Chunk,
    *,
    glossary_section: str = "",
    context_section: str = "",
    few_shot_section: str = "",
    rules_section: str = "",
    max_ctx: int = MAX_CTX_DEFAULT,
) -> str:
    """The §6 assembly template with context-budget enforcement."""
    full = build_draft_prompt(
        chunk, glossary_section, context_section, few_shot_section, rules_section
    )
    if estimate_tokens(full) <= max_ctx - RESERVE_FOR_OUTPUT:
        return full
    budget_for_ctx = (
        max_ctx
        - RESERVE_FOR_OUTPUT
        - estimate_tokens(glossary_section)
        - estimate_tokens(few_shot_section)
        - estimate_tokens(chunk.source_text)
        - 40
    )
    if budget_for_ctx > 40:
        context_section = fit_context([context_section], budget_for_ctx)
        return build_draft_prompt(
            chunk, glossary_section, context_section, few_shot_section, rules_section
        )
    return full