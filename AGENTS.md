# AGENTS.md

This file provides guidance to Opencode when working with code in this repository.

## Project Purpose

This repository is a **web-novel translation pipeline** that translate Chinese(english source text) novels and truns them into **readable Myanmar (Burmese)**.Independent translation paths exist:

1. **Human-MD path.** When a human English translation exists (`books\My House of Honnor\*.md`), each chapter is translated straight to Myanmar directly, then refined against the human En source.

All LLM calls are **offline via local ollama**.

## Core Decision

- **Lanague / runtime**: Python 3.10+, stdlib-first; `requests`, `dotenv`,
  `sqlite3`, `flashtext`

- **Translation backend:** local **Ollama** (`OLLAMA_HOST`, default
  `http://localhost:11434`, `/api/generate` endpoint). Calls use
  `think=false`, `keep_alive=-1`, `temperature=0.2`, and a batch/`num_predict`
  scaled to input length.

- **Models (benchmarked):**
  - `padauk-gemma:q8_0` — **best for Burmese output** (translate + refine).
  - `gemma4:31b` — best general EN `/` ZH→MY; needs its own
    prompt in `prompts/prompt.md`.
  - `qwen3.8:latest` — recommended fallback (analyzer / structured JSON tasks).
  Default model comes from `OLLAMA_MODEL` in `.env`; scripts accept `--model`.

- **Prompt strategy:** a system prompt (style guide) + injected **strict glossary**
  (`EN = MY`, matched terms only via flashtext). JSON-only output
  (`{"translations": [...]}`), parsed with a tolerant/malformed-JSON recovery
  helper (missing closing brackets, wrapped objects, leaked role labels).

- **Resumability:** every run is resume-safe. Progress is **committed after every batch** and on `Ctrl+C`.

## Non-Negotiable Constraints

- **Output must be standard Myanmar (Burmese) Unicode** (U+1000–U+109F) — no
  Thai, Devanagari, Bengali, Tamil, Telugu, Hangul; no Arabic question mark `؟`;
  no mojibake (`Ã…`-style); no `U+FFFD` replacement chars; no stray Chinese.
- **Never re-transliterate glossary names/terms.** Reuse the exact `EN = MY`
  spelling from the glossary in every prompt; unknown names must be
  transliterated *consistently* throughout a run.
- **JSON-only responses**: `{"translations": [...]}` (translate) /
  `{"results": [...]}` (refine). No markdown fences, no thinking, no
  meta-commentary, no explanatory appendices.
- **Numbers use Myanmar numerals** (`500` → `၅၀၀`); punctuation uses ASCII
  `? ! .` (never `؟`).
- A lone `"......"` / `"…"` paragraph is a valid translation — keep it verbatim
  (punctuation-only test runs before the "echoed source" rejection).
- Original data (`my_text`, downloaded chapters, glossary) is **read-only**:
  translation/refine writes *new* columns; defaults skiim already-done rows.
- Save progress per batch; never leave the MD half-written; close the
  connection cleanly on every exit path (including `KeyboardInterrupt`).

## Domain Invariants

- **Book (resource)**: human EN chapters in `books\My House of Horrors\chapter-####.md`
  (YAML front-matter + `# heading` + blank-line-separated paragraphs). Human EN→MY reference pairs at `en_mm_human_pair\i-have-a-haunted-house.json`.
- **Per-novel glossary**: `glossary\glossary_i-have-a-haunted-house.json`.
- **Config**: `.env` supplies `OLLAMA_HOST`, `OLLAMA_MODEL`, `OPENCODE_API_KEY`,
  `MODEL`. Never commit real keys.
- **Chapter selection**: `--chapter N`, `--chapter-to N` (single / `<= N`); no arbitrary open ranges; `--first N --last N` only in `translate_human_chapters.py`.

## Boundaries

- **Never copy model output blindly** — every Myanmar string passes
  `clean_my_text()` + `looks_incomplete()` (empty, echo-of-source, non-Burmese
  script) before being accepted.
- **Do not scrape on a schedule** or hammer sites; the scraper is resume-safe and
  polite by design (delays, retries/backoff on `403`/`429`).
- **Do not** store secrets in code, or commit `.env` / key files.
- Do not refactor shared helpers without re-running `pytest` — the other scripts import them.
- Avoid adding heavy deps (e.g. anthropic-sdk) for things `requests` can do.

## Priorities

- **Correctness of Burma literary output** over throughput. Small batches
  (refine batch_size=1) + generous `num_predict`.
- **Name/term consistency** (glossary) beats raw fluency on outlier terms.
- **Data-loss avoidance** is higher priority than speed: safe write paths.
- For pipeline stats / reporting, prefer `--dry-run` first, then a small
  `--limit`, then the full `--limit 0` run.

## External Systems

- **Ollama** (local, offline) — translation & refine. `OLLAMA_HOST`,
  `OLLAMA_MODEL`, `OLLAMA_API_KEY`.
- **OpenCode API** (`https://opencode.ai/zen/v1`) — online glossary extraction Keys via `OPENCODE_API_KEY`.

## Repository Map

translate_novel
│   .env                  # python venv
│   .gitignore
│   AGENTS.md             # this file + usage docs (source of truth)
│   main.py
│   requirements.txt
│   README.md
│
├───.opencode
│   │   .gitignore
│   │
│   └───agents
│           codex-reviewer.md
│
├───books                  # Source chapter files (*.md)
│   └───My House of Horrors # 140+ human EN chapters (resource)
│           chapter-0001.md
│           .....
│           chapter-1215.md
│
├───en_mm_human_pair
│       i-have-a-haunted-house.json
│
├───glossary               # glossary category samples
│       glossary_i-have-a-haunted-house.json
│       context_memory.json     # Dynamic chapter context
│
├───output
│   └───{novel_name}/      # ★ Per-novel output folder (created on first run)
├───prompts                # system prompts
│       prompt.md          #   master literary style guide
│
├── logs/
│       translation.log
└───src
    ├───core
    ├───docker
    ├───tests/             tests passing (pytest tests/ -v)
    └───tools              # misc helpers:

## Safety / Never Do

- **Never delete** source data needed for resume: `books\My House of Horrors`, glossary, `.env` — treat as opaque system data.
- Do **not run `--force`** on the DB path without first backing up.
- Do not run full-novel jobs (`--limit 0`) as sanity `pytest` passes first; a mis-batch prompt can burn model-hours.
- `rm -rf` / `Remove-Item -Recurse` on tracked data is off-limits unless the
  user explicitly asks.
- Secrets (`.env`, `OPENCODE_API_KEY`) must never be committed or pasted in
  prompts/logs.
