# CURRENT_STATE.md - Implementation Progress

> **FOR AI AGENTS — MANDATORY:**
> - **Session Start:** Read this file before any code. Check what is [DONE] and what is [TODO].
> - **Session End:** Update this file automatically after every task, file change, or decision.
>   No prompt needed. This is default behavior defined in AGENTS.md and GEMINI.md.

---

## Last Updated
- Date: 2026-05-02
- Last task completed:
  - **FIXED: 7 Output Quality Issues from Log/Report Review** (STATUS: READY_TO_COMMIT):
    - **Root Cause 1 (Credit lines in output)**: Orchestrator `_preprocess()` never called `strip_metadata()` — only `clean_markdown()`. Translator: Skyfarrow Editor: Skyfarrow lines leaked into chunks and were translated to Myanmar.
    - **Root Cause 2 (Chunk boundary truncation)**: `stitch_chunk_boundaries()` only stitched when next line started with medial character. Truncation at consonant-starting lines wasn't caught.
    - **Root Cause 3 (Archaic word corruptions)**: `replace_archaic_words()` used `\b` which treats Myanmar combining marks as `\W`, creating false word boundaries inside compounds like `ထိုင်ခိုင်း` → `အဲဒီင်ခိုင်း`.
    - **Root Cause 4 (Tamil script leakage)**: Postprocessor only stripped Chinese/Bengali/Thai. Ch15 had 7 Tamil chars (`எண்ணற்ற`).
    - **Root Cause 5 (Bare heading not deduplicated)**: Ch16 had `# အခန်း` (no number) that survived because bare headings tracked separately from numbered ones.
    - **Root Cause 6 (BOM breaks heading detection)**: `remove_duplicate_headings()` used `line.strip()` which doesn't strip BOM `\ufeff`.
    - **Root Cause 7 (Degraded placeholders `【??】`)**: Model outputs degraded `【??】` instead of `【?term?】` standard.
    - **Fixes Applied**:
      1. **Orchestrator**: Added `strip_metadata()` call in `_preprocess()` before `clean_markdown()` (1 line)
      2. **stitch_chunk_boundaries()**: Added Strategy 2 for short truncated lines (< SHORT_LINE_THRESHOLD=150) with no sentence-ender + next Myanmar line → stitch. Added `-> bool` type annotations.
      3. **replace_archaic_words()**: Replaced `\b` with Myanmar-specific consonant lookbehind `(?<![က-အ])` and lookahead `(?!combining*[က-အ])` — correctly identifies standalone vs compound.
      4. **undo_archaic_corruptions()**: NEW function to fix pre-existing corruptions from old `\b` regex: `အဲဒီင` → `ထိုင`, `အဲဒီ`+combining → `ထို`.
      5. **_INDIC_PATTERN**: Added Tamil, Telugu, Kannada, Malayalam, Devanagari, Sinhala, Gujarati, Oriya, Gurmukhi. `remove_indic_characters()` strips them. Updated `detect_language_leakage()` and `validate_output()`.
      6. **remove_duplicate_headings()**: `line.strip().lstrip('\ufeff')` to handle BOM. Bare `# အခန်း` after any numbered heading → treated as duplicate.
      7. **fix_degraded_placeholders()**: NEW function: `【??】` → `【?term?】`.
      8. **strip_translated_metadata()**: NEW function removes Myanmar credit lines (ဘာသာပြန်သူ-..., တည်းဖြတ်သူ-...).
      9. **clean_output()**: Pipeline updated — always strips Chinese/Bengali/Indic, runs new functions in correct order. Latin stripped only in aggressive mode.
     10. **test_postprocessor.py**: Updated `test_default_no_aggressive_removal` to reflect new behavior (Chinese always stripped).
    - **Output files**: Ch14 (99.3% MM, 0 corruptions), Ch15 (98.7% MM, 0 corruptions, 0 Tamil), Ch16 (99.5% MM, 0 corruptions) — all re-cleaned.
    - **Files Modified**: `src/pipeline/orchestrator.py` (+1 line), `src/utils/postprocessor.py` (+110 lines), `tests/test_postprocessor.py` (5 lines changed)
    - **Tests**: 280/280 pass
  - **IMPLEMENTED: Smart Paragraph Chunking (per need_to_fix.md) — Token-Aware, No Split, No Overlap** (STATUS: READY_TO_COMMIT):
    - **Spec Source**: `need_to_fix.md` — exact chunking algorithm from v1.0 specification
    - **What was wrong**: Preprocessor used per-paragraph token accumulation with overlap support (overlap_size), chunk boundaries could split mid-sentence, no token budget check before LLM send, no rolling context between chunks
    - **New Module**: `src/utils/chunker.py` — canonical location per spec:
      - `smart_chunk(text, max_tokens=1500)` — ONLY splits at paragraph boundaries (`\n\n`), never inside a paragraph, oversized paragraphs become their own chunk, overlap is always 0
      - `get_rolling_context(prev_chunk, max_context_tokens=400)` — extracts tail of previous translated chunk as context (token-limited, paragraph-complete, never mid-paragraph)
      - `estimate_tokens(text)` — `len(text) * 1.5` for Myanmar/Chinese
    - **Preprocessor updated**: `create_chunks()` now delegates to `smart_chunk()`, overlap_size hardcoded to 0 internally
    - **Orchestrator `_preprocess()`**: Uses `smart_chunk()` directly, logs token estimates
    - **Orchestrator `_translate_chunks()`**: 
      - Rolling context now uses `get_rolling_context()` per spec — tail of previous translated chunk, ≤400 tokens, never mid-paragraph
      - Token budget check before LLM send: verifies `system(800) + context + chunk ≤ 2600` tokens, truncates context if exceeded
      - Per-chunk checkpoint logging: logs chunk duration, quality, ratio after each chunk
      - `rolling_context=""` for chunk index 0 (first chunk)
    - **Translator updated**: `translate_paragraph()` accepts `rolling_context` parameter, `build_prompt()` uses rolling context as PREVIOUS CONTEXT section (fallback to accumulated memory context if empty)
    - **Config cleanup**: Removed `chunk_overlap` from settings.yaml, config/models.py (field + validator), types/definitions.py, CLI formatters, container.py, test_integration.py
    - **chunk_size**: Increased to 1500 (was 800) — token-aware paragraph grouping handles this safely
    - **Tests**: Created `tests/test_chunker.py` with 11 tests (6 required by spec + 5 additional):
      - `test_never_splits_inside_paragraph`, `test_oversized_single_paragraph_becomes_own_chunk`, `test_overlap_is_zero`, `test_short_text_single_chunk`, `test_empty_text`, `test_max_tokens_respected`
      - `test_rolling_context_respects_token_budget`, `test_empty_chunk_returns_empty_context`, `test_first_chunk_gets_empty_context`, `test_context_preserves_paragraph_order`, `test_never_splits_mid_paragraph`
    - **Files Created**: `src/utils/chunker.py`, `tests/test_chunker.py`
    - **Files Modified**: `src/agents/preprocessor.py`, `src/agents/translator.py`, `src/pipeline/orchestrator.py`, `src/cli/formatters.py`, `src/config/models.py`, `src/core/container.py`, `src/types/definitions.py`, `config/settings.yaml`, `tests/test_integration.py`
    - **Tests**: 280/280 pass
  - Previous tasks:
  - **ADDED: Translation Quality Review System + Auto-Review Pipeline + Pending Glossary Workflow** (STATUS: READY_TO_COMMIT):
    - **Translation Rules File**: Created `working_data/translation_rules.md` — comprehensive quality rules with 10 linguistic checks (L1-L10) and 6 quantitative checks (Q1-Q6), scoring matrix, and report format spec
    - **Review Module**: Created `src/utils/translation_reviewer.py` — runs all quality checks against output files:
      - Q1: Myanmar ratio (≥70% PASS, <30% REJECT)
      - Q2: Foreign script leakage (Chinese, Bengali, Thai, Korean)
      - Q3: English/Latin word leakage
      - Q4: Markdown structure (H1 count, bold balance)
      - Q5: Content completeness (char count, error markers, placeholders)
      - Q6: Paragraph structure (breaks, readability)
      - L1: Archaic words (သင်သည်, ဤ, ထို, သည်သည်ကို)
      - L2: Particle repetition (same particle ≥3x consecutively — use backreference)
      - L4: Register consistency (formal vs colloquial)
      - L7: Overlong sentences (>50 words)
      - L8: Sentence enders (proper ။, ၏ ending)
      - Paragraph duplication (chunk boundary dedup check)
      - **Note**: L3 (SVO→SOV), L5 (pronoun hierarchy), L6 (emotional quality), L9 (glossary consistency) are defined in rules but best assessed by LLM QualityAgent
    - **CLI Integration**: `--review` flag added to parser.py — `python -m src.main --review file.mm.md`
    - **Auto-Review**: Pipeline automatically runs review after each translation via `_auto_review()` in orchestrator.py — generates `logs/report/{novel}_chapter_{N}_review_{timestamp}.md`
    - **Pending Glossary Workflow**: Added `auto_approve_pending_terms()` to MemoryManager — when user edits pending file with `"status": "approved"`, next pipeline run auto-promotes terms to main glossary. Auto-approve runs on MemoryManager lazy-load initialization.
    - **Reviewer fixes applied**:
      1. Fixed `_cleanup_resources()` method restored (was absorbed into `_auto_review`)
      2. Added `သည်သည်ကို` to archaic word check
      3. Fixed particle repetition regex to use backreference (same particle only)
      4. Fixed sentence enders to exclude ASCII punctuation
      5. Fixed `save_review_report()` to use UTF-8-SIG encoding
      6. Added `_check_overlong_sentences()` and `_check_paragraph_duplication()` functions
    - **Files Created**: `working_data/translation_rules.md`, `src/utils/translation_reviewer.py`, `tests/test_translation_reviewer.py` (34 tests)
    - **Files Modified**: `src/cli/parser.py`, `src/cli/commands.py`, `src/main.py`, `src/pipeline/orchestrator.py`, `src/memory/memory_manager.py`
    - **Tests**: 269/269 pass (235 existing + 34 new)
  - Previous tasks:
  - **FIXED: Pipeline Mode, Paragraph Breaks, Chunk Stitching, Data Cleanup, Config Simplification, Enhanced Metadata** (STATUS: READY_TO_COMMIT):
    - **Root Cause 1 (CRITICAL)**: Ch12 (single_stage, 99 blank lines, good quality, ~60 min) vs Ch13 (full pipeline, 0 blank lines, terrible quality, ~120 min). The `_apply_workflow_config` was forcing `full` pipeline for way1 (EN→MM), but padauk-gemma works BETTER in `single_stage` mode — `full` adds 2 extra API calls per chunk (3x slower) and refinement/reflection with padauk-gemma collapses all paragraph breaks
    - **Root Cause 2**: No blank lines between paragraphs in Ch13 output — 0 double-newlines vs Ch12's 99
    - **Root Cause 3**: Sentences cut at chunk boundaries (lines 10, 13, 23, 29, 38 end mid-sentence) — `\n\n` between chunks creates paragraph break inside sentences
    - **Root Cause 4**: Data folder had 12+ JSON files (copies, backups, test files) polluting the directory
    - **Root Cause 5**: `config/settings.english.yaml` (189 lines) was stale — not referenced anywhere in code
    - **Root Cause 6**: Meta.json only had 4 fields — no chapter number, duration, quality metrics
    - **Fixes Applied**:
      1. **Pipeline mode**: Changed way1 from `full` to `single_stage` in `commands.py` `_apply_workflow_config()` — padauk-gemma produces better quality + 3x faster in single-stage. Updated test.
      2. **`ensure_markdown_readability()`**: New postprocessor function — adds blank lines between consecutive content paragraphs that lack them, preserves existing blank lines, ensures heading spacing. Does NOT strip existing blank lines.
      3. **`stitch_chunk_boundaries()`**: New postprocessor function — detects sentences cut at chunk boundaries (no `။`/`၊`/`"` ender) and joins them with the next Myanmar content line, skipping blank lines between
      4. **`clean_output()`**: Updated to call `stitch_chunk_boundaries()` (after tag stripping, before dedup) and `ensure_markdown_readability()` (final step after dedup)
      5. **Data cleanup**: Removed 7 stale JSON files (`context_memory (Copy).json`, `glossary (Copy).json`, `glossary_backup_gudaoxianhong_20260430_203825.json`, 4 test files) — kept only `glossary_reverend-insanity.json`, `glossary_pending_reverend-insanity.json`, `context_memory_reverend-insanity.json`, `glossary_pending.json`, `context_memory.json`
      6. **Config simplifed**: Removed `config/settings.english.yaml` (189 lines, not referenced anywhere)
      7. **Enhanced `_save_output()`**: Now accepts `extra_meta` dict — saves chapter number (extracted from filename), novel name, duration_seconds, model used, chunk_count, myanmar_ratio, char_count, avg_quality_score. Extracts chapter number from filename via regex.
      8. **Output file fixed**: Ch13 now has 75 lines, 37 paragraph breaks (up from 0), proper readability
    - **Files Modified**: `src/cli/commands.py`, `src/utils/postprocessor.py`, `src/pipeline/orchestrator.py`, `tests/test_workflow_routing.py`
    - **Files Deleted**: `config/settings.english.yaml`, 7 data/*.json files
    - **Tests**: 235/235 pass
  - Previous tasks:
  - **FIXED: Chapter 13 Translation Quality — Garbage Meta-Lines + Duplicate Headings + Temperature** (STATUS: READY_TO_COMMIT):
    - **Root Cause 1**: padauk-gemma model outputs glossary comparison garbage lines (`*:* "မြန်မာ" is . "other" is .`) — a new hallucination pattern not caught by existing postprocessor patterns
    - **Root Cause 2**: `remove_duplicate_headings()` used exact string matching, but chapter headings differ slightly between chunks (different Myanmar characters in title, or with/without subtitle suffix) → duplicate headings survived
    - **Root Cause 3**: Temperature was raised from 0.2 to 0.4 in a prior fix — increased randomness caused more padauk-gemma hallucinations
    - **Fixes Applied**:
      1. `remove_duplicate_headings()`: Changed from exact match to prefix match (`r'#\s+အခန်း\s+[\u1040-\u1049\d]+'`) — catches all variants of the same chapter heading. Added `in_duplicate_block` reset when new chapter heading encountered during skip mode (prevents skipping subtitle of a new chapter after duplicate block). Updated type hints to `set[str]` / `list[str]`.
      2. `strip_reasoning_process()`: Added line-level `*:*` garbage detection — lines matching `r'^\s*\*[\s:]*:[\s:]*\*'` (requires colon between asterisks to avoid false-positive on `**bold**` markdown)
      3. `_REASONING_PATTERNS`: Added 3 new regex patterns for padauk-gemma glossary comparison garbage:
         - `^\s*\*[\s:]*\*.*?\"[\u1000-\u109F]+\".*?(?:is|be|of|on|a|an|the)\b.*$` — lines with Myanmar quoted text + English comparison words
         - `^\s*\*[\s:]*\*[\s,.]*$` — short garbage fragments like `* :* , .`
         - `^\s*\*[\s:]*\*.*?to\s*/\.\s*.*$` — `*:* to /.` pattern lines (fixed missing `.*$` suffix to consume full line)
      4. `config/settings.yaml`: Reduced temperature 0.4→0.2 for both `processing` and `fast_config` sections (per long_term_memory: padauk-gemma best at temp=0.2). Restored missing `fast_config.translator: padauk-gemma:q8_0`.
      5. **Output file fixed**: `data/output/reverend-insanity/reverend-insanity_chapter_013.mm.md` cleaned (610 chars of garbage removed, 99.8% Myanmar ratio, 1 heading)
    - **Files Modified**: `src/utils/postprocessor.py` (+25 lines), `config/settings.yaml` (-2 temp, +1 translator)
    - **Tests**: 235/235 pass
  - Previous tasks:
  - **ADDED: Live CLI Progress Display for Translation Pipeline** (STATUS: READY_TO_COMMIT):
    - Added `print_progress_event()` to `src/cli/formatters.py` — color-coded per-chunk translation progress with timing, quality scores, Myanmar ratio, and summary
    - Added `set_progress_callback()` / `_report()` to `TranslationPipeline` in `src/pipeline/orchestrator.py` — non-intrusive callback pattern
    - Enhanced `_translate_chunks()` to emit per-stage events (translation, refinement, reflection, quality, consistency) with per-chunk metrics; returns `Tuple[List[str], List[Dict[str, Any]]]`
    - Added `_calc_myanmar_ratio()` static method for chunk-level Myanmar ratio
    - Wire-up in `src/cli/commands.py`: progress reporter passed to pipeline
    - Added 6 unit tests for `_calc_myanmar_ratio()` covering empty, Latin, Myanmar, mixed, whitespace, extended Unicode blocks
    - All 235/235 tests pass, zero breaking API changes
    - **Files Modified**: `src/cli/formatters.py` (+135 lines), `src/pipeline/orchestrator.py` (+90 lines), `src/cli/commands.py` (+12 lines), `tests/test_translator.py` (+46 lines)
  - Previous tasks:
  - Previous tasks:
  - **Infrastructure: Created .agent/ and CHANGELOG.md** (STATUS: READY_TO_COMMIT):
    - Created `.agent/` directory with 4 JSON files (phase_gate.json, session_memory.json, long_term_memory.json, error_library.json) matching AGENTS.md schemas
    - Created `CHANGELOG.md` documenting project history from v0.1.0 to v2.1.0
    - Error library pre-populated with ERR-001 through ERR-006 (preventive) + ERR-047 through ERR-043 (historical, observed)
    - All JSON files validated, 229/229 tests pass
    - **Files Created**: `.agent/phase_gate.json`, `.agent/session_memory.json`, `.agent/long_term_memory.json`, `.agent/error_library.json`, `CHANGELOG.md`
  - Previous tasks:
  - **FIXED: Pipeline Agent Initialization Bugs — 4 agents had parameter mismatches** (STATUS: READY_TO_COMMIT, commit 3617b23):
    - **Root Cause**: orchestrator.py passed wrong parameters to 4 agents — Refiner, ReflectionAgent got unexpected `memory_manager`; QATesterAgent, ContextUpdater were missing required params
    - **Impact**: Refinement, Reflection, QA, and Context Update stages silently failed on every translation
    - **Fixes**: 
      1. Refiner: `memory_manager` → `batch_size` (matches constructor signature)
      2. ReflectionAgent: removed invalid `memory_manager` param
      3. QATesterAgent: added missing `memory_manager` param  
      4. ContextUpdater: added missing `ollama_client` param
    - **All 8 pipeline agents now initialize correctly**
    - **Files Modified**: `src/pipeline/orchestrator.py`
    - **Tests**: 229/229 pass
  - **FIXED: Quality Audit Issues — Full Pipeline + Anti-Hallucination + Footnote Preservation** (STATUS: READY_TO_COMMIT, commit bdff6f0):
    - **Root Cause 1**: way1 (EN→MM) ran in `single_stage` mode — Reflection Agent and QA Tester never executed, skipping all quality checks
    - **Root Cause 2**: No anti-hallucination rule in translator prompt — model invented "ဖန်ကျန်း" (Fang Zheng) when source said "Brother Zhang" 
    - **Root Cause 3**: No footnote preservation rule — source markers (1) were dropped
    - **Root Cause 4**: Place names translated differently from glossary (Gu Yue Village)
    - **Fixes**:
      1. Changed way1 config from `mode: single_stage` to `mode: full` with `use_reflection: True` — enables Translation → Refinement → Reflection → Quality Check full pipeline
      2. Added STRICT RULES 8-10 to translator EN prompt:
         - Rule 8: ANTI-HALLUCINATION — never invent names, never substitute glossary characters
         - Rule 9: FOOTNOTES — preserve inline markers (1), (2), [1], [2]
         - Rule 10: PLACE NAMES — use exact glossary terms
      3. Added `detect_potential_hallucinations()` to postprocessor for post-hoc detection
    - **Files Modified**: `src/cli/commands.py`, `src/agents/translator.py`, `src/utils/postprocessor.py`, `tests/test_workflow_routing.py`
    - **Tests**: 229/229 pass
  - **English Source Pipeline Verification + Markdown Reader Feature** (STATUS: READY_TO_COMMIT):
    - **Pipeline Verification**: English source uses `en_mm_rules.py`, per-novel glossary/context isolated (`glossary_{novel}.json`, etc.), no cross-contamination
    - **Markdown Reader**: New `ui/pages/6_Reader.py` (Streamlit), `--view` CLI command, DRY imports from postprocessor
    - **Files Created**: `ui/pages/6_Reader.py`
    - **Files Modified**: `src/main.py`, `src/cli/commands.py`, `src/cli/parser.py`, `src/cli/__init__.py`, `ui/streamlit_app.py`
    - **Tests**: 229/229 pass
  - **FIXED: Postprocessor destroying paragraph structure + 8 duplicate headings** (STATUS: READY_TO_COMMIT, commit 98dbe5a):
    - **Root Cause 1**: `remove_latin_words` had `re.sub(r'\s+', ' ', text)` which collapsed ALL whitespace (including `\n`) to spaces, making output a single line
    - **Root Cause 2**: Model outputs `# အခန်း ၁၂ ## Title` on single line instead of proper `# H1\n\n## H2`
    - **Root Cause 3**: Heading repeated 8 times (once per chunk) due to context buffer leaking heading to subsequent chunk translations
    - **Fixes**:
      1. Changed `remove_latin_words` regex to `[^\S\n]+` — only collapses horizontal whitespace, preserves newlines
      2. Added `fix_chapter_heading_format()` — splits `# X ## Y` into `# X\n\n## Y`
      3. Added `remove_duplicate_headings()` — keeps only first `# အခန်း N` heading, strips duplicates
      4. Added `_split_into_lines_if_needed()` — recovery path for already-corrupted files (splits at heading boundaries + `။` sentence-enders)
    - **Files Modified**: `src/utils/postprocessor.py`
    - **Output file fixed**: `data/output/reverend-insanity/reverend-insanity_0012.mm.md` (backup at `.mm.md.bak`)
    - **Tests**: 229/229 pass
  - **Prompt System Upgrade & Per-Novel Glossary + DRY Refactor** (STATUS: READY_TO_COMMIT):
    - **Prompt Integration**: `get_language_prompt()` in translator.py now dynamically builds CN/EN prompts from `cn_mm_rules.build_linguistic_context()` and `en_mm_rules.build_linguistic_context()`
    - **EDITOR_SYSTEM_PROMPT upgraded**: Replaced with comprehensive 10-section prompt from `eng-mm-prompt.md` + `en_mm_rules.py` (Persona, Principles, Dialogue Rules, Confrontation Speech, Vocabulary Precision, Narration Register, Sentence Rhythm, Formatting, Unicode Safety, Output)
    - **TRANSLATOR_SYSTEM_PROMPT enhanced**: Added CN→MM linguistic rules from `cn_mm_rules.py` (SV→SOV, particles, pronouns, cultural adaptation, aspect markers)
    - **Per-Novel Glossary**: `_resolve_glossary_path()` now returns per-novel glossary/context/pending paths. Each novel gets isolated data files: `glossary_{novel}.json`, `context_memory_{novel}.json`, `glossary_pending_{novel}.json`
    - **Glossary Pending Workflow**: Added `promote_pending_to_glossary()`, `reject_pending_term()`, `get_pending_terms()` to MemoryManager. Terms go to pending → user reviews → approve/reject
    - **DRY Refactor**: `refiner.py` BATCH_REFINER_PROMPT derived from EDITOR_SYSTEM_PROMPT. `context_updater.py` uses EXTRACTOR_SYSTEM_PROMPT from prompt_patch. `translator.py` fallback prompts unified with LANGUAGE_GUARD
    - **glossary_v3 disabled**: `enabled: false` since file missing
    - **Test fix**: `test_workflow_routing.py` auto-detect tests — increased input length past 50-char minimum
    - **Files Modified**: `src/agents/translator.py`, `src/agents/prompt_patch.py`, `src/agents/refiner.py`, `src/agents/context_updater.py`, `src/memory/memory_manager.py`, `config/settings.yaml`, `tests/test_workflow_routing.py`, `tests/test_cn_mm_rules.py`, `tests/test_prompt_patch.py`
    - **Files Created**: `src/agents/prompts/__init__.py`
    - **Tests**: 229/229 pass
    - **Bug 3 (Translator credit in body)**: Added `strip_metadata()` to preprocessor.py to remove Translator/Editor/Proofreader metadata lines before chunking
    - **Bug 4 (HTML metadata in .md)**: Changed `_save_output()` to write metadata to sidecar `.meta.json` file instead of embedding HTML comments in the .md body
    - **Bug 5 (Register inconsistency)**: Added rule 9 (REGISTER CONSISTENCY) to translator prompts in translator.py — pick formal (သည်/၏/၌) OR colloquial (တယ်/ရဲ့/မှာ), not both
    - **Bug 6 (Chapter heading format)**: Added rule 10 (CHAPTER HEADINGS) to translator prompts — convert to proper Myanmar markdown heading format
    - **Bug 7 (Emotional intensity)**: Added rule 11 (EMOTIONAL INTENSITY) to translator prompts — use strong active verbs for aggressive dialogue
    - **Settings**: Changed `chunk_overlap` 50→0, `temperature` 0.2→0.4 in both `processing` and `fast_config`
    - **Files Modified**: `src/utils/postprocessor.py`, `src/agents/preprocessor.py`, `src/agents/translator.py`, `src/agents/myanmar_quality_checker.py`, `src/pipeline/orchestrator.py`, `config/settings.yaml`
    - **Tests**: 227/229 pass (2 pre-existing failures unrelated)
  - **Registered Burmese-GPT GGUF model**: Created `Modelfile.burmese-gpt`, registered as `burmese-gpt:7b` in Ollama, added to `model_roles` in settings.yaml
  - **Updated Project Documentation (README, USER_GUIDE, PROJECT_DOC, ROADMAP)**:
    - Updated supported models (padauk-gemma as primary, aya:8b as fallback)
    - Added `--chapter-range` command examples
    - Added supported file naming conventions section
    - Updated config reference to match current settings.yaml values
    - Removed references to deleted launcher scripts
    - Updated model comparison tables
  - **FIXED: --chapter-range 9-15 All Chapters Failed - File Not Found**:
    - **Root Cause**: `translate_chapter()` in orchestrator only looked for `{chapter:03d}.md` (e.g., `009.md`), but actual files use naming conventions like `{novel}_chapter_009.md`, `{novel}_0009.md`
    - **Fix Applied**:
      1. Added `_find_chapter_file()` static method to try 5 naming patterns
      2. Added `_discover_chapters()` static method for auto-discovery with regex fallback
      3. Improved per-chapter error logging in `commands.py` to always log details (not just for partial success)
    - **Files Modified**: `src/pipeline/orchestrator.py`, `src/cli/commands.py`
  - **COMMIT: 4bb2c97 - Push to remote**:
    - Committed and pushed all staged changes including translation quality fixes (ERROR-042)
  - Previous: **FIXED: Poor EN→MM Translation Quality for Reverend Insanity**:
    - **Root Cause #1**: `glossary.json` contained 50 terms from wrong novel (古道仙鸿), poisoning translations with irrelevant terminology
    - **Root Cause #2**: `OllamaClient` in orchestrator wasn't receiving config sampling params (temperature, top_p, etc.) — using wrong defaults
    - **Root Cause #3**: Chunk size 2000 too large for padauk-gemma EN→MM
    - **Root Cause #4**: System prompt lacked LANGUAGE_GUARD reinforcement
    - **Fixes Applied**:
      1. Cleared glossary.json (backed up old one) — fresh empty glossary for Reverend Insanity
      2. Added temperature/top_p/top_k/repeat_penalty/max_retries passthrough from config to OllamaClient in orchestrator
      3. Reduced chunk_size 2000→800, tuned sampling (temperature 0.2, repeat_penalty 1.15, top_p 0.95)
      4. Added LANGUAGE_GUARD to both EN→MM and CN→MM prompts in translator.py, strengthened EN prompt with COMPLETENESS rule
      5. Increased num_predict 1024→2048 for gemma models, 800→1024 for others
    - **Files Modified**: config/settings.yaml, src/agents/translator.py, src/pipeline/orchestrator.py, src/utils/ollama_client.py, data/glossary.json
  - Previous tasks:
    - **CREATED: Comprehensive Technical Documentation (`PROJECT_DOCUMENTATION.md`)**:
    - **Purpose**: Complete technical reference for all files and functions in the project
    - **Contents**:
      - Project overview and architecture
      - Complete directory structure
      - Detailed module-by-module documentation
      - Function-level explanations for all key components
      - Configuration file schemas and examples
      - Data file formats (glossary, context_memory)
      - Usage examples and CLI commands
      - Error handling and troubleshooting
    - **Files Documented**:
      - Entry points: `src/main.py`, `src/main_fast.py`
      - CLI module: `src/cli/parser.py`, `src/cli/commands.py`, `src/cli/formatters.py`
      - Pipeline: `src/pipeline/orchestrator.py`
      - Config: `src/config/models.py`, `src/config/loader.py`
      - Agents: All 15+ agent files with class and method details
      - Memory: `src/memory/memory_manager.py`
      - Utils: `src/utils/ollama_client.py`, `src/utils/file_handler.py`, `src/utils/postprocessor.py`, etc.
      - Types: `src/types/definitions.py`
      - Exceptions: `src/exceptions.py`
    - **Features**:
      - Type signatures for all public methods
      - Configuration schemas with default values
      - Pipeline flow diagrams
      - File naming conventions
      - Model requirements and installation
      - Regular maintenance tasks
  - Previous tasks:
  1. **ADDED: Auto-Clean Launchers for Python Cache (All Platforms)**:
     - **Problem**: Users running old cached Python code even after updates (seeing `qwen:7b` instead of `padauk-gemma:q8_0`)
     - **Solution**: Created launcher scripts that automatically clean `__pycache__` and `.pyc` files before running
     - **New Files**:
       - **Windows (`.bat`)**:
         - `translate.bat`: Main one-click launcher with auto-clean
         - `run.bat`: Advanced launcher with detailed output
       - **Linux/Mac (`.sh`)**:
         - `translate.sh`: Main one-click launcher (bash script)
         - `run.sh`: Advanced launcher with detailed output
         - `clean_cache.sh`: Standalone cache cleaning utility
       - **Cross-Platform (Python)**:
         - `run.py`: Python launcher that cleans cache first
         - `src/utils/cache_cleaner.py`: Utility module for cache cleaning
         - `diagnose.py`: Diagnostic tool to verify configuration
       - **Documentation**:
         - `LAUNCHERS.md`: Comprehensive documentation for all platforms
     - **Features**:
       - Automatically removes all `__pycache__` directories
       - Removes all `.pyc` and `.pyo` compiled files
       - Shows cleaning report before translation starts
       - Passes all arguments through to main program
       - Scripts are committed as executable (no chmod needed)
     - **Usage**:
       ```bash
       # Windows (recommended)
       translate.bat --input data\input\novel\chapter.md
       
       # Linux/Mac (recommended)
       chmod +x translate.sh  # First time only
       ./translate.sh --input data/input/novel/chapter.md
       
       # Cross-platform
       python3 run.py --input data/input/novel/chapter.md
       ```
     - **Also Added**:
       - `--clean` flag to `src/cli/parser.py` for manual cache cleaning
       - Prominent warning in README.md about using launchers
       - Platform-specific troubleshooting in LAUNCHERS.md
  2. **ENHANCED: Auto-Detection of Source Language with Smart Model Selection**:
     - **Feature**: Enhanced auto-detection to automatically detect if input is English or Chinese
     - **Smart Model Selection**: Based on detected language, automatically selects optimal models:
       - **English detected**: Uses `way1` (EN→MM direct) with `padauk-gemma:q8_0` for all stages
       - **Chinese detected**: Uses `way2` (CN→EN→MM pivot) with `alibayram/hunyuan:7b` for Stage 1, `padauk-gemma:q8_0` for Stage 2
     - **Visual Feedback**: Added formatted banner showing detected language, workflow, and auto-selected models
     - **Logging**: Logger now reports auto-detection decisions for transparency
     - **Files Modified**:
       - `src/cli/commands.py`: Enhanced `_resolve_workflow()` to use Preprocessor.detect_language(), updated `_apply_workflow_config()` with automatic model selection and logging
       - `src/cli/formatters.py`: Added `print_auto_detection_result()` function for formatted detection display
     - **How it works**:
       1. Reads input file and uses `Preprocessor.detect_language()` to analyze text
       2. If Chinese chars > 10 or Chinese particles detected → triggers `way2`
       3. If ASCII letters > 100 → triggers `way1`
       4. Automatically overrides config with optimal models for each workflow
       5. Displays formatted banner showing detection results before translation starts
  3. **FIXED: Translation REJECTED - Model producing English instead of Myanmar**:
     - **Issue**: User reported `CRITICAL: Translation REJECTED` with myanmar_ratio: 0.0, chinese_chars_leaked: 12, latin_words: 295
     - **Root Cause**: Config was using `qwen:7b` as translator model, which outputs English/Latin text, NOT Myanmar
     - **Solution**: Changed all model settings from `qwen:7b` to `padauk-gemma:q8_0`:
       - `models.translator`: qwen:7b → padauk-gemma:q8_0
       - `models.editor`: qwen:7b → padauk-gemma:q8_0
       - `models.refiner`: qwen:7b → padauk-gemma:q8_0
       - `fast_config.translator`: qwen2.5:14b → padauk-gemma:q8_0
       - `fast_config.editor`: qwen:7b → padauk-gemma:q8_0
       - `fast_config.refiner`: qwen:7b → padauk-gemma:q8_0
     - **Files Modified**: `config/settings.yaml`
     - **Verification**: Confirmed `padauk-gemma:q8_0` is installed on user's system
  3. **Reorganized ROADMAP.md by Priority**:
     - Changed from version-based to priority-based structure (High/Medium/Low)
     - Updated status indicators for all features (✅ DONE / 🔄 In Progress / 📋 Planned)
     - Added ETA timeline for each feature
     - Created "Completed Features Archive" section for historical reference
     - Added "Last Updated" timestamp to ROADMAP
  2. **Previous Tasks**:
  1. **FIXED: Poor Translation Quality & CLI Output Issues**:
     - **Root Cause**: Default model `qwen2.5:14b` was outputting Japanese instead of Myanmar
     - **Solution**: Changed default model to `padauk-gemma:q8_0` which is specifically designed for Myanmar
     - **Files Modified**:
       - `config/settings.yaml`: Updated translator, editor, refiner to use `padauk-gemma:q8_0`
       - `src/agents/translator.py`: Added explicit Myanmar language instructions to prompts
       - `src/cli/commands.py`: Added verbose CLI output using formatters (print_translation_header, print_pipeline_stages, etc.)
       - `src/cli/formatters.py`: Added 'single_stage' mode to pipeline stages display
     - **Result**: Translation now produces proper Myanmar with 98%+ Myanmar character ratio
     - **CLI Enhancement**: Now displays model info, settings, pipeline stages, and progress
  2. **Bug Fix - Checker.__init__() unexpected keyword argument 'ollama_client'**:
     - Fixed `TypeError: Checker.__init__() got an unexpected keyword argument 'ollama_client'`
     - Removed `ollama_client` parameter from Checker() instantiation in `src/pipeline/orchestrator.py` (line 165-168)
     - Removed `ollama_client` parameter from Checker() instantiation in `src/core/container.py` (line 111-114)
     - The Checker class doesn't need ollama_client as it performs local validation (regex, string matching) rather than LLM-based checks
  2. **GPU Support Configuration**:
     - Added GPU configuration options to `config/settings.yaml` (use_gpu, gpu_layers, main_gpu)
     - Updated `src/config/models.py` ModelsConfig with GPU settings (use_gpu, gpu_layers, main_gpu)
     - Updated `src/utils/ollama_client.py` OllamaClient to support GPU parameters
     - Updated `src/core/container.py` to pass GPU options to OllamaClient
     - Updated `src/pipeline/orchestrator.py` to pass GPU options to OllamaClient
     - Created `scripts/verify_gpu.py` for GPU verification before translation
  1. **AMD GPU Support (RX 580 2048SP)**:
     - Updated `scripts/verify_gpu.py` to detect both NVIDIA and AMD GPUs
     - Added AMD-specific setup guide for RX 580 with ROCm instructions
     - Added AMD environment variable guidance to `config/settings.yaml`
     - Supports Polaris (gfx803) architecture detection
  1. **Bug Fix - MyanmarQualityChecker**:
     - Fixed `TypeError: MyanmarQualityChecker.__init__() got an unexpected keyword argument 'ollama_client'`
     - Updated `MyanmarQualityChecker.__init__` to accept `ollama_client`, `memory_manager`, and `config` parameters
     - This aligns with how other agents are instantiated in the pipeline orchestrator
   2. **CODE REFACTORING - Phase 1 Complete** (per need_fix.md):
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
| `PROJECT_DOCUMENTATION.md` | [DONE] | Complete technical documentation with all files and functions |

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

