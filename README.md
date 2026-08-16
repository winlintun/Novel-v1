# Translate Novel — English → Literary Burmese Translation Pipeline

Offline web-novel translation pipeline that turns English (human-translated) novel chapters into
standard **Myanmar (Burmese) Unicode** with named-character consistency, using a local **Ollama**
backend. No cloud APIs are required for translation.

## Features

- **Chunked translation**: chapters are split into context-aware chunks (scene breaks, dialogue
  runs, optional overlap) to fit the model's context window.
- **Strict glossary enforcement**: per-novel `EN = MY` glossary (names, places, terms). Matched
  terms are spell-checked and auto-fixed; wrong variants are flagged.
- **Verification gate**: glossary identity, overlap identity, formatting, register mixing, stray
  English fragments, voice continuity across chapters (active-speaker pronouns).
- **Auto-verify / revise loop**: deterministic auto-fix first, then fix-mode retranslation.
- **LLM auditor**: grades flow / voice / terminology / literary quality (A–F), with a heuristic
  fallback when the model is unavailable.
- **Resume-safe**: progress is committed to disk after every batch; already-done chapters are
  skipped unless `--force`.
- **Testing**: `pytest tests/ -q` — 102 tests across unit + end-to-end orchestration.

## Architecture

```
main.py                      CLI entry point
src/pipeline/
  orchestrator.py            state machine: ingest → chunk → translate → verify → audit → commit
  chunker.py                 paragraph grouping, scene breaks, overlap
  glossary.py                glossary index (longest-first, flashtext + regex fallback)
  translator.py              draft + polish passes via Ollama, fixed-format JSON prompt
  postprocessor.py           clean_my_text, enumerate_overlap, glossary enforcement
  verifier.py                deterministic quality gate (R-GLOSS / R-FORBID / R-STRUCT / R-CTX…)
  auditor.py                 A–F grading with LLM + heuristic path
  prompt_builder.py          prompt assembly (glossary section, context, few-shots)
  context_buffer.py          cross-chapter memory (active speakers, running summary)
  rules.py                   auto/verify/audit rule engine (config/rules.json)
  ollama_client.py           local Ollama HTTP client (backoff, retries, error matrix)
  markdownio.py              chapter .md parse/build (YAML front-matter + heading + paragraphs)
tests/                       pytest suite (unit + e2e with a scriptable fake Ollama)
```

## Requirements

- Python 3.10+
- Local **Ollama** running at `http://localhost:11434`
- A Burma-capable model installed (see `.env` → `OLLAMA_MODEL`; e.g. `padauk-gemma:q8_0`)

```powershell
python -m venv env
.\env\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Configuration

Create a `.env` file (never commit it):

```ini
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=padauk-gemma:q8_0
```

`config/` holds the pipeline rules:

| File | Purpose |
|------|---------|
| `config/chunking_rules.json` | chunk size, dialogue grouping, overlap paragraphs |
| `config/rules.json` | auto / verify / audit rules with severity + max_auto_fix cap |
| `config/style_guide.json` | literary register guide for the system prompt |

Per-novel glossary lives at `config/<novel>/glossary_<novel>.json`:

```json
{
  "version": "0.1",
  "novel_title": "…",
  "entries": [
    {
      "term": "Chen Ge",
      "translation": "ချန်ဂီ",
      "original_name": "陈歌",
      "category": "character",
      "gender": "male",
      "locked": true,
      "aliases": ["Chen Ge", "Boss"],
      "pronoun_dialogue": "ငါ",
      "particles": ["ကွာ", "ဗျာ"],
      "my_variants": ["ချန်ဂေါ်"]
    }
  ]
}
```

- `translation` is the canonical Burmese spelling the verifier enforces.
- `aliases` lets the glossary match alternate source spellings.
- `pronoun_dialogue` / `particles` feed the voice-continuity check.
- `locked: true` marks a term that must never be re-transliterated.

## Usage

Run a single chapter from a book under `books/<novel>/`:

```powershell
python main.py --novel my_house_of_horrors --chapter 1
```

Translate a range of chapters:

```powershell
python main.py --novel my_house_of_horrors --chapter 1 --chapter-to 5
```

Translate an explicit source file (with per-novel glossary and human-pair few-shots):

```powershell
python main.py --src books/MyHouseOfHorrors/chapter-0001.md `
  --glossary config/my_house_of_horrors/glossary_my_house_of_horrors.json `
  --pairs en_mm_human_pair/i-have-a-haunted-house.json
```

Dry-run — print the assembled prompt for the first N chunks without calling Ollama:

```powershell
python main.py --src tests/fixtures/chapter-en-0001.md `
  --glossary tests/fixtures/glossary-minimal.json `
  --dry-run 1
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--novel` | `my_house_of_horrors` | slug under `books/`; also selects default glossary |
| `--src` | — | explicit source chapter `.md` (overrides `--novel`/`--chapter`) |
| `--chapter` | `1` | chapter number |
| `--chapter-to` | — | last chapter (inclusive) for a range run |
| `--out` | `output` | output root directory |
| `--config` | `config` | dir with `chunking_rules.json`, `rules.json`, `style_guide.json` |
| `--model` | `OLLAMA_MODEL` | Ollama model name |
| `--temperature` | `0.2` | sampling temperature |
| `--glossary` | auto | glossary JSON path |
| `--pairs` | — | human EN↔MY few-shot pair JSON |
| `--human-ref` | — | human-translated reference `.md` for the auditor |
| `--compare-with-human` | — | auditor compares output against `--human-ref` |
| `--no-two-pass` | — | draft only, skip the polish pass |
| `--no-auto-fix` | — | disable deterministic glossary auto-fix |
| `--no-audit` | — | skip the auditor (useful for smoke runs) |
| `--myanmar-numbers` | — | convert digits to Myanmar numerals |
| `--dry-run N` | `0` | print prompts for the first N chunks, never call Ollama |
| `--limit N` | `0` | translate at most N chunks (0 = all) |
| `--max-revise` | `3` | verify/revise attempts per chunk |
| `--force` | — | re-translate even if the chapter is already committed |

### Output

Per-novel results are written under `output/<novel>/`:

```
output/<novel>/
  chapter-my-<no>.md      translated + verified chapter
  metadata.json           run metadata + final grade
  audit-report.json       auditor report (when audit enabled)
  archive/…               context buffer snapshots for resume
```

## Tests

```powershell
python -m pytest tests/ -q
```

The e2e suite uses a scriptable fake Ollama — no server or network needed.

## Safety Notes

- Source chapters, glossaries, and `.env` are treated as read-only input.
- Never commit `.env` or real API keys.
- Run `--dry-run` with a small `--limit`, then a small batch, before a full `--limit 0` run.