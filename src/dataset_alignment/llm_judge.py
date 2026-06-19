"""Optional LLM-as-judge for auditing alignment quality."""

import json
import logging
from dataclasses import dataclass
from typing import Optional

from src.dataset_alignment.config import get_alignment_config

logger = logging.getLogger(__name__)

JUDGE_PROMPT = """You are auditing a Chinese/English -> Burmese (Myanmar) literary
translation for a Wuxia/Xianxia web-novel pipeline. Be strict but fair.

SOURCE ({src_lang}):
\"\"\"
{src}
\"\"\"

TARGET (Burmese):
\"\"\"
{tgt}
\"\"\"

Return ONLY a JSON object with these keys:
  faithful:        bool   (no hallucination, no significant omission)
  fluent:          bool   (natural literary Burmese)
  tone_preserved:  bool   (register, humor, gravity match)
  terminology_ok:  bool   (cultivation/Wuxia terms consistent)
  rating:          int    (0-5; 5 = publication quality, 0 = unusable)
  issues:          list of short strings (max 5)
  fix_suggestion:  string (optional)

Output JSON only. No prose."""


@dataclass
class JudgeVerdict:
    faithful: bool
    fluent: bool
    tone_preserved: bool
    terminology_ok: bool
    rating: int
    issues: list[str]
    fix_suggestion: str


def judge_pair(
    src: str,
    tgt: str,
    src_lang: str = "English",
) -> Optional[JudgeVerdict]:
    """Send a single EN/MM pair to the LLM judge."""
    cfg = get_alignment_config()
    if not cfg.get("alignment_pipeline", "llm_judge", "enabled", default=False):
        return None

    provider = cfg.get("alignment_pipeline", "llm_judge", "provider", default="ollama")
    model = cfg.get("alignment_pipeline", "llm_judge", "model", default="qwen2.5:14b")

    if provider == "ollama":
        return _ollama_judge(src, tgt, src_lang, model)
    logger.warning(f"Unknown llm_judge.provider: {provider}")
    return None


def _parse(raw: str) -> Optional[JudgeVerdict]:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:].lstrip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning(f"Judge returned non-JSON: {raw[:200]}")
        return None
    return JudgeVerdict(
        faithful=bool(data.get("faithful", False)),
        fluent=bool(data.get("fluent", False)),
        tone_preserved=bool(data.get("tone_preserved", False)),
        terminology_ok=bool(data.get("terminology_ok", False)),
        rating=int(data.get("rating", 0)),
        issues=list(data.get("issues", []))[:5],
        fix_suggestion=str(data.get("fix_suggestion", "")),
    )


def _ollama_judge(src: str, tgt: str, src_lang: str, model: str) -> Optional[JudgeVerdict]:
    try:
        from src.utils.ollama_client import OllamaClient
        client = OllamaClient(model=model, timeout=60, max_retries=1)
        prompt = JUDGE_PROMPT.format(src_lang=src_lang, src=src, tgt=tgt)
        system = "You are a translation quality auditor. Respond ONLY with valid JSON."
        response = client.chat(prompt=prompt, system_prompt=system)
        return _parse(response)
    except Exception as e:
        logger.warning(f"Ollama judge failed: {e}")
        return None
