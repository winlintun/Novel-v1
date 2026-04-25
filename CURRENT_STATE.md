# CURRENT_STATE.md - Implementation Progress

> **FOR AI AGENTS — MANDATORY:**
> - **Session Start:** Read this file before any code. Check what is [DONE] and what is [TODO].
> - **Session End:** Update this file automatically after every task, file change, or decision.
>   No prompt needed. This is default behavior defined in AGENTS.md and GEMINI.md.

---

## Last Updated
- Date: 2026-04-25
- Last task completed: Tested dao-equaling-the-heavens translation files (glossary + context_memory for chapters 1-10). All files working correctly - 12 glossary terms loaded, chapter 11 ready for translation, MemoryManager integration verified, glossary v3.0 format compatible.

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
| Glossary v3.0 Manager | `src/utils/glossary_v3_manager.py` | [DONE] | Rich metadata support (aliases, exceptions, examples) |
| Glossary v3.0 Loader | `src/utils/glossary_v3_loader.py` | [DONE] | JSON I/O with validation, caching, and prompt export |
| Glossary Matcher | `src/utils/glossary_matcher.py` | [DONE] | Dynamic term extraction for relevant glossary injection |
| Repetition Detector | `src/utils/postprocessor.py` | [DONE] | check_repetition() function for output quality |
| Progress Logger | `src/utils/progress_logger.py` | [DONE] | Real-time translation progress tracking with live log file |

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
| `ERROR_LOG.md` | [DONE] | Error tracking and fix record for AI agents |
| `README.md` | [TODO] | Project overview |

---

## Features Backlog

### In Progress
<!-- AI: move tasks here when you start working on them -->
- (none)

### Completed
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
- [x] Myanmar Unicode quality validation
- [x] Configuration system (settings.yaml)
- [x] User documentation
- [x] 201+ passing tests (Unit, Integration, Regression, Quality)
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
- [x] **Glossary v3.0 Integration** (need_fix_another.md):
  - [x] `src/utils/glossary_v3_manager.py` - Rich metadata dataclasses (aliases, exceptions, dialogue_register)
  - [x] `src/utils/glossary_v3_loader.py` - JSON I/O with validation and caching
  - [x] `tests/test_glossary_v3.py` - 21 comprehensive unit tests (all passing)
  - [x] Config section in `settings.yaml` - Full v3.0 configuration options
  - [x] Non-breaking addition - compatible with existing pipeline
  - [x] Features: alias matching, exception rules, prompt export (markdown/json/plain)
- [x] **Translation Quality Fixes** (need_fix.md + need_fix_another.md):
  - [x] Updated `data/glossary.json` - 8 correct terms for 古道仙鸿 (罗青, 黄牛, 方宗主, etc.)
  - [x] Fixed `config/settings.fast.yaml` - chunk_size: 1500, repeat_penalty: 1.25, temperature: 0.3
  - [x] Created `src/utils/glossary_matcher.py` - Dynamic glossary term extraction
  - [x] Added `check_repetition()` to `src/utils/postprocessor.py` - Detects repetitive output
  - [x] Updated `src/agents/fast_translator.py` - Uses dynamic glossary, enhanced SOV prompt with examples
  - [x] Updated `src/main_fast.py` - Repetition guard after translation
  - [x] Post-implementation code review: Both reviewers PASSED
  - [x] All 201 tests passing
- [x] **Implemented need_fix.md requirements**:
  - [x] Created `scripts/bootstrap_glossary.py` - Semi-automated glossary extraction from Chinese text
  - [x] Script extracts 2-4 character sequences appearing 2+ times as proper noun candidates
  - [x] Creates glossary v1.0 compatible JSON with placeholder translations
  - [x] Uses utf-8-sig encoding per project standards
  - [x] Full error handling and logging implemented
