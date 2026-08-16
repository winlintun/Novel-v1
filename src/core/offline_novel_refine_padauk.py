#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Recheck + refine novel Myanmar (Burmese) translations with padauk-gemma.

After a novel has been translated (my_text populated), this tool re-reads each
paragraph's Chinese (zh_simplified), English (en_text) draft and existing
Myanmar translation (my_text), and asks the local Ollama `padauk-gemma:q8_0`
model to:

  - verify the Myanmar conveys the same meaning as the Chinese/English source
  - rewrite it (if wrong or awkward) into correct, natural, *readable* Burmese

Results are written into two NEW columns on `paragraph_pairs` so the original
my_text is always preserved for comparison:

    my_refined     TEXT    refined / confirmed Myanmar output
    refine_status  TEXT    ok | refined | skip | error | pending

The judge prompt is auto-generated per novel at
`prompts/padauk-gemma_refine_novel/<novel>.md` (reused if it already exists)
and has the novel's glossary EN->MY terms baked in so character/place/sect
names stay consistent.

Usage:
    # Inspect prompts without calling Ollama
    python offline_novel_refine_padauk.py output/<slug>/<slug>.db --limit 3 --dry-run

    # Test first 3 paragraphs
    python offline_novel_refine_padauk.py output/<slug>/<slug>.db --chapter 1 --limit 0

    # Full novel (resume-safe, skips rows already refined unless --force)
    python offline_novel_refine_padauk.py output/<slug>/<slug>.db --limit 0 --batch-size 3
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from dotenv import load_dotenv

from offline_novel_translate_pairs import (
    _interruptible_sleep,
    _ollama,
    build_context_section,
    build_corrections_section,
    build_glossary_index,
    build_glossary_section,
    check_ollama,
    clean_my_text,
    find_corrections,
    find_glossary,
    format_eta,
    has_myanmar,
    unload_model,
)

ROOT_DIR = Path(__file__).resolve().parent
load_dotenv(ROOT_DIR / ".env")

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "").strip() or "padauk-gemma:q8_0"

BATCH_SIZE = 1          # paragraphs are long; keep the judge focused
MAX_RETRIES = 4
DEFAULT_CONTEXT_LINES = 3
DEFAULT_GLOSSARY_MAX = 25

# Prompt folder per the user's layout.
PROMPT_DIR = ROOT_DIR / "prompts" / "padauk-gemma_refine_novel"
PROMPT_DIR.mkdir(parents=True, exist_ok=True)

MOJIBAKE_RE = re.compile(r"[\u00C3\u00C2][\x80-\xBF]")
CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F]")
ARABIC_QUESTION_MARK = "\u061F"
FOREIGN_SCRIPT_RANGES: Dict[str, Tuple[int, int]] = {
    "thai": (0x0E00, 0x0E7F),
    "bengali": (0x0980, 0x09FF),
    "devanagari": (0x0900, 0x097F),
    "hangul": (0xAC00, 0xD7FF),
}


def log(msg: str) -> None:
    print(msg, flush=True)


# --------------------------------------------------------------------------- #
# Unicode / sanity guards
# --------------------------------------------------------------------------- #
def detect_encoding_corruption(text: str) -> bool:
    t = text or ""
    if "\ufffd" in t or MOJIBAKE_RE.search(t) or CONTROL_CHAR_RE.search(t):
        return True
    return any(0xD800 <= ord(ch) <= 0xDFFF for ch in t)


def detect_language_drift(text: str) -> Optional[str]:
    t = text or ""
    if ARABIC_QUESTION_MARK in t:
        return "arabic"
    for name, (lo, hi) in FOREIGN_SCRIPT_RANGES.items():
        for ch in t:
            if lo <= ord(ch) <= hi:
                return name
    return None


# --------------------------------------------------------------------------- #
# Prompt generation (per-novel, glossary baked in)
# --------------------------------------------------------------------------- #
def prompt_file_path(novel: str) -> Path:
    return PROMPT_DIR / f"{novel}.md"


def build_glossary_terms(glossary_path: Optional[Path]) -> str:
    """Render a plain 'EN (ZH) = MY' list from the glossary JSON."""
    entries = build_glossary_index(glossary_path)
    if not entries:
        return ""
    lines: List[str] = []
    for e in entries:
        ref = f" ({e['zh']})" if e.get("zh") else ""
        lines.append(f"- {e['en']}{ref} = {e['my']}")
    return "\n".join(lines)


