"""LLM verification step for glossary candidate terms.

Uses Ollama to verify/improve candidate term translations
before inserting into the database.
"""

import logging
import json
from typing import Optional

logger = logging.getLogger(__name__)

LLM_VERIFY_PROMPT = """You are a xianxia novel translation specialist (EN→MY).
Verify these glossary term candidates mined from parallel text.

For each term, respond with a JSON object:
{{
  "source_term": "...",
  "target_term": "..." or null if uncertain,
  "confidence": 0.0-1.0,
  "category": "character|location|technique|cultivation_concept|item_artifact|title_honorific|general",
  "is_valid": true/false,
  "notes": "reasoning or null"
}}

Rules:
- Only confirm translations you are CERTAIN about
- Set confidence < 0.5 if unsure
- Set is_valid=false if the term is common English (not a glossary term)
- Prefer Myanmar literary/xianxia conventions for cultivation terms
- Category must match: character, location, technique, cultivation_concept, item_artifact, title_honorific, general

Terms to verify:
{terms_json}
"""


def verify_candidate(
    candidate: dict,
    ollama_client: Optional[object] = None,
    model: str = "qwen2.5:14b",
) -> dict:
    """Verify a single candidate term using LLM.

    Args:
        candidate: Candidate dict with 'source_term', 'contexts'
        ollama_client: Optional OllamaClient instance
        model: Model name for verification

    Returns:
        Candidate dict with LLM verification results added
    """
    source = candidate["source_term"]
    contexts = candidate.get("contexts", [])

    context_str = "\n".join(f"- {c}" for c in contexts) if contexts else "No context available"

    prompt = f"""Term: {source}
Context sentences:
{context_str}

Respond ONLY with JSON:
{{
  "source_term": "{source}",
  "target_term": null,
  "confidence": 0.5,
  "category": "general",
  "is_valid": true,
  "notes": null
}}"""

    if ollama_client is None:
        candidate["llm_verified"] = False
        candidate["llm_confidence"] = candidate.get("confidence", 0.5)
        candidate["llm_target"] = None
        candidate["llm_notes"] = "No LLM available for verification"
        return candidate

    try:
        system_prompt = LLM_VERIFY_PROMPT.replace("{terms_json}", json.dumps([{"source_term": source, "contexts": contexts}]))
        response = ollama_client.chat(
            prompt=prompt,
            system_prompt=system_prompt,
            model=model,
        )
        content = response.strip()
        content = content.replace("```json", "").replace("```", "").strip()

        result = json.loads(content)

        candidate["llm_verified"] = result.get("is_valid", False)
        candidate["llm_confidence"] = result.get("confidence", candidate.get("confidence", 0.5))
        candidate["llm_target"] = result.get("target_term")
        candidate["llm_notes"] = result.get("notes")
        candidate["category"] = result.get("category", candidate.get("category", "general"))

        if result.get("is_valid") and result.get("target_term"):
            candidate["confidence"] = max(candidate.get("confidence", 0), result.get("confidence", 0.5))
            if result.get("target_term") != f"【?{source}?】":
                candidate["target_term"] = result["target_term"]

        logger.debug(f"LLM verified '{source}': valid={result.get('is_valid')}, conf={result.get('confidence')}")

    except Exception as e:
        logger.warning(f"LLM verification failed for '{source}': {e}")
        candidate["llm_verified"] = False
        candidate["llm_confidence"] = candidate.get("confidence", 0.5)
        candidate["llm_notes"] = f"LLM error: {e}"

    return candidate