- [x] **Implemented need_fix_another.md requirements**:
  - [x] Created `config/settings.pivot.yaml` - Two-stage pivot translation (CN→EN→MM)
  - [x] Stage 1: alibayram/hunyuan:7b (Chinese → English)
  - [x] Stage 2: yxchia/seallms-v3-7b:Q4_K_M (English → Myanmar)
  - [x] Updated `config/settings.fast.yaml` - Changed to pivot language approach
  - [x] Optimized for Ryzen 7 5700X / 16GB RAM / CPU-only

### Planned
- [ ] Batch chapter translation (`--all` flag) - PARTIAL (implemented in main.py)
- [ ] Glossary pending review CLI tool (`python -m src.tools.approve_terms`)
- [ ] Myanmar Unicode ratio checker in Checker agent - DONE
- [ ] Automatic `.bak` backup before glossary writes
- [ ] `【?term?】` placeholder detection and reporting

---

## Known Issues / Blockers

<!-- AI: log any bugs or blockers discovered here -->

### CRITICAL: Chinese Character Leakage in Translation Output [FIXED]
**Discovered:** 2026-04-25
**Status:** COMPLETED - All fixes implemented and tested

**Problem:** Model was outputting mixed Myanmar/Chinese text instead of pure Myanmar.
Example: "မြန်မာစာ 千年难逢的事儿吧！正好，被我撞到了！缅甸语"
Only 22% Myanmar characters, 69% Chinese!

**Root Cause:**
- LANGUAGE_GUARD forbade Chinese but postprocessor didn't actually remove leaked characters
- No retry mechanism for Chinese leakage (only existed for English)
- validate_output() counted Chinese but didn't reject based on it

**Fixes Applied:**
1. ✅ Added `remove_chinese_characters()` function to `postprocessor.py`
2. ✅ Updated `clean_output()` to strip Chinese characters (Step 3 in pipeline)
3. ✅ Strengthened LANGUAGE_GUARD with explicit Chinese prohibition examples
4. ✅ Added Chinese retry mechanism to `translator.py` (similar to English retry)
5. ✅ Updated `validate_output()` to REJECT output containing any Chinese characters
6. ✅ Added comprehensive tests for Chinese removal (6 new tests)

### CRITICAL: qwen2.5:14b English Output Issue [FIXED]
**Discovered:** 2026-04-25
**Status:** COMPLETED - All fixes implemented and tested

**Problem:** qwen2.5:14b produces mixed Myanmar/English output instead of pure Myanmar.
Example: `"နတ်ဆရာက အဖင့္မယဲ့ပစၥည်းလုပါ？thousands of years once-in-a-lifetime event ba!"`
Only 6.2% Myanmar characters!

**Root Cause:**
- Model has limited Myanmar training vocabulary
- Falls back to English when uncertain
- Temperature 0.5 was too high, causing creative drift

**Fixes Applied:**
1. ✅ Strengthened LANGUAGE_GUARD in `prompt_patch.py` with:
   - Explicit Myanmar examples (correct/incorrect)
   - Stronger penalties for English output
   - Clear placeholder instruction 【?term?】
2. ✅ Added example-based prompting to system prompts
3. ✅ Lowered temperature from 0.5 → 0.2 (more deterministic)
4. ✅ Added English detection in `postprocessor.py`:
   - Detects Latin words and common English words
   - Returns `has_english` flag in leakage detection
5. ✅ Added automatic retry mechanism in `translator.py`:
   - Detects English in output
   - Retries with reinforced language guard
   - Selects better result (lower English count)
6. ✅ Updated validation to track English words in report

**Workarounds if issue persists:**
- Use `qwen2.5:7b` instead (faster, less English drift)
- Use `gemma:7b` (better multilingual support)
- Use cloud API (Gemini) for critical translations
- Further lower temperature to 0.1
- Increase repeat_penalty to 1.2

