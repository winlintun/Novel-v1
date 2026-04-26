# Novel Translation Pipeline

Automated Chinese-to-Myanmar (Burmese) novel translation system specializing in Wuxia/Xianxia cultivation novels.

## Overview

This pipeline uses a multi-stage agent system to translate web novels while preserving:
- Tone, style, and literary depth
- Terminology consistency via glossary
- Story context across chapters
- Proper Chinese SVO to Myanmar SOV syntax conversion

## Architecture

```
Input (Chinese) → Preprocess → Stage 1 (CN→EN) → Stage 2 (EN→MM) → Refine → QA Check → Output (Myanmar)
```

## Supported Models

| Model | Quality | Speed | VRAM | Notes |
|-------|---------|-------|------|-------|
| `qwen2.5:14b` | ⭐⭐⭐⭐⭐ | Medium | 9GB | Best Chinese comprehension |
| `qwen2.5:7b` | ⭐⭐⭐⭐ | Fast | 4GB | Good balance |
| `qwen:7b` | ⭐⭐⭐ | Fastest | 4GB | Lightweight |

**NOT recommended**: `alibayram/hunyuan:7b`, `yxchia/seallms-v3-7b` (produce Thai instead of Myanmar)

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Ollama and Pull Models

```bash
# Install Ollama from https://ollama.ai

# Pull recommended model
ollama pull qwen2.5:14b

# Or use lighter model for testing
ollama pull qwen2.5:7b
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

# All chapters
python -m src.main --novel 古道仙鸿 --all

# From specific chapter
python -m src.main --novel 古道仙鸿 --all --start 10

# Skip refinement (faster)
python -m src.main --novel 古道仙鸿 --chapter 1 --skip-refinement

# Unload model after each chapter (saves VRAM)
python -m src.main --novel 古道仙鸿 --all --unload-after-chapter
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
│   │   └── context_updater.py  # Term extraction
│   ├── memory/             # 3-tier memory system
│   │   └── memory_manager.py
│   ├── utils/               # Utilities
│   │   ├── ollama_client.py  # Ollama API wrapper
│   │   ├── file_handler.py   # File I/O
│   │   └── postprocessor.py # Output cleaning
│   └── main.py              # Entry point
├── tests/                   # Unit tests (221 tests)
└── tools/                  # Maintenance tools
    └── cleanup.py          # Ollama memory cleanup
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
  translator: "qwen2.5:14b"
  ollama_base_url: "http://localhost:11434"
```

### Processing Settings

```yaml
processing:
  chunk_size: 800        # Characters per chunk
  temperature: 0.2      # Lower = more deterministic
  repeat_penalty: 1.5    # Prevents repetition loops
  max_retries: 3        # Retry failed requests
```

## Troubleshooting

### Model produces Thai instead of Myanmar

- Verify using `qwen2.5:14b` not `hunyuan` or `seallms`
- Lower temperature to 0.2
- Check `LANGUAGE_GUARD` in prompts

### Out of VRAM

```bash
# Unload model after each chapter
python -m src.main --novel 古道仙鸿 --all --unload-after-chapter

# Or use lighter model
python -m src.main --novel 古道仙鸿 --all --config config/settings.fast.yaml
```

### Slow inference

- Use `qwen2.5:7b` instead of `14b`
- Enable batch processing in config
- Reduce `chunk_size`

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_pivot_translator.py -v

# Run with coverage
pytest tests/ -v --cov=src --cov-report=term-missing
```

## Development

### Adding New Agents

Follow the modular boundaries defined in `AGENTS.md`:
- Agents must not import other agents directly
- Use `MemoryManager` as the single data gateway
- All public methods require type hints

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