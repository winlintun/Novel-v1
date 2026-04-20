# AGENTS.md - AI Agent Guidance for Novel Translation Project

## Project Overview

This is a **Chinese-to-Burmese novel translation system** built in Python. The system uses AI models (local via Ollama or cloud APIs) to translate Chinese web novels and literary works into Burmese while preserving tone, style, and emotional depth.

---

## Quick Reference

- **Main Entry Point**: `main.py` - Orchestrates the entire translation pipeline
- **Configuration**: `.env` for API keys, `config/config.json` for runtime settings
- **Scripts**: `scripts/` folder contains modular pipeline components
- **Input**: Place Chinese novels in `input_novels/` (.txt or .md)
- **Output**: Burmese translations appear in `translated_novels/`

---

## Agent Roles

### 1. Translation Agent

**Role**: Professional Literary Translator (Chinese → Burmese)

**Responsibilities**:
- Faithfully translate Chinese text to natural, literary Burmese
- Maintain original tone (formal, colloquial, poetic)
- Adapt cultural references appropriately
- Ensure consistent naming across all chunks
- Output clean, UTF-8 encoded Burmese text

**Guidelines**:
- **NO Explanations**: Do not add translator notes or commentary
- **Direct Output**: Provide only the translated Burmese text
- **NO Mixed Language**: Never output Chinese characters
- **Literary Quality**: Avoid literal word-for-word translations
- **Myanmar Script**: Use only Myanmar Unicode (U+1000–U+109F)

**Prompt Template**:
```
SYSTEM:
You are a professional literary translator fluent in Chinese and Burmese, 
specializing in Chinese web novels. Translate the following Chinese novel 
excerpt into Burmese.

REQUIREMENTS:
- Maintain the original literary style and emotional tone
- Ensure terminology is consistent throughout
- Output only the Burmese translation
- No explanations, notes, or greetings
- Use Myanmar Unicode script exclusively

USER:
[CHINESE_TEXT_CHUNK]
```

### 2. Code Review Agent

**Role**: Code Quality Auditor

**Responsibilities**:
- Review `scripts/` for bugs or inefficiencies
- Validate checkpoint and data flow
- Run automated checks (`flake8`, `pylint`, `pytest`)
- Ensure error handling is robust

**Guidelines**:
- Check for proper exception handling
- Verify logging is comprehensive
- Ensure resource cleanup (file handles, connections)
- Validate configuration management

---

## Translation Pipeline

The system follows a 7-step pipeline managed by `main.py`:

```
input_novels/*.txt
      ↓
[1] preprocessor.py    → Clean text, enforce UTF-8
      ↓
[2] chunker.py         → Split into 1500-2000 char chunks with overlap
      ↓
[3] translator.py      → AI translate each chunk (streaming)
      ↓
[4] checkpoint.py      → Save progress after each chunk
      ↓
[5] myanmar_checker.py → Validate readability (≥70% Myanmar, no Chinese)
      ↓
[6] postprocessor.py   → Fix punctuation & character name consistency
      ↓
[7] assembler.py       → Merge all chunks into final .md
      ↓
translated_novels/*.md
```

---

## Key Technical Details

### Chunking Strategy
- **Size**: 1500-2000 characters per chunk
- **Overlap**: 100-200 characters between chunks
- **Purpose**: Maintain context across chunk boundaries

### Checkpoint System
- Stored in `working_data/checkpoints/{novel_name}.json`
- Contains: chunk index, total chunks, translated cache, status
- Allows safe interruption and resume

### Quality Checks (myanmar_checker.py)
- Myanmar script ratio ≥ 70%
- Zero Chinese characters (U+4E00–U+9FFF)
- At least one sentence ending marker (`။`)
- Output length ≥ 30% of input
- No replacement characters (U+FFFD)

### Configuration Files
- **config/settings.py**: Pydantic validation for all settings
- **config/config.json**: Runtime configuration (model, chunk size, etc.)
- **names.json**: Character/place name mappings (CN → MM)

---

## Best Practices

### When Translating
1. Use the TERMINOLOGY MAPPING from `names.json` for consistency
2. Maintain narrative flow between chunks using context retention
3. Adapt Chinese idioms to culturally appropriate Burmese expressions
4. Preserve genre-specific terms (xianxia/cultivation)
5. Use Burmese sentence endings (။) consistently

### When Coding
1. Use type hints for function signatures
2. Add docstrings for all public functions
3. Handle errors with try/except and proper logging
4. Use context managers for file operations
5. Follow PEP 8 style guidelines

---

## Common Commands

```bash
# Run translation
python main.py

# Check status of manual translation
python translate_manual.py novel_name --status

# Validate configuration
python config/settings.py validate

# Run tests
pytest tests/ -v

# Lint code
flake8 *.py scripts/*.py --max-line-length=120
pylint *.py scripts/*.py --disable=C0103,C0111
```

---

## Important Notes

1. **Streaming**: Translation uses streaming mode by default for real-time progress
2. **Context Retention**: Previous chunk translation is passed as context to maintain consistency
3. **Error Recovery**: Failed chunks are retried with exponential backoff (max 3 attempts)
4. **Resource Cleanup**: All file handles and HTTP connections are properly closed
5. **Encoding**: UTF-8 is enforced throughout the pipeline

---

## Myanmar Unicode Reference

- **Myanmar Block**: U+1000–U+109F
- **Sentence Ending**: `။` (U+104B)
- **Fonts**: Padauk, Noto Sans Myanmar, Myanmar Text

---

*This file is read automatically by AI agents working on this project.*
*Keep it updated when making structural or workflow changes.*

**Last Updated**: April 21, 2026
