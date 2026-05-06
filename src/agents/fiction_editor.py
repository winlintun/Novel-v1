"""
Fiction Editor Agent
Sentence/paragraph-level rewriting for natural Myanmar fiction flow.
Supports: tone presets, humanize, custom rewrite instructions.
"""

import logging
from typing import Optional

from src.utils.ollama_client import OllamaClient
from src.utils.postprocessor import clean_output

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# System prompt shared by all editor operations
# ─────────────────────────────────────────────────────────────
_BASE_SYSTEM = """You are an expert Myanmar literary editor for translated fiction novels.
You receive a Myanmar paragraph and rewrite it according to the instruction.

ABSOLUTE RULES:
- Output ONLY the rewritten Myanmar text. Zero English. Zero meta-commentary.
- Do NOT add "Here is the rewritten text:" or any preamble.
- Do NOT change story facts, character names, or plot events.
- Preserve all Markdown: *italic*, **bold**, # headings, > quotes.
- Use ONLY Myanmar Unicode (U+1000-U+109F, U+AA60-U+AA7F, U+A9E0-U+A9FF).
- NEVER output Korean (봐 봤자), Bengali (গাঢ়), Arabic (؟), or Chinese characters.
- Correct any mixed-script errors you find in the input as you rewrite.
"""

# ─────────────────────────────────────────────────────────────
# Tone instruction snippets
# ─────────────────────────────────────────────────────────────
TONE_PROMPTS = {
    "humanize": (
        "Fix robotic or mechanical-sounding phrasing. "
        "The translation should read as if a fluent native Myanmar speaker wrote it naturally. "
        "Keep meaning identical. Improve rhythm, word choice, and particle usage only."
    ),
    "dramatic": (
        "Rewrite with a dramatic, emotionally intense tone suitable for confrontation or climax scenes.\n"
        "Rules:\n"
        "- Enemy/hostile address: use နင် (not မင်း)\n"
        "- Accusation speeches: drop ခဲ့ particle for vivid present-intensity\n"
        "- One accusation per sentence — split comma-chained lists\n"
        "- Narration register: သည်/၏/ဖြင့် (literary), NOT တယ် (casual)\n"
        "- Hatred idiom: အရိုးစွဲအောင် မုန်း (bone-deep), NOT မီးလို မုန်းတီး\n"
        "- Death threat: declarative fate, e.g. 'ဒီနေ့ နင်သေရမယ်!' (NOT 'မင်းသေစေချင်တယ်')\n"
        "- Show emotions through physical sensation, not abstract labels."
    ),
    "casual": (
        "Rewrite in a natural, conversational Myanmar tone for light or everyday scenes.\n"
        "Rules:\n"
        "- Use တယ်/ဘူး/မယ် particles throughout\n"
        "- Sentence length: 8-14 words, flowing\n"
        "- Dialogue: '...' လို့ [character] ပြောတယ် format\n"
        "- Pronouns: မင်း (neutral), ကျွန်တော်/ကျွန်မ (formal self)\n"
        "- Avoid archaic ဟု / လေသည် patterns."
    ),
    "literary": (
        "Rewrite in formal Myanmar literary style suitable for epic or serious narrative.\n"
        "Rules:\n"
        "- Narration: သည်/၏/သော/ဖြင့်/တွင် particles throughout\n"
        "- Avoid colloquial တယ်/ဟာ/နဲ့ in narration blocks\n"
        "- Sentence length: 12-20 words, dignified and flowing\n"
        "- Verb choice: precise literary verbs (ဝတ်ထားသည်, မြင်တွေ့ရသည်)\n"
        "- Emotion: physical/sensory description over abstract labels."
    ),
    "action": (
        "Rewrite for a fast-paced action or combat scene.\n"
        "Rules:\n"
        "- Sentence length: 3-7 words MAX per sentence\n"
        "- Each sentence = one action beat\n"
        "- Use active, punchy verbs: ထိုးလိုက်တယ်, ကာလိုက်တယ်, ဆုတ်ခဲ့တယ်\n"
        "- No long subordinate clauses\n"
        "- Fast rhythm — read aloud and feel the speed."
    ),
    "romantic": (
        "Rewrite with a gentle, poetic, romantic tone.\n"
        "Rules:\n"
        "- Slightly longer sentences with soft rhythm (10-16 words)\n"
        "- Sensory and imagery-rich language: warmth, light, breath, heartbeat\n"
        "- Show emotion through physical sensation: 'သူ့ရင်ထဲ နွေးထွေးမှု ပြည့်လျှံသွားတယ်'\n"
        "- Avoid blunt emotional labels like 'သူ ချစ်မိသွားတယ်' alone — add sensory depth\n"
        "- Dialogue: soft, measured, intimate register."
    ),
}


