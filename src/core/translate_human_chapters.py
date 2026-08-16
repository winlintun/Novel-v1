#!/usr/bin/env python3
"""Translate the human English novel chapters (My House of Horrors/*.md) into
Myanmar (Burmese) using a single local Ollama model (e.g. gemma-4-26b-a4b-it-ud).

This is the "translate human EN chapters" path: it does NOT use the LNMTL DB
paragraph alignment at all. Each chapter's paragraphs are batched and sent to
the EN->MY model with the production glossary strictly injected (EN = MY), so
character/place names stay consistent.

Usage (translate with gemma):
  python translate_human_chapters.py \
      --model gemma-4-26b-a4b-it-ud \
      --glossary output/i-have-a-haunted-house/glossary_i-have-a-haunted-house.json \
      --src "My House of Horrors" \
      --out output/i-have-a-haunted-house/myanmar \
      --chapter 1            # or --first 1 --last 5 / --all

  # Improve quality with the human-translated reference (ch1 has an aligned
  # human EN<->MY pair). The pairs are injected as few-shot style examples and
  # also used to QC each translated paragraph + write a report:
  python translate_human_chapters.py --model gemma-4-26b-a4b-it-ud \
      --src "My House of Horrors" \
      --glossary output/i-have-a-haunted-house/glossary_i-have-a-haunted-house.json \
      --pairs output/i-have-a-haunted-house/english_human_myanmar_pair_ch1.json \
      --few-shot 3 --qc-report output/i-have-a-haunted-house/qc_ch1.json \
      --out output/i-have-a-haunted-house/myanmar --chapter 1

# Then refine the translated Myanmar with padauk-gemma (separate tool):
#   python offline_novel_refine_human_md.py --model "padauk-gemma:q8_0" ...
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import requests
from dotenv import load_dotenv

from offline_novel_translate_pairs import (
    PROMPT_MD,
    _interruptible_sleep,
    _ollama,
    build_glossary_index,
    build_glossary_section,
    check_ollama,
    clean_my_text,
    format_eta,
    load_system_prompt,
    log,
    looks_incomplete,
    parse_translations,
    unload_model,
)

ROOT_DIR = Path(__file__).resolve().parent
load_dotenv(ROOT_DIR / ".env")

BATCH_SIZE = 4
MAX_RETRIES = 3
FRONT_RE = re.compile(r"^(---\s*\r?\n.*?^---\s*\r?\n)", re.DOTALL | re.MULTILINE)
HEADING_RE = re.compile(r"^#\s+.+$", re.MULTILINE)

# Scripts that must NOT appear in the Myanmar output (padauk occasionally leaks
# a few words in Telugu/Tamil/Devanagari even when the rest is Burmese).
_FOREIGN_SCRIPT_RANGES = (
    (0x0900, 0x097F),  # Devanagari
    (0x0980, 0x09FF),  # Bengali
    (0x0A00, 0x0A7F),  # Gurmukhi
    (0x0A80, 0x0AFF),  # Gujarati
    (0x0B00, 0x0B7F),  # Oriya
    (0x0B80, 0x0BFF),  # Tamil
    (0x0C00, 0x0C7F),  # Telugu
    (0x0C80, 0x0CFF),  # Kannada
    (0x0D00, 0x0D7F),  # Malayalam
    (0x0D80, 0x0DFF),  # Sinhala
    (0x0E00, 0x0E7F),  # Thai
    (0x0E80, 0x0EFF),  # Lao
    (0x1700, 0x17FF),  # Khmer
)


def has_foreign_script(text: str) -> bool:
    """True if `text` contains characters from a non-Burmese, non-Latin script."""
    return any(
        lo <= ord(ch) <= hi for ch in (text or "") for (lo, hi) in _FOREIGN_SCRIPT_RANGES
    )


def parse_chapter(text: str) -> tuple[str, str, list[str]]:
    """Return (front_matter, heading_line, body_paragraphs)."""
    fm = ""
    m = FRONT_RE.match(text)
    if m:
        fm = m.group(1)
        text = text[m.end():]
    body = text.strip()
    heading = ""
    m = HEADING_RE.match(body)
    if m:
        heading = m.group(0)
        body = body[m.end():].strip()
    paras = [p.strip() for p in body.split("\n\n") if p.strip()]
    return fm, heading, paras


def pseudo_rows(chapter: int, paras: list[str]) -> list[tuple]:
    """Wrap human paragraphs into the Row shape used by the prompt builders.

    Row = (id, novel_slug, chapter_num, para_index, en_text, zh_simplified, en_human)
    """
    return [
        (i, "human", chapter, i, p, "", p) for i, p in enumerate(paras)
    ]


def _normalize_for_match(text: str) -> str:
    """Normalize an EN sentence for reference lookup (curly quotes, whitespace, case)."""
    t = (text or "").replace("\u2018", "'").replace("\u2019", "'")
    t = t.replace("\u201c", '"').replace("\u201d", '"').replace("\u2013", "-").replace("\u2014", "-")
    t = re.sub(r"[\u00a0\xa0\s]+", " ", t).strip(" \t\r\n\"'“”")
    return t.casefold()


def load_reference_pairs(path: Optional[Path]) -> tuple[list[dict], dict[str, dict]]:
    """Load the human EN<->MY alignment JSON.

    Expects a list under ``entries`` where each entry has ``en`` and either
    ``my_original``/``my``. Returns (pairs, {normalized_en: pair}).
    """
    if not path or not path.is_file():
        return [], {}
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data.get("entries") if isinstance(data, dict) else data
    pairs: list[dict] = []
    index: dict[str, dict] = {}
    for e in entries or []:
        en = (e.get("en") or "").strip()
        my = (e.get("my_original") or e.get("my") or "").strip()
        if not en:
            continue
        rec = {"en": en, "my": my}
        pairs.append(rec)
        index[_normalize_for_match(en)] = rec
    return pairs, index


def build_few_shot_section(pairs: list[dict], n: int) -> str:
    """Render up to ``n`` human EN->MY paragraphs as a style reference block."""
    if not pairs or n <= 0:
        return ""
    shown = pairs[:n]
    block = [
        "Below are a few HUMAN-WRITTEN reference examples (English -> natural literary "
        "Myanmar) from the same novel to match the style, register and terminology. "
        "Use them to guide your translation; do NOT copy them verbatim. Lines starting "
        "with '(ref EN)' are the source meaning and '(ref MY)' is the target Burmese.\n"
    ]
    for i, p in enumerate(shown, 1):
        block.append(f"({i}) ref EN: {p['en']}")
        block.append(f"    ref MY: {p['my']}")
    return "\n".join(block) + "\n"


def check_translation(my: Optional[str], ref_my: str) -> list[str]:
    """Simple heuristic QC of a model Myanmar paragraph against the human reference.

    Returns a list of problem flags (empty = acceptable). Used both for reporting and
    to decide whether a ``--fix`` re-run is worth it.
    """
    flags: list[str] = []
    if not my or not my.strip():
        return ["empty"]
    if has_foreign_script(my):
        flags.append("foreign-script")
    if not my.strip():
        flags.append("empty")
    if ref_my:
        import difflib
        sim = difflib.SequenceMatcher(None, my, ref_my, autojunk=False).ratio()
        if sim < 0.15:
            flags.append("low-ref-sim")
        len_ratio = len(my) / max(1, len(ref_my))
        if len_ratio < 0.35:
            flags.append("too-short")
    return flags


def translate_batch_paras(
    batch: list[tuple],
    model: str,
    timeout: int,
    glossary_section: str,
    system_prompt: str,
    few_shot_section: str = "",
) -> list[Optional[str]]:
    """Translate one batch of human-EN paragraphs -> Myanmar (EN is authoritative)."""
    lines = []
    for i, (_id, _slug, _chapter, para, en_text, _zh, _eh) in enumerate(batch, 1):
        lines.append(f"{i}. EN: {(en_text or '').strip()}")
    n = len(batch)
    parts = [
        "Translate these English novel paragraphs into natural literary "
        "Myanmar (Burmese). The English text is the sole source of meaning.\n"
    ]
    if few_shot_section:
        parts.append(few_shot_section.rstrip() + "\n")
    if glossary_section:
        parts.append(glossary_section + "\n")
    parts.extend(
        [
            "Keep character / place / sect names consistent exactly as the glossary "
            "specifies (do not re-transliterate them).\n"
            "CRITICAL: Use Myanmar (Burmese) Unicode ONLY for that. NEVER "
            "copy in Telugu, Tamil, Devanagari, or any other Indic/Southeast Asian script.\n"
            "Do not add notes or explanations.\n"
            "Return ONLY valid JSON, no markdown, no thinking, no extra text:\n"
            f'{{"translations": ["...", "..."]}}\n'
            f"Exactly {n} Myanmar strings, same order as the list.\n",
            "\n".join(lines),
        ]
    )
    prompt = "\n".join(parts)
    approx_chars = sum(len(r[4] or "") for r in batch)
    num_predict = min(8192, max(2048, approx_chars * 3 + 512 * n))

    last_error: Optional[str] = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            raw = _ollama(
                prompt,
                model,
                timeout=timeout,
                retries=1,
                num_predict=num_predict,
                system=system_prompt,
            )
            translations = parse_translations(raw)

            # padauk sometimes splits one paragraph into several JSON strings
            # (at internal dialogue/newline boundaries). For a single-input
            # batch, rejoin them before the length check.
            if n == 1 and len(translations) > 0:
                translations = _join_single(translations, 1)

            if len(translations) != n:
                last_error = f"length mismatch: got {len(translations)}, expected {n}"
                continue
            cleaned: list[Optional[str]] = []
            for (_id, _slug, _ch, _pi, en_text, _zh, _eh), my in zip(batch, translations):
                my = clean_my_text(my)
                if looks_incomplete(my, en_text or ""):
                    cleaned.append(None)
                else:
                    cleaned.append(my)
            if sum(1 for x in cleaned if x) >= max(1, n // 2):
                return cleaned
            last_error = "too many incomplete Myanmar results in batch"
        except requests.RequestException as exc:
            last_error = str(exc)
        if attempt < MAX_RETRIES:
            log(f"  Batch retry {attempt + 1}/{MAX_RETRIES} ({last_error})")
            _interruptible_sleep(2 ** attempt)
    log(f"  Batch failed after {MAX_RETRIES} attempts ({last_error})")
    return [None] * n


def clean_my_text(text: str) -> str:
    """Post-process padauk Myanmar output.

    - removes foreign-script glyphs (padauk occasionally leaks a word in
      Telugu/Tamil/Devanagari) since it's the only failure-case the LLM gives us.
    """
    from offline_novel_translate_pairs import clean_my_text as _base_clean
    t = _base_clean(text or "")
    if not t:
        return ""
    return "".join(
        ch for ch in t
        if not any(lo <= ord(ch) <= hi for (lo, hi) in _FOREIGN_SCRIPT_RANGES)
    )


def _join_single(translations: list[str], num_expected: int) -> list[str]:
    """When one paragraph is returned as several JSON strings (padauk splits at
    dialogue/newline boundaries), join them back into one with a space."""
    if num_expected == 1 and len(translations) > 1:
        joined = clean_my_text(" ".join(translations))
        return [joined]
    return [clean_my_text(t) for t in translations]


def rescue_single(
    row: tuple,
    model: str,
    timeout: int,
    system_prompt: str,
) -> Optional[str]:
    """Translate ONE paragraph with a strict minimal prompt (no glossary, no labels).

    Used as a last-ditch rescue when the batch (and the normal single fallback)
    both fail. A stripped prompt removes irrelevant text so padauk replies.
    """
    en = (row[4] or "").strip()
    last_error = ""
    parts = [
        f'Translate to natural Myanmar (Burmese). Use Myanmar Unicode ONLY. '
        f'Never use Telugu/Tamil/Devanagari/Thai script.\n'
        f'Reply ONLY with the translation, no JSON, no quotes, no notes:\n'
        f"{en}",
        "Translation:",
    ]
    prompt = "\n".join(parts)
    num_predict = min(4096, max(1024, len(en) * 3 + 256))
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            raw = _ollama(
                prompt, model, timeout=timeout, retries=1,
                num_predict=num_predict, system=system_prompt,
            )
            raw = raw.split("Translation:")[-1].strip().strip('"`.: ')
            # rescue prompt sometimes yields a markdown heading — drop it
            lines = [l for l in raw.splitlines() if l.strip() and not l.strip().startswith("#")]
            raw = "\n".join(lines).strip()
            if has_foreign_script(raw):
                raw = clean_my_text(raw)
            if raw and not looks_incomplete(raw, en):
                return raw
        except requests.RequestException as exc:
            last_error = str(exc)
        if attempt < MAX_RETRIES:
            log(f"  rescue retry {attempt + 1}/{MAX_RETRIES} ({last_error})")
            _interruptible_sleep(3 ** attempt)
    return None
    # en = (row[4] or "").strip()
    # last_error = ""
    # parts = [
    #     f'Translate to natural Myanmar (Burmese). Use Myanmar Unicode ONLY. '
    #     f'Never use Telugu/Tamil/Devanagari/Thai script.\n'
    #     f'Reply ONLY with the translation, no JSON, no quotes, no notes:\n'
    #     f"{en}",
    #     "Translation:",
    # ]
    # prompt = "\n".join(parts)
    # num_predict = min(4096, max(1024, len(en) * 3 + 256))
    # for attempt in range(1, MAX_RETRIES + 1):
    #     try:
    #         raw = _ollama(
    #             prompt, model, timeout=timeout, retries=1,
    #             num_predict=num_predict, system=system_prompt,
    #         )
    #         raw = raw.split("Translation:")[-1].strip().strip('"`.: ')
    #         if has_foreign_script(raw):
    #             continue
    #         if raw and not looks_incomplete(raw, en):
    #             return raw
    #     except requests.RequestException as exc:
    #         last_error = str(exc)
    #     if attempt < MAX_RETRIES:
    #         log(f"  rescue retry {attempt + 1}/{MAX_RETRIES} ({last_error})")
    #         _interruptible_sleep(3 ** attempt)
    # return None


def build_chapter_output(
    fm: str, heading: str, paras: list[str], my_paras: list[Optional[str]]
) -> str:
    """Assemble the translated chapter as a markdown file."""
    lines: list[str] = []
    if fm:
        lines.append(fm.strip())
        lines.append("")
    if heading:
        lines.append(heading)
        lines.append("")
    for p in my_paras:
        if p:
            lines.append(p)
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass

    ap = argparse.ArgumentParser(
        description="Translate human EN novel chapters -> Myanmar (single model, strict glossary)."
    )
    ap.add_argument("--src", default=str(ROOT_DIR / "My House of Horrors"), help="Human EN chapter folder")
    ap.add_argument("--out", required=True, help="Output folder for Myanmar chapters")
    ap.add_argument("--model", required=True, help="Ollama model (e.g. padauk-gemma:q8_0)")
    ap.add_argument("--glossary", default=None, help="Glossary JSON (strict EN=MY)")
    ap.add_argument("--prompt", default=None, help="System prompt file (default prompt.md; 'none' to disable)")
    ap.add_argument("--chapter", type=int, default=None, help="Translate only this chapter number")
    ap.add_argument("--first", type=int, default=None, help="First chapter to translate (inclusive)")
    ap.add_argument("--last", type=int, default=None, help="Last chapter to translate (inclusive)")
    ap.add_argument("--all", action="store_true", help="Translate every chapter")
    ap.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    ap.add_argument("--glossary-mode", choices=["full", "dynamic"], default="full",
                    help="full=inject all glossary terms (strict); dynamic=only matched")
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--delay", type=float, default=0.0)
    ap.add_argument("--unload", action="store_true")
    ap.add_argument("--dry-run", type=int, default=0, help="Print N batch prompts without calling Ollama")
    ap.add_argument("--pairs", default=None,
                    help="Human EN<->MY alignment JSON (e.g. english_human_myanmar_pair_ch1.json). "
                         "Provides few-shot style examples + a per-paragraph quality reference.")
    ap.add_argument("--few-shot", type=int, default=3,
                    help="Number of human reference pairs to inject as few-shot style examples (0 disables)")
    ap.add_argument("--qc-report", default=None,
                    help="Write a JSON QC report comparing each translated paragraph to the human "
                         "reference (only meaningful where the human reference is aligned, e.g. ch1)")
    args = ap.parse_args()

    src = Path(args.src)
    out = Path(args.out)
    if not src.is_dir():
        log(f"ERROR: source folder not found: {src}")
        return 1
    out.mkdir(parents=True, exist_ok=True)

    glossary_path = Path(args.glossary) if args.glossary else None
    if glossary_path and not glossary_path.is_file():
        log(f"ERROR: glossary not found: {glossary_path}")
        return 1
    glossary_index = build_glossary_index(glossary_path) if glossary_path else []
    log(f"Glossary: {glossary_path.name if glossary_path else '(none)'} "
        f"[{len(glossary_index)} entries, mode={args.glossary_mode}]")

    system_prompt = load_system_prompt(Path(args.prompt) if args.prompt else None)

    ref_pairs, ref_index = load_reference_pairs(Path(args.pairs) if args.pairs else None)
    if args.pairs:
        log(f"Human reference pairs: {len(ref_pairs)} loaded, few-shot={args.few_shot}")
    else:
        log("No --pairs given; few-shot + reference QC disabled.")

    files = sorted(src.glob("chapter-*.md"))
    chapters: list[int] = []
    for f in files:
        ch = int(f.stem.split("-")[1])
        if args.chapter is not None and ch != args.chapter:
            continue
        if args.first is not None and ch < args.first:
            continue
        if args.last is not None and ch > args.last:
            continue
        if not args.all and args.chapter is None and args.first is None and args.last is None:
            continue
        chapters.append(ch)
    if not chapters:
        log("No chapters selected. Use --all, --chapter N, or --first/--last.")
        return 1
    log(f"Chapters: {len(chapters)} ({chapters[0]}..{chapters[-1]})")

    try:
        check_ollama(args.model)
    except SystemExit:
        raise
    log(f"  Warming up {args.model}...")
    try:
        _ollama("Say OK.", args.model, timeout=min(args.timeout, 120), retries=1, num_predict=16, system=system_prompt)
        log(f"  {args.model} ready.")
    except Exception as exc:
        log(f"  WARNING: warmup failed ({exc}), continuing anyway...")

    translated_ch = 0
    done_paras = 0
    failed_paras = 0
    t0 = time.time()
    try:
        for ci, ch in enumerate(chapters, 1):
            f = src / f"chapter-{ch:04d}.md"
            text = f.read_text(encoding="utf-8")
            fm, heading, paras = parse_chapter(text)
            if not paras:
                log(f"  ch{ch}: no paragraphs, skipping")
                continue
            batch = pseudo_rows(ch, paras)
            batches = [batch[i : i + args.batch_size] for i in range(0, len(batch), args.batch_size)]

            my_paras: list[Optional[str]] = [None] * len(paras)
            ch_t0 = time.time()
            few_shot_section = build_few_shot_section(ref_pairs, args.few_shot)
            log(f"\nch{ch}: {len(paras)} paras in {len(batches)} batch(es)")
            for bi, b in enumerate(batches, 1):
                batch_t0 = time.time()
                glossary_section = ""
                if glossary_index:
                    texts = [r[4] for r in b]
                    glossary_section = build_glossary_section(
                        glossary_path,
                        index=glossary_index,
                        texts=texts,
                        dynamic=(args.glossary_mode == "dynamic"),
                        max_terms=len(glossary_index),
                    )
                if args.dry_run:
                    if bi <= args.dry_run:
                        log(f"\n===== ch{ch} Batch {bi}/{len(batches)} prompt =====")
                        lines = []
                        for k, r in enumerate(b, 1):
                            lines.append(f"{k}. [ch{ch}p{r[3]}] EN: {r[4]}")
                        log("\n".join(lines))
                        if glossary_section:
                            log("--- glossary ---")
                            log(glossary_section)
                        if few_shot_section:
                            log("--- few-shot human refs ---")
                            log(few_shot_section.rstrip())
                    continue
                results = translate_batch_paras(
                    b, args.model, args.timeout, glossary_section, system_prompt,
                    few_shot_section=few_shot_section,
                )
                for r, my in zip(b, results):
                    if not my:
                        log(f"  fallback p{r[3]} retry single...")
                        try:
                            my = translate_batch_paras(
                                [r], args.model, args.timeout, glossary_section, system_prompt,
                                few_shot_section=few_shot_section,
                            )[0]
                        except requests.RequestException as exc:
                            log(f"  fail p{r[3]} error: {exc}")
                            my = None
                    if not my:
                        log(f"  rescue p{r[3]} minimal prompt...")
                        my = rescue_single(r, args.model, args.timeout, system_prompt)
                    my_paras[r[3]] = my
                    if my:
                        done_paras += 1
                        log(f"  ok  p{r[3]} | {(r[4] or '')[:45]} -> {my[:45]}")
                    else:
                        failed_paras += 1
                        log(f"  fail p{r[3]} | {(r[4] or '')[:45]}")
                elapsed = time.time() - t0
                if done_paras + failed_paras > 0:
                    rate = (done_paras + failed_paras) / elapsed
                    remaining_paras = len(paras) - (done_paras + failed_paras)
                    eta = format_eta(remaining_paras / rate)
                    log(f"  batch took {time.time() - batch_t0:.1f}s | progress {done_paras + failed_paras}/{len(paras)} ch{ch} | ETA {eta}")
                else:
                    log(f"  batch took {time.time() - batch_t0:.1f}s")
                if args.delay:
                    _interruptible_sleep(args.delay)

            if not args.dry_run:
                out_file = out / f"chapter-{ch:04d}.md"
                out_file.write_text(
                    build_chapter_output(fm, heading, paras, my_paras), encoding="utf-8"
                )
                ok = sum(1 for p in my_paras if p)
                log(f"  wrote {out_file.name} ({ok}/{len(my_paras)} paras, {time.time()-ch_t0:.1f}s)")

                if args.qc_report and ref_index:
                    import difflib
                    report_items = []
                    flagged = 0
                    for pi, (en_text, my_text) in enumerate(zip(paras, my_paras), 1):
                        ref = ref_index.get(_normalize_for_match(en_text))
                        ref_my = (ref or {}).get("my", "")
                        flags = check_translation(my_text, ref_my)
                        item = {
                            "chapter": ch,
                            "para": pi,
                            "en": en_text,
                            "my": my_text or "",
                            "ref_found": ref is not None,
                        }
                        if ref_my:
                            item["ref_my"] = ref_my
                            item["sim"] = round(
                                difflib.SequenceMatcher(None, my_text or "", ref_my, autojunk=False).ratio(), 3
                            )
                        if flags:
                            item["flags"] = flags
                            flagged += 1
                        report_items.append(item)
                    qc = Path(args.qc_report)
                    qc.parent.mkdir(parents=True, exist_ok=True)
                    payload = {"chapter": ch, "total": len(report_items),
                               "flagged": flagged, "items": report_items}
                    qc.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
                    log(f"  QC report ch{ch}: {flagged}/{len(report_items)} flagged -> {qc.name}")
            translated_ch += 1
        log(
            f"\nDone in {format_eta(time.time() - t0)}. "
            f"Chapters: {translated_ch}, paras OK: {done_paras}, failed: {failed_paras}"
        )
        return 0 if failed_paras == 0 else 2
    except KeyboardInterrupt:
        log(f"\nInterrupted. Partial: {translated_ch} chapters, {done_paras} OK, {failed_paras} failed.")
        return 130
    finally:
        if args.unload:
            try:
                unload_model(args.model)
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
