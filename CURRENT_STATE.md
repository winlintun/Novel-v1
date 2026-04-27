# CURRENT_STATE.md - Implementation Progress

> **FOR AI AGENTS — MANDATORY:**
> - **Session Start:** Read this file before any code. Check what is [DONE] and what is [TODO].
> - **Session End:** Update this file automatically after every task, file change, or decision.
>   No prompt needed. This is default behavior defined in AGENTS.md and GEMINI.md.

---

## Last Updated
- Date: 2026-04-27
- Last task completed:
  1. **CODE REFACTORING - Phase 1 Complete** (per need_fix.md):
     - Created new module structure: `src/cli/`, `src/pipeline/`, `src/web/`, `src/config/`, `src/core/`, `src/types/`
     - Implemented `src/exceptions.py` with structured error hierarchy (NovelTranslationError, ModelError, GlossaryError, etc.)
     - Implemented Pydantic configuration with validation (`src/config/models.py`, `src/config/loader.py`)
     - Extracted `main.py` monolith (1136 lines) into specialized modules:
       - `src/cli/parser.py` - Argument parsing
       - `src/cli/formatters.py` - Output formatting
       - `src/cli/commands.py` - Command handlers
       - `src/pipeline/orchestrator.py` - Pipeline coordination
       - `src/web/launcher.py` - UI launching
     - Created thin `src/main.py` dispatcher (<50 lines)
     - Added TypedDict definitions for key data structures (`src/types/definitions.py`)
     - Implemented dependency injection container (`src/core/container.py`)
  2. Fixed UI import path issues - corrected sys.path in 2_Translate.py and 4_Glossary_Editor.py
  3. Created tools/launch_ui.py for web server logging - all output goes to logs/web_server.log
  4. Enhanced CLI processing info display - rich formatted header, step-by-step progress (7 steps), model info, settings display
  5. Fixed --ui flag to properly launch web UI with subprocess
  6. Created comprehensive test suite (test_novel_v1.py) - 11/11 tests passing
  7. Fixed postprocessor to strip model's "thinking process" from output (ERROR-019)
  8. Fixed Web UI Settings page - model selection now shows all models from config (ERROR-020)
  9. Fixed Glossary Editor - ValueError for 'person_character' category (ERROR-021)
  10. Fixed Progress page - chapter filter now checks chapters/ subdirectory (ERROR-022)
  11. Fixed Progress page - session status shows COMPLETE/FAILED correctly (ERROR-023)
  12. Fixed Progress page - clear old logs button now works (ERROR-024)
  13. Fixed Translate page - output files now found in chapters/ subdirectory (ERROR-025)
  14. Fixed Translate page - model selection and two-stage mode now applied (ERROR-026)
  15. Fixed Web UI Sidebar - ALL settings now applied (ERROR-027)
  16. Fixed FileNotFoundError for output files in chapters/ subdirectory (ERROR-028)
  17. Fixed Model Selection - Now discovers all Ollama models via API (ERROR-029)
  18. Fixed Navigation Links - Changed from link_button to switch_page (ERROR-030)
  19. Fixed Dashboard Progress Count - Now checks chapters/ subdirectory (ERROR-031)
  20. Fixed model discovery in Sidebar + Settings - now loads live installed models from Ollama API/CLI with config fallback (ERROR-032)
  21. All fixes verified with test suite
  22. Added explicit workflow routing: way1 (English→Myanmar direct) and way2 (Chinese→English→Myanmar pivot) in CLI + UI command builder with tests (ERROR-033)
  23. Added auto workflow detection (no required flags) + pivot Stage2 anti-English-leak retry guard to prevent REJECTED outputs (ERROR-034)
  24. **Updated documentation** for new codebase structure:
      - Updated `AGENTS.md` with new directory structure
      - Updated `GEMINI.md` with new file paths
      - Updated `README.md` with new modules and architecture overview
  25. **Fixed pipeline integration issues** (ERROR-037):
      - Fixed method name mismatches in orchestrator (clean_text→clean_markdown, translate→translate_paragraph, etc.)
      - Fixed parameter name mismatch (chunk_overlap→overlap_size)
      - Fixed result handling for batch vs single translation in commands.py
      - All 229 tests pass, CLI working correctly
  26. **Fixed type hints** (ERROR-038):
      - Added missing type hints to all `args` parameters per AGENTS.md requirements
      - Fixed src/cli/commands.py and src/web/launcher.py
      - All 229 tests pass
