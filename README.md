# ဝတ္ထုဘာသာပြန် Pipeline (Novel Translation Pipeline)

AI-powered English/Chinese → Myanmar novel translation system using local LLMs (Ollama). Built for Xianxia, Wuxia, and Fantasy novels with production-grade quality gates.

---

## ⚡ Interactive Launchers (No Manual Commands)

Don't want to type long `python -m src.main --novel ... --chapter ...` commands? Two menu-driven helper scripts do it for you — they discover your novels/chapters, build the command, and run it.

### `scripts/translate.py` — Run any pipeline function from a menu

```bash
python scripts/translate.py            # interactive menus
python scripts/translate.py --dry-run  # show the command without running it
```

Top-level menu:

```
=== Novel Translation Launcher ===
  1. Translate chapters
  2. Generate glossary
  3. Approve / promote glossary terms
  4. Show quality stats
  5. Review / view a translated file
  6. Launch web UI
```

What each option does (it just assembles the matching CLI command):

| Menu | Sub-options | Example command built |
|------|-------------|-----------------------|
| **1. Translate chapters** | single / range / all + mode + optional model | `--novel a-will-eternal --chapter 5 --mode single_stage` |
| **2. Generate glossary** | source chapters / EN↔MM pairs / init 1-5 | `--generate-glossary --chapter-range 1-10 --from-mm` |
| **3. Approve / promote** | auto-promote / bulk approve | `--novel a-will-eternal --approve-glossary` |
| **4. Quality stats** | (novel only) | `--stats --novel a-will-eternal` |
| **5. Review / view file** | view / review + file path | `--view <file.mm.md>` |
| **6. Web UI** | port prompt | `--ui --port 5000` |

- Novels and chapter numbers are auto-discovered from `data/input/` — just pick from the list.
- After each action it returns to the main menu; press `q` (or `b`/`back` in a submenu) to go back.
- `--dry-run` prints the exact command so you can learn the CLI as you go.

### `scripts/change_model.py` — Switch the Ollama model per role

Reassign the model used for each pipeline role (`translator`, `refiner`, `checker`, `editor`) without hand-editing `config/settings.yaml`. It lists the models actually installed in Ollama and edits the YAML in place (comments preserved).

```bash
python scripts/change_model.py                 # interactive menu
python scripts/change_model.py --list          # show current roles + installed models
python scripts/change_model.py --set translator=padauk-gemma:q8_0   # non-interactive
```

Example `--list` output:

```
Current role -> model mapping (config/settings.yaml):
  translator  gemma4-e4b-it:q8_0
  refiner     padauk-gemma:q8_0
  checker     padauk-gemma:q8_0
  editor      padauk-gemma:q8_0

Installed Ollama models:
   1. gemma4-e4b-it:q8_0
   2. padauk-gemma:q8_0
```

> Tip: use `change_model.py` to set the default model, then `translate.py` to run — or override the model right inside the translate menu for a single run.

---

## 🚀 First-Run Setup Guide

Follow these steps **in order** on your first run. Skipping steps (especially glossary generation and RAG alignment) will significantly reduce translation quality.

### Step 1: Install Prerequisites

```bash
# Python 3.10+ required
python --version

# Install dependencies
pip install -r requirements.txt

# Install Ollama from https://ollama.com and ensure it's running
ollama serve

# Pull the mandatory Myanmar translation model
ollama pull padauk-gemma:q8_0

# Optional but recommended models
ollama pull alibayram/hunyuan:7b   # CN→EN pivot (needed for Chinese source novels)
ollama pull qwen:7b                # Validation/fallback
```

### Step 2: Prepare Input Files

Place your source `.md` chapter files in the correct directory:

```
data/
└── input/
    └── your-novel-name/
        ├── en/                          # English source files (way1)
        │   ├── your-novel-name_chapter_001.md
        │   └── ...
        └── your-novel-name_chapter_001.md   # Chinese source (way2, or mixed)
```

**File naming rules:**
- Novel directory name = novel slug (e.g., `a-will-eternal`, `reverend-insanity`)
- Chapter files: `{novel}_chapter_{XXX}.md` (e.g., `a-will-eternal_chapter_001.md`)
- Source language is auto-detected (EN → way1, CN → way2 pivot)

### Step 3: Initialize Database & Import Universal Glossary

