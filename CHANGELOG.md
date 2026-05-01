# CHANGELOG

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [2.1.0] - 2026-05-01

### Added
- `.agent/` directory with phase_gate.json, session_memory.json, long_term_memory.json, error_library.json (agent brain infrastructure)
- CHANGELOG.md (this file)

### Infrastructure
- Project infrastructure files created to match AGENTS.md specifications

---

## [2.0.0] - 2026-04-27

### Refactored
- Monolithic main.py (1136 lines) extracted into modular components:
  - `src/cli/` - CLI argument parsing, formatters, command handlers
  - `src/config/` - Pydantic-based configuration with validation
  - `src/core/` - Dependency injection container
  - `src/pipeline/` - Translation pipeline orchestrator
  - `src/types/` - TypedDict definitions
  - `src/web/` - Streamlit UI launcher

### Added
- Exception hierarchy (`src/exceptions.py`)
- Type definitions for all data structures
- Configuration validation with Pydantic
- Translation pipeline orchestrator with lazy agent loading

---

## [1.x.0] - 2026-04-24 to 2026-04-27

### Added
- Core 6-stage translation pipeline (Preprocess → Translate → Edit → Reflect → Quality Check → Consistency Check)
- Multi-model router for model selection
- Linguistic rules: SVO→SOV conversion
- Glossary synchronization agent
- QA Tester agent for automated validation
- Reflection agent for self-correction
- Myanmar quality checker for linguistic validation
- Web UI (Streamlit) with Home, Translate, Progress, Glossary, Settings pages
- Glossary generator for pre-translation terminology extraction
- Pivot translation (CN→EN→MM) support
- Fast translation mode with optimized batch processing
- Progress logger with real-time markdown logs
- Glossary v3.0 with rich metadata support (aliases, exceptions, examples)
- RAG memory for context-aware translation
- GPU support (NVIDIA + AMD)
- Auto-clean launchers for Python cache
- Auto-detection of source language with smart model selection

### Fixed
- Postprocessor stripping thinking process from output
- Web UI navigation and model selection issues
- Glossary editor category validation
- Progress page chapter filtering
- Translation quality with Myanmar-specific models (padauk-gemma)
- Pipeline integration method name mismatches
- Agent initialization parameter mismatches in orchestrator
- Chapter file naming convention discovery (5 patterns)
- Postprocessor whitespace collapse destroying paragraph structure
- Duplicate chapter headings in output

---

## [0.1.0] - Initial

### Added
- Basic Chinese-to-Myanmar translation pipeline
- Ollama client integration
- File handler with UTF-8-SIG and atomic writes
- Glossary and context memory systems
- Preprocessor for text cleaning and chunking
