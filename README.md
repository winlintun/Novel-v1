# Novel Translation Pipeline

AI-powered Chinese/English-to-Myanmar (Burmese) novel translation system specializing in Wuxia/Xianxia cultivation novels. Supports both direct EN→MM translation and CN→EN→MM pivot workflows.

> 💡 **Tip**: Use `--clean` flag to clear Python cache before running: `python3 -m src.main --chapter 1 --novel "古道仙鸿" --clean`

## Overview

This pipeline uses a multi-stage agent system to translate web novels while preserving:
- Tone, style, and literary depth
- Terminology consistency via glossary
- Story context across chapters
- Proper Chinese SVO to Myanmar SOV syntax conversion

## Architecture

```
Input (Chinese) → Preprocess → Stage 1 (CN→EN) → Stage 2 (EN→MM) → Refine → Reflection (Critique) → QA Check → Output (Myanmar)
```

## Advanced Features

### 🧠 Reflection & Self-Correction
The `ReflectionAgent` implements Andrew Ng's translation-agent pattern. After the initial translation and refinement, the model analyzes its own work, identifies issues (awkward phrasing, tone inconsistency, etc.), and iteratively improves it.

### 🇲🇲 Myanmar Quality Checker
A specialized `MyanmarQualityChecker` validates translations for linguistic naturalness, proper particle usage, and tone consistency. It helps ensure the output sounds like literary Myanmar rather than a machine translation.

### 🌐 Web Interface
A Streamlit-based Web UI provides a user-friendly way to manage translations, view progress, and edit the glossary.

Run the UI:
```bash
streamlit run ui/streamlit_app.py
```

## Supported Models

| Model | Quality | Speed | VRAM | Best For |
|-------|---------|-------|------|----------|
| `padauk-gemma:q8_0` | ⭐⭐⭐⭐⭐ | Fast | 5GB | **Primary**: Best EN→MM output, low hallucination |
| `aya:8b` | ⭐⭐⭐⭐ | Fast | 5GB | Fallback multilingual model |
| `alibayram/hunyuan:7b` | ⭐⭐⭐⭐ | Medium | 4GB | CN→EN pivot (Stage 1 of way2) |
| `qwen:7b` | ⭐⭐⭐ | Fast | 4GB | QA checks, lightweight tasks |
| `qwen2.5:14b` | ⭐⭐⭐⭐⭐ | Medium | 9GB | CN→EN (alternative for way2 Stage 1) |

**NOT recommended**: `yxchia/seallms-v3-7b` (produces Thai instead of Myanmar)

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Ollama and Pull Models

```bash
# Install Ollama from https://ollama.ai

# Pull primary model (Myanmar-optimized)
ollama pull padauk-gemma:q8_0

# Pull pivot model (Chinese→English, for way2 workflow)
ollama pull alibayram/hunyuan:7b

# Pull fallback models
ollama pull aya:8b
```

### 3. Configure Settings

Edit `config/settings.yaml` or use one of the preset configs:

```yaml
# Standard (Chinese → Myanmar direct)
config: config/settings.yaml

# Pivot via English (CN → EN → MM)
config: config/settings.pivot.yaml

# Fast mode (lighter model)
config: config/settings.fast.yaml
```

### 4. Run Translation

```bash
# Single chapter
python -m src.main --novel 古道仙鸿 --chapter 1

# Multiple chapters (range)
python -m src.main --novel 古道仙鸿 --chapter-range 9-15

# All chapters
python -m src.main --novel 古道仙鸿 --all

# From specific chapter onwards
python -m src.main --novel 古道仙鸿 --all --start 10

# Use specific workflow (auto-detected if omitted)
python -m src.main --novel 古道仙鸿 --chapter 1 --workflow way2

# Skip refinement (faster, lower quality)
python -m src.main --novel 古道仙鸿 --chapter 1 --skip-refinement

# Unload model after each chapter (saves VRAM)
python -m src.main --novel 古道仙鸿 --all --unload-after-chapter

# Multiple chapters with specific start/end
python -m src.main --novel 古道仙鸿 --start 9 --end 15
```

## Directory Structure