**Run this ONCE before your first translation:**

```bash
# Verify project setup (creates DB, checks paths, runs a test chunk)
python -m src.main --test

# View what was imported
python tools/glossary_stats.py
```

This populates the SQLite database with universal cultivation terms like 金丹 → ကျင့်တန်း, 筑基 → ကျူးကျီ, etc.

### Step 4: Generate Novel-Specific Glossary

**BEFORE translating, extract terms from your novel's chapters:**

```bash
# Extract glossary terms from chapters 1-5 of your novel
python -m src.main --novel your-novel-name --generate-glossary --chapter-range 1-5

# Or use --init-glossary to extract and then STOP (for human review)
python -m src.main --novel your-novel-name --init-glossary

# Extract glossary from EXISTING EN↔MM translation pairs
# (uses actual terms from both en/*.md and mm/*.md — more accurate)
python -m src.main --novel your-novel-name --generate-glossary --chapter-range 1-5 --from-mm
```

This scans your source chapters and extracts character names, places, cultivation levels, and items. New terms go into **pending** state — they are NOT used in translation until approved.

**Two modes:**
- Default (`--generate-glossary`): reads English source and asks the model to **generate** Myanmar transliterations
- `--from-mm`: reads **both** English source and existing Myanmar translation, asks the model to **extract** the actual Myanmar terms used in the translation — guarantees the glossary matches what's in your translated text

### Step 5: (Optional) Run Dataset Alignment for RAG

**If you have existing translations** (human or previous sessions), align them to build a RAG database for few-shot retrieval. This dramatically improves consistency:

```bash
# Populate RAG with aligned EN→MY sentence pairs
python tools/run_dataset_alignment.py --novel your-novel-name

# Process all novels at once
python tools/run_dataset_alignment.py --all
```

The alignment pipeline:
1. Pairs source chapters with existing `.mm.md` translations
2. Runs BGE-M3 embeddings + DP sentence alignment (1:1 pairs)
3. Validates pairs with 16 quality checks
4. Populates SQLite RAG database → used during translation for few-shot examples

**Without this step**, the LLM translates each chunk from scratch with no reference examples — terminology and name consistency will suffer.

### Step 6: Review & Approve Glossary

Before translating, review and approve extracted terms:

```bash
# Approve ALL pending terms at once (quick start)
python -m src.main --novel your-novel-name --approve-glossary

# Or auto-approve high-confidence terms (confidence ≥ 0.75)
python -m src.main --novel your-novel-name --auto-promote

# Or use the Web UI for selective review
python -m src.main --ui
# Navigate to Glossary tab → review pending terms
```

**Standalone Glossary Review UI** (port 5001, more powerful than Web UI):
```bash
python -m glossary_app.app
# Open http://127.0.0.1:5001
```
Features: filter by status/category/confidence, search, inline edit, bulk approve, audit log.

Approved terms are injected into every translation prompt (top 20 per call). Unapproved terms are skipped — the model will either guess or output `【?term?】` placeholders.

### Step 7: Run Your First Translation

```bash
# Translate a single chapter (auto-detects EN→MM or CN→EN→MM)
python -m src.main --novel your-novel-name --chapter 1

# Translate a range
python -m src.main --novel your-novel-name --chapter-range 1-10

# Translate all chapters
python -m src.main --novel your-novel-name --all
```

Output appears in `data/output/{novel}/` as `{novel}_chapter_XXXX.mm.md`.

**Pipeline modes** (recommended: `single_stage` for padauk-gemma):
- `--mode single_stage` — Translate only (best quality/speed balance)
- `--mode lite` — Translate → Refine → Quality
- `--mode full` — All 6+ stages (slowest, highest quality)

### Step 8: Verify Output Quality

```bash
# View the translated chapter
python -m src.main --view data/output/your-novel/your-novel_chapter_0001.mm.md

# Run quality review
python -m src.main --review data/output/your-novel/your-novel_chapter_0001.mm.md

# Check stats across all chapters
python -m src.main --stats --novel your-novel-name
```

Quality gates enforce: Myanmar ratio ≥ 70%, quality score ≥ 70/100, zero Indic script leakage, no paragraph duplication, placeholder integrity check.

---

## 📖 Project Overview

**Multi-language support**: EN→MM (way1) and CN→EN→MM (way2) — auto-detected from input.