def _build_prompt(text: str, tone: str, custom_instruction: str = "") -> tuple[str, str]:
    """Return (system_prompt, user_prompt) for the given tone."""
    if tone == "custom":
        instruction = custom_instruction.strip() or "Improve the quality and naturalness of this text."
    else:
        instruction = TONE_PROMPTS.get(tone, TONE_PROMPTS["humanize"])

    system = _BASE_SYSTEM + f"\nTASK: {instruction}\n"
    user = f"Rewrite the following Myanmar text:\n\n{text}\n\nREWRITTEN MYANMAR TEXT:"
    return system, user


class FictionEditor:
    """
    AI-powered editing agent for Myanmar fiction translations.
    Each call is stateless — pass the Ollama client from the caller.
    """

    def __init__(
        self,
        model: str = "padauk-gemma:q8_0",
        base_url: str = "http://localhost:11434",
        temperature: float = 0.4,
        num_ctx: int = 4096,
        config: Optional[dict] = None,
    ):
        cfg_models = (config or {}).get("models", {})
        cfg_proc = (config or {}).get("processing", {})

        self.model = cfg_models.get("editor", model)
        self.base_url = cfg_models.get("ollama_base_url", base_url)
        self.temperature = cfg_proc.get("temperature", temperature)
        self.num_ctx = cfg_models.get("num_ctx", num_ctx)

    def _get_client(self) -> OllamaClient:
        return OllamaClient(
            model=self.model,
            base_url=self.base_url,
            temperature=self.temperature,
            num_ctx=self.num_ctx,
            max_retries=2,
            timeout=120,
            unload_on_cleanup=False,
        )

    def rewrite(self, text: str, tone: str = "humanize", custom_instruction: str = "") -> str:
        """
        Rewrite a Myanmar paragraph with the given tone preset or custom instruction.

        Args:
            text: Myanmar text to rewrite
            tone: One of humanize / dramatic / casual / literary / action / romantic / custom
            custom_instruction: Used only when tone == "custom"

        Returns:
            Rewritten Myanmar text, or original text on failure.
        """
        if not text.strip():
            return text

        system, user = _build_prompt(text, tone, custom_instruction)

        try:
            client = self._get_client()
            raw = client.chat(prompt=user, system_prompt=system)
            result = clean_output(raw).strip()
            if not result:
                logger.warning("FictionEditor returned empty output — returning original")
                return text
            return result
        except Exception as e:
            logger.error(f"FictionEditor.rewrite failed: {e}")
            return text

    def humanize(self, text: str) -> str:
        """Convenience wrapper: fix robotic phrasing."""
        return self.rewrite(text, tone="humanize")

    def suggest_alternatives(self, text: str, tone: str = "humanize", n: int = 2) -> list[str]:
        """
        Generate multiple rewrite alternatives for the user to choose from.

        Args:
            text: Myanmar text to rewrite
            tone: Tone preset
            n: Number of alternatives (max 3 to stay fast)

        Returns:
            List of rewritten alternatives (may be fewer than n on error)
        """
        n = min(n, 3)
        results = []
        for _ in range(n):
            alt = self.rewrite(text, tone=tone)
            if alt and alt not in results:
                results.append(alt)
        return results or [text]