- Fixed UI syntax errors (Glossary_Editor, horizontal parameter) per code-reviewer; All UI files working
- Added GlossaryGenerator agent for pre-translation terminology extraction; Fixed English source support bug in Translator agent by ensuring correct system prompt selection; Updated AGENTS.md and USER_GUIDE.md.
- Integrated Web UI (Streamlit) into `main.py` via `--ui` flag; Added `--test` flag for easy pipeline validation with `sample.md`.
- Refactored ContextUpdater and Preprocessor to inherit from BaseAgent for architectural consistency.
- Integrated ReflectionAgent, MyanmarQualityChecker, and QATesterAgent into the main pipeline; Updated ROADMAP, CONTRIBUTING, GLOSSARY_GUIDE, and README documentation.
- BaseAgent refactoring completed for all agents
- Web UI multi-page structure ready using Streamlit (Home, Translate, Progress, Glossary, Settings)
- 6-stage translation pipeline documented and implemented

---

## Core Pipeline Status

| Component | File | Status | Notes |
|-----------|------|--------|-------|
| Entry point / CLI | `src/main.py` | [DONE] | Now orchestrates Reflection and Myanmar Quality agents |
| Preprocessor | `src/agents/preprocessor.py` | [DONE] | Chunking with overlap support |
| Translator Agent (Stage 1) | `src/agents/translator.py` | [DONE] | Chinese → Myanmar translation |
| Reflection Agent | `src/agents/reflection_agent.py` | [DONE] | Self-correction and iterative improvement |
| Myanmar Quality Checker | `src/agents/myanmar_quality_checker.py` | [DONE] | Linguistic checks for tone and naturalness |
| QA Tester Agent | `src/agents/qa_tester.py` | [DONE] | Automated validation of output quality |
| Pivot Translator | `src/agents/pivot_translator.py` | [DONE] | Native CN→EN→MM translation routing |
| Editor Agent (Stage 2) | `src/agents/refiner.py` | [DONE] | Literary quality refinement |
| Consistency Checker (Stage 3) | `src/agents/checker.py` | [DONE] | Enhanced with Myanmar Quality checks |
| Glossary Generator | `src/agents/glossary_generator.py` | [DONE] | Pre-translation terminology extraction |
| Web UI | `ui/streamlit_app.py` | [DONE] | Multi-page Streamlit interface with Myanmar localization, individual file support, and live log viewing |