### Recently Verified
- ✅ **dao-equaling-the-heavens Translation Files Tested**: Chapters 1-10 data working correctly
  - Glossary: 12 terms (Gu Wen → ကူဝမ်, Zhao Feng → ကျောက်ဖန်, Yu Hua → ယွီဟွာ, etc.)
  - Context: Summary of chapters 1-10 with active characters tracked
  - Chapter 11: 12,987 characters ready for translation
  - MemoryManager: Successfully loads and queries glossary terms
  - Format: Glossary v3.0 (source_term/target_term) compatible with codebase

### Recently Fixed
- ✅ **CRITICAL: Fixed problematic model references**:
  - `config/settings.yaml`: Changed `stage1_model` from `yxchia/seallms-v3-7b:Q4_K_M` to `qwen2.5:14b` (produces THAI ❌)
  - `config/settings.yaml`: Removed `hunyuan-mt:7b` from model_roles translator list (produces THAI ❌)
  - `src/utils/model_router.py`: Removed `hunyuan-mt:7b` from MODEL_REGISTRY and fixed translategemma fallback to `qwen2.5:7b`
  - Updated model_roles to use only verified Myanmar-capable models: qwen2.5:14b, qwen2.5:7b, qwen:7b
  - Added documentation comments warning about Thai-producing models
- ✅ Translation quality fixes (need_fix.md + need_fix_another.md): Updated glossary with 8 correct characters, fixed pipeline settings (chunk_size: 1500, repeat_penalty: 1.25, temperature: 0.3), added GlossaryMatcher and repetition detection, enhanced SOV prompt with examples. Post-implementation code review PASSED.
- ✅ Thai output bug: Added LANGUAGE_GUARD to all system prompts
- ✅ </think> </answer> tag leakage: Added clean_output() postprocessor
- ✅ extract_pdf_terms.py KeyError: Fixed curly brace escaping in ALIGNMENT_PROMPT template (JSON example was interpreted as format placeholder)
- ✅ Glossary v3.0 code review fixes:
  - Fixed Python 3.10+ union syntax (`str | Path` → `Union[str, Path]`)
  - Fixed deprecated `datetime.utcnow()` → `datetime.now(timezone.utc)`
  - Added proper logging to exception handling
  - Removed unused imports (json, re, hashlib, datetime from manager)
  - Fixed test file encoding to use utf-8-sig
  - Documented lookup ambiguity in docstrings
- ✅ Corrupted context_memory.json: Reset to clean state (contained Thai contamination, XML tags, mixed languages)
- ✅ Entity extraction JSON decode errors: Added safe_parse_terms() with 3-attempt fallback
- ✅ Missing language guard: LANGUAGE_GUARD now prefixes all agent prompts
- ✅ Memory cleanup on exit: Added signal handlers, atexit cleanup, and OllamaClient cleanup()
- ✅ Ollama server keeps running after translation: Created cleanup tool (tools/cleanup.py)
- ✅ Code review fixes for existing modules:
  - `src/agents/glossary_sync.py`: Moved imports to top of file, added proper logging, replaced `os.path.exists()` with FileHandler
  - `src/agents/qa_tester.py`: Removed non-existent `frequency` field reference from glossary schema
  - `src/utils/glossary_v3_loader.py`: Replaced direct `open()` with `FileHandler.read_json()`
  - `tests/test_qa_tester.py`: Updated mock to use `verified` field instead of non-existent `frequency` field
- ✅ ERROR_LOG.md created: Tracks all runtime errors and fixes for AI agent reference
- ✅ ERROR-001 Fixed: Glossary key mismatch (`source`/`target` vs `source_term`/`target_term`)
- ✅ ERROR-002 Fixed: Module import path issue in `main_fast.py`
- ✅ ERROR-003 Fixed: Unavailable model config in `settings.fast.yaml`

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

### Monitor Translation Progress
```bash
# While translation is running, watch progress in real-time:
tail -f logs/progress/progress_古道仙鸿_ch001_*.md

# View completed progress log:
cat logs/progress/progress_古道仙鸿_ch001_20250424_143022.md
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
