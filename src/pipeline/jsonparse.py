"""Tolerant / malformed-JSON recovery helpers (AGENTS.md invariant).

Small Kadai/Gemma models emit EOS-truncated or fence-wrapped JSON; every LLM
response parser in the pipeline funnels through these so a single closing
brace missing never sinks a batch.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional


def extract_balanced_json(text: str) -> Optional[str]:
    """First balanced JSON *object* substring honouring strings/escapes.

    If the object never closes (truncated at EOS), repairs up to 4 missing
    trailing braces.
    """
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    end = -1
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end >= 0:
        return text[start:end]
    if 0 < depth <= 4:
        candidate = text[start:] + "}" * depth
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            return None
    return None


def load_json(text: str) -> Optional[Any]:
    """Try several recovery strategies to parse JSON from a noisy blob."""
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    for strategy in (
        lambda t: t,              # whole string as-is
        extract_balanced_json,    # balanced / truncated-repaired substring
    ):
        candidate = strategy(text)
        if candidate is None:
            continue
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, (dict, list)):
            return parsed
    return None


def parse_translations(raw: str) -> List[str]:
    """Parse a ``{"translations": [...]}`` response into a list of strings."""
    if not raw:
        return []
    parsed = load_json(raw.strip())
    if isinstance(parsed, dict) and isinstance(parsed.get("translations"), list):
        return [str(x) for x in parsed["translations"]]
    if isinstance(parsed, list) and all(isinstance(x, (str, int, float)) for x in parsed):
        return [str(x) for x in parsed]
    # No JSON wrapper -> most likely a plain line-separated list.
    out = [l.strip() for l in raw.splitlines() if l.strip()]
    return out


def parse_results(raw: str) -> List[Dict[str, Any]]:
    """Parse a ``{"results": [...]}`` response (refine/audit) into a list."""
    if not raw:
        return []
    parsed = load_json(raw.strip())
    if isinstance(parsed, dict):
        results = parsed.get("results", [])
    elif isinstance(parsed, list):
        results = parsed
    else:
        results = []
    out: List[Dict[str, Any]] = []
    for item in results:
        if isinstance(item, dict):
            out.append(item)
        elif isinstance(item, (str, int, float)):
            out.append({"value": item})
    return out