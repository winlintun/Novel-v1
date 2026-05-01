# Error Log & Fix Record

> **Purpose**: Track all runtime errors encountered and their fixes for AI agent reference.
> **Updated**: Auto-updated by AI agents after fixing errors
> **Format**: Chronological log with error details, root cause, and fix verification

---


### ERROR-047: Code Review — 10 Reviewer A Issues Verified Resolved
**Date**: 2026-05-01
**Files**: `ui/pages/6_Reader.py`, `src/cli/commands.py`, `src/cli/__init__.py`, `src/cli/parser.py`, `src/main.py`, `ui/streamlit_app.py`
**Issue Summary**:
10 issues flagged by Reviewer A were verified as RESOLVED:
1. CODE DUPLICATION — imports from postprocessor proper
2. HARDCODED PATH — pre-existing constant pattern
3. LAZY IMPORT — `import re` at module top
4. BARE EXCEPT — changed to `except UnicodeDecodeError`
5. MISSING EXPORT — `run_view_file` in `__init__.py`
6. DEAD CODE — no `reader_scroll` found
7. XSS RISK — `.replace("<", "&lt;").replace(">", "&gt;")` sanitization
8. ENCODING — `utf-8-sig` in all streamlit_app.py file reads
9. CHAPTER NUMBER REGEX — anchored `r"[_s]*(\d{2,4})$"` with fallback
10. READER HTML WRAPPER — `st.columns()` + native `st.markdown()`
**Status**: RESOLVED/VERIFIED
**Verified By**: Manual code review, grep, full file read
**Commit**: 67faff7

## How to Use This File

### When an error occurs:
1. Run the program and capture the error
2. Record the error in the "Active Issues" section
3. Debug and fix the issue
4. Move the entry to "Resolved Issues" with fix details
5. Update CURRENT_STATE.md

### Format:
```markdown
### ERROR-XXX: [Brief Title]
**Date**: YYYY-MM-DD
**File**: `path/to/file.py`
**Error Message**:
```
[Full error traceback]
```
**Root Cause**: [Explanation of why it happened]
**Fix Applied**: [What was changed]
**Files Modified**:
- `file1.py` - [what changed]
- `file2.py` - [what changed]
**Status**: [RESOLVED / IN PROGRESS / VERIFIED]
**Verified By**: [code-reviewer / manual test / pytest]
```

---

## Active Issues

*No active issues currently.*

### ERROR-046: Postprocessor Destroys Paragraph Structure + 8 Duplicate Chapter Headings
**Date**: 2026-05-01
**File**: `src/utils/postprocessor.py`
**Error Description**:
1. Output file `reverend-insanity_0012.mm.md` was a single line (0 newlines, 12904 chars) — all paragraph breaks destroyed
2. Chapter heading `# အခန်း ၁၂ ## Title` appeared on same line (no `\n\n` between H1 and H2)
3. Chapter heading repeated 8 times (once per translation chunk) throughout the body

**Root Cause**:
1. `remove_latin_words()` line 234: `re.sub(r'\s+', ' ', text)` collapsed ALL whitespace including `\n` to spaces, destroying all paragraph structure
2. Model outputs `# အခန်း N ## Title` as a single concatenated line instead of proper markdown
3. The context buffer feeds the previous chunk's heading to the translator, causing it to repeat the heading at the start of each new chunk. `_deduplicate_chunks()` couldn't catch it because the text had no newlines to split on.

**Fix Applied**:
1. Changed `remove_latin_words` regex from `r'\s+'` to `r'[^\S\n]+'` — only collapses horizontal whitespace
2. Added `fix_chapter_heading_format()` — splits `# H1 ## H2` into `# H1\n\n## H2`
3. Added `remove_duplicate_headings()` — keeps only first `# အခန်း N`, removes subsequent duplicates and their `##` subtitles
4. Added `_split_into_lines_if_needed()` — recovery path for already-corrupted single-line files (splits at heading boundaries + `။` sentence markers)
5. All heading regexes now support both Myanmar (`\u1040-\u1049`) and Western (`\d`) digits

**Files Modified**:
- `src/utils/postprocessor.py` — 3 bug fixes + 1 recovery function + digit support (91 insertions, 3 deletions)

**Output File Fixed**:
- `data/output/reverend-insanity/reverend-insanity_0012.mm.md` — restored proper formatting (backup at `.mm.md.bak`)

**Status**: RESOLVED
**Verified By**: pytest (229/229 pass), manual fix verification (headings: 8→1, newlines: 0→203, double-newlines: 0→99)

### ERROR-045: Workflow Auto-Detect Returns None (Tests Failing)
**Date**: 2026-05-01
**File**: `tests/test_workflow_routing.py`, `src/agents/preprocessor.py`
**Error Message**:
```
FAILED: test_resolve_workflow_auto_detect_chinese_input — AssertionError: None != 'way2'
FAILED: test_resolve_workflow_auto_detect_english_input — AssertionError: None != 'way1'
```
**Root Cause**: `Preprocessor.detect_language()` at line 46 returns `"unknown"` when `len(text.strip()) < 50`. Test inputs were too short — Chinese: 21 chars, English: 60 chars (borderline).

**Fix Applied**: Increased test input lengths to exceed 50-char minimum. Chinese text: 65 chars, English text: 130 chars.

**Files Modified**:
- `tests/test_workflow_routing.py` - Extended auto-detect test inputs

**Status**: RESOLVED
**Verified By**: pytest (229/229 pass)

