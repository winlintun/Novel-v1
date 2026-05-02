# Novel Translation Pipeline

AI-powered Chinese/English-to-Myanmar (Burmese) novel translation system specializing in Wuxia/Xianxia cultivation novels.
**Ollama-only** — runs entirely on local models, no cloud API needed.

> **Quick start**: `python -m src.main --novel reverend-insanity --chapter 1`
> **Web UI**: `python -m src.main --ui`
> **Full help**: `python -m src.main --help`

---

## Features

| Feature | Description |
|---------|-------------|
| Dual workflows | way1 (EN→MM direct), way2 (CN→EN→MM pivot) — auto-detected |
| 6-stage pipeline | Translate → Refine → Reflect → Quality Check → Consistency → QA |
| Smart chunking | Token-aware, paragraph-safe, zero overlap, rolling context |
| 3-tier memory | Glossary (persistent) + Context (FIFO) + Session rules |
| Glossary engine | Auto-extract terms, confidence-based auto-promote, deduplication |
| Quality gates | Myanmar ratio ≥70%, register mixing, archaic words, particle repetition |
| Auto-review | Per-chapter quality reports in `logs/report/` |
| Quality stats | `--stats` shows per-chapter score trends with bar charts |
| Web UI | 6-page Streamlit interface: Quickstart, Translate, Progress, Glossary, Settings, Reader |
| CI/CD | GitHub Actions: Python 3.10-3.13, Ruff linter, 35% coverage |

---

## Quick Start

### 1. Install
```bash
pip install -r requirements.txt
ollama pull padauk-gemma:q8_0
ollama pull alibayram/hunyuan:7b
```

### 2. Translate
```bash
# Single chapter (auto-detects language)
python -m src.main --novel reverend-insanity --chapter 1

# Chapter range
python -m src.main --novel reverend-insanity --chapter-range 1-10

# All chapters starting from chapter 5
python -m src.main --novel reverend-insanity --all --start 5

# Single file
python -m src.main --input data/input/reverend-insanity/ch001.md
```

### 3. Review Quality
```bash
# Review a translated file
python -m src.main --review data/output/reverend-insanity/reverend-insanity_chapter_001.mm.md

# Show quality score trends for entire novel
python -m src.main --stats --novel reverend-insanity

# View translated file in terminal
python -m src.main --view data/output/reverend-insanity/reverend-insanity_chapter_001.mm.md
```

### 4. Manage Glossary
```bash
# Generate glossary from first 5 chapters
python -m src.main --novel reverend-insanity --generate-glossary --chapter-range 1-5

# Auto-promote high-confidence pending terms
python -m src.main --auto-promote --novel reverend-insanity
```

### 5. Web UI
```bash
python -m src.main --ui
# or: streamlit run ui/streamlit_app.py
```

---

## CLI Reference

```
python -m src.main [OPTIONS]

Translation:
  --novel NAME              Novel name
  --chapter N               Single chapter
  --chapter-range 1-10      Chapter range
  --all                     All chapters
  --start N                 Start chapter (default: 1)
  --input FILE              Single input file
  --output-dir DIR          Override output directory

Workflow:
  --workflow {way1,way2}    Force workflow (auto-detected if omitted)
  --lang {zh,en}            Source language hint
  --mode {full,lite,fast}   Pipeline mode
  --skip-refinement         Skip Stage 2 (faster)
  --use-reflection          Enable self-correction (Stage 3)

Config:
  --config FILE             Config file (default: config/settings.yaml)
  --model MODEL             Override translator model

Quality & Review:
  --review FILE             Review translated .mm.md file
  --stats                   Show per-chapter score trends (requires --novel)
  --view FILE               View translated file in terminal

Glossary:
  --generate-glossary       Generate glossary from chapters
  --auto-promote            Promote high-confidence pending terms (requires --novel)

Utilities:
  --ui                      Launch Streamlit web UI
  --test                    Run sample translation test
  --clean                   Clear Python cache
  --no-metadata             Skip metadata in output
  --version                 Show version
```

---

## Supported Models

| Model | Quality | Speed | Best For |
|-------|---------|-------|----------|
| `padauk-gemma:q8_0` | ⭐⭐⭐⭐⭐ | ~5 min/chunk | **Primary** EN→MM output |
| `alibayram/hunyuan:7b` | ⭐⭐⭐⭐ | Medium | CN→EN pivot (way2 Stage 1) |
| `qwen:7b` | ⭐⭐⭐ | Fast | QA checks, glossary sync |

---

## Architecture

```
Input → Preprocess → Translate → Refine → Reflect → Quality Check → Consistency → QA → Output
         (chunk)     (Stage 1)  (Stage 2)  (Stage 3)  (Stage 4)      (Stage 5)    (Stage 6)
```

### Pipeline Stages

| Stage | Agent | Role |
|-------|-------|------|
| 1 | `Translator` | CN/EN → MM translation with glossary + rolling context |
| 2 | `Refiner` | Literary editing, natural flow, glossary enforcement |
| 3 | `ReflectionAgent` | Self-critique + iterative improvement |
| 4 | `MyanmarQualityChecker` | Archaic words, register mixing, particle repetition |
| 5 | `Checker` | Glossary consistency (untranslated terms + target spelling) |
| 6 | `QATesterAgent` | Markdown, Myanmar ratio, placeholders, chapter title |

---

## Memory System

| Tier | Storage | Scope |
|------|---------|-------|
| Glossary | `data/glossary_{novel}.json` | Persistent (per-novel isolation) |
| Context | `data/context_memory_{novel}.json` | Chapter FIFO buffer (last 3) |
| Pending | `data/glossary_pending_{novel}.json` | Terms awaiting review |

---

## Directory Structure

```
├── config/settings.yaml          # Main config (Ollama-only)
├── data/
│   ├── input/{novel}/            # Source chapters (*.md)
│   └── output/{novel}/           # Translated output (*.mm.md + meta.json)
├── src/
│   ├── agents/                   # 8 pipeline agents
│   ├── cli/                      # CLI parser, commands, formatters
│   ├── config/                   # Pydantic config models + loader
│   ├── memory/                   # MemoryManager (3-tier + dedup)
│   ├── pipeline/                 # TranslationPipeline orchestrator
│   └── utils/                    # postprocessor, chunker, ollama_client, fluency_scorer, reviewer
├── tests/                        # 254 tests (35% coverage)
├── logs/report/                  # Auto-generated quality reports
└── ui/                           # 6-page Streamlit Web UI
```

---

## Testing

```bash
pytest tests/ -v                          # All tests
pytest tests/ -v --cov=src --cov-report=term   # With coverage
ruff check src/ tests/ --select=E,F       # Lint
```

---

## License

MIT License — see `LICENSE`