def build_prompt_template(novel: str, glossary_path: Optional[Path]) -> str:
    """Compose the reader-friendly, per-novel Padauk refine system prompt."""
    glossary_terms = build_glossary_terms(glossary_path)
    body = []
    if glossary_terms:
        body.append(
            "## GLOSSARY (CRITICAL)\n\n"
            "These EN = MY terms are authoritative spellings for this novel. Whenever a "
            "paragraph contains one of these names/terms, reuse the EXACT Myanmar spelling "
            "below — never re-transliterate:\n\n" + glossary_terms
        )
    body.append(
        "## OUTPUT (STRICT)\n\n"
        "- Return ONLY one valid JSON object: "
        '{"results": [{"index": 1, "verdict": "CORRECT|REFINED|SKIP", '
        '"burmese": "…", "note": "…"}, ...]}\n'
        "- Exactly one result per input paragraph, indices 1..N, same order, no markdown "
        "fences, no thinking, no extra text.\n"
        "- `verdict`: CORRECT (kept as-is), REFINED (rewritten/readable), "
        "SKIP (punctuation-only, unchanged).\n"
        "- `burmese` holds the final Myanmar text (for CORRECT keep the original)."
    )
    return (
        f"# ROLE\n\n"
        f"You are a meticulous Burmese literary editor and proofreader working on the "
        f"novel \"{novel}\". You receive a Chinese (ZH) source paragraph, an English (EN) "
        f"rough reference, and an existing Myanmar (MY) machine draft. Recheck the MY "
        f"draft against ZH/EN and refine it into correct, readable, natural Burmese — as "
        f"if a native Burmese novelist wrote it.\n\n"
        f"# REFINE DECISION\n\n"
        f"- If the MY draft is semantically correct against ZH/EN, you may still lightly "
        f"polish it so it reads naturally (readable mode: clear word order, natural rhythm, "
        f"correct particles).\n"
        f"- If the MY draft is wrong (meaning drift), incomplete, or badly written, rewrite "
        f"it fully into correct, flowing, readable Myanmar that preserves the source meaning.\n"
        f"- Meaning must come from ZH (Chinese). EN is only a helper for names/terms.\n\n"
        f"# CORE RULES\n\n"
        f"- Unicode correctness (CRITICAL): use standard Myanmar script (U+1000–U+109F). "
        f"No Thai/Devanagari/Bengali/Hangul, no Arabic question mark (؟), no mojibake, no "
        f"replacement chars.\n"
        f"- Numbers use Myanmar numerals: 500 -> ၅၀၀, 35 -> ၃၅.\n"
        f"- Punctuation: use standard `?`, `!`, `.`; never Arabic `؟`.\n"
        f"- If the source paragraph is only \"......\" (or \"…\"), output exactly that.\n"
        f"- Keep character/place/sect names consistent (use the glossary).\n"
        f"- Do NOT add explanations, notes, summaries, or copy ZH/EN text.\n\n"
        + ("\n".join(body) if body else "")
    )


def generate_prompt(novel: str, glossary_path: Optional[Path], *, force: bool = False):
    """Write (or reuse) the per-novel prompt file. Returns (path, created)."""
    path = prompt_file_path(novel)
    if path.is_file() and not force:
        return path, False
    path.write_text(build_prompt_template(novel, glossary_path), encoding="utf-8")
    return path, True


# --------------------------------------------------------------------------- #
# DB helpers
# --------------------------------------------------------------------------- #
def ensure_columns(conn: sqlite3.Connection) -> None:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(paragraph_pairs)")}
    if "my_refined" not in cols:
        conn.execute("ALTER TABLE paragraph_pairs ADD COLUMN my_refined TEXT")
        log("Added column paragraph_pairs.my_refined")
    if "refine_status" not in cols:
        conn.execute("ALTER TABLE paragraph_pairs ADD COLUMN refine_status TEXT")
        log("Added column paragraph_pairs.refine_status")
    if "refine_note" not in cols:
        conn.execute("ALTER TABLE paragraph_pairs ADD COLUMN refine_note TEXT")


# Row shape: (id, novel_slug, chapter_num, para_index, en_text, zh_simplified, my_text)
Row = Tuple[int, str, int, int, str, str, str]