| QA Reviewer (Stage 4) | `src/agents/checker.py` | [DONE] | Part of Checker class |
| Term Extractor | `src/agents/context_updater.py` | [DONE] | Post-chapter term extraction |
| Memory Manager | `src/memory/memory_manager.py` | [DONE] | 3-tier memory system |
| Ollama Client | `src/utils/ollama_client.py` | [DONE] | Ollama API wrapper with retries, cleanup, context manager support. Supports both `/api/chat` and `/api/generate` endpoints. Configurable num_ctx (8192) and keep_alive (10m) per need_fix.md |
| File Handler | `src/utils/file_handler.py` | [DONE] | UTF-8-SIG, atomic writes |
| **NEW: Exception Hierarchy** | `src/exceptions.py` | [DONE] | Structured error handling with NovelTranslationError base class |
| **NEW: Type Definitions** | `src/types/` | [DONE] | TypedDict definitions for GlossaryTerm, TranslationChunk, PipelineResult, etc. |
| **NEW: Configuration** | `src/config/` | [DONE] | Pydantic-based config with validation (AppConfig, load_config, etc.) |
| **NEW: CLI Module** | `src/cli/` | [DONE] | Argument parsing, formatters, command handlers |
| **NEW: Pipeline** | `src/pipeline/` | [DONE] | TranslationPipeline orchestrator with lazy loading |
| **NEW: Web Launcher** | `src/web/` | [DONE] | Streamlit UI launcher |
| **NEW: DI Container** | `src/core/` | [DONE] | Dependency injection container for testability |
| Postprocessor | `src/utils/postprocessor.py` | [DONE] | Strips <think>, <answer>, validates Myanmar output. Now configurable (aggressive vs non-aggressive) to prevent over-processing that could corrupt Myanmar script (per need_fix.md) |
| JSON Extractor | `src/utils/json_extractor.py` | [DONE] | Safe JSON parsing with fallback for malformed responses |
| Prompt Patch | `src/agents/prompt_patch.py` | [DONE] | Hardened prompts with LANGUAGE_GUARD |
| Fast Translator | `src/agents/fast_translator.py` | [DONE] | Optimized with larger chunks (3000), streaming support |
| Fast Refiner | `src/agents/fast_refiner.py` | [DONE] | Batch processing (5 paragraphs per API call) |
| Fast Main | `src/main_fast.py` | [DONE] | Fast entry point with optimized pipeline, signal handling |
| Cleanup Tool | `tools/cleanup.py` | [DONE] | Ollama memory management and cleanup utility |
| Glossary v3.0 Manager | `src/utils/glossary_v3_manager.py` | [DONE] | Rich metadata support (aliases, exceptions, examples) |
| Glossary v3.0 Loader | `src/utils/glossary_v3_loader.py` | [DONE] | JSON I/O with validation, caching, and prompt export |
| Glossary Matcher | `src/utils/glossary_matcher.py` | [DONE] | Dynamic term extraction for relevant glossary injection |
| Repetition Detector | `src/utils/postprocessor.py` | [DONE] | check_repetition() function for output quality |
| Progress Logger | `src/utils/progress_logger.py` | [DONE] | Real-time translation progress tracking with live log file |
| Pivot Test Script | `test_pivot_translation.py` | [DONE] | Standalone test for CN→EN→MM workflow validation |
| Chapter Translation Test | `src/test_translate/test_ch_en_mm_translation.py` | [DONE] | Full chapter translation with log display, output validation, Gemini reviewer integration |

---

## Data Files Status

| File | Status | Notes |
|------|--------|-------|
| `data/glossary.json` | [DONE] | Created on first run |
| `data/glossary_pending.json` | [DONE] | Auto-created by ContextUpdater |
| `data/context_memory.json` | [DONE] | Auto-created on first run |
| `config/settings.yaml` | [DONE] | Standard config (qwen2.5:14b, Chinese→Myanmar) |
| `config/settings.english.yaml` | [DONE] | English→Myanmar direct translation using padauk-gemma:q8_0 (per need_fix.md) |
| `config/settings.pivot.yaml` | [DONE] | Chinese→English→Myanmar pivot using alibayram/hunyuan:7b (Stage 1) + padauk-gemma:q8_0 (Stage 2) + qwen:7b (Checker) per need_fix.md |
| `config/settings.fast.yaml` | [DONE] | Fast mode configuration |
| `config/settings.padauk.yaml` | [DONE] | Padauk-Gemma optimized config |

---

## Documentation Status

| Document | Status | Purpose |
|----------|--------|---------|
| `AGENTS.md` | [DONE] | Architecture & system design |
| `GEMINI.md` | [DONE] | Gemini AI agent guidance |
| `QWEN.md` | [DONE] | Qwen AI agent guidance (primary model) |
| `USER_GUIDE.md` | [DONE] | User instructions & examples |
| `MEMORY_MANAGEMENT.md` | [DONE] | Memory cleanup and Ollama management |
| `FAST_MODE.md` | [DONE] | Fast translation mode documentation |
| `ERROR_LOG.md` | [DONE] | Error tracking and fix record for AI agents |
| `README.md` | [DONE] | Project overview |

---

## Features Backlog

### In Progress
<!-- AI: move tasks here when you start working on them -->
- (none)

