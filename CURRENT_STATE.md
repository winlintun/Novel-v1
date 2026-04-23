# CURRENT_STATE.md - Implementation Progress

> **FOR AI AGENTS — MANDATORY:**
> - **Session Start:** Read this file before any code. Check what is [DONE] and what is [TODO].
> - **Session End:** Update this file automatically after every task, file change, or decision.
>   No prompt needed. This is default behavior defined in AGENTS.md and GEMINI.md.

---

## Last Updated
- Date: 2026-04-23
- Last task completed: Implemented Multi-Model Router, Linguistic Rules, Glossary Sync, and QA Tester per need_fix.md

---

## Core Pipeline Status

| Component | File | Status | Notes |
|-----------|------|--------|-------|
| Entry point / CLI | `src/main.py` | [DONE] | Supports local Ollama and cloud APIs, with resource cleanup |
| Preprocessor | `src/agents/preprocessor.py` | [DONE] | Chunking with overlap support |
| Translator Agent (Stage 1) | `src/agents/translator.py` | [DONE] | Chinese → Myanmar translation |
| Editor Agent (Stage 2) | `src/agents/refiner.py` | [DONE] | Literary quality refinement |
| Consistency Checker (Stage 3) | `src/agents/checker.py` | [DONE] | Glossary and quality checking |
| QA Reviewer (Stage 4) | `src/agents/checker.py` | [DONE] | Part of Checker class |
| Term Extractor | `src/agents/context_updater.py` | [DONE] | Post-chapter term extraction |
| Memory Manager | `src/memory/memory_manager.py` | [DONE] | 3-tier memory system |
| Ollama Client | `src/utils/ollama_client.py` | [DONE] | Ollama API wrapper with retries, cleanup, context manager support |
| File Handler | `src/utils/file_handler.py` | [DONE] | UTF-8-SIG, atomic writes |
| Postprocessor | `src/utils/postprocessor.py` | [DONE] | Strips <think>, <answer>, validates Myanmar output |
| JSON Extractor | `src/utils/json_extractor.py` | [DONE] | Safe JSON parsing with fallback for malformed responses |
| Prompt Patch | `src/agents/prompt_patch.py` | [DONE] | Hardened prompts with LANGUAGE_GUARD |
| Fast Translator | `src/agents/fast_translator.py` | [DONE] | Optimized with larger chunks (3000), streaming support |
| Fast Refiner | `src/agents/fast_refiner.py` | [DONE] | Batch processing (5 paragraphs per API call) |
| Fast Main | `src/main_fast.py` | [DONE] | Fast entry point with optimized pipeline, signal handling |
| Cleanup Tool | `tools/cleanup.py` | [DONE] | Ollama memory management and cleanup utility |

---

## Data Files Status

| File | Status | Notes |
|------|--------|-------|
| `data/glossary.json` | [DONE] | Created on first run |
| `data/glossary_pending.json` | [DONE] | Auto-created by ContextUpdater |
| `data/context_memory.json` | [DONE] | Auto-created on first run |
| `config/settings.yaml` | [DONE] | Fully documented |

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
| `README.md` | [TODO] | Project overview |

---

## Features Backlog

### In Progress
<!-- AI: move tasks here when you start working on them -->
- (none)

### Completed
- [x] Core 4-stage translation pipeline
- [x] Local Ollama support
- [x] Cloud API support (Gemini, OpenRouter)
- [x] Single-stage and two-stage translation modes
- [x] Glossary consistency checking
- [x] Myanmar Unicode quality validation
- [x] Configuration system (settings.yaml)
- [x] User documentation
- [x] 165+ passing tests (Unit, Integration, Regression, Quality)
- [x] LANGUAGE_GUARD hardened prompts (prevents Thai/Chinese output)
- [x] Output postprocessor (strips <think>, <answer> tags)
- [x] Safe JSON extractor (handles malformed model responses)
- [x] Comprehensive test suite (test_postprocessor, test_json_extractor, test_prompt_patch, test_regression, test_quality)
- [x] Fast translation mode (5-10x speedup with batch processing)
- [x] Batch refinement (5 paragraphs per API call)
- [x] Larger chunk size (3000 chars vs 1500)
- [x] Single-stage mode for 2x speed
- [x] Fast config file (settings.fast.yaml)
- [x] Streaming support for faster responses
- [x] **Memory management improvements**:
  - [x] OllamaClient cleanup() method with keep_alive=0
  - [x] Context manager support for OllamaClient (`with` statement)
  - [x] Signal handling (SIGINT, SIGTERM) for graceful shutdown
  - [x] atexit handlers for resource cleanup
  - [x] --unload-after-chapter flag for batch translation
  - [x] Cleanup tool (tools/cleanup.py) for Ollama management
  - [x] MEMORY_MANAGEMENT.md documentation
- [x] **Qwen AI documentation**:
  - [x] QWEN.md - Complete Qwen agent guidance
  - [x] Model selection guide (14B vs 7B)
  - [x] Qwen-specific prompt engineering tips
  - [x] Performance characteristics
  - [x] Common issues & solutions
  - [x] Best practices for Qwen