def fetch_rows(
    cur: sqlite3.Cursor,
    *,
    limit: int,
    offset: int,
    force: bool,
    chapter: Optional[int],
    chapter_to: Optional[int],
) -> List[Row]:
    clauses = [
        "my_text IS NOT NULL",
        "trim(my_text) != ''",
        "en_text IS NOT NULL",
        "trim(en_text) != ''",
    ]
    params: List[Any] = []
    if not force:
        clauses.append("(refine_status IS NULL OR refine_status = '')")
    if chapter is not None:
        clauses.append("chapter_num = ?")
        params.append(chapter)
    if chapter_to is not None:
        clauses.append("chapter_num <= ?")
        params.append(chapter_to)

    where = " AND ".join(clauses)
    query = (
        "SELECT id, novel_slug, chapter_num, para_index, en_text, "
        "COALESCE(zh_simplified, ''), my_text "
        f"FROM paragraph_pairs WHERE {where} "
        "ORDER BY chapter_num, para_index, id"
    )
    if limit > 0:
        query += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])
    elif offset > 0:
        query += " LIMIT -1 OFFSET ?"
        params.append(offset)
    cur.execute(query, params)
    return cur.fetchall()


def batch_source_texts(batch: Sequence[Row]) -> List[str]:
    texts: List[str] = []
    for row in batch:
        texts.append(row[4] or "")     # en
        texts.append(row[5] or "")     # zh
        texts.append(row[6] or "")     # my
    return texts


# --------------------------------------------------------------------------- #
# Judge prompt + parsing
# --------------------------------------------------------------------------- #
def build_judge_prompt(
    batch: Sequence[Row],
    glossary_section: str = "",
    context_section: str = "",
    corrections_section: str = "",
) -> str:
    blocks: List[str] = []
    for i, (_id, _slug, chapter, para, en, zh, my) in enumerate(batch, 1):
        blocks.append(
            f"{i}. [ch{chapter}p{para}]\n"
            f"   ZH: {zh or '(none)'}\n"
            f"   EN: {en or '(none)'}\n"
            f"   MY draft: {my or '(missing)'}"
        )
    n = len(batch)

    parts: List[str] = []
    parts.append(
        f"Recheck and refine these {n} Myanmar paragraph draft(s) into correct, "
        "readable Burmese. For each result choose CORRECT / REFINED / SKIP and return "
        "the final Myanmar text in `burmese`."
    )
    if context_section:
        parts.append(context_section.strip())
    if corrections_section:
        parts.append(corrections_section.strip())
    if glossary_section:
        parts.append(glossary_section.strip())
    parts.append("\n".join(blocks))
    example_results = ", ".join(
        f"{{'index': {i}, 'verdict': 'CORRECT|REFINED|SKIP', 'burmese': '…', 'note': '…'}}"
        for i in range(1, n + 1)
    )
    parts.append(
        f'Return ONLY valid JSON, no markdown: {{"results": [{example_results}]}} — '
        f"exactly {n} results, indices 1..{n}, same order as the blocks."
    )
    return "\n\n".join(parts)