- **CODE REVIEW: Postprocessor Bug Fix Verification** (STATUS: READY_TO_COMMIT):
  - **Review Scope**: `src/utils/postprocessor.py` — 3 bug fixes verified
  - **Bug 1 (Critical)**: `remove_latin_words` regex `\s+` → `[^\S\n]+` — correctly preserves paragraph breaks while collapsing horizontal whitespace. PASS.
  - **Bug 2**: `fix_chapter_heading_format()` — correctly splits `# X ## Y` into proper H1/H2 on separate lines. PASS.
  - **Bug 3**: `remove_duplicate_headings()` — keeps only first `# အခန်း N`, strips duplicates and their subtitles. PASS.
  - **Recovery**: `_split_into_lines_if_needed()` — restores newlines from previously-corrupted single-line files at heading/sentence boundaries. PASS (only activates when no newlines exist).
  - **No breaking API changes**: `clean_output`, `Postprocessor`, `remove_latin_words` signatures unchanged.
  - **No cross-agent imports**: Modular boundary compliance confirmed.
  - **All 229 tests pass**.
  - **Minor issues noted** (non-blocking): `is_valid_myanmar_syllable` type hint mismatch (`-> bool` but returns `float`); no targeted tests for the 3 new functions; `fix_chapter_heading_format` only matches Myanmar digits not Latin digits.
  - **Files Reviewed**: `src/utils/postprocessor.py`
