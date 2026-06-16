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
    # Collapse a doubled opening quote on a key: {""source"  ->  {"source"
    # padauk-gemma emits this regularly. Restricted to a key position (right after
    # { or ,) and followed by a word char, so legitimate empty strings ("k": "")
    # are never touched.
    text = re.sub(r'([{,]\s*)""(?=\w)', r'\1"', text)
    return text


def _balanced_span(text: str, open_ch: str, close_ch: str) -> Optional[str]:
    """Return the first balanced open_ch..close_ch span, respecting strings.

    A non-greedy regex like ``\\{.*?\\}`` stops at the FIRST closing brace, which
    truncates nested JSON (e.g. ``{"meta":{...}, "terms":[...]}`` would be cut at
    the inner ``}``). This scans with a depth counter and skips braces inside
    string literals, so it captures the COMPLETE top-level object/array.
    """
    start = text.find(open_ch)
    if start == -1:
        return None
    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None  # unbalanced (e.g. truncated by token limit)


def _close_unbalanced_json(raw: str) -> Optional[str]:
    """Repair JSON truncated before its closing brackets.

    LLMs frequently emit all the content but drop the final ``}``/``]`` (e.g.
    padauk-gemma returning ``{"terms": [ {..}, {..} ]`` with the root ``}``
    missing → unbalanced → unparseable, losing every term). This scans
    string-aware from the first ``{``/``[``, tracks the open-bracket stack, and
    appends the missing closers (plus closing an unterminated string and dropping
    a dangling trailing comma) so the result can parse.
    """
    start = -1
    for i, ch in enumerate(raw):
        if ch in "{[":
            start = i
            break
    if start == -1:
        return None

    stack: list[str] = []
    in_str = False
    escape = False
    for i in range(start, len(raw)):
        ch = raw[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            stack.append("}")
        elif ch == "[":
            stack.append("]")
        elif ch in "}]" and stack:
            stack.pop()

    if not stack and not in_str:
        return None  # already balanced — nothing to repair

    repaired = raw[start:]
    if in_str:
        repaired += '"'
    repaired = re.sub(r",\s*$", "", repaired.rstrip())  # drop dangling comma
    repaired += "".join(reversed(stack))  # close innermost-first
    return repaired


def extract_json_block(raw: str) -> Optional[str]:
    """
    Find the first complete JSON object or array in a string.
    Handles models that wrap JSON in markdown fences or prose, and nested objects.
    """
    # Strip markdown fences if present so the scanner sees raw JSON.
    fence = re.search(r"```(?:json)?\s*(.*?)\s*```", raw, re.DOTALL)
    candidate = fence.group(1) if fence else raw

    # Extract whichever top-level container appears FIRST (object vs array), via
    # balanced scanning so nested braces/brackets are never truncated.
    obj_at = candidate.find("{")
    arr_at = candidate.find("[")
    if obj_at == -1 and arr_at == -1:
        return None
    obj_first = arr_at == -1 or (obj_at != -1 and obj_at < arr_at)
    if obj_first:
        return _balanced_span(candidate, "{", "}") or _balanced_span(candidate, "[", "]")
    return _balanced_span(candidate, "[", "]") or _balanced_span(candidate, "{", "}")


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

    # Attempt 1b: repair raw (doubled key-quotes, smart quotes, trailing commas)
    try:
        data = json.loads(_repair_json(raw.strip()))
        if "new_terms" in data:
            logger.info("JSON repaired (raw) successfully")
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

    # Attempt 4: close truncated/unbalanced JSON (model dropped final brackets)
    closed = _close_unbalanced_json(raw)
    if closed:
        try:
            data = json.loads(_repair_json(closed))
            if "new_terms" in data:
                logger.info("JSON recovered from truncated response")
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

    # Attempt 1b: repair common malformations (doubled key-quotes {""k", smart
    # quotes, trailing commas) on the RAW text, then parse. Must run on raw, not
    # the extracted block — doubled quotes corrupt block extraction's string-state
    # tracking, so the block would already be garbage.
    try:
        data = json.loads(_repair_json(raw.strip()))
        if isinstance(data, dict):
            logger.info("JSON repaired (raw) and extracted successfully")
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

    # Attempt 4: close truncated/unbalanced JSON (model dropped final brackets)
    closed = _close_unbalanced_json(raw)
    if closed:
        try:
            data = json.loads(_repair_json(closed))
            if isinstance(data, dict):
                logger.info("JSON recovered from truncated response")
                return data
        except json.JSONDecodeError:
            pass

    logger.warning("JSON extraction failed after 3 attempts")
    logger.debug("Raw response was: %s", raw[:300])
    return {}