```
novel_translation_project/
├── config/                    # Model and pipeline configs
│   ├── settings.yaml         # Standard CN→MM
│   ├── settings.pivot.yaml   # CN→EN→MM pivot
│   └── settings.fast.yaml    # Fast mode
├── data/
│   ├── input/               # Chinese chapter files (*.md)
│   ├── output/              # Myanmar translations
│   │   └── {novel}/        #   ├── en/     (English intermediate)
│   │   │                  #   └── mm/     (Myanmar final)
│   │   ├── glossary.json    # Approved terminology
│   │   ├── glossary_pending.json  # Terms awaiting review
│   │   └── context_memory.json    # Chapter context
├── src/
│   ├── agents/              # Translation agents
│   │   ├── pivot_translator.py  # CN→EN→MM routing
│   │   ├── translator.py    # Stage 1
│   │   ├── refiner.py       # Stage 2
│   │   ├── checker.py       # QA validation
│   │   ├── reflection_agent.py   # Self-correction
│   │   ├── myanmar_quality_checker.py  # Linguistic validation
│   │   ├── qa_tester.py     # QA validation agent
│   │   └── context_updater.py  # Term extraction
│   ├── cli/                 # CLI module (refactored)
│   │   ├── parser.py        # Argument parsing
│   │   ├── formatters.py    # Output formatting
│   │   └── commands.py      # Command handlers
│   ├── config/              # Configuration management
│   │   ├── models.py        # Pydantic config models
│   │   └── loader.py        # Config loading with validation
│   ├── core/                # Core functionality
│   │   └── container.py     # Dependency injection container
│   ├── memory/              # 3-tier memory system
│   │   └── memory_manager.py
│   ├── pipeline/            # Pipeline orchestration
│   │   └── orchestrator.py  # TranslationPipeline coordinator
│   ├── types/               # Type definitions
│   │   └── definitions.py   # TypedDict for data structures
│   ├── utils/               # Utilities
│   │   ├── ollama_client.py  # Ollama API wrapper
│   │   ├── file_handler.py   # File I/O
│   │   └── postprocessor.py # Output cleaning
│   ├── web/                 # Web UI launcher
│   │   └── launcher.py      # Streamlit launcher
│   ├── exceptions.py        # Exception hierarchy
│   └── main.py              # Entry point (thin dispatcher)
├── tests/                   # Unit tests (229+ tests)
└── tools/                   # Maintenance tools
    └── cleanup.py           # Ollama memory cleanup
```

## Translation Workflow

### 4-Stage Pipeline

1. **Preprocess**: Clean and chunk input text with sliding window overlap
2. **Translate**: CN → EN → MM pivot translation (or direct CN → MM)
3. **Refine**: Literary editing for natural flow
4. **QA Check**: Terminology consistency and quality validation

### Memory System

| Tier | Storage | Scope |
|------|---------|-------|
| 1 | `glossary.json` | Persistent terminology |
| 2 | `context_memory.json` | Chapter context (FIFO) |
| 3 | Session rules | Runtime only |

### Glossary Management

New terms are extracted automatically and stored in `glossary_pending.json` for review:

```json
{
  "pending_terms": [
    {
      "source": "新术语",
      "target": "မြန်မာဘာသာ",
      "category": "item",
      "extracted_from_chapter": 12,
      "status": "pending"
    }
  ]
}
```

Approve terms by changing `"status": "pending"` to `"status": "approved"`.

## Configuration Reference

### Model Settings

```yaml
models:
  provider: "ollama"
  translator: "padauk-gemma:q8_0"
  editor: "padauk-gemma:q8_0"
  refiner: "padauk-gemma:q8_0"
  checker: "qwen:7b"
  ollama_base_url: "http://localhost:11434"
```

### Processing Settings

```yaml
processing:
  chunk_size: 800        # Characters per chunk (800 optimal for padauk-gemma)
  temperature: 0.2       # Lower = more deterministic (0.2 recommended)
  repeat_penalty: 1.15   # Prevents repetition loops (1.15 recommended)
  top_p: 0.95
  top_k: 40
  max_retries: 2
```

## Troubleshooting

### Model produces Thai/English instead of Myanmar

- Use `padauk-gemma:q8_0` as primary model (Myanmar-optimized)
- Verify `LANGUAGE_GUARD` is active in translator prompts
- Lower temperature to 0.2
- Reduce `chunk_size` to 800

### Out of VRAM

```bash
# Unload model after each chapter
python -m src.main --novel 古道仙鸿 --all --unload-after-chapter

# Or use lighter model
python -m src.main --novel 古道仙鸿 --all --config config/settings.fast.yaml
```

### Slow inference

- Use `padauk-gemma:q8_0` (smaller, faster than qwen2.5:14b)
- Reduce `chunk_size` from 800 to 400
- Disable reflection: set `use_reflection: false`

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_pivot_translator.py -v

# Run with coverage
pytest tests/ -v --cov=src --cov-report=term-missing
```

## Architecture Overview

### Refactored Codebase (v2.0)

The codebase has been refactored for better maintainability and testability:

| Module | Purpose |
|--------|---------|
| `src/cli/` | CLI argument parsing, formatting, and command handlers |
| `src/config/` | Pydantic-based configuration with validation |
| `src/pipeline/` | Pipeline orchestration with lazy agent loading |
| `src/core/` | Dependency injection container |
| `src/types/` | TypedDict definitions for type safety |
| `src/web/` | Web UI launcher |
| `src/exceptions.py` | Structured exception hierarchy |

### Key Improvements

- **Type Safety**: Pydantic models for configuration validation
- **Error Handling**: Structured exception hierarchy (NovelTranslationError, ModelError, etc.)
- **Testability**: Dependency injection container for easy mocking
- **Modularity**: Clean separation between CLI, pipeline, and agents
- **Lazy Loading**: Agents loaded only when needed

## Development

### Adding New Agents

Follow the modular boundaries defined in `AGENTS.md`:
- Agents must not import other agents directly
- Use `MemoryManager` as the single data gateway
- All public methods require type hints
- Add types to `src/types/definitions.py`

### Running CI Locally

```bash
# Same checks as GitHub Actions
pytest tests/ -v --tb=short
python -m py_compile src/**/*.py
```

## License

MIT License

## Contributing

1. Read `AGENTS.md` for architecture rules
2. Run tests before committing: `pytest tests/ -v`
3. Update `CURRENT_STATE.md` after changes