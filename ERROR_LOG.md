# Error Log & Fix Record

> **Purpose**: Track all runtime errors encountered and their fixes for AI agent reference.
> **Updated**: Auto-updated by AI agents after fixing errors
> **Format**: Chronological log with error details, root cause, and fix verification

---

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

---

## Resolved Issues

### ERROR-008: UI does not match basic_template_design
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