def _extract_balanced_json(text: str) -> Optional[str]:
    """Return the first balanced JSON object substring from `text`.

    Some small Kadai/Gemma models emit EOS-truncated JSON (drop the final closing
    brace, or stop mid-object), so plain json.loads fails. This scans from the first
    '{' honouring strings/escapes, and if the object never closes, tries appending
    up to 4 missing '}' braces (repairing the truncation).
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

    # Object never closed -> try to repair a truncated trailing set of braces.
    if 0 < depth <= 4:
        candidate = text[start:] + "}" * depth
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            return None
    return None


def _load_json(text: str) -> Optional[Any]:
    """Try several recovery strategies to parse a JSON object out of text."""
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    for strategy in (
        lambda t: t,              # 1. whole string as-is
        _extract_balanced_json,    # 2. balanced / truncated-repaired substring
    ):
        candidate = strategy(text)
        if candidate is None:
            continue
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def parse_judge_response(content: str) -> Dict[int, Dict[str, Any]]:
    stripped = (content or "").strip()
    parsed = _load_json(stripped)
    if parsed is None:
        return {}

    results = parsed.get("results", []) if isinstance(parsed, dict) else []
    if isinstance(results, dict):
        results = [{"index": int(k), **v} for k, v in results.items() if isinstance(v, dict)]

    out: Dict[int, Dict[str, Any]] = {}
    for item in results:
        try:
            idx = int(item["index"])
            out[idx] = {
                "verdict": str(item.get("verdict", "")).strip().upper(),
                "burmese": item.get("burmese"),
                "note": item.get("note", ""),
            }
        except (KeyError, ValueError, TypeError):
            continue
    return out


def judge_batch(
    batch: Sequence[Row],
    model: str,
    timeout: int,
    system_prompt: str = "",
    glossary_section: str = "",
    context_section: str = "",
    corrections_section: str = "",
) -> Dict[int, Dict[str, Any]]:
    prompt = build_judge_prompt(batch, glossary_section, context_section, corrections_section)
    # Generous output budget: REFINED rewrites are often longer than the source MY
    # draft, and cutting it short yields unrepairable truncated JSON.
    num_predict = min(12000, max(4096, sum(len(r[6] or "") for r in batch) * 4 + 1024))

    last_error: Optional[str] = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            raw = _ollama(
                prompt, model, timeout, retries=1,
                num_predict=num_predict, system=system_prompt,
            )
            parsed = parse_judge_response(raw)
            if len(parsed) == len(batch) and all((i + 1) in parsed for i in range(len(batch))):
                return parsed
            last_error = f"incomplete/malformed response ({len(parsed)}/{len(batch)} indices)"
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
        if attempt < MAX_RETRIES:
            _interruptible_sleep(2 ** attempt)

    if len(batch) > 1:
        mid = max(1, len(batch) // 2)
        left = judge_batch(batch[:mid], model, timeout, system_prompt,
                           glossary_section, context_section, corrections_section)
        right = judge_batch(batch[mid:], model, timeout, system_prompt,
                            glossary_section, context_section, corrections_section)
        merged: Dict[int, Dict[str, Any]] = {}
        merged.update(left)
        for idx, val in right.items():
            merged[idx + mid] = val
        return merged

    log(f"  -> single-item judge failure (row id={batch[0][0]}): {last_error}")
    return {}


# --------------------------------------------------------------------------- #
# Apply + persist verdicts
# --------------------------------------------------------------------------- #
def apply_verdicts(
    conn: sqlite3.Connection,
    batch: Sequence[Row],
    verdicts: Dict[int, Dict[str, Any]],
) -> Tuple[int, int]:
    refined = 0
    errors = 0
    for i, (_id, *_rest) in enumerate(batch, 1):
        orig = batch[i - 1][6]
        result = verdicts.get(i)
        if result is None:
            conn.execute(
                "UPDATE paragraph_pairs SET refine_status='error', my_refined=?, "
                "refine_note='no judge response' WHERE id=?",
                (orig, _id),
            )
            errors += 1
            continue

        verdict = result["verdict"]
        note = result.get("note", "")

        if verdict == "REFINED":
            fixed = clean_my_text(result.get("burmese") or "")
            if fixed and has_myanmar(fixed) and not detect_encoding_corruption(fixed) \
                    and not detect_language_drift(fixed):
                conn.execute(
                    "UPDATE paragraph_pairs SET refine_status='refined', my_refined=?, "
                    "refine_note=? WHERE id=?",
                    (fixed, note, _id),
                )
                refined += 1
            else:
                conn.execute(
                    "UPDATE paragraph_pairs SET refine_status='error', my_refined=?, "
                    "refine_note=? WHERE id=?",
                    (orig, f"judge refinement rejected (invalid output): {note}", _id),
                )
                errors += 1
        elif verdict in ("CORRECT", "OK", "KEEP"):
            conn.execute(
                "UPDATE paragraph_pairs SET refine_status='ok', my_refined=?, "
                "refine_note=? WHERE id=?",
                (orig, note, _id),
            )
        elif verdict == "SKIP":
            conn.execute(
                "UPDATE paragraph_pairs SET refine_status='skip', my_refined=?, "
                "refine_note=? WHERE id=?",
                (orig, note, _id),
            )
        else:
            conn.execute(
                "UPDATE paragraph_pairs SET refine_status='error', my_refined=?, "
                "refine_note=? WHERE id=?",
                (orig, f"unrecognized verdict: {verdict}", _id),
            )
            errors += 1
    conn.commit()
    return refined, errors


def summary(conn: sqlite3.Connection) -> Dict[str, int]:
    rows = conn.execute(
        "SELECT refine_status, COUNT(*) FROM paragraph_pairs "
        "WHERE refine_status IS NOT NULL AND trim(refine_status) != '' "
        "GROUP BY refine_status"
    ).fetchall()
    return dict(rows)


def export_json(conn: sqlite3.Connection, out_path: Path) -> None:
    rows = conn.execute(
        "SELECT novel_slug, chapter_num, para_index, en_text, zh_simplified, "
        "my_text, my_refined, refine_status FROM paragraph_pairs "
        "WHERE refine_status IS NOT NULL AND trim(refine_status) != '' "
        "ORDER BY novel_slug, chapter_num, para_index"
    ).fetchall()
    payload = {
        "output": str(out_path),
        "count": len(rows),
        "entries": [
            {
                "slug": r[0], "chapter": r[1], "para": r[2],
                "en": r[3], "zh": r[4], "my_original": r[5],
                "my_refined": r[6], "status": r[7],
            }
            for r in rows
        ],
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"Exported review JSON -> {out_path}")


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def process_db(
    db_path: Path,
    *,
    model: str,
    limit: int,
    offset: int,
    force: bool,
    batch_size: int,
    timeout: int,
    unload: bool,
    chapter: Optional[int],
    chapter_to: Optional[int],
    glossary_arg: Optional[str],
    context_lines: int,
    corrections_arg: Optional[str],
    dry_run: int,
    export: Optional[Path],
    prompt_force: bool,
) -> int:
    db_path = db_path.resolve()
    novel = db_path.stem

    glossary_path = find_glossary(db_path, glossary_arg)
    glossary_index = build_glossary_index(glossary_path)
    corrections_path = find_corrections(db_path, corrections_arg)

    prompt_path, created = generate_prompt(novel, glossary_path, force=prompt_force)
    system_prompt = prompt_path.read_text(encoding="utf-8").strip()

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    ensure_columns(conn)
    cur = conn.cursor()
    try:
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_pp_refine "
            "ON paragraph_pairs(novel_slug, chapter_num, para_index)"
        )
    except sqlite3.Error as exc:
        log(f"WARNING: could not create index: {exc}")
    conn.commit()

    total_all = cur.execute("SELECT COUNT(*) FROM paragraph_pairs").fetchone()[0]
    done_all = cur.execute(
        "SELECT COUNT(*) FROM paragraph_pairs "
        "WHERE refine_status IS NOT NULL AND trim(refine_status) != ''"
    ).fetchone()[0]

    rows = fetch_rows(
        cur, limit=limit, offset=offset, force=force,
        chapter=chapter, chapter_to=chapter_to,
    )
    total = len(rows)
    batches = [rows[i:i + batch_size] for i in range(0, total, batch_size)]

    log(f"DB: {db_path}")
    log(f"Model: {model} @ {OLLAMA_HOST} (think=false, keep_alive=-1)")
    log(f"Prompt: {prompt_path} {'[generated]' if created else '[existing]'}")
    log(f"Glossary: {glossary_path.name if glossary_path else '(none)'}")
    log(f"Corrections: {corrections_path.name if corrections_path else '(none)'}")
    log(f"Context lines: {context_lines}")
    log(
        f"Paragraphs: {total_all} | already done: {done_all} | this run: {total} "
        f"({len(batches)} batches)"
    )

    if not total:
        log("Nothing to refine.")
        conn.close()
        return 0

    if dry_run:
        show = min(dry_run, len(batches))
        log(f"DRY RUN: printing {show} batch prompt(s), no Ollama calls.")
        for bi, batch in enumerate(batches[:show], 1):
            gloss = build_glossary_section(
                glossary_path, index=glossary_index,
                texts=batch_source_texts(batch), dynamic=True,
            )
            ctx = build_context_section(cur, batch, context_lines)
            corr = build_corrections_section(corrections_path)
            prompt = build_judge_prompt(batch, gloss, ctx, corr)
            log(f"\n===== Batch {bi}/{show} prompt =====")
            log("[SYSTEM prompt above; USER prompt below]")
            log(prompt)
        conn.close()
        return 0

    try:
        check_ollama(model)
    except SystemExit:
        conn.close()
        raise

    t0 = time.time()
    refined = 0
    errors = 0
    try:
        for bi, batch in enumerate(batches, 1):
            gloss = build_glossary_section(
                glossary_path, index=glossary_index,
                texts=batch_source_texts(batch), dynamic=True,
            )
            ctx = build_context_section(cur, batch, context_lines)
            corr = build_corrections_section(corrections_path)

            verdicts = judge_batch(
                batch, model, timeout, system_prompt, gloss, ctx, corr
            )
            br, be = apply_verdicts(conn, batch, verdicts)
            refined += br
            errors += be

            _id = batch[0][0]
            log(
                f"Batch {bi}/{len(batches)} id={_id} | refined={br} error={be} | "
                f"elapsed {format_eta(time.time() - t0)}"
            )
        conn.commit()
    except KeyboardInterrupt:
        log("\nInterrupted. Saving progress...")
        conn.commit()
        if export:
            export_json(conn, export)
        return 130
    finally:
        if unload:
            try:
                unload_model(model)
            except Exception:
                pass

    if export:
        export_json(conn, export)

    log(f"\nDone in {format_eta(time.time() - t0)}. refined={refined}, errors={errors}")
    for status, count in sorted(summary(conn).items()):
        log(f"  {status}: {count}")
    conn.close()
    return 0 if errors == 0 else 2


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass

    ap = argparse.ArgumentParser(
        description="Recheck + refine paragraph_pairs my_text via local Ollama padauk-gemma."
    )
    ap.add_argument("db", help="Path to novel SQLite database")
    ap.add_argument("--limit", type=int, default=10,
                    help="Max paragraphs to refine (default: 10; 0 = all)")
    ap.add_argument("--offset", type=int, default=0, help="Skip first N matching rows")
    ap.add_argument("--chapter", type=int, default=None, help="Only this chapter_num")
    ap.add_argument("--chapter-to", type=int, default=None,
                    help="Refine chapters with chapter_num <= this value")
    ap.add_argument("--batch-size", type=int, default=BATCH_SIZE,
                    help=f"Paragraphs per Ollama call (default: {BATCH_SIZE})")
    ap.add_argument("--model", default=DEFAULT_MODEL, help="Ollama model name")
    ap.add_argument("--glossary", default=None,
                    help="Path to glossary JSON (default: auto-discover beside DB)")
    ap.add_argument("--corrections", default=None,
                    help="Path to per-novel corrections JSON (optional few-shot)")
    ap.add_argument("--context-lines", type=int, default=DEFAULT_CONTEXT_LINES,
                    help=f"Previous translated paragraphs as context (default: {DEFAULT_CONTEXT_LINES})")
    ap.add_argument("--timeout", type=int, default=600, help="Request timeout seconds")
    ap.add_argument("--force", action="store_true",
                    help="Re-refine rows already having refine_status")
    ap.add_argument("--prompt-force", action="store_true",
                    help="Regenerate the per-novel prompt even if it exists")
    ap.add_argument("--unload", action="store_true", help="Unload model when finished")
    ap.add_argument("--export", default=None,
                    help="Path for a review JSON export (default: refines beside the DB)")
    ap.add_argument("--no-export", action="store_true",
                    help="Do not write the review JSON export")
    ap.add_argument("--dry-run", nargs="?", const=1, type=int, default=0, metavar="N",
                    help="Print prompts for N batches (default 1) then exit")
    args = ap.parse_args()

    db_path = Path(args.db)
    if not db_path.is_file():
        log(f"ERROR: database not found: {db_path}")
        return 1

    export = None if args.no_export else (Path(args.export) if args.export else
                db_path.parent / f"refined_{db_path.stem}.json")

    return process_db(
        db_path,
        model=args.model.strip(),
        limit=args.limit,
        offset=args.offset,
        force=args.force,
        batch_size=max(1, args.batch_size),
        timeout=args.timeout,
        unload=args.unload,
        chapter=args.chapter,
        chapter_to=args.chapter_to,
        glossary_arg=args.glossary,
        context_lines=max(0, args.context_lines),
        corrections_arg=args.corrections,
        dry_run=args.dry_run,
        export=export,
        prompt_force=args.prompt_force,
    )


if __name__ == "__main__":
    raise SystemExit(main())