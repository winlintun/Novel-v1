#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Vendored shared helper library for the offline novel translation scripts.

This module is the *self-contained* re-implementation of the helpers that the
novel pipeline scripts used to import from a sibling folder outside this repo
(e.g. ``offline_novel_translate_pairs.py`` in the parent ``DNovels``
directory).  All functions it exposes are implemented here from their usage
contracts inside ``translate_human_chapters.py`` and
``offline_novel_refine_padauk.py`` plus the invariants in ``AGENTS.md`` /
``RULES.md``.

Everything talks to a LOCAL Ollama only (``OLLAMA_HOST``, default
``http://localhost:11434``).  Nothing in here calls a cloud API.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import requests
from dotenv import load_dotenv

# --------------------------------------------------------------------------- #
# Environment
# --------------------------------------------------------------------------- #
# Best-effort: load repo-root .env so scripts work even when run from a bare
# checkout (the historical scripts referenced ROOT_DIR/.env in src/core which
# does not exist; dotenv only fills missing keys, so this stays harmless).
for _candidate in (
    Path(__file__).resolve().parent / ".env",
    Path(__file__).resolve().parent.parent.parent / ".env",
):
    if _candidate.is_file():
        load_dotenv(_candidate)
        break

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
DEFAULT_TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0.2"))

# Prompt template kept for parity with the historical module.
PROMPT_MD = """### SYSTEM PROMPT ###

# Context (Role-Playing)
သင်သည် Wuxia/Xianxia web novel များကို English မှ Burmese သို့ ဘာသာပြန်ဆိုရာတွင် အထူးကျွမ်းကျင်သော
စာပေဘာသာပြန်ဆရာတစ်ဦးဖြစ်သည်။ Cultivation terminology, martial arts terms, နှင့် English literary
style များကို Burmese စာဖတ်သူများ လက်ခံနိုင်သည့် သဘာဝကျသော ရေးဟန်ဖြင့် ပြန်ဆိုတတ်သည်။

# Task
အောက်ပါ ### TEXT ### အတွင်းရှိ English စာသားကို Burmese ဘာသာသို့ ပြန်ဆိုပါ။

# Instruction (Constraints)
1. Glossary ထဲပါ character နာမည်၊ တိုက်ခန်းအမည်၊ cultivation term များကို ပေးထားသည့်အတိုင်းသာ ပြန်ဆိုပါ
2. မူရင်းအဓိပ္ပာယ်ကို မထပ်ဖြည့်၊ မချန်ထားပါနှင့်
3. စကားပြော (dialogue) များတွင် ပုံဖော်ပါဇာတ်ကောင်၏ status/register နှင့်ကိုက်ညီသော အသုံးအနှုန်းသုံးပါ
4. English idiom သို့မဟုတ် ရှင်းရှင်းလင်းလင်း ဘာသာမပြန်နိုင်သော စကားစုများကို context အတိုင်း လိုက်လျောညီထွေ ပြန်ဆိုပါ

# Format
- ဘာသာပြန်ထားသော Burmese စာသားကိုသာ ထုတ်ပေးပါ
- ရှင်းလင်းချက်၊ note၊ meta-commentary လုံးဝ မထည့်ပါနှင့်
- Paragraph structure ကို မူရင်းအတိုင်း ထိန်းသိမ်းပါ

### GLOSSARY ###
{glossary_terms}

### TEXT ###
{source_text}

### OUTPUT ###
"""


def log(msg: str) -> None:
    """Plain, immediate, unicode-safe progress output (stdout)."""
    print(msg, flush=True)


def _interruptible_sleep(seconds: float) -> None:
    """Sleep in small increments so Ctrl+C always lands promptly."""
    deadline = time.time() + seconds
    while time.time() < deadline:
        time.sleep(min(0.25, max(0.0, deadline - time.time())))


# --------------------------------------------------------------------------- #
# Ollama low-level helpers
# --------------------------------------------------------------------------- #
def _payload(
    prompt: str,
    model: str,
    system: Optional[str],
    temperature: float,
    num_predict: int,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "keep_alive": -1,
        "options": {"temperature": temperature, "num_predict": num_predict},
    }
    if system:
        payload["system"] = system
    return payload


def _ollama(
    prompt: str,
    model: str,
    timeout: int = 600,
    retries: int = 1,
    num_predict: int = 2048,
    system: Optional[str] = None,
    temperature: float = DEFAULT_TEMPERATURE,
) -> str:
    """POST one non-streaming completion to local Ollama `/api/generate`.

    Mirrors the pipeline invocation contract: `think=false`, `keep_alive=-1`,
    temperature default 0.2, `num_predict` sized by the caller.  Returns the
    model's raw response text.
    """
    payload = _payload(prompt, model, system, temperature, num_predict)
    last_error: Optional[Exception] = None
    for attempt in range(1, max(1, retries) + 1):
        try:
            resp = requests.post(
                f"{OLLAMA_HOST}/api/generate", json=payload, timeout=timeout
            )
            resp.raise_for_status()
            data = resp.json()
            return str(data.get("response", "") or "")
        except requests.RequestException as exc:
            last_error = exc
            if attempt < retries:
                _interruptible_sleep(2 ** attempt)
    if last_error is not None:
        raise last_error
    return ""


def check_ollama(model: str) -> None:
    """Verify the model is present on local Ollama; exits if not reachable."""
    try:
        resp = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=10)
        resp.raise_for_status()
        models = [m.get("name", "") for m in resp.json().get("models", [])]
    except requests.RequestException as exc:
        log(f"ERROR: cannot reach Ollama at {OLLAMA_HOST}: {exc}")
        raise SystemExit(1)
    if model not in models:
        log(f"ERROR: model '{model}' not found on Ollama. Available: {', '.join(models) or '(none)'}")
        raise SystemExit(1)
    log(f"Ollama OK ({OLLAMA_HOST}); model '{model}' available.")


