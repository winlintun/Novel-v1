# Novel Translation Pipeline

> AI-powered Chinese/English-to-Myanmar (Burmese) novel translation system specializing in Wuxia/Xianxia cultivation novels. Ollama-only — runs entirely on local models, no cloud API needed.

---

## Introduction

This is an AI-powered translation system that translates Chinese and English novels into Myanmar (Burmese). It's specifically optimized for Wuxia and Xianxia (Chinese fantasy/cultivation) novels.

**Key Features:**
- Runs locally with Ollama - no cloud API required
- Uses padauk-gemma model for Myanmar output
- Glossary system ensures name consistency
- Quality gates enforce translation standards
- Web UI (Streamlit) available

---

## Quick Start

### Installation

```bash
# Install Python dependencies
pip install -r requirements.txt

# Pull Ollama models
ollama pull padauk-gemma:q8_0      # Primary Myanmar output model
ollama pull alibayram/hunyuan:7b   # CN→EN pivot (optional for Chinese)
```

### Basic Usage

```bash
# Translate single chapter
python -m src.main --novel novel_name --chapter 1

# Translate chapter range (e.g., 1-10)
python -m src.main --novel novel_name --chapter-range 1-10

# Translate all chapters
python -m src.main --novel novel_name --all

# Start from chapter 5
python -m src.main --novel novel_name --all --start 5

# Translate single input file
python -m src.main --input data/input/novel_name/ch001.md

# Launch Web UI
python -m src.main --ui
```

---

## Features

| Feature | Description |
|---------|-------------|
| **Dual Workflows** | way1 (English→Myanmar direct) and way2 (Chinese→English→Myanmar pivot) - auto-detects language |
| **6-Stage Pipeline** | Preprocess → Translate → Refine → Reflect → Quality Check → QA |
| **Smart Chunking** | Token-aware, paragraph-safe, zero overlap, rolling context |
| **3-Tier Memory** | Glossary (persistent) + Context (FIFO) + Session rules |
| **Glossary Engine** | Auto-extract terms, confidence-based auto-promote, deduplication |
| **Quality Gates** | Myanmar ratio ≥70%, register mixing, archaic words, particle repetition |
| **Auto-Review** | Per-chapter quality reports in `logs/report/` |
| **Stats Display** | `--stats` shows per-chapter score trends with bar charts |
| **Web UI** | 7-page Streamlit interface |

---

## CLI Reference

```bash
python -m src.main [OPTIONS]
```

### Translation Options

| Option | Description |
|--------|-------------|
| `--novel NAME` | Novel name (folder name) |
| `--chapter N` | Single chapter |
| `--chapter-range 1-10` | Chapter range |
| `--all` | All chapters |
| `--start N` | Starting chapter (default: 1) |
| `--input FILE` | Single input file |
| `--output-dir DIR` | Override output directory |

### Workflow Options

| Option | Description |
|--------|-------------|
| `--workflow {way1,way2}` | Force workflow (auto-detected if omitted) |
| `--lang {zh,en}` | Source language hint |
| `--mode {full,lite,fast}` | Pipeline mode |
| `--skip-refinement` | Skip Stage 2 (faster) |
| `--use-reflection` | Enable self-correction (Stage 3) |

### Config Options

| Option | Description |
|--------|-------------|
| `--config FILE` | Config file (default: `config/settings.yaml`) |
| `--model MODEL` | Override translator model |
| `--provider PROVIDER` | Override model provider |

### Quality & Review Options

| Option | Description |
|--------|-------------|
| `--review FILE` | Review translated .mm.md file |
| `--stats` | Show per-chapter score trends (requires --novel) |
| `--view FILE` | View translated file in terminal |

### Glossary Options

| Option | Description |
|--------|-------------|
| `--generate-glossary` | Generate glossary from first 3-5 chapters |
| `--auto-promote` | Promote high-confidence pending terms (requires --novel) |

### Utility Options

| Option | Description |
|--------|-------------|
| `--ui` | Launch Streamlit Web UI |
| `--test` | Run sample translation test |
| `--clean` | Clear Python cache |
| `--no-metadata` | Skip metadata in output |
| `--version` | Show version |
| `--help` | Show help |

---

## Supported Models

| Model | Myanmar Output | Best For |
|-------|:---:|---|
| `padauk-gemma:q8_0` | ✅ | **Primary** English→Myanmar |
| `sailor2-20b` | ✅ | Alternative Myanmar model |
| `alibayram/hunyuan:7b` | ❌ | CN→EN pivot (way2 Stage 1 only) |
| `qwen:7b` | ❌ | QA checks, glossary sync (English output) |

---

## Architecture

