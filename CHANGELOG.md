# CHANGELOG

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [2.2.0] - 2026-06-19

### Added
- **Genre-aware translation prompts** — `build_translator_prompt(genre=...)` injects a
  genre-specific rule block (xianxia / wuxia / fantasy / romance / general) on top of the
  scene/linguistic rules. Translator reads `project.novel_genre` from config and passes it
  through (`src/agents/prompts/system_prompts.py`, `src/agents/translator.py`).
- **Native Ollama JSON mode for glossary extraction** — `OllamaClient.chat(format="json")`
  passes Ollama's structured-output flag; `GlossaryGenerator` now requests `format="json"`,
  so term extraction is constrained to valid JSON instead of relying on prompt wording
  (ERR-093).
- **`en/` subdirectory chapter discovery** — `FileHandler.list_chapter_files()` now also
  scans `data/input/{novel}/en/` (resolves the long-standing "English chapters live in en/
  but pipeline looks in the novel root" known issue) (ERR-096).
- **Interactive terminal tools** — `scripts/translate.py` (menu-driven launcher for
  translate / glossary / approve / stats / review / UI) and `scripts/change_model.py`
  (list installed Ollama models, reassign per-role models in `settings.yaml` in place).
  `tools/verify_rag.py` RAG-DB sanity checker.
- **Per-novel model/genre config** — `config/novel_models.yaml` + `src/config/novel_model_loader.py`
  (`get_novel_config()`), mapping each novel to its own model, temperature, chunk size, and genre.

### Fixed
- **Glossary pending-term insert wrote the wrong column** — `scripts/glossary_manager.py`
  inserted `target_term` into the source-variant slot; corrected to `source_term` (ERR-092).
- **Windows console UnicodeEncodeError on emoji** — `src/cli/formatters.py` reconfigures
  stdout/stderr to UTF-8 (errors='replace') and the auto-detection banner no longer emits
  emoji/flag glyphs that crash CP1252 consoles (ERR-094).
- **`--generate-glossary` fell through into translation** — when combined with
  `--chapter-range`/`--chapter`, glossary generation chained into the full pipeline.
  `src/main.py` now treats `--generate-glossary` / `--init-glossary` as a terminal command:
  it extracts then STOPS; the chapter range only scopes which chapters are scanned. New
  regression test in `tests/test_workflow_routing.py` (ERR-095).

### Removed (dead-code cleanup)
- Deleted unused packages/modules: `glossary_extraction/` (8 files), `src/validators/`
  (7 files), `src/feedback/` (omission_filler, terminology_feedback), `src/utils/model_registry.py`
  (+ test), and dead methods (`OllamaClient.chat_stream/check_model_available/unload_model`,
  `BaseAgent.handle_error/validate_config/get_config`, `Preprocessor._llm_detect_language/get_chapter_info`,
  `MyanmarQualityChecker.check_dialogue_tone/suggest_improvements`).
- Removed generated data blobs and stray files: `data/universal_glossary_blueprint.json`
  (~12k lines) and sibling blueprints, `logs/temp/` chunk dumps, `sample.md`, stray `main`.
- Trimmed `AGENTS.md` (removed the verbose inline crash-pattern code gallery; the 3 stability
  rules remain authoritative).
- Net: 143 files, +346 / −27,327 lines.

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
  - `src/web/` - Flask UI launcher

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
- Web UI with Flask routes for dashboard, translation, progress, editor, cleanup, and reader
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