### Completed
- [x] **CI/CD Pipeline**: Added `.github/workflows/ci.yml` with pytest and lint checks
- [x] **Rate Limit Handling**: Enhanced `OllamaClient` with exponential backoff + jitter for 429 errors
- [x] **Fail-Fast Pattern**: `pivot_translator.py` now raises exceptions instead of returning error strings
- [x] **README.md**: Complete project documentation
- [x] **Two-Step Translation Workflow with File Persistence**:
  - [x] Step 1 (CN→EN): Translates and saves to `output/novel_name/en/001.md`
  - [x] Step 2 (EN→MM): Reads from EN file, translates, saves to `output/novel_name/mm/001.md`
  - [x] Added resume capability: checks if EN file exists before re-translating
  - [x] Updated `src/main.py` with proper file paths and progress logging
- [x] **Fixed CRITICAL Issues from Gemini Reviewer A+B**:
  - [x] CRITICAL: Fixed repeat_penalty 1.0 → 1.15 (prevents Myanmar infinite repetition loops like "လာလာလာလာ...")
  - [x] CRITICAL: Added LANGUAGE_GUARD to settings.english.yaml (was missing, causing English leakage)
  - [x] Added particle rules (၍/ဖြင့့်, ၌/မှာ, ကို/အား, ၏/သည့်) to Stage 2 prompts
  - [x] Added Markdown preservation rules to prompts (# headers, **bold**, *italics*)
  - [x] Added pronoun consistency rules (ကျွန်တော်/ကျွန်မ, မင်း/နင်, သင်/ခင်ဗျား)
  - [x] Changed pivot_translator.py to raise exceptions on failure (fail-fast pattern) instead of returning "[TRANSLATION ERROR]" strings
  - [x] Fixed resource cleanup with proper try/finally blocks in translate_stage1/2
- [x] **Fixed all issues from `need_fix.md`**:
  - [x] Updated `config/settings.pivot.yaml` to use `alibayram/hunyuan:7b` (Stage 1 CN→EN), `padauk-gemma:q8_0` (Stage 2 EN→MM), and `qwen:7b` (Checker/QA)
  - [x] Updated `config/settings.english.yaml` to use `padauk-gemma:q8_0` for single-stage EN→MM translation
  - [x] Fixed sampling parameters: temperature 0.2, top_p 0.95, repeat_penalty 1.15
  - [x] Added `/api/generate` endpoint support to `OllamaClient` (alternative to `/api/chat`)
  - [x] Increased `num_ctx` from 4096 to 8192 to fix context window truncation
  - [x] Increased `keep_alive` from "5m" to "10m" to prevent model unload/reload issues
  - [x] Made post-processing configurable (`aggressive` parameter) - default is non-aggressive to prevent Myanmar corruption
- [x] **Two-Step Pivot Persistence**: Implemented explicit file saving for intermediate English translations (`output/novel/en/`) and final Myanmar translations (`output/novel/mm/`).
- [x] **Native Pivot Translation Support**: Integrated CN→EN→MM routing in `src/main.py` using new `PivotTranslator` agent based on `test_ch_en_mm_translation.py`.
- [x] **Dual Translation Workflow Support**:
  - [x] Way 1 (CN→EN→MM): Fixed `config/settings.pivot.yaml` to use working qwen2.5 models (removed Thai-producing seallms-v3-7b)
  - [x] Way 2 (EN→MM): Created `config/settings.english.yaml` for direct English→Myanmar translation
  - [x] Both workflows validated and tested for Myanmar output quality
- [x] **Alternative 7B Model Pivot Workflow**: Updated `config/settings.pivot.yaml` to use qwen2.5:7b (CN→EN) + qwen:7b (EN→MM) instead of 14B models. Requires only ~4GB VRAM instead of ~9GB. Created `test_pivot_translation.py` for standalone workflow validation.
- [x] Created `tools/extract_pdf_terms.py` for automated term extraction and context updates from English MD and Myanmar PDF pairs.
- [x] **Translation Progress Logger**: Real-time progress tracking with live markdown log files showing each translated chunk as it completes. See logs/progress/ folder.
- [x] Implemented Multi-Model Router
- [x] Added Linguistic Rules SVO->SOV
- [x] Added Glossary Sync Agent
- [x] Added QA Tester Agent
- [x] Core 4-stage translation pipeline
- [x] Local Ollama support
- [x] Cloud API support (Gemini, OpenRouter)
- [x] Single-stage and two-stage translation modes
- [x] Glossary consistency checking