```
Input → Preprocess → Translate → Refine → Reflect → Quality Check → Consistency → QA → Output
         (chunk)     (Stage 1)  (Stage 2)  (Stage 3)  (Stage 4)       (Stage 5)    (Stage 6)
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
| 1 - Glossary | `data/output/{novel}/glossary/glossary.json` | Persistent (per-novel isolation) |
| 2 - Context | `data/output/{novel}/glossary/context_memory.json` | Chapter FIFO buffer |
| 3 - Pending | `data/output/{novel}/glossary/glossary_pending.json` | Terms awaiting review |

---

## Directory Structure

```
novel_translation_project/
├── config/
│   ├── settings.yaml           # Main config (default)
│   ├── settings.pivot.yaml     # CN→EN→MM workflow
│   ├── settings.fast.yaml     # Fast mode (CPU-only)
│   ├── settings.sailor2.yaml  # Sailor2 model config
│   └── error_recovery.yaml    # Error recovery config
│
├── data/
│   ├── input/                  # Source chapters (*.md)
│   │   └── {novel}/
│   │       └── ch001.md
│   │
│   └── output/                 # Translated output
│       └── {novel}/
│           ├── glossary/
│           │   ├── glossary.json
│           │   ├── glossary_pending.json
│           │   └── context_memory.json
│           ├── {novel}_chapter_001.mm.md
│           └── {novel}.mm.meta.json
│
├── src/
│   ├── agents/                 # 16 pipeline agents
│   │   ├── translator.py       # Stage 1: Translation
│   │   ├── refiner.py          # Stage 2: Literary polish
│   │   ├── reflection_agent.py # Stage 3: Self-correction
│   │   ├── myanmar_quality_checker.py  # Stage 4
│   │   ├── checker.py          # Stage 5: Consistency
│   │   ├── qa_tester.py        # Stage 6: Final QA
│   │   └── ...
│   │
│   ├── cli/                    # CLI parser, commands, formatters
│   ├── config/                 # Pydantic config models + loader
│   ├── memory/                 # MemoryManager (3-tier)
│   ├── pipeline/               # TranslationPipeline orchestrator
│   └── utils/                  # Utilities
│       ├── ollama_client.py    # Ollama wrapper with retry
│       ├── file_handler.py    # Atomic file I/O
│       ├── postprocessor.py    # Output cleaning
│       ├── chunker.py          # Smart chunking
│       ├── translation_reviewer.py  # Auto quality review
│       └── fluency_scorer.py  # Myanmar fluency scoring
│
├── tests/                      # 282 tests (41% coverage)
├── logs/
│   └── report/                 # Auto-generated quality reports
│       └── {novel}_chapter_{N}_review_{timestamp}.md
│
├── ui/                         # Streamlit Web UI (7 pages)
│   ├── pages/
│   │   ├── 0_Quickstart.py
│   │   ├── 1_Translate.py
│   │   ├── 2_Progress.py
│   │   ├── 3_Glossary_Editor.py
│   │   ├── 4_Settings.py
│   │   └── 5_Reader.py
│   └── streamlit_app.py
│
├── .agent/                     # Agent memory (do not edit manually)
│   ├── phase_gate.json
│   ├── session_memory.json
│   ├── long_term_memory.json
│   └── error_library.json
│
├── README.md                   # This file
├── requirements.txt           # Python dependencies
├── pytest.ini                  # Test configuration
└── CHANGELOG.md               # Version history
```

---

## Configuration

### Config Files

| File | Purpose |
|------|---------|
| `settings.yaml` | Default config - English→Myanmar direct |
| `settings.pivot.yaml` | Chinese→English→Myanmar pivot |
| `settings.fast.yaml` | Fast mode - CPU only, smaller chunks |
| `settings.sailor2.yaml` | Sailor2-20B model |
| `error_recovery.yaml` | Error recovery policies (reference only) |

### Config Options (settings.yaml)

```yaml
models:
  translator: "padauk-gemma:q8_0"   # Primary model
  editor: "padauk-gemma:q8_0"
  checker: "sailor2:8b"
  ollama_base_url: "http://localhost:11434"
  timeout: 300                       # 5 minutes per chunk

processing:
  chunk_size: 2500                   # Max characters per chunk
  max_retries: 2
  temperature: 0.2                   # Keep low - prevents garbage output
  top_p: 0.95
  top_k: 40
  repeat_penalty: 1.15
```

---

## Testing

```bash
# All tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=src --cov-report=term

# Linter
ruff check src/ tests/ --select=E,F
```

---

## Quality Gates

| Gate | Threshold | Action |
|------|----------:|--------|
| Myanmar Ratio | ≥70% per chunk | Block save if <40% |
| LLM Score | ≥70/100 | Retry up to 3x |
| Glossary Match | 100% | Fix mismatches automatically |
| Archaic Words | 0 | Replace with modern equivalents |

---

## Examples

```bash
# 1. way1 - English→Myanmar direct
python -m src.main --novel novel_name --chapter 1

# 2. way2 - Chinese→English→Myanmar pivot
python -m src.main --novel novel_name --chapter 1 --config config/settings.pivot.yaml

# 3. Review translated file
python -m src.main --review data/output/novel_name/novel_name_chapter_001.mm.md

# 4. Show quality stats
python -m src.main --stats --novel novel_name

# 5. View file in terminal
python -m src.main --view data/output/novel_name/novel_name_chapter_001.mm.md

# 6. Generate glossary
python -m src.main --novel novel_name --generate-glossary --chapter-range 1-5

# 7. Launch Web UI
python -m src.main --ui

# Or
streamlit run ui/streamlit_app.py
```

---

## Active Novels

| Novel | Chapters | Average Quality |
|-------|----------:|:---------------:|
| reverend-insanity | 26 | ~85/100 |
| dao-equaling-the-heavens | 13 | ~75/100 |

---

## Project Stats

| Metric | Value |
|--------|-------|
| Python Code | ~15,000 lines |
| Test Files | 21 |
| Tests | 282 (all passing) |
| Test Coverage | 41% |
| Config Files | 5 |
| Agent Modules | 16 |
| Utility Modules | 14 |
| UI Pages | 7 |

---

## License

MIT License

---

## Getting Help

```bash
# Help
python -m src.main --help

# Version
python -m src.main --version
```

---

**Happy translating!**