def unload_model(model: str) -> None:
    """Ask Ollama to release the model from memory (keep_alive=0)."""
    try:
        requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json={"model": model, "prompt": "", "keep_alive": 0, "stream": False},
            timeout=30,
        )
    except requests.RequestException:
        pass


# --------------------------------------------------------------------------- #
# Unicode / quality guards
# --------------------------------------------------------------------------- #
ZWSP = "\u200b"
_THINK_TAG_RE = re.compile(r"<thinking>.*?</thinking>", re.DOTALL | re.IGNORECASE)
_LEADING_THINK_RE = re.compile(r"^\s*thinking\b[^]*?(?=<|[ကခဂဃငစဆဇဈဉညဋဌဍဎဏတထဒဓနပဖဗဘမယရလဝသဟဠအ])", re.DOTALL)
_MD_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)
_SPACE_RE = re.compile(r"[ \t]+")


def has_myanmar(text: str) -> bool:
    """True if the text contains any U+1000..U+109F Burmese character."""
    return any(0x1000 <= ord(ch) <= 0x109F for ch in (text or ""))


MYANMAR_DIGITS = {str(i): c for i, c in enumerate("၀၁၂၃၄၅၆၇၈၉")}


def to_myanmar_numbers(text: str) -> str:
    """Convert plain ASCII digit runs into Myanmar numerals (500 -> ၅၀၀)."""
    if not text:
        return text
    return re.sub(r"\b\d+\b", lambda m: "".join(MYANMAR_DIGITS.get(c, c) for c in m.group(0)), text)


def clean_my_text(text: str) -> str:
    """Post-process raw Myanmar output.

    - strips ``<thinking>`` blocks and a stray leading ``thinking`` token
    - removes markdown fences and zero-width spaces
    - collapses multiple spaces to one and strips each line
    """
    if text is None:
        return ""
    t = str(text)
    t = _THINK_TAG_RE.sub("", t)
    t = _LEADING_THINK_RE.sub("", t)
    t = _MD_FENCE_RE.sub("", t, count=1)
    t = t.replace(ZWSP, "")
    t = re.sub(r"^```(?:json)?\s*", "", t).strip()
    t = t.replace("\r\n", "\n")
    lines = [l.strip() for l in t.split("\n")]
    t = "\n".join(l for l in lines if l or True)
    t = _SPACE_RE.sub(" ", t)
    return t.strip()