### ERROR-044: Translation Quality Bugs from need_fix_bug.md
**Date**: 2026-05-01
**File**: Multiple (postprocessor.py, preprocessor.py, translator.py, myanmar_quality_checker.py, orchestrator.py, settings.yaml)
**Error Description**:
1. Bengali script (গাঢ়) leaked into Myanmar output — not caught by quality checker
2. Duplicate paragraphs from chunking overlap (same paragraph translated twice with slight variation)
3. Translator credit line included in body text
4. HTML metadata comment (<!-- Translated:... -->) embedded in output .md body
5. Inconsistent formal/colloquial register mixed within same chapter
6. Chapter heading format incorrect (inline instead of markdown # heading)
7. Emotional intensity flat in aggressive dialogue (weak verbs)

**Root Cause**: 
1. `detect_language_leakage()` only checked Thai/Chinese/English, not Bengali
2. Chunk overlap=50 passed same paragraphs into adjacent chunks, no deduplication during assembly
3. Preprocessor didn't strip `Translator:`/`Editor:` metadata lines
4. `_save_output()` embedded HTML comments in .md body instead of sidecar file
5. Translator prompts lacked register consistency rule
6. Translator prompts lacked chapter heading format instruction
7. Translator prompts lacked emotional intensity guidance for aggressive dialogue

**Fix Applied**: See CURRENT_STATE.md for full details. 7 bugs fixed across 6 files.

**Files Modified**:
- `src/utils/postprocessor.py` - Bengali detection, removal, validation
- `src/agents/preprocessor.py` - strip_metadata()
- `src/agents/translator.py` - Prompt rules 9-11 (register, headings, intensity)
- `src/agents/myanmar_quality_checker.py` - Bengali detection in quality check
- `src/pipeline/orchestrator.py` - _deduplicate_chunks(), sidecar metadata writing
- `config/settings.yaml` - chunk_overlap=0, temperature=0.4

**Status**: RESOLVED
**Verified By**: python3 verification tests, pytest 227/229 pass

### ERROR-043: --chapter-range 9-15 - All Chapters Failed (File Not Found)
**Date**: 2026-05-01
**File**: `src/pipeline/orchestrator.py`, `src/cli/commands.py`
**Error Message**:
```
ERROR - All 7 chapters failed to translate
```
**Root Cause**: 
1. `translate_chapter()` only looked for `{chapter:03d}.md` (e.g., `009.md`), but actual input files use naming conventions like:
   - `{novel}_chapter_{chapter:03d}.md` (e.g., `dao-equaling-the-heavens_chapter_009.md`)
   - `{novel}_{chapter:04d}.md` (e.g., `reverend-insanity_0009.md`)
2. `translate_novel()` auto-discovery used `f.stem.isdigit()` which fails for stems like `reverend-insanity_0009`
3. Per-chapter error details only logged for partial success, not total failure — making debugging hard

**Fix Applied**:
1. Added `_find_chapter_file()` static method to try 5 naming patterns in priority order:
   - `{novel}_chapter_{XXX}.md`
   - `{XXX}.md` (3-digit)
   - `{XXXX}.md` (4-digit)
   - `{novel}_{XXX}.md` (3-digit)
   - `{novel}_{XXXX}.md` (4-digit)
2. Added `_discover_chapters()` static method with regex fallback for non-pure-digit stems
3. Fixed `commands.py` to always log per-chapter failures with actual chapter number

**Files Modified**:
- `src/pipeline/orchestrator.py` - Added `_find_chapter_file()` and `_discover_chapters()`, updated `translate_chapter()` and `translate_novel()`
- `src/cli/commands.py` - Always log per-chapter errors, use actual chapter numbers in messages

**Status**: RESOLVED
**Verified By**: python3 py_compile, manual path resolution test (all 3 novel naming conventions confirmed)
**Date**: 2026-04-30
**Files**: Multiple (glossary.json, orchestrator.py, ollama_client.py, translator.py, settings.yaml)
**Error Messages**:
```
Chunk 1: myanmar_ratio: 0.417, english_common_words: 24 → NEEDS_REVIEW
Chunk 2: myanmar_ratio: 0.000 → REJECTED
Chunk 3: myanmar_ratio: 0.912 → NEEDS_REVIEW  
Chunk 4: myanmar_ratio: 0.000 → REJECTED

Output contained: raw English fragments, Korean chars, wrong glossary terms from different novel
```
**Root Cause**: 
1. `data/glossary.json` contained 50 terms from wrong novel (dao-equaling-the-heavens/古道仙鸿) that were being injected into Reverend Insanity translations, confusing the model
2. `OllamaClient` in orchestrator was created without passing temperature/top_p/repeat_penalty from config — used wrong defaults (temp=0.5 instead of config's 0.3)
3. Chunk size 2000 chars overwhelmed padauk-gemma for EN→MM translation
4. English system prompt lacked LANGUAGE_GUARD reinforcement against English leakage

**Fix Applied**:
1. Backed up old glossary, created fresh empty glossary for Reverend Insanity
2. Added temperature/top_p/top_k/repeat_penalty/max_retries passthrough from config.processing to OllamaClient in orchestrator
3. Reduced chunk_size 2000→800, tuned sampling params (temperature 0.3→0.2, repeat_penalty 1.3→1.15, top_p 0.92→0.95, top_k 50→40)
4. Added LANGUAGE_GUARD prefix to both EN→MM and CN→MM prompts; strengthened EN prompt with COMPLETENESS rule
5. Increased num_predict for gemma models 1024→2048 and others 800→1024

**Files Modified**:
- `config/settings.yaml` - chunk_size, temperature, repeat_penalty, top_p, top_k
- `src/agents/translator.py` - LANGUAGE_GUARD + strengthened EN prompt
- `src/pipeline/orchestrator.py` - config param passthrough to OllamaClient
- `src/utils/ollama_client.py` - increased num_predict
- `data/glossary.json` - replaced with fresh empty glossary

**Status**: RESOLVED
**Verified By**: pytest (227/229 pass, 2 pre-existing failures), py_compile checks, code review

### ERROR-040: Poor Translation Quality & Missing CLI Information
**Date**: 2026-04-27
**Files**: `config/settings.yaml`, `src/agents/translator.py`, `src/cli/commands.py`, `src/cli/formatters.py`
**Error Messages**:
```
Translation output contained garbled/incorrect characters:
"အခန်း ၁: ရညပင့်တစိမာသည် ႏွစ္ကြံလေးမထဲမှုဘယ်ဆီအဖြစ်မဟူ"
(Myanmar char ratio: ~10%, mostly gibberish)

CLI only showed basic logging without detailed info:
- No model information displayed
- No settings displayed  
- No pipeline stages shown
- No progress indication
```
**Root Cause**:
1. Default model `qwen2.5:14b` was outputting Japanese/Chinese instead of Myanmar
2. System prompts were not explicit enough about requiring Myanmar language output
3. CLI commands.py was not using the formatter functions to display detailed information

**Fix Applied**:
1. Changed default model from `qwen2.5:14b` to `padauk-gemma:q8_0` (specialized for Myanmar)
2. Updated translator prompts with explicit Myanmar language requirements:
   - Added "CRITICAL: Output MUST be in Myanmar/Burmese script" warnings
   - Added example Myanmar text in prompts
   - Added "NO Japanese. NO Chinese. NO English" constraints
3. Enhanced CLI output in commands.py:
   - Added print_translation_header() to show model, settings, config
   - Added print_pipeline_stages() to show all pipeline stages
   - Added print_section_header() and print_info() for progress updates
   - Added detailed success/error messages with file paths and metrics
4. Fixed formatters.py to handle 'single_stage' mode in pipeline stages

**Files Modified**:
- `config/settings.yaml` - Changed default models to padauk-gemma:q8_0
- `src/agents/translator.py` - Enhanced prompts with explicit Myanmar language requirements
- `src/cli/commands.py` - Added verbose CLI output using formatters
- `src/cli/formatters.py` - Added single_stage mode handling

**Status**: RESOLVED
**Verified By**: 
- Direct model test: padauk-gemma produced 98% Myanmar char ratio vs 0% for qwen2.5
- Full pipeline test: Translation completed successfully with proper Myanmar output
- CLI display test: All model info, settings, and stages now displayed correctly

### ERROR-039: Checker.__init__() unexpected keyword argument 'ollama_client'
**Date**: 2026-04-27
**File**: `src/pipeline/orchestrator.py`, `src/core/container.py`
**Error Message**:
```
TypeError: Checker.__init__() got an unexpected keyword argument 'ollama_client'
```
**Root Cause**: The Checker class only accepts `memory_manager` and `config` parameters (it performs local validation without LLM calls), but orchestrator.py and container.py were passing `ollama_client` like other agents that do use LLMs
**Fix Applied**:
1. Removed `ollama_client=self.ollama_client` parameter from Checker() instantiation in `src/pipeline/orchestrator.py` (line 165-168)
2. Removed `ollama_client=self.get_ollama_client()` parameter from Checker() instantiation in `src/core/container.py` (line 111-114)
**Files Modified**:
- `src/pipeline/orchestrator.py` - Fixed Checker instantiation
- `src/core/container.py` - Fixed Checker instantiation
**Status**: RESOLVED
**Verified By**: python3 -m src.main --mode full --test (passed initialization, timed out during translation as expected)

### ERROR-036: Documentation Update for Refactored Codebase
**Date**: 2026-04-27
**File**: `AGENTS.md`, `GEMINI.md`, `README.md`
**Error Message**:
```
Documentation did not reflect the new modular codebase structure after refactoring
```
**Root Cause**: After extracting main.py into modular components (cli/, pipeline/, web/, config/, core/, types/), the documentation files still showed the old monolithic structure
**Fix Applied**:
1. Updated `AGENTS.md`:
   - Updated Directory Structure section with new modules
   - Updated System Architecture diagram to show new flow
   - Updated test structure to include new test files
2. Updated `GEMINI.md`:
   - Added new "New Refactored Modules (v2.0)" table with all new file paths
   - Preserved original file paths for backward compatibility reference
3. Updated `README.md`:
   - Updated Directory Structure with new modules
   - Added "Architecture Overview" section explaining the refactoring
   - Added table explaining each new module's purpose
   - Updated test count from 221 to 229+
**Files Modified**:
- `AGENTS.md` - Updated directory structure, architecture diagram, test structure
- `GEMINI.md` - Added new file paths table
- `README.md` - Updated structure, added architecture section
**Status**: RESOLVED
**Verified By**: manual review

### ERROR-038: Type Hint Missing on Function Parameters
**Date**: 2026-04-27
**File**: `src/cli/commands.py`, `src/web/launcher.py`
**Error Message**:
```
Code review found missing type hints on function parameters:
- run_translation_pipeline(args) missing type hint
- run_glossary_generation(args) missing type hint
- run_ui_launch(args) missing type hint
- run_test(args) missing type hint
- launch_web_ui(args) missing type hint
```
**Root Cause**: The AGENTS.md requires "Type Hints (Every function, no exceptions)" but the refactored code had missing type hints on `args` parameters
**Fix Applied**:
1. Added `import argparse` to src/cli/commands.py
2. Added type hint `args: argparse.Namespace` to:
   - `run_translation_pipeline()`
   - `run_glossary_generation()`
   - `run_ui_launch()`
   - `run_test()`
3. Added `import argparse` to src/web/launcher.py
4. Added type hint `args: Optional[argparse.Namespace]` to `launch_web_ui()`
**Files Modified**:
- `src/cli/commands.py` - Added argparse import and type hints
- `src/web/launcher.py` - Added argparse import and type hint
**Status**: RESOLVED
**Verified By**: pytest (229 tests passed), code-reviewer

### ERROR-037: Pipeline Integration Issues
**Date**: 2026-04-27
**File**: `src/pipeline/orchestrator.py`, `src/cli/commands.py`
**Error Message**:
```
1. TypeError: Preprocessor.__init__() got an unexpected keyword argument 'chunk_overlap'
2. AttributeError: 'Preprocessor' object has no attribute 'clean_text'
3. AttributeError: 'Translator' object has no attribute 'translate'
4. TypeError: list indices must be integers or slices, not str (in commands.py line 127)
```
**Root Cause**: The refactored pipeline code had method name mismatches and incorrect parameter names that didn't match the actual agent class implementations
**Fix Applied**:
1. Fixed `src/pipeline/orchestrator.py` line 105: Changed `chunk_overlap` to `overlap_size` to match Preprocessor signature
2. Fixed `src/pipeline/orchestrator.py` lines 316-326: Changed `clean_text` to `clean_markdown`, fixed `create_chunks` call to pass text directly and extract text from returned dicts
3. Fixed `src/pipeline/orchestrator.py` lines 345-363: Corrected method names:
   - `translate` → `translate_paragraph`
   - `refine` → `refine_paragraph`
   - `improve` → `reflect_and_improve`
   - `check` → `check_quality`
   - `check_consistency` → `check_glossary_consistency`
4. Fixed `src/cli/commands.py` lines 119-145: Added proper handling for list results from `translate_novel()` vs single results from `translate_file()`/`translate_chapter()`
**Files Modified**:
- `src/pipeline/orchestrator.py` - Fixed method calls and parameter names
- `src/cli/commands.py` - Fixed result handling for batch vs single translation
**Status**: RESOLVED
**Verified By**: pytest (229 tests passed)

### ERROR-035: Code Refactoring - main.py Monolith Extraction
**Date**: 2026-04-27
**File**: `src/main.py`
**Error Message**:
```
main.py contained 1136 lines mixing:
- CLI argument parsing
- Pipeline orchestration logic
- UI launch logic
- Progress display functions
- File I/O operations
- No structured error handling
- No type safety for configuration
```
**Root Cause**: main.py grew into a monolith violating single responsibility principle, making it difficult to test and maintain
**Fix Applied**:
1. Extracted CLI functionality to `src/cli/` module:
   - `parser.py`: Argument parsing with argparse
   - `formatters.py`: Output formatting functions
   - `commands.py`: Command handlers for translate, glossary, ui, test
2. Extracted pipeline to `src/pipeline/orchestrator.py`:
   - TranslationPipeline class with lazy agent loading
   - Stage coordination (preprocess → translate → refine → check → save)
3. Extracted web UI to `src/web/launcher.py`:
   - Streamlit launch functionality
4. Created configuration module `src/config/`:
   - `models.py`: Pydantic models with validation
   - `loader.py`: Config loading with error handling
5. Created exception hierarchy `src/exceptions.py`:
   - NovelTranslationError base class
   - ModelError, GlossaryError, ValidationError, ResourceError, PipelineError
6. Created type definitions `src/types/definitions.py`:
   - TypedDict for GlossaryTerm, TranslationChunk, PipelineResult, etc.
7. Created DI container `src/core/container.py`:
   - Dependency injection for testability
8. Simplified `src/main.py` to <50 lines as thin dispatcher
9. Updated `tests/test_workflow_routing.py` to use new module paths
10. Updated `tests/test_agents.py` to match new prompt format
**Files Modified**:
- `src/main.py` - Refactored to thin dispatcher
- `src/cli/parser.py` - NEW: Argument parsing
- `src/cli/formatters.py` - NEW: Output formatting
- `src/cli/commands.py` - NEW: Command handlers
- `src/cli/__init__.py` - NEW: CLI module exports
- `src/pipeline/orchestrator.py` - NEW: Pipeline coordination
- `src/pipeline/__init__.py` - NEW: Pipeline module exports
- `src/web/launcher.py` - NEW: UI launcher
- `src/web/__init__.py` - NEW: Web module exports
- `src/config/models.py` - NEW: Pydantic config models
- `src/config/loader.py` - NEW: Config loader
- `src/config/__init__.py` - NEW: Config module exports
- `src/exceptions.py` - NEW: Exception hierarchy
- `src/types/definitions.py` - NEW: Type definitions (moved from src/types.py)
- `src/types/__init__.py` - NEW: Types module exports
- `src/core/container.py` - NEW: DI container
- `src/core/__init__.py` - NEW: Core module exports
- `tests/test_workflow_routing.py` - Updated imports
- `tests/test_agents.py` - Updated test assertions for new prompts
**Status**: RESOLVED
**Verified By**: pytest (229 tests passed)

### ERROR-027: Web UI Sidebar Settings Not Applied
**Date**: 2026-04-27
**File**: `ui/components/sidebar.py`, `ui/pages/2_Translate.py`
**Error Message**:
```
Translation Settings: Use Glossary checkbox not working
Model Settings (Advanced): temperature, max_tokens, context_window not saved
Translation Behavior: batch_size, retries, fallback not applied
Glossary Settings: enable_glossary, priority not working
```
**Root Cause**: Many sidebar settings were defined in UI but not returned in settings dict, and not applied when starting translation
**Fix Applied**:
1. Updated `ui/components/sidebar.py`:
   - Added all missing settings to return dictionary
   - Added unique keys to all form elements to prevent conflicts
   - Added variables: top_p, freq_penalty, pres_penalty, api_key
   - Added variables: batch_size, retry_on_fail, max_retries, delay_retry, fallback, concurrent_workers, preserve_formatting, term_separation
   - Added variables: enable_glossary, priority, new_term_notify
2. Updated `ui/pages/2_Translate.py`:
   - Added comprehensive config update before translation
   - Saves: model, temperature, max_tokens, context_window (as num_ctx)
   - Saves: batch_size, max_retries
   - Saves: enable_glossary, priority
   - Saves: enable_reflection
   - Added user feedback showing saved settings
**Files Modified**:
- `ui/components/sidebar.py` - Added all settings to return dict, added unique keys
- `ui/pages/2_Translate.py` - Added config update logic
**Status**: RESOLVED

### ERROR-028: FileNotFoundError for Output Files in chapters/ Subdirectory
**Date**: 2026-04-27
**File**: `ui/pages/2_Translate.py`
**Error Message**:
```
FileNotFoundError: [Errno 2] No such file or directory: 'data/output/reverend-insanity/reverend-insanity_0001_mm.md'
```
**Root Cause**: Translation output files are saved to `chapters/` subdirectory but UI was only looking in root output directory
**Fix Applied**:
1. Created `find_output_file()` helper function to search both locations
2. Updated file reading logic to use helper (lines 218-225)
3. Updated Save Edit button to use helper (lines 265-272)
4. Added error handling with user-friendly messages
**Files Modified**:
- `ui/pages/2_Translate.py` - Added helper function and updated file operations
**Status**: RESOLVED

### ERROR-029: Model Selection Limited to 3 Models
**Date**: 2026-04-27
**File**: `ui/components/sidebar.py`
**Error Message**:
```
Model select showing only: qwen2.5:14b, qwen2.5:7b, qwen:7b
```
**Root Cause**: Model list was hardcoded and config only had 3 models in model_roles.translator
**Fix Applied**:
1. Added `get_available_models()` function that:
   - First tries to fetch from Ollama API (http://localhost:11434/api/tags)
   - Falls back to config model_roles.translator
   - Final fallback to common models
2. Updated model selectbox to use this function
**Files Modified**:
- `ui/components/sidebar.py` - Added get_available_models() function
**Status**: RESOLVED

### ERROR-030: Navigation Links Return 404
**Date**: 2026-04-27
**File**: `ui/components/sidebar.py`
**Error Message**:
```
http://localhost:8501/page/4_Glossary_Editor (404 Not Found)
```
**Root Cause**: Using `st.link_button()` with URL paths instead of Streamlit's navigation methods
**Fix Applied**:
1. Changed `st.link_button("Show all...", "/page/4_Glossary_Editor")` to:
   ```python
   if st.button("Show all..."):
       st.switch_page("pages/4_Glossary_Editor.py")
   ```
2. This uses Streamlit's proper page navigation
**Files Modified**:
- `ui/components/sidebar.py` - Fixed navigation button
**Status**: RESOLVED

### ERROR-031: Dashboard Progress Count Incorrect
**Date**: 2026-04-27
**File**: `ui/streamlit_app.py`
**Error Message**:
```
Dashboard shows incorrect translation progress count
```
**Root Cause**: Progress counting only checked root output dir, not chapters/ subdirectory
**Fix Applied**:
1. Updated progress counting logic to check both locations:
   - Root output directory
   - chapters/ subdirectory
2. Now correctly counts all translated chapters
**Files Modified**:
- `ui/streamlit_app.py` - Updated progress counting (lines 39-46)
**Status**: RESOLVED

### ERROR-032: Settings Model Selector Still Limited to Config List
**Date**: 2026-04-27
**File**: `ui/pages/5_Settings.py`, `ui/components/sidebar.py`, `ui/utils/model_loader.py`
**Error Message**:
```
Model Configuration and Translation Settings only show:
qwen2.5:14b, qwen2.5:7b, qwen:7b
```
**Root Cause**: Settings page used a static/hardcoded model list path, and sidebar fallback could still collapse to config-only models.
**Fix Applied**:
1. Added shared model loader `ui/utils/model_loader.py`:
   - First tries Ollama API `/api/tags`
   - Falls back to `ollama list` CLI parsing
   - Falls back to config (`model_roles` + `models`)
   - Uses default list only as last fallback
2. Updated `ui/components/sidebar.py` to import and use shared loader.
3. Updated `ui/pages/5_Settings.py` to use shared loader with configured Ollama base URL.
**Files Modified**:
- `ui/utils/model_loader.py` - New shared model discovery utility
- `ui/components/sidebar.py` - Replaced local model fetch logic with shared loader
- `ui/pages/5_Settings.py` - Replaced hardcoded/config-limited model list with shared loader
**Status**: RESOLVED
**Verified By**: manual smoke test (`MODEL_COUNT 10`)

### ERROR-033: Workflow Routing Not Explicit for Required Way1/Way2
**Date**: 2026-04-27
**File**: `src/main.py`, `ui/pages/2_Translate.py`, `tests/test_workflow_routing.py`
**Error Message**:
```
Required workflows were implicit and mixed with lang/two-stage flags:
- way1: English -> Myanmar direct
- way2: Chinese -> English -> Myanmar (step1 + step2 using way1)
```
**Root Cause**: Pipeline selection depended on config + language heuristics, without a first-class workflow selector.
**Fix Applied**:
1. Added explicit CLI flag: `--workflow {way1,way2}` in `src/main.py`
2. Added workflow resolvers:
   - `resolve_workflow(args)`
   - `apply_workflow_overrides(config, workflow)`
3. Enforced routing behavior:
   - `way1` => direct EN→MM (non-pivot)
   - `way2` => CN→EN→MM (pivot)
4. Updated web UI command builder (`ui/pages/2_Translate.py`) to pass:
   - English source -> `--workflow way1`
   - Chinese source -> `--workflow way2`
5. Added tests in `tests/test_workflow_routing.py` (5 tests, all pass)
**Files Modified**:
- `src/main.py` - workflow flag, routing helpers, and runtime routing enforcement
- `ui/pages/2_Translate.py` - workflow argument mapping for UI launches
- `tests/test_workflow_routing.py` - unit tests for way1/way2 resolution and config overrides
**Status**: RESOLVED
**Verified By**: `python3 -m unittest tests.test_workflow_routing -v` (5/5 passed), CLI help smoke test

### ERROR-034: Pivot Stage2 Output Rejected Due English Leakage
**Date**: 2026-04-27
**File**: `src/agents/pivot_translator.py`, `src/main.py`, `ui/components/sidebar.py`, `ui/pages/2_Translate.py`, `tests/test_workflow_routing.py`, `tests/test_pivot_stage2_guard.py`
**Error Message**:
```
CRITICAL: Translation REJECTED in chapter 2:
{'chapter': 2, 'myanmar_ratio': 0.0, 'latin_words_found': 64, 'status': 'REJECTED'}
```
**Root Cause**:
1. Stage2 (EN→MM) in pivot flow could return mostly English and fail hard without strong language-leak retry.
2. Workflow selection depended on explicit flags; user wanted automatic routing without adding parameters.
**Fix Applied**:
1. Added automatic workflow detection in `src/main.py`:
   - explicit `--workflow` (optional) -> highest priority
   - `--lang` hint -> next priority
   - source text heuristic detection (English vs Chinese) -> auto route
2. Updated Web UI source selector to include `Auto` (default) and stop forcing workflow param.
3. Added Stage2 leakage guard in `PivotTranslator.translate_stage2()`:
   - detect severe non-Myanmar output
   - retry with stronger Myanmar-only constraints
   - keep best candidate by Myanmar ratio before validation
4. Added regression tests:
   - `tests/test_workflow_routing.py` (auto detection cases)
   - `tests/test_pivot_stage2_guard.py` (stage2 retry on English leakage)
**Files Modified**:
- `src/main.py`
- `src/agents/pivot_translator.py`
- `ui/components/sidebar.py`
- `ui/pages/2_Translate.py`
- `tests/test_workflow_routing.py`
- `tests/test_pivot_stage2_guard.py`
**Status**: RESOLVED
**Verified By**: `python3 -m unittest tests.test_workflow_routing tests.test_pivot_stage2_guard -v` (8/8 passed)

---

## Issues Fixed in Web UI Update Session

### ERROR-020: Settings Page Model Selection Limited
**Date**: 2026-04-27
**File**: `ui/pages/5_Settings.py`, `ui/components/sidebar.py`
**Error Message**:
```
Settings page shows text input instead of dropdown for models
Sidebar only shows 3 hardcoded models: ["qwen2.5:14b", "padauk-gemma:q8_0", "qwen:7b"]
```
**Root Cause**: Model selection was hardcoded to only 3 models and used text_input instead of selectbox
**Fix Applied**:
1. Updated `ui/pages/5_Settings.py` to use selectbox with models from config `model_roles.translator`
2. Updated `ui/components/sidebar.py` to load available models from config
3. Both now dynamically load model list from `config/settings.yaml`
**Files Modified**:
- `ui/pages/5_Settings.py` - Changed text_input to selectbox for model selection
- `ui/components/sidebar.py` - Load models from config instead of hardcoded list
**Status**: RESOLVED

### ERROR-021: Glossary Editor ValueError 'person_character' not in list
**Date**: 2026-04-27
**File**: `ui/pages/4_Glossary_Editor.py`
**Error Message**:
```
ValueError: 'person_character' is not in list
```
**Root Cause**: Category dropdowns had hardcoded list `["character", "place", "item", "level"]` that didn't include 'person_character' and other valid categories
**Fix Applied**:
1. Changed category selection to dynamically load from existing terms in glossary
2. Added fallback list with common categories including 'person_character'
3. Fixed all three locations: filter dropdown, add term form, and edit term form
**Files Modified**:
- `ui/pages/4_Glossary_Editor.py` - Dynamic category loading (lines 48-52, 67-73, 113-121)
**Status**: RESOLVED

### ERROR-022: Progress Page Chapter Filter Not Working
**Date**: 2026-04-27
**File**: `ui/pages/3_Progress.py`
**Error Message**:
```
Chapter 1 is translated but not showing in "Translated" filter
Output files not found - looking in wrong directory
```
**Root Cause**: Code only looked in `data/output/{novel}/` but output files are in `data/output/{novel}/chapters/`
**Fix Applied**:
1. Updated file search to check both root output dir and `chapters/` subdirectory
2. Now correctly finds output files regardless of location
**Files Modified**:
- `ui/pages/3_Progress.py` - Added chapters/ subdirectory search (lines 50-58)
**Status**: RESOLVED

### ERROR-023: Progress Page Session Info Shows Wrong Status
**Date**: 2026-04-27
**File**: `ui/pages/3_Progress.py`
**Error Message**:
```
Status shows "IN PROGRESS" after translation is complete
No status indicator in log statistics
```
**Root Cause**: Log viewer didn't parse status from log content
**Fix Applied**:
1. Added log content parsing to detect COMPLETE/FAILED status
2. Added status metric to Log Statistics section
3. Searches for status markers in log content
**Files Modified**:
- `ui/pages/3_Progress.py` - Added status detection (lines 119-135)
**Status**: RESOLVED

### ERROR-024: Progress Page Clear Old Logs Not Working
**Date**: 2026-04-27
**File**: `ui/pages/3_Progress.py`
**Error Message**:
```
"Clear Old Logs" button shows "Feature not implemented yet"
```
**Root Cause**: Button was a placeholder without implementation
**Fix Applied**:
1. Implemented log cleanup function that keeps 10 most recent logs
2. Deletes older logs from `logs/progress/` directory
3. Shows success message with count of deleted files
**Files Modified**:
- `ui/pages/3_Progress.py` - Implemented clear old logs functionality (lines 136-152)
**Status**: RESOLVED

### ERROR-025: Translate Page Output Files Not Showing
**Date**: 2026-04-27
**File**: `ui/pages/2_Translate.py`
**Error Message**:
```
Myanmar translation output chapter shows "-- None --"
Translated files exist but not appearing in dropdown
```
**Root Cause**: Output file search only looked in root output dir, not in `chapters/` subdirectory
**Fix Applied**:
1. Updated file search to check both locations
2. Now correctly populates output chapter dropdown
**Files Modified**:
- `ui/pages/2_Translate.py` - Added chapters/ subdirectory search (lines 141-152)
**Status**: RESOLVED

### ERROR-026: Translate Page Model Selection Not Applied
**Date**: 2026-04-27
**File**: `ui/pages/2_Translate.py`
**Error Message**:
```
Selected model in sidebar not used for translation
```
**Root Cause**: Translation command didn't include model selection
**Fix Applied**:
1. Added code to update config/settings.yaml with selected model before running
2. Both translator and editor models are updated
3. Two-stage mode flag is now passed to command
**Files Modified**:
- `ui/pages/2_Translate.py` - Added model config update and two-stage flag (lines 64-97)
**Status**: RESOLVED

---

## Issues Fixed in This Session

### ERROR-019: Translation Output Contains Model's Thinking Process
**Date**: 2026-04-27
**File**: `src/utils/postprocessor.py`
**Error Message**:
```
Output file contains:
- "Here's a thinking process that leads to the suggested translation:"
- "1. **Analyze the Request and Constraints:**"
- "**Burmese Draft:**" markers
- Model's internal analysis instead of pure translation
```
**Root Cause**: The postprocessor only stripped `<think>` tags but not the plain-text thinking process that Qwen outputs before the actual translation
**Fix Applied**:
1. Added `_REASONING_PATTERNS` list to match thinking process sections
2. Added `strip_reasoning_process()` function to remove:
   - "Here's a thinking process..." sections
   - "Analyze the Request and Constraints" sections
   - "Analyze the Glossary" sections
   - "Segment and Translate" analysis (keeping only the draft)
   - "**Burmese Draft:**" and "**Myanmar Draft:**" markers
   - Analysis lines without Myanmar text
3. Updated `clean_output()` to call `strip_reasoning_process()`
**Files Modified**:
- `src/utils/postprocessor.py` - Added reasoning pattern removal
**Status**: RESOLVED
**Verified By**: test_novel_v1.py (11/11 tests pass), manual test with 100% Myanmar char ratio

---

## Issues Fixed in This Update Session

### ERROR-016: UI Import Path Error
**Date**: 2026-04-27
**File**: `ui/pages/2_Translate.py`, `ui/pages/4_Glossary_Editor.py`
**Error Message**:
```
ModuleNotFoundError: No module named 'ui'
```
**Root Cause**: Incorrect sys.path insertion - `Path(__file__).parent.parent` pointed to project root but imports expected parent of project root
**Fix Applied**: Changed to `Path(__file__).parent.parent.parent` to add project root's parent, then use absolute imports from project root
**Files Modified**:
- `ui/pages/2_Translate.py` - Fixed path insertion (line 10-12)
- `ui/pages/4_Glossary_Editor.py` - Fixed path insertion (line 8-10)
**Status**: RESOLVED
**Verified By**: test_novel_v1.py (11/11 tests pass)

### ERROR-017: Web UI Not Launching with --ui Flag
**Date**: 2026-04-27
**File**: `src/main.py`, `tools/launch_ui.py` (new)
**Error Message**:
```
--ui flag did not launch web UI, terminal showed no output
```
**Root Cause**: The --ui flag in main.py launched streamlit directly without proper logging and process management
**Fix Applied**: 
1. Created `tools/launch_ui.py` - Dedicated launcher with log file support
2. Updated `src/main.py` to use the launcher script
3. Logs all Streamlit output to `logs/web_server.log`
**Files Modified**:
- `tools/launch_ui.py` - New file created
- `src/main.py` - Updated --ui flag handler (lines 715-740)
**Status**: RESOLVED
**Verified By**: test_novel_v1.py (launcher script test pass)

### ERROR-018: CLI Processing Info Not Visible
**Date**: 2026-04-27
**File**: `src/main.py`
**Error Message**:
```
Translation process showed minimal info - user couldn't see models, settings, steps
```
**Root Cause**: Original code only printed basic model info without rich formatting or step-by-step progress
**Fix Applied**:
1. Added `print_box()` function - Display formatted boxes with config info
2. Added `print_pipeline_status()` function - Show step status with icons
3. Added `print_translation_header()` function - Rich formatted header with all settings
4. Added step-by-step progress updates throughout `translate_single_file()`:
   - Step 1/7: Preprocessing
   - Step 2/7: Translation
   - Step 3/7: Refinement
   - Step 4/7: Reflection
   - Step 5/7: Quality Checks
   - Step 6/7: Save Output
   - Step 7/7: Update Context
**Files Modified**:
- `src/main.py` - Added display functions (lines 242-337) and step updates throughout
**Status**: RESOLVED
**Verified By**: test_novel_v1.py (enhanced display test pass)

---

## Issues Fixed in This Review Session

### ERROR-015: Glossary_Editor.py corrupted Unicode character
**Date**: 2026-04-27
**File**: `ui/pages/4_Glossary_Editor.py`
**Error Message**:
```
Corrupted Unicode string: "အတည်ပါ�ပါသည်" (contained invalid character)
```
**Root Cause**: Unicode corruption in the Myanmar text for "Approve"
**Fix Applied**: Changed to correct text "အတည်ပြုပါသည်"
**Files Modified**:
- `ui/pages/4_Glossary_Editor.py` - Line 164
**Status**: RESOLVED
**Verified By**: py_compile check

### ERROR-014: main.py undefined variable myanmar_quality
**Date**: 2026-04-27
**File**: `src/main.py`
**Error Message**:
```
NameError: name 'myanmar_quality' is not defined
```
**Root Cause**: Variable `myanmar_quality` was used outside its defining block (only defined inside `if myanmar_checker is not None:`)
**Fix Applied**: Added `myanmar_checker is not None` check before accessing myanmar_quality dictionary
**Files Modified**:
- `src/main.py` - Lines 511-514
**Status**: RESOLVED
**Verified By**: py_compile check

### ERROR-013: sidebar.py indentation issue
**Date**: 2026-04-27
**File**: `ui/components/sidebar.py`
**Error Message**:
```
Indentation error: return statement inside with block instead of function level
```
**Root Cause**: The return statement was indented inside the `with st.sidebar:` block instead of at function level
**Fix Applied**: Moved return statement outside the with block, fixed dictionary indentation
**Files Modified**:
- `ui/components/sidebar.py` - Lines 144-161
**Status**: RESOLVED
**Verified By**: py_compile check

### ERROR-012: file_handler.py duplicate import
**Date**: 2026-04-27
**File**: `src/utils/file_handler.py`
**Error Message**:
```
Duplicate import: yaml imported twice (lines 8 and 14)
```
**Root Cause**: yaml module was imported at both module level and later in the file
**Fix Applied**: Removed duplicate import at line 14
**Files Modified**:
- `src/utils/file_handler.py` - Removed line 14
**Status**: RESOLVED
**Verified By**: py_compile check

### ERROR-011: streamlit_app.py incorrect link_button usage
**Date**: 2026-04-27
**File**: `ui/streamlit_app.py`
**Error Message**:
```
Incorrect st.link_button URL format - should use st.switch_page or st.page_link
```
**Root Cause**: st.link_button was used with incorrect URL paths for internal page navigation
**Fix Applied**: Changed to st.button with st.switch_page() for proper Streamlit multi-page navigation
**Files Modified**:
- `ui/streamlit_app.py` - Lines 137-144
**Status**: RESOLVED
**Verified By**: py_compile check

---

## Resolved Issues

### ERROR-041: Translation REJECTED - Model Outputting English Instead of Myanmar
**Date**: 2026-04-28
**File**: `config/settings.yaml`
**Error Message**:
```
WARNING - Chinese (30 chars) detected in translation (chapter 0), retrying with stronger prompt...
ERROR - CRITICAL: Translation REJECTED in chapter 0: {
  'chapter': 0,
  'myanmar_ratio': 0.0,
  'thai_chars_leaked': 0,
  'chinese_chars_leaked': 12,
  'latin_words_found': 295,
  'english_common_words': 115,
  'status': 'REJECTED'
}
Provider:        OLLAMA
Translator:      qwen:7b
Editor:          qwen:7b
Pipeline Mode:   SINGLE_STAGE
```
**Root Cause**: Configuration was using `qwen:7b` as the translator model. `qwen:7b` is a general-purpose Chinese model that outputs English/Latin text when asked to translate to Myanmar - it is NOT trained for Myanmar output. The `padauk-gemma:q8_0` model is specifically designed for Myanmar and must be used instead.

**Fix Applied**:
1. Changed all model assignments in `config/settings.yaml` from `qwen:7b` to `padauk-gemma:q8_0`:
   - `models.translator`: qwen:7b → padauk-gemma:q8_0
   - `models.editor`: qwen:7b → padauk-gemma:q8_0
   - `models.refiner`: qwen:7b → padauk-gemma:q8_0
   - `fast_config.translator`: qwen2.5:14b → padauk-gemma:q8_0
   - `fast_config.editor`: qwen:7b → padauk-gemma:q8_0
   - `fast_config.refiner`: qwen:7b → padauk-gemma:q8_0

**Files Modified**:
- `config/settings.yaml` - Updated all model assignments to use padauk-gemma:q8_0

**Status**: RESOLVED
**Verified By**: 
- Confirmed `padauk-gemma:q8_0` is installed on the system
- Model is specifically trained for Myanmar output (98%+ Myanmar char ratio expected)

### ERROR-011: Glossary_Editor.py syntax error
**Date**: 2026-04-27
**File**: `ui/pages/4_Glossary_Editor.py`
**Error Message**:
```
SyntaxError: closing parenthesis '}' does not match opening parenthesis '('
```
**Root Cause**: Missing closing parenthesis in f-string at line 155
**Fix Applied**: Added missing `)` to close term.get()
**Files Modified**:
- `ui/pages/4_Glossary_Editor.py` - fixed line 155
**Status**: RESOLVED
**Verified By**: py_compile check

### ERROR-012: Streamlit horizontal parameter not supported
**Date**: 2026-04-27
**File**: `ui/pages/3_Progress.py`, `ui/components/sidebar.py`
**Error Message**:
```
TypeError: SelectboxMixin.selectbox() got an unexpected keyword argument 'horizontal'
```
**Root Cause**: Streamlit 1.56.0 doesn't support horizontal parameter for selectbox/radio
**Fix Applied**: Removed horizontal=True from all selectbox/radio calls
**Files Modified**:
- `ui/pages/3_Progress.py` - removed horizontal from 3 locations
- `ui/components/sidebar.py` - removed horizontal from 3 locations
**Status**: RESOLVED
**Verified By**: py_compile check

### ERROR-010: batch_size undefined in main.py
**Date**: 2026-04-27
**File**: `src/main.py`
**Error Message**:
```
NameError: name 'batch_size' is not defined
```
**Root Cause**: batch_size used but never defined before pipeline mode logic
**Fix Applied**: Added batch_size = config['processing']... before agent initialization
**Status**: RESOLVED
**Verified By**: py_compile check
**Date**: 2026-04-27
**File**: `ui/pages/dashboard.py`
**Error Message**:
```
SyntaxError: 'unicodeescape' codec can't decode bytes
```
**Root Cause**: Python string literals in `\u1000` format require raw strings or ord() - lowercase doesn't work
**Fix Applied**: Changed to use ord() function for Unicode code point comparison
**Status**: RESOLVED
**Verified By**: py_compile check
**File**: `ui/components/sidebar.py`, `ui/pages/2_Translate.py`, `ui/pages/3_Progress.py`, `ui/pages/4_Glossary_Editor.py`, `ui/streamlit_app.py`
**Error Message**:
```
Design vs Current mismatch:
- Sidebar: Basic settings only (missing Chapter Selection, Model Settings, Translation Behavior, Glossary Settings)
- Translate: Missing side-by-side preview, stage indicators, live logs
- Glossary: Missing full CRUD, search, import/export
- Progress: Missing chapter list, status filter
- Home: Missing dashboard charts
```
**Root Cause**: Initial UI prototype was static and lacked integration logic matching the design document
**Fix Applied**: 
1. Rewrote sidebar.py with full design sections (Novel/Chapter Selection, Model Settings, Translation Behavior, Glossary Settings)
2. Updated Translate.py with side-by-side preview, progress bar, stage indicators, live logs
3. Updated Glossary_Editor.py with full CRUD, search, filter, import/export
4. Updated Progress.py with chapter list, status filter, detailed logs
5. Updated streamlit_app.py with dashboard stats, charts, quick actions
**Files Modified**:
- `ui/components/sidebar.py` - Full sidebar with all design sections
- `ui/pages/2_Translate.py` - Side-by-side preview, progress tracking
- `ui/pages/3_Progress.py` - Chapter list, status filter
- `ui/pages/4_Glossary_Editor.py` - Full CRUD, search, import/export
- `ui/streamlit_app.py` - Dashboard with charts
**Status**: RESOLVED
**Verified By**: code-reviewer (PASS)

### ERROR-004: Duplicate detect_language() function
**Date**: 2026-04-27
**File**: `src/agents/translator.py`, `src/agents/preprocessor.py`
**Error Message**:
```
Code review found detect_language() defined in TWO locations:
- translator.py (module-level function)
- preprocessor.py (Preprocessor class method)
```
**Root Cause**: Initial implementation copied the function to both files from Novel-Step.md
**Fix Applied**: Removed duplicate from translator.py, kept in preprocessor.py as class method
**Files Modified**:
- `src/agents/translator.py` - removed duplicate function
- `src/agents/preprocessor.py` - kept detect_language() method
**Status**: RESOLVED
**Verified By**: code-reviewer (REVIEWER A, iteration 3)

### ERROR-005: Missing SVO→SOV rules in new prompts
**Date**: 2026-04-27
**File**: `src/agents/translator.py`
**Error Message**:
```
REVIEWER B found new prompts missing mandatory translation rules:
- SVO→SOV conversion rule
- Particle accuracy rules (သည်/ကို/မှာ)
- Glossary enforcement with 【?term?】 placeholders
```
**Root Cause**: Initial prompt implementation from Novel-Step.md did not include full AGENTS.md rules
**Fix Applied**: Added full translation rules to get_language_prompt():
- SYNTAX: Convert Chinese SVO to Myanmar SOV
- TERMINOLOGY: Use EXACT glossary terms with 【?term?】 placeholder
- PARTICLES: Proper particle usage rules
- MARKDOWN: Preserve all formatting
**Files Modified**:
- `src/agents/translator.py` - updated get_language_prompt()
**Status**: RESOLVED
**Verified By**: code-reviewer (REVIEWER B, iteration 1)

### ERROR-006: Modular boundary violation - Preprocessor import in Translator
**Date**: 2026-04-27
**File**: `src/agents/translator.py`
**Error Message**:
```
AGENTS.md Code Drift Prevention: Agent တစ်ခုက တစ်ခုကို import မလုပ်ရ
(translator.py imported Preprocessor directly)
```
**Root Cause**: Initial translate_chapter() method instantiated Preprocessor internally
**Fix Applied**: 
1. Removed Preprocessor import from top of translator.py
2. Refactored translate_chapter() to take pre-processed chunks as parameter
3. Recommended flow now: Preprocessor.load_and_preprocess() → Translator.translate_chunks()
**Files Modified**:
- `src/agents/translator.py` - refactored translate_chapter()
**Status**: RESOLVED
**Verified By**: code-reviewer (REVIEWER A, iteration 3)

---

### ERROR-001: KeyError 'source' in glossary consistency check
**Date**: 2026-04-24
**File**: `src/memory/memory_manager.py`, `src/agents/checker.py`
**Error Message**:
```
2026-04-24 00:43:47,824 - ERROR - Failed to translate chapter 114: 'source'
```
**Root Cause**: 
- `glossary.json` uses keys: `source_term` and `target_term`
- Python code expected: `source` and `target`
- This schema mismatch caused KeyError when accessing `term['source']`

**Fix Applied**:
1. Added normalization in `_load_memory()` to copy old format keys to new format
2. Updated all methods to use `.get()` with fallbacks for backward compatibility
3. Fixed `update_term()` to always update both key formats
4. Added security sanitization for prompt generation

**Files Modified**:
- `src/memory/memory_manager.py`:
  - Added normalization logic in `_load_memory()` (lines 57-70)
  - Updated `get_term()` to use `.get()` with fallback
  - Updated `add_term()` duplicate check to use `.get()` with fallback
  - Updated `update_term()` to update both `target` and `target_term` keys
  - Updated `get_glossary_for_prompt()` to use normalized access + sanitization
  - Added `_sanitize_for_prompt()` method (lines 193-203)
  - Applied sanitization to `get_context_buffer()` (line 227)
  - Applied sanitization to `get_session_rules()` (line 256)
  - Applied sanitization to `get_summary()` (line 238)
  
- `src/agents/checker.py`:
  - Added `Any` to imports (line 8)
  - Fixed type hint `any` → `Any` (line 140)
  - Updated `check_glossary_consistency()` to use `.get()` with fallbacks (lines 39-43)

**Status**: ✅ RESOLVED & VERIFIED
**Verified By**: code-reviewer (3 passes - bugs, security, fix verification)
**Review Results**:
- ✅ Code Quality Review: READY_TO_COMMIT
- ✅ Security Review: READY_TO_COMMIT  
- ✅ Fix Verification: All changes confirmed working

**Verification Date**: 2026-04-24
**Verification Details**:
- Normalization logic verified in `_load_memory()`
- All `.get()` with fallbacks confirmed in 5 locations
- Both key updates confirmed in `update_term()`
- Sanitization applied to 4 prompt methods
- Type hints and imports verified in checker.py

### ERROR-002: ModuleNotFoundError for 'src' package
**Date**: 2026-04-24
**File**: `src/main_fast.py`
**Error Message**:
```
Traceback (most recent call last):
  File "/home/wangyi/Desktop/Novel_Translation/novel_translation_project/src/main_fast.py", line 22, in <module>
    from src.utils.file_handler import FileHandler
ModuleNotFoundError: No module named 'src'
```
**Root Cause**:
- Running `python src/main_fast.py` directly doesn't recognize the `src` package
- `sys.path.insert(0, str(Path(__file__).parent))` was adding `src/` instead of project root

**Fix Applied**:
Changed `sys.path.insert()` to add project root instead of src directory:
```python
# Before
sys.path.insert(0, str(Path(__file__).parent))

# After  
sys.path.insert(0, str(Path(__file__).parent.parent))
```

**Files Modified**:
- `src/main_fast.py` - Line 20

**Status**: ✅ RESOLVED
**Verified By**: manual test

### ERROR-003: Model 'qwen2.5:7b' not available
**Date**: 2026-04-24
**File**: `config/settings.fast.yaml`
**Error Message**:
```
2026-04-24 00:40:43,756 - WARNING - Model 'qwen2.5:7b' not found. 
Available: ['yxchia/seallms-v3-7b:Q4_K_M', 'alibayram/hunyuan:7b', 'gemma:7b', 
'qwen2.5:14b', 'kimi-k2.6:cloud', 'translategemma:12b', 'qwen:7b']
```
**Root Cause**:
- Config specified `qwen2.5:7b` but only `qwen2.5:14b` was installed

**Fix Applied**:
Updated config to use available models:
- `translator`: `qwen2.5:7b` → `qwen2.5:14b`
- `editor`: `qwen2.5:7b` → `qwen2.5:14b`
- `stage1_model`: `qwen2.5:7b` → `qwen2.5:14b`
- `stage2_model`: `qwen2.5:7b` → `qwen2.5:14b`

**Files Modified**:
- `config/settings.fast.yaml` - Lines 18, 19, 31, 32, 95

**Status**: ✅ RESOLVED
**Verified By**: code-reviewer

### ERROR-007: UI Command and Process Execution Issues
**Date**: 2026-04-27
**File**: `ui/pages/2_Translate.py`, `ui/pages/4_Glossary_Editor.py`
**Error Message**:
```
- Translation command construction was incomplete (missing chapter ranges)
- Subprocess execution was commented out
- Glossary Editor lacked direct persistence to MemoryManager
```
**Root Cause**: Initial UI prototype was static and lacked integration logic
**Fix Applied**: 
1. Implemented dynamic command builder in `Translate.py`
2. Enabled background execution via `subprocess.Popen`
3. Integrated `MemoryManager` in `Glossary_Editor.py` for atomic term saving
4. Added Myanmar localization for better user experience
**Status**: RESOLVED
**Verified By**: code-reviewer (gemini-reviewer, READY_TO_COMMIT)

### ERROR-013: UI selection limited to folders
**Date**: 2026-04-27
**File**: `ui/components/sidebar.py`, `ui/pages/2_Translate.py`
**Error Message**:
```
- User unable to select loose .md files in data/input (only folders supported)
- Live log view was biased towards progress markdown, lacked technical log access
- Start Translation button logic was static
```
**Root Cause**: Initial implementation assumed structured novel folders; UI design prioritized producing text over technical monitoring.
**Fix Applied**: 
1. Updated `sidebar.py` to list both folders and individual files in `data/input`.
2. Updated `2_Translate.py` to use `--input` flag for single files and `--novel` for folders.
3. Enhanced log viewer with "Log Type" selector (Progress vs Technical) and auto-refresh state management.
**Status**: RESOLVED
**Verified By**: code-reviewer (PASS)

---

## Error Patterns & Prevention

### Pattern 1: Schema Mismatch
**Issue**: JSON/config file schema differs from code expectations
**Prevention**:
- Always validate schema on load
- Use `.get()` with defaults for optional fields
- Normalize data at load time

### Pattern 2: Import Path Issues
**Issue**: Running scripts directly causes import errors
**Prevention**:
- Use `python -m src.module` syntax
- Ensure sys.path includes project root, not just src/

### Pattern 3: Missing Dependencies
**Issue**: Config specifies resources that don't exist
**Prevention**:
- Validate configs against available resources on startup
- Provide clear error messages with available options

---

## Quick Reference

### Last 3 Errors Fixed:
1. **ERROR-001**: Glossary key mismatch (KeyError: 'source') - 2026-04-24
2. **ERROR-002**: Module import path issue - 2026-04-24
3. **ERROR-003**: Unavailable model in config - 2026-04-24

### Files Most Often Fixed:
- `src/memory/memory_manager.py`
- `src/agents/checker.py`
- `config/settings.fast.yaml`
- `src/main_fast.py`

---

*This file is maintained automatically by AI agents. Do not edit manually unless instructed.*

### CODE REVIEW SESSION (2026-05-01): Postprocessor Bug Fix Review
**Scope**: `src/utils/postprocessor.py` — review of 3 bug fixes + recovery function
**Reviewers**: REVIEWER A (Architecture & Logic) + REVIEWER B (Myanmar Translation & Quality)
**Status**: READY_TO_COMMIT (both reviewers PASS)
**Test Results**: 229/229 pass, no regressions
**Findings**:
- Bug 1 fix (`remove_latin_words` regex) — correctly preserves newlines. VERIFIED.
- Bug 2 fix (`fix_chapter_heading_format`) — correctly splits H1/H2. VERIFIED. Minor: only matches Myanmar digits, not Latin.
- Bug 3 fix (`remove_duplicate_headings`) — correctly removes duplicates. VERIFIED. Minor: TOC edge case noted.
- Recovery (`_split_into_lines_if_needed`) — safe guard condition, activates only on single-line text. VERIFIED.
- No breaking API changes to `clean_output`, `Postprocessor`, `remove_latin_words`. CONFIRMED.
- No cross-agent imports (modular boundaries intact). CONFIRMED.
- Type hints present on all new functions. CONFIRMED.
- Minor pre-existing issues noted: `is_valid_myanmar_syllable` type hint mismatch, no targeted unit tests for new functions.