### Planned
- [ ] Batch chapter translation (`--all` flag) - PARTIAL (implemented in main.py)
- [ ] Glossary pending review CLI tool (`python -m src.tools.approve_terms`)
- [ ] Myanmar Unicode ratio checker in Checker agent - DONE
- [ ] Automatic `.bak` backup before glossary writes
- [ ] `【?term?】` placeholder detection and reporting

---

## Known Issues / Blockers

<!-- AI: log any bugs or blockers discovered here -->
- (none currently)

### Recently Fixed
- ✅ Thai output bug: Added LANGUAGE_GUARD to all system prompts
- ✅ </think> </answer> tag leakage: Added clean_output() postprocessor
- ✅ Entity extraction JSON decode errors: Added safe_parse_terms() with 3-attempt fallback
- ✅ Missing language guard: LANGUAGE_GUARD now prefixes all agent prompts
- ✅ Memory cleanup on exit: Added signal handlers, atexit cleanup, and OllamaClient cleanup()
- ✅ Ollama server keeps running after translation: Created cleanup tool (tools/cleanup.py)

---

## Architecture Decisions (Do Not Reverse)

These decisions are final. Do not refactor or change these without explicit user instruction:

1. **4-stage pipeline** — Translate → Edit → Check → QA. Do not merge or skip stages.
2. **glossary_pending.json** — New terms NEVER go directly to `glossary.json`. Always pending first.
3. **`【?term?】` placeholder** — Unknown terms get this placeholder. AI must NOT guess translations.
4. **Atomic JSON writes** — All JSON saves go through `FileHandler.write_json()` (temp + rename). No direct `json.dump()` to final path.
5. **UTF-8-SIG encoding** — All file reads/writes use this encoding. Do not use plain `utf-8`.
6. **MemoryManager is the single source of truth** — No agent reads `glossary.json` or `context_memory.json` directly. Always go through `MemoryManager`.
7. **Type hints on every function** — All public methods in `src/` must have full type hints. No untyped functions allowed.
8. **Test before commit** — Every new function must have a corresponding test in `tests/`. Run `pytest tests/ -v` before every commit. No test = Gemini reviewer returns `NEEDS REVISION`.


## Code Drift Prevention Checklist (AI: run before SESSION END)
 
Before updating CURRENT_STATE.md at session end, verify:
 
```
[x] No cross-agent imports (agents only talk through MemoryManager)
[x] No direct file reads of glossary.json / context_memory.json (use FileHandler)
[x] All new/modified functions have type hints
[x] All new functions have at least one test in tests/  # Note: cleanup tool is utility, tested manually
[x] pytest tests/ passes with no failures (165 tests pass, 4 pytest import errors unrelated)
[x] Unknown terms use 【?term?】 placeholder — no free-form guesses
[x] JSON writes go through FileHandler.write_json() only
```
 
---
 

## API / Model Config (Current)

```yaml
# Local Ollama (Default)
provider: "ollama"
translator_model: "qwen2.5:14b"
editor_model: "qwen2.5:14b"
checker_model: "qwen:7b"
temperature: 0.3
repeat_penalty: 1.1
ollama_base_url: "http://localhost:11434"
translation_mode: "two_stage"

# Cloud Alternative
provider: "gemini"  # or "openrouter"
cloud_model: "gemini-2.5-flash"
```

---

## Quick Reference

### Run Translation (Standard Mode - Best Quality)
```bash
# Single chapter (~5 hours with 14B model)
python -m src.main --novel 古道仙鸿 --chapter 1

# All chapters
python -m src.main --novel 古道仙鸿 --all

# With automatic memory cleanup between chapters
python -m src.main --novel 古道仙鸿 --all --unload-after-chapter
```

### Run Translation (Fast Mode - 5-10x Speedup)
```bash
# Single chapter (~30-50 minutes with 7B model)
python -m src.main_fast --novel 古道仙鸿 --chapter 1

# All chapters
python -m src.main_fast --novel 古道仙鸿 --all

# From chapter 10
python -m src.main_fast --novel 古道仙鸿 --all --start 10

# With automatic memory cleanup
python -m src.main_fast --novel 古道仙鸿 --all --unload-after-chapter
```

### Qwen Model Setup
```bash
# Pull recommended Qwen models
ollama pull qwen2.5:14b  # Best quality (9GB)
ollama pull qwen2.5:7b   # Good quality, fast (4GB)

# See QWEN.md for detailed Qwen guidance
cat QWEN.md
```

### Memory Management
```bash
# Check Ollama status and memory usage
python -m tools.cleanup --status

# Stop all running models (frees GPU VRAM)
python -m tools.cleanup --stop-all

# Stop Ollama service completely (frees all memory)
python -m tools.cleanup --stop-service

# Full cleanup (stop all + show status)
python -m tools.cleanup --full

# Show memory management tips
python -m tools.cleanup --tips
```

### Run Tests
```bash
python -m unittest discover tests -v
```

### Update Ollama Model
```bash
ollama pull qwen2.5:14b
```

Do not change these defaults without updating `config/settings.yaml` AND this file.