def looks_incomplete(my: Optional[str], source: str) -> bool:
    """True when an output is unusable: empty, echoes the source, or contains
    no Burmese script."""
    if not my or not my.strip():
        return True
    if not has_myanmar(my):
        return True
    normalized_my = clean_my_text(my)
    normalized_src = clean_my_text(source or "")
    if normalized_src and normalized_src.casefold() == normalized_my.casefold():
        return True
    # Echo-of-source where most of the output is just English.
    ascii_letters = sum(1 for ch in normalized_my if ch.isascii() and ch.isalpha())
    if ascii_letters > 0 and ascii_letters * 2 > len(normalized_my):
        return True
    return False


# --------------------------------------------------------------------------- #
# Tolerant JSON recovery (the single source of truth for every caller)
# --------------------------------------------------------------------------- #
def _extract_balanced_json(text: str) -> Optional[str]:
    """First balanced JSON object substring, repairing up to 4 trailing
    missing braces (small Kadai/Gemma models truncate at EOS)."""
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


def _load_json(text: str) -> Optional[Any]:
    """Try several recovery strategies to parse JSON out of a noisy blob."""
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    for strategy in (
        lambda t: t,              # whole string as-is
        _extract_balanced_json,   # balanced / truncated-repaired substring
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
    """Parse a ``{"translations": [...]}`` response into a list of strings.

    Falls back to a line-split when no JSON wrapper is present.  Returns an
    empty list rather than raising so callers can retry.
    """
    if raw is None:
        return []
    stripped = clean_my_text(raw)
    if not stripped:
        return []
    parsed = _load_json(stripped)
    if isinstance(parsed, dict) and isinstance(parsed.get("translations"), list):
        return [str(x) for x in parsed["translations"]]
    if isinstance(parsed, list):
        if all(isinstance(x, (str, int, float)) for x in parsed):
            return [str(x) for x in parsed]
    # Not JSON: a plain line-separated list is the next-best guess.
    out = [l.strip() for l in stripped.splitlines() if l.strip()]
    return out


# --------------------------------------------------------------------------- #
# Glossary helpers
# --------------------------------------------------------------------------- #
def _extract_glossary_entries(raw: Any) -> List[Dict[str, Any]]:
    """Normalize any of the supported glossary JSON shapes into entry dicts.

    Supported shapes:
    - ``{"categories": {"<name>": {"entries": [...]}}}``   (current project)
    - ``{"entries": [...]}``                                (older project)
    - a bare JSON list of entries
    """
    if isinstance(raw, dict):
        if isinstance(raw.get("categories"), dict):
            out: List[Dict[str, Any]] = []
            for _cat_name, cat in raw["categories"].items():
                if isinstance(cat, dict) and isinstance(cat.get("entries"), list):
                    out.extend(cat["entries"])
            return out
        if isinstance(raw.get("entries"), list):
            return raw["entries"]
        # single entry object?
        if raw.get("term") or raw.get("en"):
            return [raw]
        return []
    if isinstance(raw, list):
        return [e for e in raw if isinstance(e, dict)]
    return []


def build_glossary_index(glossary_path: Optional[Path]) -> List[Dict[str, Any]]:
    """Load + normalize a glossary JSON into ``[{"en","zh","my",...}]``.

    Entries are sorted longest-term-first so partial matches never win.
    ``glossary_path`` may be ``None`` (=> ``[]``).
    """
    if not glossary_path or not Path(glossary_path).is_file():
        return []
    try:
        data = json.loads(Path(glossary_path).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    index: List[Dict[str, Any]] = []
    for e in _extract_glossary_entries(data):
        en = (e.get("term") or e.get("en") or "").strip()
        my = (e.get("translation") or e.get("my") or "").strip()
        if not en or not my:
            continue
        index.append(
            {
                "en": en,
                "my": my,
                "zh": (e.get("original_name") or e.get("zh") or "").strip(),
                "category": e.get("category", ""),
                "gender": e.get("gender", "neutral"),
                "formality": e.get("formality", "mixed"),
                "locked": bool(e.get("locked", True)),
                "aliases": list(e.get("aliases") or [en]),
                "pronoun": e.get("pronoun_dialogue", ""),
                "particles": list(e.get("particles") or []),
                "my_variants": list(e.get("my_variants") or e.get("variants") or []),
            }
        )
    index.sort(key=lambda d: len(d["en"]), reverse=True)
    return index


def build_glossary_section(
    glossary_path: Optional[Path],
    index: Optional[List[Dict[str, Any]]] = None,
    texts: Optional[Sequence[str]] = None,
    dynamic: bool = False,
    max_terms: int = 100,
) -> str:
    """Render ``- EN (ZH) = MY`` lines for prompt injection.

    ``dynamic=True`` keeps only terms whose English form appears in ``texts``
    (matched via the alias list).  ``max_terms`` caps the injected list.
    """
    entries = index if index is not None else build_glossary_index(glossary_path)
    if not entries:
        return ""
    if dynamic:
        haystack = " ".join(t or "" for t in (texts or []))
        entries = [
            e
            for e in entries
            if any(a in haystack for a in e["aliases"])
        ]
        entries = entries[:max_terms]
    if not entries:
        return ""
    lines = [
        "GLOSSARY (CRITICAL - use EXACTLY these spellings):"
    ]
    for e in entries:
        ref = f" ({e['zh']})" if e.get("zh") else ""
        lines.append(f"- {e['en']}{ref} = {e['my']}")
    return "\n".join(lines)


def find_glossary(db_path: Path, glossary_arg: Optional[str]) -> Optional[Path]:
    """Locate the glossary beside the DB unless --glossary given."""
    if glossary_arg:
        return Path(glossary_arg)
    candidates = sorted(Path(db_path).parent.glob("glossary_*.json"))
    return candidates[0] if candidates else None


def find_corrections(db_path: Path, corrections_arg: Optional[str]) -> Optional[Path]:
    """Locate per-novel corrections JSON beside the DB unless given."""
    if corrections_arg:
        return Path(corrections_arg)
    candidates = sorted(Path(db_path).parent.glob("*corrections*.json"))
    return candidates[0] if candidates else None


# --------------------------------------------------------------------------- #
# Context / corrections builder (refine judge)
# --------------------------------------------------------------------------- #
def build_context_section(
    cur: Any, batch: Sequence[Tuple], context_lines: int = 3
) -> str:
    """Render previous translated paragraphs (the last ones *before* the batch)
    from ``paragraph_pairs`` as continuity context.

    Row shape expected: (id, novel_slug, chapter_num, para_index, en_text,
    zh_simplified, my_text).
    """
    if not batch or context_lines <= 0:
        return ""
    first = batch[0]
    rows = cur.execute(
        "SELECT my_text FROM paragraph_pairs "
        "WHERE novel_slug = ? "
        "AND (chapter_num < ? OR (chapter_num = ? AND para_index < ?)) "
        "AND my_text IS NOT NULL AND trim(my_text) != '' "
        "ORDER BY chapter_num DESC, para_index DESC LIMIT ?",
        (first[1], first[2], first[2], first[3], context_lines),
    ).fetchall()
    if not rows:
        return ""
    block = ["PREVIOUS TRANSLATED CONTEXT (for continuity):"]
    for i, (my,) in enumerate(rows, 1):
        block.append(f"[ctx{i}] {my}")
    return "\n".join(block)


def build_corrections_section(corrections_path: Optional[Path]) -> str:
    """Render per-novel corrections JSON as ``EN -> MY`` few-shot lines."""
    if not corrections_path or not Path(corrections_path).is_file():
        return ""
    try:
        data = json.loads(Path(corrections_path).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return ""
    entries = data.get("entries", []) if isinstance(data, dict) else data
    if not isinstance(entries, list):
        return ""
    lines = ["KNOWN CORRECTIONS (apply these):"]
    for e in entries:
        if not isinstance(e, dict):
            continue
        en = e.get("en") or e.get("term") or ""
        my = e.get("my") or e.get("translation") or ""
        if en and my:
            lines.append(f"- {en} -> {my}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Misc formatting
# --------------------------------------------------------------------------- #
def load_system_prompt(path: Optional[Path]) -> str:
    """Read a system prompt file; default to prompts/prompt.md when absent."""
    if path is not None and Path(path).is_file():
        return Path(path).read_text(encoding="utf-8").strip()
    if path is None:
        default = Path(__file__).resolve().parent.parent.parent / "prompts" / "prompt.md"
        if default.is_file():
            return default.read_text(encoding="utf-8").strip()
    return ""


def format_eta(seconds: float) -> str:
    """Human-readable duration: ``3h 05m 20s`` / ``4m 03s`` / ``9s``."""
    seconds = int(max(0, seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m:02d}m {s:02d}s"
    if m:
        return f"{m}m {s:02d}s"
    return f"{s}s"