# CONTRIBUTING.md - Contributing Guide

## Welcome to Novel Translation Project

Thank you for your interest in contributing! This document will help you get started.

## Project Structure

```
novel_translation_project/
├── src/
│   ├── agents/           # AI agents (Translator, Refiner, Checker, etc.)
│   ├── memory/           # Memory management
│   ├── utils/            # Utilities (Ollama client, File handler)
│   └── main.py           # Entry point
├── config/               # Configuration files
├── data/                 # Data files (glossary, context)
├── tests/                # Test files
└── logs/                 # Log files
```

## Quick Start

### 1. Setup Environment
```bash
# Clone and enter project
cd novel_translation_project

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or .venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Install Ollama and pull models
ollama pull qwen2.5:14b
ollama pull padauk-gemma:q8_0
```

### 2. Run Tests
```bash
pytest tests/ -v
```

### 3. Run Translation
```bash
# Single chapter
python -m src.main --novel နမဲ့စာ --chapter 1

# All chapters
python -m src.main --novel နမဲ့စာ --all
```

## Coding Standards

### Type Hints (Required)
All functions must have type hints:
```python
def translate(text: str, glossary: dict[str, str]) -> str:
    ...
```

### No Cross-Agent Imports
Use MemoryManager as single gateway:
```python
# ✅ CORRECT
from src.memory.memory_manager import MemoryManager

# ❌ WRONG
from src.agents.refiner import Refiner
```

### Error Handling
Use try/except and proper logging:
```python
try:
    result = self.client.generate(prompt)
except Exception as e:
    self.log_error("Translation failed", e)
    raise
```

## Adding New Features

1. Create feature branch: `git checkout -b feature/my-feature`
2. Add tests in `tests/`
3. Implement feature
4. Run tests: `pytest tests/ -v`
5. Commit: `git commit -m "feat: add my feature"`

## Testing

Run all tests:
```bash
pytest tests/ -v --tb=short
```

Run specific test:
```bash
pytest tests/test_translator.py -v
```

## Questions?

- Open an issue on GitHub
- Check AGENTS.md for architecture details
- Check USER_GUIDE.md for usage examples