**8-stage pipeline**: Preprocess → Translate → Refine → Reflect → Quality → Consistency → FictionEditor → QA

**3-tier memory system**:
- **Glossary**: Per-novel term database (characters, places, levels, items)
- **Context**: Rolling chapter summaries (FIFO sliding window, last 3 chapters)
- **Session**: Dynamic corrections per translation session

**Key features**:
- Production-quality gates with automatic retry
- SQLite database (10 tables) with full audit trail
- RAG retrieval (ChromaDB + SQLite) for few-shot examples
- Flask Web UI with Dashboard, Editor, Reader, Glossary Manager
- Version control: chapter snapshots, rollback, diff
- LoRA fine-tuning from human-rated translations

---

## 🖥️ CLI Reference

> Prefer menus? Run `python scripts/translate.py` to drive everything below interactively (see [Interactive Launchers](#-interactive-launchers-no-manual-commands)).

### Translation

```bash
python -m src.main --novel <name> --chapter <N>
python -m src.main --novel <name> --chapter-range <M-N>
python -m src.main --novel <name> --all [--start <N>]
python -m src.main --input <file.md>

# Force workflow
python -m src.main --novel <name> --chapter 1 --workflow way1   # EN→MM
python -m src.main --novel <name> --chapter 1 --lang zh          # CN→MM

# Custom config
python -m src.main --novel <name> --chapter 1 --config config/settings.pivot.yaml
python -m src.main --novel <name> --chapter 1 --mode single_stage
python -m src.main --novel <name> --chapter 1 --model qwen:7b
```

### Glossary Management

```bash
# Generate glossary terms from chapters
python -m src.main --novel <name> --generate-glossary --chapter-range 1-5

# Initial glossary (extract → stop for review)
python -m src.main --novel <name> --init-glossary

# Approve pending terms
python -m src.main --novel <name> --approve-glossary
python -m src.main --novel <name> --auto-promote

# Import universal glossary (one-time, 490+ terms)
python scripts/import_universal_glossary.py

# Mine glossary from existing EN/MM parallel corpus
python tools/mine_glossary.py --novel-id <id> --en-dir data/input/<novel> --my-dir data/output/<novel>

# Glossary statistics
python tools/glossary_stats.py [--novel <id>]
```

### Dataset Alignment (RAG)

```bash
python tools/run_dataset_alignment.py --novel <name>
python tools/run_dataset_alignment.py --all
python tools/run_dataset_alignment.py --novel <name> --skip-validators
python tools/run_dataset_alignment.py --novel <name> --no-rag
```

### Quality & Review

```bash
python -m src.main --review <file.mm.md>
python -m src.main --view <file.mm.md>
python -m src.main --stats --novel <name>
python -m src.main --novel <name> --rebuild-meta
```

### Web UI

```bash
python -m src.main --ui
python -m src.main --flask --port 8080
```

### Utilities

```bash
python -m src.main --test            # Verify setup + test translation
python -m src.main --clean           # Clear Python cache
python -m src.main --version
python -m src.main --novel <name> --compare-models   # Model comparison
python -m src.main --rate-rejected --novel <name>    # Rate rejected chunks
python -m src.main --finetune --novel <name>         # LoRA fine-tuning
```

### Database & Versioning

```bash
python -m src.main --migrate-sql --novel <name>      # JSON→SQLite migration
python -m src.main --novel <name> --versions          # List versions
python -m src.main --novel <name> --rollback <hash>   # Rollback chapter
python -m src.main --novel <name> --diff <hash1> <hash2>
```

---

## 📚 Glossary System

The glossary system has three tiers: **LLM extraction** (runtime), **offline mining** (batch from parallel corpus), and **universal import** (pre-mined xianxia terms).

### Tier 1: LLM Glossary Generation (Pre-Translation)

Extracts character names, places, cultivation levels, and items from source chapters using an LLM:

```bash
# Generate glossary from chapters 1-5
python -m src.main --novel <name> --generate-glossary --chapter-range 1-5

# Extract then STOP for human review
python -m src.main --novel <name> --init-glossary
```

Extracted terms go to **pending** state. You must approve them before they appear in translation prompts.

### Tier 2: Universal Glossary Import (One-Time)

490+ pre-mined xianxia/cultivation terms (金丹→ကျင့်တန်း, 筑基→ကျူးကျီ, etc.):

```bash
# Preview only (no DB changes)
python scripts/import_universal_glossary.py --dry-run

# Import all terms
python scripts/import_universal_glossary.py

# View stats
python tools/glossary_stats.py
python tools/glossary_stats.py --novel <name> --json
```

### Tier 3: Offline Glossary Mining (From Parallel Corpus)

If you already have translated `.mm.md` files, mine new glossary terms from aligned EN/MM chapter pairs:

```bash
# Basic mining
python tools/mine_glossary.py --novel-id novel_<name> --en-dir data/input/<name> --my-dir data/output/<name>

# Dry-run first (preview only)
python tools/mine_glossary.py --novel-id novel_<name> --en-dir data/input/<name> --my-dir data/output/<name> --dry-run

# With LLM verification (more accurate but slower)
python tools/mine_glossary.py --novel-id novel_<name> --en-dir data/input/<name> --my-dir data/output/<name> --limit-chapters 5

# Skip LLM verification (faster)
python tools/mine_glossary.py --novel-id novel_<name> --en-dir data/input/<name> --my-dir data/output/<name> --no-llm
```

### Approving Glossary Terms

```bash
# Approve all pending
python -m src.main --novel <name> --approve-glossary

# Auto-approve high confidence (≥ 0.75)
python -m src.main --novel <name> --auto-promote
```

### Standalone Review UI

A dedicated Flask app for glossary review (port 5001):

```bash
python -m glossary_app.app
# http://127.0.0.1:5001
```

Features: filter by status/category/confidence, search, inline edit target/category, add variants, bulk approve/reject, full audit log.

---

## 🔍 Dataset Alignment Pipeline (RAG Data Preparation)

Populates the RAG database with aligned EN→MY sentence pairs from existing chapter files. This enables few-shot retrieval during translation — the LLM receives 3 similar EN-MY pairs as examples instead of translating each chunk from scratch.

### When To Run

Run this **after** you have translated a few chapters (or have existing human translations). Without it, the LLM translates with zero reference examples.

### Usage

```bash
# Process a single novel
python tools/run_dataset_alignment.py --novel <name>

# Process all novels
python tools/run_dataset_alignment.py --all

# Skip validators (faster, just populate RAG)
python tools/run_dataset_alignment.py --novel <name> --skip-validators

# Skip RAG population (validation only)
python tools/run_dataset_alignment.py --novel <name> --no-rag

# Adjust alignment sensitivity (default: 0.50)
python tools/run_dataset_alignment.py --novel <name> --min-similarity 0.6
```

### What It Does

1. **Scan**: Reads source `.md` files from `data/input/<name>/` (including `en/` subdirectory)
2. **Pair**: Matches with target `.mm.md` files from `data/output/<name>/`
3. **Align**: DP sentence alignment with BGE-M3 embeddings
4. **Validate**: 2 quality checks (omission ratio, inflation ratio)
5. **Ingest**: Populates `data/novel_v1_dataset.db` → `translation_pairs` table

### Data Flow

```
1. python tools/run_dataset_alignment.py --novel <name>
   ↓
2. Pipeline reads data/input/<name>/*.md + data/output/<name>/*.mm.md
   ↓
3. DP alignment creates 1:1 sentence pairs
   ↓
4. Pairs inserted into data/novel_v1_dataset.db (translation_pairs table)
   ↓
5. python -m src.main --novel <name> --chapter N
   ↓
6. RAGRetriever finds relevant pairs → injected into translator prompt
   ↓
7. Better terminology, name, and register consistency
```

### Reports

After each run, reports are saved to `data/reports/alignment/`:
- `{novel}_alignment_report.html` — Interactive HTML
- `{novel}_alignment_report.json` — Machine-readable summary

---

## 🌐 Web UI

| Page | Function |
|---|---|
| **Dashboard** | Translation history, quality stats, progress |
| **Translate** | Select novel/chapter and translate |
| **Editor** | Review/edit translated text |
| **Reader** | Read translated novel by chapter |
| **Glossary** | Review/approve/reject glossary terms |
| **Settings** | Model, config, database settings |
| **Cleanup** | Clear cache and temp files |

Standalone Glossary Review UI (port 5001):
```bash
python -m glossary_app.app
```

---

## 📊 Quality System

### Quality Gates
```
Score ≥ 70  → PASS
Score 50-69 → RETRY (max 2x, lower temperature + reinject rules)
Score ≤ 49  → STOP (alert user)
```

### Quality Checks

| Check | Description |
|---|---|
| Myanmar ratio ≥ 70% | Minimum Myanmar character proportion |
| Chinese/Bengali/Indic/Thai leak = 0 | Zero foreign script contamination |
| SVO→SOV conversion | No English/Chinese sentence order |
| Archaic words banned | သင်သည်/ဤ/ထို → မင်း/ဒီ/အဲဒီ |
| Particle repetition ≤ 2× per paragraph | Same particle not overused |
| Placeholder integrity | `【?term?】` preserved exactly |
| Paragraph duplication | No repeated sentences at chunk boundaries |
| Markdown preservation | Headers, bold, italic, lists intact |

### Fluency Scorer (7 Dimensions)

Lexical Diversity → Particle Diversity → Sentence Flow → Syllable Richness → Paragraph Rhythm → Punctuation Health → Repetition Penalty

---

## 🎯 Model Warnings

### ✅ Proven Myanmar Models
| Model | Use | Temperature |
|---|---|---|
| **padauk-gemma:q8_0** | PRIMARY — EN→MM, CN→MM | ≤ 0.2 |
| sailor2-20b | Alternative backup | ≤ 0.35 |

### ❌ DO NOT Use for Myanmar Output
| Model | Problem |
|---|---|
| sailor2:8b | Myanmar ratio only 11-55% (outputs English) |
| qwen2.5:14b | Outputs Chinese/Japanese, NOT Myanmar |
| qwen:7b | Outputs English, NOT Myanmar |

### ⚠️ Pivot-Only (CN→EN Stage 1)
- `alibayram/hunyuan:7b`, `qwen2.5:14b` — CN→EN only. Do not use as Myanmar translators.

### 🔴 Critical: padauk-gemma Temperature
> **Temperature MUST be ≤ 0.2.** Above 0.2 causes glossary-comparison garbage output mixed into translations.

---

## 📁 Directory Structure

```
novel_translation_project/
├── .agent/                    # Orchestration memory (phase gate, sessions, errors)
├── config/                    # settings.yaml, settings.pivot.yaml, models.*.yaml
├── data/
│   ├── input/{novel}/         # Source chapter files (*.md)
│   └── output/{novel}/        # Translated .mm.md files
├── src/
│   ├── main.py                # Entry point
│   ├── agents/                # Translator, Refiner, Checker, QA, etc.
│   ├── pipeline/              # Orchestrator
│   ├── memory/                # MemoryManager, VersionManager
│   ├── utils/                 # OllamaClient, FileHandler, Chunker, Postprocessor
│   ├── web/                   # Flask Web UI
│   └── training/              # LoRA fine-tuning
├── scripts/                   # translate.py + change_model.py (interactive launchers), import_universal_glossary.py, bootstrap_glossary.py
├── tools/                     # mine_glossary.py, run_dataset_alignment.py, glossary_stats.py
├── glossary_extraction/       # Offline glossary mining pipeline
├── glossary_app/              # Standalone Glossary Review UI
├── tests/                     # 440+ tests
├── requirements.txt
└── README.md
```

---

## 🐛 Troubleshooting

| Problem | Likely Cause | Fix |
|---|---|---|
| `Could not connect to Ollama` | Ollama not running | Run `ollama serve` |
| `Chapter file not found` | Wrong path/naming | Use `{novel}_chapter_{XXX}.md` in `data/input/{novel}/` |
| `Myanmar ratio < 70%` | Wrong model or high temp | Use `padauk-gemma:q8_0`, temp ≤ 0.2 |
| `database is locked` | Another process using DB | Wait for auto-retry (30s), close other tools |
| `Ollama process killed (OOM)` | Out of memory | Reduce chunk_size to 800, use smaller model |
| `Glossary terms not applied` | Terms are in pending state | Run `--approve-glossary` or approve via Web UI |

### Testing

```bash
pytest tests/ -v --tb=short           # All tests (440+)
pytest tests/test_translator.py -v    # Single test file
pytest tests/ --cov=src --cov-report=term-missing  # Coverage
```

---

> **Note:** CLI flags, file paths, and model names reflect the current source code. Always run `python -m src.main --version` to check your build.
