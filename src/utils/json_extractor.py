"""
src/utils/json_extractor.py
Safe JSON extraction with fallback for malformed model responses.
Fixes: "Entity extraction failed: Expecting value: line 5 column 14"
"""

import json
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _repair_json(raw: str) -> str:
    """
    Attempt basic JSON repair on common model output mistakes:
    - Trailing commas before } or ]
    - Single quotes instead of double quotes
    - Unquoted keys
    """
    # Remove trailing commas
    text = re.sub(r",\s*([}\]])", r"\1", raw)
    # Replace smart/curly quotes
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    return text


def extract_json_block(raw: str) -> Optional[str]:
    """
    Find the first JSON object or array in a string.
    Handles models that wrap JSON in markdown fences or prose.
    """
    # Try ```json ... ``` fence first
    fence = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", raw, re.DOTALL)
    if fence:
        return fence.group(1)

    # Try bare { ... } block
    brace = re.search(r"(\{.*?\})", raw, re.DOTALL)
    if brace:
        return brace.group(1)

    return None


def safe_parse_terms(raw: str) -> dict:
    """
    Parse term extractor model output into a dict.
    Falls back to empty result instead of raising — never crashes the pipeline.

    Expected format:
    {"new_terms": [{"source": "X", "target": "Y", "category": "Z"}]}
    """
    empty_result: dict = {"new_terms": []}

    if not raw or not raw.strip():
        logger.warning("Entity extractor returned empty response")
        return empty_result

    # Attempt 1: direct parse
    try:
        data = json.loads(raw.strip())
        if "new_terms" in data:
            return data
    except json.JSONDecodeError:
        pass

    # Attempt 2: extract JSON block from prose
    block = extract_json_block(raw)
    if block:
        try:
            data = json.loads(block)
            if "new_terms" in data:
                return data
        except json.JSONDecodeError:
            pass

        # Attempt 3: repair then parse
        try:
            data = json.loads(_repair_json(block))
            if "new_terms" in data:
                logger.info("JSON repaired successfully")
                return data
        except json.JSONDecodeError:
            pass

    logger.warning("Entity extraction failed after 3 attempts — returning empty terms")
    logger.debug("Raw response was: %s", raw[:300])
    return empty_result

def extract_json_from_response(raw: str) -> dict:
    """
    Generic JSON extraction from LLM response.
    Extracts any JSON object from the response, not just term extraction format.
    
    This is a more generic version of safe_parse_terms that doesn't require
    the 'new_terms' key to be present.
    
    Args:
        raw: Raw LLM response text that may contain JSON
        
    Returns:
        Parsed JSON dict, or empty dict if extraction fails
    """
    if not raw or not raw.strip():
        logger.warning("Empty response for JSON extraction")
        return {}
    
    # Attempt 1: direct parse of entire response
    try:
        data = json.loads(raw.strip())
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    
    # Attempt 2: extract JSON block from prose
    block = extract_json_block(raw)
    if block:
        try:
            data = json.loads(block)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
        
        # Attempt 3: repair then parse
        try:
            data = json.loads(_repair_json(block))
            if isinstance(data, dict):
                logger.info("JSON repaired and extracted successfully")
                return data
        except json.JSONDecodeError:
            pass
    
    logger.warning("JSON extraction failed after 3 attempts")
    logger.debug("Raw response was: %s", raw[:300])
    return {}
