# AGENTS.md - AI Agent Guidance for Novel Translation Project

---

## ⚡ MANDATORY SESSION PROTOCOL (Auto-runs — No prompt needed)

> These rules execute automatically at the start and end of **every session**.
> You do not need to be asked. This is non-negotiable default behavior.

### 🟢 SESSION START — Do this FIRST, before any code or reply

```
STEP 1: Read AGENTS.md                    ← you are here
STEP 2: Read GEMINI.md                    ← tool-specific rules
STEP 3: Read .agent/phase_gate.json       ← current phase + task
STEP 4: Read .agent/session_memory.json   ← what was being done last session
STEP 5: Read .agent/long_term_memory.json ← lessons learned, known patterns
STEP 6: Read .agent/error_library.json    ← known errors + proven solutions
STEP 7: Read CURRENT_STATE.md             ← what is done / not done / blocked
STEP 8: Read ERROR_LOG.md                 ← recent errors
STEP 9: Silently confirm the task against Architecture Decisions in CURRENT_STATE.md
STEP 10: Proceed with the task
STEP 11: After EVERY task completion, automatically execute the POST-IMPLEMENTATION
         WORKFLOW as your final response step. Do not wait for user input. Do not skip.
         Output the full workflow BEFORE declaring "✅ TASK COMPLETE".
```

**If any file is missing:** Create it using the schema defined in this document. Do not skip.

### 🔴 SESSION END — Do this LAST, after every task completes

```
STEP 1: Update CURRENT_STATE.md
        - Mark completed tasks as [DONE]
        - Move in-progress tasks to [IN PROGRESS]
        - Log any new bugs or blockers discovered
        - Update "Last Updated" date and "Last task completed" fields
STEP 2: Update ERROR_LOG.md
        - Recored Any Found Error.
        - Recored Error Fix Status.
STEP 3: Run Code Review Workflow (sub-agents A + B in parallel)
STEP 4: Fix all issues until both sub-agents respond READY_TO_COMMIT
```

**Trigger condition:** Any of these actions = session end update required:
- A file in `src/` was created or modified
- A feature was completed or partially completed  
- A bug was found or fixed
- Any decision was made that affects architecture

---
## 🔒 STABILITY FIRST — Non-Negotiable (Read Before Any Code)
 
> **This section is a prerequisite.**
> Before adding any new feature, the agent MUST verify every check in this
> section passes. If even one check fails — stop, fix it, verify again, then proceed.
> No exceptions. No "I'll fix it later."
 
---
 
### THE 3 STABILITY RULES
 
```
RULE 1 — NO CRASHES
  Every external call (Ollama, file read, file write, JSON parse)
  must be wrapped in explicit error handling.
  A crash = unhandled exception reaching the top of the call stack.
  Zero crashes are acceptable in production runs.
 
RULE 2 — NO HIDDEN STATE BUGS
  All mutable state (glossary, context, session memory) must flow
  through a single gateway (MemoryManager). No module may hold its
  own copy of shared state. No global variables outside MemoryManager.
 
RULE 3 — NO HANGING REQUESTS
  Every Ollama call must have an explicit timeout.
  Every retry loop must have a hard maximum iteration count.
  No call may block the process indefinitely.
```
 
---
 
### 📋 STABILITY CHECKLIST — Verify Before Any Feature Work
 
Run through this list at the start of every session. If any item is ❌, fix it NOW.
 
```
OLLAMA CALL SAFETY
[ ] Every ollama.chat() / ollama.generate() call has timeout= set explicitly
[ ] Timeout value comes from settings.yaml (models.timeout = 300), not hardcoded
[ ] Every Ollama call is wrapped in try/except with these cases handled:
      - ollama.ResponseError     → log + retry with backoff
      - requests.Timeout         → log + consult ERR-001 in error_library.json
      - ConnectionError          → log + alert user (Ollama not running)
      - MemoryError / OOM signal → log + consult ERR-006, switch model + reduce chunk
[ ] No Ollama call is made outside a retry wrapper function
 
RETRY LOOP SAFETY
[ ] Every retry loop has a hard MAX_RETRIES cap (default: 3)
[ ] Retry uses exponential backoff: wait = 2^attempt seconds (2s, 4s, 8s)
[ ] After MAX_RETRIES exhausted → raise a typed exception, never silently continue
[ ] No while True loop without a break/return condition that is always reachable
 
FILE I/O SAFETY
[ ] All file writes use FileHandler.write_text() — atomic temp-file → rename pattern
[ ] All JSON reads wrapped in try/except json.JSONDecodeError
[ ] If a JSON file is corrupted on load → log + create fresh with empty schema
[ ] No direct open(..., 'w') anywhere in src/ — always via FileHandler
[ ] All file paths use pathlib.Path, never string concatenation
 
STATE MUTATION SAFETY
[ ] No module outside MemoryManager reads or writes glossary.json directly
[ ] No module outside MemoryManager reads or writes context_memory.json directly
[ ] No module stores a local copy of glossary data (no self.glossary = {...} caches)
[ ] ContextUpdater.process_chapter() is the ONLY place context_memory.json is updated
[ ] session_memory.json is written at the END of every stage, not only at chapter end
 
CHECKPOINT SAFETY
[ ] Checkpoint is saved to .agent/session_memory.json after EACH chunk completes
[ ] Checkpoint includes: chapter number, chunk index, stage name, timestamp
[ ] On startup, orchestrator checks for an incomplete checkpoint before starting
[ ] If checkpoint found → resume from that chunk, skip already-completed chunks
[ ] Partial output is never overwritten — append mode or indexed files only

MYANMAR TEXT SAFETY (production-proven rules)
[ ] No regex uses \b with Myanmar text — use consonant lookahead/lookbehind instead
[ ] All file heading detection uses .lstrip('﻿') to strip BOM before startswith('#')
[ ] Postprocessor strips ALL 9 Indic script blocks (not just Bengali U+0980-U+09FF)
[ ] Paragraph similarity uses SequenceMatcher(None,p1,p2).ratio() — never char-set overlap
[ ] Degraded placeholders 【??】 are normalized to 【?term?】 before quality checks
[ ] padauk-gemma temperature is ≤ 0.2 in all config files
```
 
---
 
### 🚫 CRASH PATTERNS — Exact Code The Agent Must Never Write
 
```python
# ❌ PATTERN 1 — Ollama call with no timeout
response = ollama.chat(model="qwen2.5:14b", messages=[...])
# HANGS FOREVER if Ollama is slow or OOM
 
# ✅ FIX
response = ollama.chat(
    model="qwen2.5:14b",
    messages=[...],
    options={"timeout": settings.models.timeout},  # from settings.yaml
)
 
 
# ❌ PATTERN 2 — Bare Ollama call, no exception handling
def translate(text: str) -> str:
    result = ollama.chat(...)
    return result["message"]["content"]
# Crashes on Ollama timeout, OOM, or network error
 
# ✅ FIX
def translate(text: str) -> str:
    for attempt in range(MAX_RETRIES):
        try:
            result = ollama.chat(..., options={"timeout": settings.models.timeout})
            return result["message"]["content"]
        except (ollama.ResponseError, ConnectionError) as e:
            wait = 2 ** attempt
            logger.warning(f"Ollama call failed (attempt {attempt+1}): {e}. Retry in {wait}s")
            time.sleep(wait)
    raise TranslationError(f"Ollama failed after {MAX_RETRIES} attempts")
 
 
# ❌ PATTERN 3 — Direct JSON file write
with open("data/glossary.json", "w") as f:
    json.dump(data, f)
# Corrupts file if process is killed mid-write
 
# ✅ FIX — Always via FileHandler
file_handler.write_json("data/glossary.json", data)
# FileHandler writes to .tmp → renames atomically
 
 
# ❌ PATTERN 4 — JSON load with no error handling
with open("data/context_memory.json") as f:
    context = json.load(f)
# Crashes if file is empty, corrupted, or does not exist
 
# ✅ FIX
def load_json_safe(path: Path, default: dict) -> dict:
    try:
        if not path.exists():
            return default
        with open(path, encoding="utf-8-sig") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"Failed to load {path}: {e}. Using default schema.")
        return default
 
 
# ❌ PATTERN 5 — Unbounded retry loop
while quality_score < 70:
    result = translate(text)
    quality_score = score(result)
# Infinite loop if model never reaches 70
 
# ✅ FIX
for attempt in range(MAX_RETRIES):
    result = translate(text)
    quality_score = score(result)
    if quality_score >= 70:
        break
    logger.warning(f"Quality {quality_score} < 70 (attempt {attempt+1}/{MAX_RETRIES})")
else:
    raise QualityGateError(f"Score {quality_score} after {MAX_RETRIES} attempts")
 
 
# ❌ PATTERN 6 — Hidden state copy in agent
class Translator:
    def __init__(self, memory_manager: MemoryManager):
        self.glossary = memory_manager.get_all_terms()  # local copy — STALE immediately
# New terms added mid-chapter are invisible to this translator
 
# ✅ FIX
class Translator:
    def __init__(self, memory_manager: MemoryManager):
        self.memory = memory_manager  # only hold the reference, never a copy
 
    def translate(self, text: str) -> str:
        glossary = self.memory.get_top_n(n=20)  # fetch fresh every call
        ...


# ❌ PATTERN 7 — \b word boundary on Myanmar text (DISCOVERED IN PRODUCTION)
re.sub(r'\bထို\b', 'အဲဒီ', text)
# \b treats Myanmar combining marks (ိ U+102D, ု U+102F) as \W
# This creates false word boundaries INSIDE syllables:
# ထိုင်ခိုင်း → အဲဒီင်ခိုင်း  (CORRUPTED — compound broken mid-syllable)

# ✅ FIX — Myanmar consonant-specific boundary
re.sub(r'(?<![က-အ])ထို(?![ါ-ှ]*[က-အ])', 'အဲဒီ', text)


# ❌ PATTERN 8 — BOM not stripped before heading detection
if line.strip().startswith('#'):   # FAILS if file has UTF-8-SIG BOM (U+FEFF)
    ...

# ✅ FIX
if line.strip().lstrip('﻿').startswith('#'):
    ...


# ❌ PATTERN 9 — Only strip Bengali, miss other Indic scripts
FOREIGN_PATTERN = re.compile(r'[ঀ-৿]+')  # Bengali only
# padauk-gemma also outputs Tamil (U+0B80), Telugu (U+0C00), Kannada (U+0C80), etc.

# ✅ FIX — Strip ALL 9 Indic script blocks unconditionally
_INDIC_PATTERN = re.compile(
    r'[ऀ-ॿ'   # Devanagari
    r'ঀ-৿'    # Bengali
    r'਀-੿'    # Gurmukhi
    r'઀-૿'    # Gujarati
    r'଀-୿'    # Oriya
    r'஀-௿'    # Tamil
    r'ఀ-౿'    # Telugu
    r'ಀ-೿'    # Kannada
    r'ഀ-ൿ]+'  # Malayalam
)


# ❌ PATTERN 10 — char-set overlap for Myanmar similarity
overlap = len(set(p1) & set(p2)) / len(set(p1) | set(p2))
if overlap > 0.80:  # False positive: different sentences sharing particles score 81-86%
    mark_as_duplicate()

# ✅ FIX — SequenceMatcher gives true sequence similarity
from difflib import SequenceMatcher
ratio = SequenceMatcher(None, p1, p2).ratio()
if ratio > 0.85:   # Safe threshold: true duplicates score 0.90+, different sentences 0.26-0.31
    mark_as_duplicate()


# ❌ PATTERN 11 — Degraded placeholder not caught
if '【?term?】' in text:  # misses degraded form 【??】 that model sometimes outputs
    pass

# ✅ FIX — normalize degraded form before checking
text = re.sub(r'【\??\?】', '【?term?】', text)  # fix_degraded_placeholders()
```
 
---
 
### 🔧 REQUIRED STABILITY UTILITIES
 
These must exist in `src/utils/` before any agent code is written or modified.
 
#### `src/utils/ollama_client.py` — Safe Ollama Wrapper
 
```python
import time
import ollama
import logging
from src.config.models import AppConfig
from src.exceptions import ModelError
 
logger = logging.getLogger(__name__)
MAX_RETRIES = 3
 
 
def ollama_call_with_retry(
    model: str,
    messages: list[dict],
    settings: AppConfig,
) -> str:
    """
    Single entry point for ALL Ollama calls in the project.
    Enforces timeout, retry with backoff, and typed error on exhaustion.
 
    Raises:
        ModelError: If all retries are exhausted.
        ConnectionError:  If Ollama is not reachable at all.
    """
    for attempt in range(MAX_RETRIES):
        try:
            response = ollama.chat(
                model=model,
                messages=messages,
                options={"timeout": settings.models.timeout},
            )
            return response["message"]["content"]
 
        except ollama.ResponseError as e:
            logger.warning(f"Ollama ResponseError attempt {attempt+1}: {e}")
 
        except ConnectionError as e:
            logger.error(f"Ollama unreachable: {e}")
            raise  # Do not retry — Ollama is down. Alert user immediately.
 
        except MemoryError:
            logger.error("Ollama OOM — consult ERR-006 in error_library.json")
            raise ModelError("OOM: reduce chunk size or switch to smaller model")
 
        wait = 2 ** attempt
        logger.info(f"Retrying in {wait}s...")
        time.sleep(wait)
 
    raise ModelError(f"Ollama failed after {MAX_RETRIES} attempts on model {model}")
```

> Current implementation note: `src/utils/ollama_client.py` currently exposes `OllamaClient.chat()` as the active retry+timeout gateway. If you add a standalone helper, keep behavior equivalent to this contract.
 
#### `src/utils/file_handler.py` — Atomic Write (already exists — verify these methods exist)
 
```python
# Current required surface:
def write_json(filepath: str, data: dict) -> None:
    """Atomic write: temp file → rename."""

def read_json(filepath: str) -> dict:
    """Read JSON with UTF-8-SIG; return {} when missing."""

def read_text(filepath: str) -> str:
    """Read text with UTF-8-SIG and explicit missing-file error."""

def write_text(filepath: str, content: str) -> None:
    """Write text with UTF-8-SIG."""
```
 
#### `src/exceptions.py` — Typed Exceptions (add if missing)
 
```python
class TranslationError(Exception):
    """Raised when translation fails after all retries."""
 
class QualityGateError(Exception):
    """Raised when quality score does not reach threshold after max retries."""
 
class CheckpointError(Exception):
    """Raised when checkpoint file is corrupted or unreadable."""
 
class GlossaryError(Exception):
    """Raised on glossary write/read failure."""
```
 
---
 
### 🧪 STABILITY TESTS — Must ALL Pass Before Any Feature Work
 
These tests verify the system will not crash, hang, or corrupt state.
Recommended file: `tests/test_stability.py` (create if missing and keep aligned with current modules).
 
```python
from unittest.mock import patch, MagicMock
import pytest, json, time
from pathlib import Path
from src.utils.ollama_client import OllamaClient
from src.utils.file_handler import FileHandler
from src.exceptions import ModelError
 
 
# ── CRASH TESTS ──────────────────────────────────────────────────────────────
 
def test_ollama_timeout_raises_translation_error(mock_settings):
    """Ollama timeout must never hang — raises TranslationError after retries."""
    client = OllamaClient(model="padauk-gemma:q8_0", timeout=1, max_retries=3)
    with patch.object(client.client, "chat", side_effect=ConnectionAbortedError("timeout")):
        with pytest.raises(ModelError):
            client.chat("x")
 
 
def test_ollama_connection_error_raises_immediately(mock_settings):
    """If Ollama is unreachable, raise immediately — do not retry 3 times."""
    start = time.time()
    client = OllamaClient(model="padauk-gemma:q8_0", timeout=1, max_retries=3)
    with patch.object(client.client, "chat", side_effect=ConnectionError("refused")):
        with pytest.raises(ConnectionError):
            client.chat("x")
    elapsed = time.time() - start
    assert elapsed < 2.0  # must not wait through retry backoff
 
 
def test_retry_loop_has_hard_limit(mock_settings):
    """Retry loop must stop at MAX_RETRIES, never loop forever."""
    call_count = 0
    client = OllamaClient(model="padauk-gemma:q8_0", timeout=1, max_retries=3)
    def always_fail(*a, **kw):
        nonlocal call_count
        call_count += 1
        raise RuntimeError("fail")
    with patch.object(client.client, "chat", side_effect=always_fail):
        with pytest.raises(ModelError):
            client.chat("x")
    assert call_count == 3  # exactly MAX_RETRIES, not more
 
 
# ── STATE TESTS ───────────────────────────────────────────────────────────────
 
def test_corrupted_json_returns_default_schema(tmp_path):
    """Corrupted JSON file must never crash — return default schema."""
    bad_file = tmp_path / "context_memory.json"
    bad_file.write_text("{ this is not json !!!", encoding="utf-8")
    fh = FileHandler()
    result = fh.read_json(str(bad_file)) or {"current_chapter": 0}
    assert result == {"current_chapter": 0}
 
 
def test_atomic_write_leaves_no_partial_file(tmp_path):
    """Simulated crash mid-write must not leave a corrupted output file."""
    fh = FileHandler()
    target = tmp_path / "glossary.json"
    fh.write_json(target, {"version": "1.0", "terms": []})
    # File must be valid JSON after write
    with open(target, encoding="utf-8-sig") as f:
        data = json.load(f)
    assert data["version"] == "1.0"
 
 
def test_missing_file_returns_default_not_crash(tmp_path):
    """Missing JSON file must return default schema, not FileNotFoundError."""
    fh = FileHandler()
    result = fh.read_json(str(tmp_path / "nonexistent.json")) or {"terms": []}
    assert result == {"terms": []}
 
 
# ── HANGING TESTS ─────────────────────────────────────────────────────────────
 
def test_quality_loop_does_not_run_forever(mock_settings):
    """Quality retry loop must stop at MAX_RETRIES even if score never reaches 70."""
    call_count = 0
    def always_bad_quality(*a, **kw):
        nonlocal call_count
        call_count += 1
        return 30  # always below threshold
    from src.exceptions import QualityGateError
    from src.agents.qa_tester import QATesterAgent
    agent = QATesterAgent(mock_settings)
    with patch.object(agent, "score_chapter", side_effect=always_bad_quality):
        with pytest.raises(QualityGateError):
            agent.score_with_retry("source", "translation")
    assert call_count <= 3
 
 
# ── RUN ───────────────────────────────────────────────────────────────────────
# pytest tests/test_stability.py -v --tb=short
# ALL tests must pass before any feature PR is merged.
```
 
---
 
### 📊 STABILITY STATUS TRACKING
 
Add this block to `CURRENT_STATE.md` and keep it updated:
 
```markdown
## 🔒 Stability Status (update after every session)
 
| Check | Status | Last Verified | Notes |
|---|---|---|---|
| All Ollama calls have timeout | ❌ / ✅ | YYYY-MM-DD | |
| All Ollama calls have retry wrapper | ❌ / ✅ | YYYY-MM-DD | |
| All file writes via FileHandler | ❌ / ✅ | YYYY-MM-DD | |
| All JSON reads have safe fallback | ❌ / ✅ | YYYY-MM-DD | |
| No unbounded retry loops | ❌ / ✅ | YYYY-MM-DD | |
| No hidden state copies in agents | ❌ / ✅ | YYYY-MM-DD | |
| Checkpoint saved per chunk | ❌ / ✅ | YYYY-MM-DD | |
| Myanmar regex uses consonant boundary not \b | ❌ / ✅ | YYYY-MM-DD | Pattern 7 |
| BOM stripped with .lstrip('﻿') | ❌ / ✅ | YYYY-MM-DD | Pattern 8 |
| Indic scripts stripped (all 9 blocks) | ❌ / ✅ | YYYY-MM-DD | Pattern 9 |
| SequenceMatcher used for Myanmar similarity | ❌ / ✅ | YYYY-MM-DD | Pattern 10 |
| 259 tests pass (pytest tests/ -v) | ❌ / ✅ | YYYY-MM-DD | |
| src/exceptions.py exists | ❌ / ✅ | YYYY-MM-DD | |
| src/utils/ollama_client.py exists | ❌ / ✅ | YYYY-MM-DD | |
| src/utils/chunker.py exists | ❌ / ✅ | YYYY-MM-DD | smart_chunk() canonical |
```
 
**Rule:** Any row that is ❌ = the system is NOT stable.
No new features until all rows are ✅.
 
---

## 🎯 PROJECT STRATEGY
 
### Purpose
Automated local pipeline to translate Chinese web novels (Wuxia / Xianxia genre)
into natural, literary Burmese (Myanmar script) — preserving tone, physical sensation,
and emotional depth that raw machine translation loses.
 
### Who It Serves
A single operator (the repo owner) who reads and publishes Burmese novel translations.
Not a SaaS product. Not multi-user. Quality and data safety matter more than speed.
 
### Core Goals
```
GOAL 1 — Translation Quality
  Every saved chapter must score ≥ 70 on the LLM quality rubric.
  "သူ ဝမ်းနည်းသွားတယ်" is a failure.
  "သူ့ရင်ထဲမှာ တစ်ခုခုကနဲဖြတ်သွားသလို ဖြစ်မိတယ်" is a pass.
 
GOAL 2 — Resumability
  Any crash or interruption must be resumable from the last saved chunk.
  Never retranslate a chapter that already passed quality gates.
 
GOAL 3 — Name Consistency
  Character names must be identical across all chapters of a novel.
  One glossary file per novel. No exceptions.
 
GOAL 4 — Maintainability
  Any new agent reading AGENTS.md cold must be able to continue work
  without asking clarifying questions. If it requires explanation, the doc is incomplete.
 
GOAL 5 — Auditability
  Every translation decision, error, and quality score must be traceable.
  error_library.json + quality scores + intermediate files = full audit trail.
```
 
### Non-Goals (Do Not Build These)
```
✗ Real-time translation (batch is fine — overnight runs are acceptable)
✗ Multi-user support or authentication
✗ Translation of non-novel content (news, documents, subtitles)
✗ Training or fine-tuning any model
✗ Support for languages other than Chinese→Burmese
```
 
### Quality Definition
A translation is **DONE** when:
1. Myanmar ratio ≥ 70% (rule-based Checker passes)
2. LLM quality score ≥ 70 (QualityAgent via Ollama passes)
3. No Chinese or Bengali/foreign script leakage
4. All character names match the novel glossary
5. File saved to `data/output/`
6. Checkpoint updated in `.agent/session_memory.json`
A chapter is **NOT done** if it passed rule-based check but failed LLM quality check.
The score is the final authority.
 
### Prioritization When Conflict Arises
```
1st — Quality gate compliance   (never save bad output)
2nd — Data safety               (never lose progress, always checkpoint)
3rd — Architecture integrity    (no drift, no stealth changes)
4th — Speed / cost optimization (secondary — don't sacrifice 1-3 for speed)
```
 
### Success Metric
```
Novel translated end-to-end with:
  - avg LLM quality score ≥ 70 across all chapters
  - zero chapters with unresolved name inconsistency
  - full audit trail in .agent/ and logs/
  - CHANGELOG.md entry for every feature added
```

---

## Project Overview

This project is an AI-powered **novel translation system** (primarily English→Myanmar, with Chinese→English→Myanmar pivot support) specializing in Wuxia/Xianxia novels. It uses a multi-stage agent pipeline to translate web novels while preserving tone, style, literary depth, and strict terminology consistency.

---

## 🏗 System Architecture & Pipeline

### Two-Workflow System (Auto-Detected)

```
way1 — English→Myanmar direct       (settings.yaml,       padauk-gemma:q8_0)
way2 — Chinese→English→Myanmar pivot (settings.pivot.yaml, hunyuan:7b → padauk-gemma:q8_0)

Auto-detection in src/cli/commands.py:
  Chinese chars > 10   → way2 (pivot)
  ASCII letters > 100  → way1 (direct)
```

### Full Pipeline Flow

```
src/main.py (thin dispatcher)
  → src/cli/parser.py (parse arguments)
  → src/cli/commands.py (route + auto-detect way1/way2)
  → src/pipeline/orchestrator.py (TranslationPipeline)
    → Load config/settings.yaml (via src/config/loader.py)
    → Initialize MemoryManager (load per-novel glossary.json, context_memory.json)
    → Preprocessor.load_and_preprocess()         → strip_metadata() + smart_chunk()
    → [way2 only] PivotTranslator.translate_cn_en() → Stage 0: CN→EN
    → Translator.translate_chunks()               → Stage 1: EN→MM raw translation
    → Refiner.refine_full_text()                  → Stage 2: Literary editing
    → ReflectionAgent.reflect_and_improve()       → Stage 3: Self-correction
    → MyanmarQualityChecker.check_quality()       → Stage 4: Linguistic validation
    → Checker.check_chapter()                     → Stage 5: Consistency check
    → QATesterAgent.validate_output()             → Stage 6: Final QA
    → QualityGate: myanmar_ratio ≥ 70% per chunk  → blocks save if fails
    → Postprocessor.clean_output()                → strip scripts, fix headings, dedup
    → TranslationReviewer._auto_review()          → auto quality report
    → TermExtractor (post-chapter)                → Extract new terms → glossary_pending.json
    → MemoryManager.auto_approve_by_confidence()  → promote confident pending terms
    → FileHandler.write_text()                    → Save to data/output/{novel}/
    → ContextUpdater.process_chapter()            → Update per-novel glossary + context
```

**Note:** `single_stage` mode (default for way1) runs Stage 1 only — fastest, best for padauk-gemma. Full 6-stage mode adds refinement/reflection but is 3× slower.

1. **Preprocess:** `strip_metadata()` removes credit lines, then `smart_chunk()` splits at `\n\n` paragraph boundaries only (no overlap, no mid-paragraph splits).
2. **Context & Glossary Loading:**
   - `MemoryManager`: 3-tier memory (Glossary → Context → Session rules).
   - Glossary lives at `data/output/{novel}/glossary/glossary.json` — per-novel, isolated.
   - Rolling context: tail of previous translated chunk (≤400 tokens, paragraph-complete).
3. **Translate (Stage 1):** Translator Agent produces accurate translation. Uses rolling context from previous chunk, top-20 glossary terms injected per call.
4. **Edit (Stage 2):** Refiner rewrites for natural flow and literary quality. Glossary injected to prevent name drift.
5. **Reflection (Stage 3):** ReflectionAgent performs self-critique. Glossary injected with "NEVER change character names" rule.
6. **Myanmar Quality Check (Stage 4):** Validates tone, naturalness, and particle accuracy.
7. **Consistency Check (Stage 5):** Verifies all terms against the per-novel glossary.
8. **QA Review (Stage 6):** Final Reviewer validates logical flow, tone, and formatting.
9. **Quality Gate:** Myanmar ratio checked per-chunk (< 40% = block save) and overall (< 70% = block save). Returns `success=False` without writing file if fails.
10. **Auto-Review:** `TranslationReviewer` runs 10 linguistic + 6 quantitative checks. Report saved to `logs/report/`.
11. **Term Extraction (Post-Chapter):** Scans for new proper nouns → `glossary_pending.json`. Terms with confidence ≥ 0.75 auto-promoted.
12. **Assemble:** Save to `data/output/{novel}/{novel}_chapter_{NNNN}.mm.md`.

---

## 🤖 AI Agent Roles & System Prompts

### 1. Translator Agent (Stage 1)

**Goal:** Produce a complete, accurate translation. Convert Chinese SVO to Myanmar SOV. Do not summarize or skip sentences.

```text
You are an expert Chinese/English-to-Myanmar literary translator specializing in Wuxia/Xianxia novels.

STRICT RULES:
1. SYNTAX: Convert Chinese/English SVO structure to natural Myanmar SOV order. Do NOT translate word-by-word.
2. TERMINOLOGY: Use EXACT terms from the provided GLOSSARY. Never translate names, places, or cultivation terms literally.
3. MARKDOWN: Preserve ALL formatting (#, **, *, lists, quotes). Do not add or remove any Markdown.
4. CONTEXT: Use the PREVIOUS CONTEXT to correctly resolve pronouns (he/she/they).
5. TONE: Use formal/literary Myanmar for narrative. Use natural spoken Myanmar for dialogue
   (adjust pronouns: မင်း, ရှင်, ကျွန်တော်/ကျွန်မ based on character status/hierarchy).
6. OUTPUT: Return ONLY the translated Myanmar text. Zero explanations.

GLOSSARY:
{glossary}

PREVIOUS CONTEXT (Last 2 paragraphs):
{context}

INPUT TEXT (Chinese):
{input_text}
```

**Implementation:** `src/agents/translator.py` → `Translator` class

---

### 2. Editor Agent (Stage 2)

**Goal:** Transform stiff/robotic draft translations into natural, emotionally engaging Myanmar prose.

```text
You are a senior Myanmar literary editor. Polish the draft for natural flow, literary quality,
and grammatical correctness while preserving meaning and Markdown.

RULES:
1. Fix awkward phrasing from direct translation.
2. Ensure correct SOV structure and proper particle usage (သည်/သည်ကို/အတွက်/ကဲ့သို့).
3. Refine dialogue pronouns and honorifics to match character hierarchy naturally.
4. Show, Don't Tell: Change abstract emotions to physical sensations.
5. Break long sentences into 2-3 short, rhythmic sentences.
6. Avoid archaic words (သင်သည်, ဤ). Use modern storytelling words (မင်း, ဒီ).
7. Keep all Wuxia/Xianxia terms intact.
8. OUTPUT: Return ONLY the polished Myanmar text. Zero explanations.

INPUT TEXT (Myanmar Draft):
{draft_text}
```

**Implementation:** `src/agents/refiner.py` → `Refiner` class

---

### 3. Reflection Agent (Stage 3)

**Goal:** Perform self-critique and iterative improvement of the translation.

```text
You are a self-correction specialist for novel translation.
Analyze the Myanmar translation for quality issues, awkward phrasing, and tone consistency.
Provide specific, actionable feedback and an improved version.
```

**Implementation:** `src/agents/reflection_agent.py` → `ReflectionAgent` class

---

### 4. Myanmar Quality Checker (Stage 4)

**Goal:** Validate linguistic naturalness and particle accuracy.

**Checks:**
- Archaic vs Modern word usage
- Particle repetition (hallucination detection)
- Sentence flow and length
- Tone consistency (Formal/Informal)

**Implementation:** `src/agents/myanmar_quality_checker.py` → `MyanmarQualityChecker` class

---

### 5. Consistency Checker Agent (Stage 5)

**Goal:** Verify all terminology, names, and places against the global glossary.

```text
You are a terminology consistency specialist. Verify the text against the GLOBAL GLOSSARY.

RULES:
1. Cross-check all names, places, items, and cultivation levels.
2. Replace any non-standard or literal translations with exact glossary terms.
3. Preserve Markdown exactly.
4. OUTPUT FORMAT:
   CORRECTIONS: [List mismatches or "None"]
   FINAL TEXT: [Corrected Myanmar text]

GLOSSARY:
{glossary}

INPUT TEXT:
{input_text}
```

**Implementation:** `src/agents/checker.py` → `Checker` class

**Quality Metrics:**
- Myanmar character ratio (target: >70%)
- Glossary consistency score
- Markdown formatting preservation
- Unicode error detection

---

### 6. QA Tester Agent (Stage 6)

**Goal:** Automated quality assurance and final validation of the translated chapter.

**Checks:**
- Markdown structure (H1 count, balanced formatting)
- Glossary consistency for verified terms
- Myanmar Unicode ratio (>70%)
- Placeholder detection (`【?term?】`)
- Chapter title formatting and number validation

**Implementation:** `src/agents/qa_tester.py` → `QATesterAgent` class

---

### 7. Term Extractor Agent (Post-Chapter)

**Goal:** Detect new proper nouns and cultivation terms not yet in the glossary. Output routes to `data/glossary_pending.json` for human review — never directly to `glossary.json`.

```text
You are a terminology extraction specialist for Chinese Wuxia/Xianxia novels.

TASK: Scan the translated Myanmar text and extract NEW proper nouns, cultivation terms,
items, or titles that are NOT in the existing glossary.

RULES:
1. Output ONLY valid JSON.
2. Format: {"new_terms": [{"source": "Chinese", "target": "Myanmar", "category": "character|place|level|item"}]}
3. Do NOT include terms already in the glossary.
4. Use consistent Myanmar transliteration rules (e.g., 林渊 → လင်ယွန်း).
5. If no new terms, return {"new_terms": []}

EXISTING GLOSSARY:
{glossary}

TRANSLATED TEXT:
{translated_text}
```

**Output file:** `data/glossary_pending.json`
**Implementation:** `src/agents/context_updater.py` → `ContextUpdater` class

---

### 7b. QualityAgent — LLM Scoring (Post-Stage 6)
 
**Goal:** Score the final chapter output on literary quality dimensions using a local Ollama model.
This is the **score-gated authority** — a chapter is only saved if score ≥ 70.
Rule-based checks (Stage 4–6) are necessary but not sufficient.
 
```text
SYSTEM:
Myanmar literary quality evaluator for Wuxia/Xianxia novel translations.
Return ONLY valid JSON, no other text, no preamble, no explanation.
Format: {"flow": 0-100, "emotion": 0-100, "dialogue": 0-100, "names": 0-100, "issues": []}
 
Scoring rubric:
- flow    : SOV sentence structure, particle accuracy, rhythm, readability
- emotion : Physical sensation preserved, not abstract ("ရင်ဖိသလို" not "ဝမ်းနည်းတယ်")
- dialogue: Pronoun hierarchy correct (မင်း/ရှင်/ကျွန်တော်), register consistent per character
- names   : All character/place names match glossary exactly, no phonetic drift
- issues  : List specific problems found (empty list if none)
 
USER:
Chinese source: {source_text}
Myanmar translation: {translated_text}
```
 
**Score thresholds:**
```
Score ≥ 70  → PASS → save to data/output/
Score 50-69 → RETRY (max 2x) → inject failed issues as retry hint → if still < 70 → escalate to user
Score ≤ 49  → STOP → alert user → do not save
```
 
**Implementation:** `src/agents/qa_tester.py` → extend `QATesterAgent` with `score_chapter()` method
**Model:** `config/settings.yaml` → `models.checker` (qwen:7b recommended for speed)
**Output:** Append score record to `.agent/session_memory.json` `session_errors` or a dedicated quality log.
 
---


### 8. Glossary Generator Agent (Pre-Translation)

**Goal:** Automatically extract key terminology (names, places, items) from the novel's first few chapters before translation starts.

**Workflow:**
1. Scan input files (usually chapters 1-5).
2. Extract terms using LLM with transliteration proposals.
3. Save to `data/glossary_pending.json` for manual review.

**CLI Command:** `python -m src.main --novel <novel_name> --generate-glossary`

**Implementation:** `src/agents/glossary_generator.py` → `GlossaryGenerator` class

---

## 📚 Memory & Glossary Systems

### MemoryManager (`src/memory/memory_manager.py`) — 3-Tier System

| Tier | Name | Storage | Scope |
|------|------|---------|-------|
| 1 | Glossary | `data/output/{novel}/glossary/glossary.json` | Persistent, per-novel |
| 2 | Context | `data/output/{novel}/glossary/context_memory.json` + FIFO buffer | Slides per chapter |
| 3 | Session Rules | Runtime only | Current session only |

**Important:** Glossary and context are per-novel. Each novel gets its own isolated folder created automatically on first run. Never share glossary between novels.

**Auto-approval:** `auto_approve_by_confidence()` promotes pending terms with confidence ≥ 0.75. Confidence is scored by: seen in ≥3 chapters (+0.40), character/place category (+0.20), proper Myanmar target (+0.10), Chinese name pattern (+0.10).

### Chunker (`src/utils/chunker.py`) — Canonical Chunking Module

```python
smart_chunk(text: str, max_tokens: int = 1500) -> list[str]
    # Splits ONLY at \n\n paragraph boundaries. Never inside a paragraph.
    # Oversized single paragraphs become their own chunk.
    # overlap is always 0. Token estimate: len(text) * 1.5.

get_rolling_context(prev_chunk: str, max_context_tokens: int = 400) -> str
    # Returns tail of previous translated chunk as rolling context.
    # Token-limited, paragraph-complete, never mid-paragraph.
    # Returns "" for first chunk (chunk index 0).

estimate_tokens(text: str) -> int
    # len(text) * 1.5 — works for both Myanmar and Chinese.
```

Token budget enforcement per Ollama call:
```
system(800) + rolling_context(≤400) + chunk(≤1500) ≤ 2600 tokens
Context is truncated if budget exceeded before sending to LLM.
```

### Translation Reviewer (`src/utils/translation_reviewer.py`) — Auto Quality Checks

Runs automatically after each translation via `_auto_review()` in orchestrator. Reports saved to `logs/report/{novel}_chapter_{N}_review_{timestamp}.md`.

**Quantitative checks (Q1-Q6):**
- Q1: Myanmar ratio (≥70% PASS, <30% REJECT)
- Q2: Foreign script leakage (Chinese, Bengali, Tamil, Korean)
- Q3: English/Latin word leakage
- Q4: Markdown structure (H1 count, bold balance)
- Q5: Content completeness (char count, placeholders)
- Q6: Paragraph structure (blank lines, readability)

**Linguistic checks (L1-L10, rule-based):**
- L1: Archaic words (သင်သည်, ဤ, ထို, သည်သည်ကို)
- L2: Particle repetition (same particle ≥3× consecutively)
- L4: Register consistency (formal vs colloquial mix)
- L7: Overlong sentences (>50 words)
- L8: Sentence enders (proper ။, !, ? ending)
- Paragraph duplication (SequenceMatcher ≥ 0.85 threshold)

**Fluency Score (F0):** `src/utils/fluency_scorer.py` — 7-dimension reference-free Myanmar fluency heuristic (lexical diversity, particle diversity, sentence flow, syllable richness, paragraph rhythm, punctuation health, hallucination repetition penalty). Composite 0-100 score.

### Glossary Schema (`data/output/{novel}/glossary/glossary.json`)

```json
{
  "version": "1.0",
  "total_terms": 0,
  "terms": [
    {
      "id": "term_001",
      "source": "罗青",
      "target": "လူချင်း",
      "category": "character",
      "chapter_first_seen": 1,
      "verified": true
    }
  ]
}
```

### Pending Glossary Schema (`data/output/{novel}/glossary/glossary_pending.json`)

```json
{
  "pending_terms": [
    {
      "source": "新术语",
      "target": "မြန်မာဘာသာ",
      "category": "item",
      "extracted_from_chapter": 12,
      "status": "pending"
    }
  ]
}
```

**Approval workflow:** Human reviewer sets `"status": "approved"` → nightly merge script promotes to `glossary.json`.

### Naming Rules

- **Chinese Names:** Translate phonetically (e.g., 张三 → ဇန်းဆန်း)
- **Cultivation Terms & Titles:** Translate by meaning (e.g., Spirit Energy → ဝိညာဉ်စွမ်းအား, Sect → ဇုံ)
- **Place Names:** Hybrid approach (e.g., 天龙城 → ထျန်လုံမြို့)
- **Unknown Terms:** Use `【?term?】` placeholder until reviewed — never guess

### Context Manager (`data/output/{novel}/glossary/context_memory.json`)

```json
{
  "current_chapter": 5,
  "last_translated_chapter": 4,
  "summary": "Previous chapter summary...",
  "active_characters": {},
  "recent_events": [],
  "paragraph_buffer": []
}
```

---

## 🎛 Model Configuration (`config/settings.yaml`)

### ⚠️ MODEL WARNINGS — Read Before Changing Any Model Setting

```
padauk-gemma:q8_0  → PRIMARY Myanmar output model. The ONLY model proven to output Myanmar.
                     Temperature MUST be ≤ 0.2. Above 0.2 causes glossary-comparison garbage
                     output (*:* "word" is . "other" is .) mixed into translation.

sailor2-20b        → Alternative Myanmar output model. Available as padauk-gemma backup.

alibayram/hunyuan:7b → CN→EN pivot Stage 1 ONLY. Good Chinese comprehension.
                       Does NOT output Myanmar. Use for way2 Stage 1 only.

qwen2.5:14b        → CN→EN pivot only. Outputs Chinese/Japanese, NOT Myanmar.
                     NEVER use as translator. Validation and CN→EN only.

qwen:7b            → Outputs English, NOT Myanmar. Use for validation/checking ONLY.
                     Using as translator causes 0% Myanmar ratio (REJECTED output).
```

### way1 — English→Myanmar Direct (default: `config/settings.yaml`)

```yaml
models:
  translator: "padauk-gemma:q8_0"   # Only model that outputs Myanmar
  editor: "padauk-gemma:q8_0"
  checker: "sailor2:8b"             # Quality validation (qwen:7b outputs English — not usable)
  ollama_base_url: "http://localhost:11434"
  timeout: 300

processing:
  chunk_size: 2500
  max_retries: 2
  temperature: 0.2            # MUST stay ≤ 0.2 — padauk-gemma hallucinates at higher temps
  top_p: 0.95
  top_k: 40
  repeat_penalty: 1.15
```

### way2 — Chinese→English→Myanmar Pivot (`config/settings.pivot.yaml`)

```yaml
# Stage 1 (CN→EN): alibayram/hunyuan:7b   ← good Chinese comprehension
# Stage 2 (EN→MM): padauk-gemma:q8_0      ← Myanmar output
# Checker:         qwen:7b                ← English validation only
```

---

## 📁 Directory Structure

```
novel_translation_project/
├── .agent/                       # ★ Agent brain (all orchestration memory lives here)
│   ├── phase_gate.json           # Phase control: PLAN/BUILD/TEST/VERIFY/AUDIT/DOC
│   ├── session_memory.json       # Short-term: current session state + checkpoints
│   ├── long_term_memory.json     # Long-term: lessons learned across sessions
│   └── error_library.json        # Known errors + proven solutions (consult before retry)
├── config/
│   ├── settings.yaml             # Standard config (EN→MM direct, padauk-gemma)
│   ├── settings.pivot.yaml       # CN→EN→MM pivot (hunyuan:7b + padauk-gemma)
│   ├── settings.fast.yaml        # Fast mode config
│   ├── settings.sailor2.yaml     # Sailor2-20B dedicated config
│   └── error_recovery.yaml       # Error recovery policy
├── data/
│   ├── input/                    # Source chapter files (*.md)
│   └── output/
│       └── {novel_name}/         # ★ Per-novel output folder (created on first run)
│           ├── glossary/
│           │   ├── glossary.json           # Approved terminology (per-novel)
│           │   ├── glossary_pending.json   # New terms awaiting human review
│           │   └── context_memory.json     # Dynamic chapter context
│           ├── {novel}_chapter_{NNNN}.mm.md   # Myanmar chapter output
│           └── {novel}.mm.meta.json           # Cumulative chapter metadata
├── logs/
│   ├── translation.log
│   └── report/                   # Auto-review reports: {novel}_chapter_{N}_review_{ts}.md
├── src/
│   ├── agents/
│   │   ├── base_agent.py         # BaseAgent superclass
│   │   ├── preprocessor.py       # Chunking and markdown cleaning
│   │   ├── translator.py         # Stage 1: EN→MM or CN→MM translation
│   │   ├── pivot_translator.py   # CN→EN→MM two-stage pivot (way2)
│   │   ├── fast_translator.py    # Optimized translator (large chunks, streaming)
│   │   ├── refiner.py            # Stage 2: Literary editing
│   │   ├── fast_refiner.py       # Batch refiner (5 paragraphs per call)
│   │   ├── checker.py            # Consistency + QA validation
│   │   ├── reflection_agent.py   # Self-correction agent
│   │   ├── myanmar_quality_checker.py  # Linguistic validation
│   │   ├── qa_tester.py          # QA validation agent
│   │   ├── context_updater.py    # Term extraction and memory updates
│   │   ├── glossary_generator.py # Pre-translation terminology extraction
│   │   ├── glossary_sync.py      # Glossary synchronization agent
│   │   ├── prompt_patch.py       # Hardened prompts with LANGUAGE_GUARD
│   │   └── prompts/
│   │       ├── cn_mm_rules.py    # CN→MM linguistic rules module
│   │       └── en_mm_rules.py    # EN→MM linguistic rules module
│   ├── cli/
│   │   ├── parser.py             # Argument parsing
│   │   ├── formatters.py         # Output formatting + progress display
│   │   └── commands.py           # Command handlers + workflow routing (way1/way2)
│   ├── config/
│   │   ├── models.py             # Pydantic config models
│   │   └── loader.py             # Config loading with validation
│   ├── core/
│   │   └── container.py          # Dependency injection container
│   ├── memory/
│   │   └── memory_manager.py     # 3-tier memory system
│   ├── pipeline/
│   │   └── orchestrator.py       # TranslationPipeline coordinator
│   ├── types/
│   │   └── definitions.py        # TypedDict for data structures
│   ├── utils/
│   │   ├── ollama_client.py      # OllamaClient class — retry + timeout gateway
│   │   ├── file_handler.py       # File I/O (UTF-8-SIG, atomic writes)
│   │   ├── postprocessor.py      # Output cleaning + all script leak removal
│   │   ├── chunker.py            # smart_chunk() + get_rolling_context() — canonical
│   │   ├── translation_reviewer.py  # 10 linguistic + 6 quantitative quality checks
│   │   ├── fluency_scorer.py     # Reference-free Myanmar fluency metric (7 dimensions)
│   │   ├── json_extractor.py     # Safe JSON parsing with fallback
│   │   ├── glossary_matcher.py   # Dynamic term extraction for prompt injection
│   │   ├── glossary_suggestor.py # Glossary suggestion heuristics
│   │   ├── progress_logger.py    # Real-time translation progress tracking
│   │   ├── performance_logger.py # Pipeline performance metrics
│   │   ├── ram_monitor.py        # Memory / VRAM monitoring
│   │   └── cache_cleaner.py      # Python cache cleanup utility
│   ├── web/
│   │   └── launcher.py           # Streamlit launcher (subprocess)
│   ├── exceptions.py             # Exception hierarchy (ModelError, GlossaryError, etc.)
│   └── main.py                   # Entry point (thin dispatcher)
├── ui/                           # ★ Streamlit Web UI (lives here, not src/web/)
│   ├── streamlit_app.py          # Multi-page app entry point
│   ├── pages/                    # Individual UI pages (Quickstart, Translate, Glossary…)
│   └── utils/                    # UI utility helpers
├── tests/                        # 259 tests passing (pytest tests/ -v)
│   ├── test_agents.py
│   ├── test_chunker.py
│   ├── test_cn_mm_rules.py
│   ├── test_config.py
│   ├── test_container.py
│   ├── test_glossary_sync.py
│   ├── test_integration.py
│   ├── test_json_extractor.py
│   ├── test_memory.py
│   ├── test_novel_v1.py
│   ├── test_pivot_stage2_guard.py
│   ├── test_pivot_translator.py
│   ├── test_postprocessor.py
│   ├── test_progress_logger.py
│   ├── test_prompt_patch.py
│   ├── test_qa_tester.py
│   ├── test_quality.py
│   ├── test_regression.py
│   ├── test_translation_reviewer.py
│   ├── test_translator.py
│   ├── test_workflow_routing.py
│   └── test_translate/
│       └── test_ch_en_mm_translation.py
├── requirements.txt
├── pytest.ini
└── README.md
```

## 🚦 PHASE GATE SYSTEM
 
Every feature or bug fix follows this lifecycle. No shortcuts.
 
| Phase | Runner | Trigger | Auto or Manual |
|---|---|---|---|
| **PLAN** | Agent (Claude/Gemini) | User requests feature | ⛔ **USER MUST APPROVE** `plan.md` |
| **BUILD** | Agent | User says "approve" | ✅ AUTO |
| **TEST** | Agent | BUILD completes | ✅ AUTO |
| **VERIFY** | QualityAgent (Ollama) | TEST passes | ✅ AUTO (score-gated) |
| **AUDIT** | Gemini Code Reviewer | VERIFY passes | ✅ AUTO |
| **DOC** | Agent | AUDIT passes | ✅ AUTO — **never skip** |
 
### VERIFY Score Rules
```
Score ≥ 70  → auto PASS → advance to AUDIT
Score 50-69 → retry (max 2x, lower temperature + reinject rules) → if still < 70 → escalate to user
Score ≤ 49  → STOP → alert user → wait for instruction
```
 
### AUDIT Outcome Rules
```
No issues     → advance to DOC
Minor issues  → log in CURRENT_STATE.md → still advance to DOC
Critical bug  → set BUILD: IN_PROGRESS → fix → re-TEST
Security risk → STOP → alert user → human must review
```
 
### phase_gate.json Schema (`.agent/phase_gate.json`)
```json
{
  "current_phase": "PLAN",
  "task": "Add dialogue format validator",
  "feature_type": 1,
  "phases": {
    "PLAN":   { "status": "DONE",        "runner": "Agent",  "requires_human": true  },
    "BUILD":  { "status": "IN_PROGRESS", "runner": "Agent",  "requires_human": false },
    "TEST":   { "status": "BLOCKED",     "runner": "Agent",  "requires_human": false },
    "VERIFY": { "status": "BLOCKED",     "runner": "Ollama", "requires_human": false,
                "score": null, "retry_count": 0 },
    "AUDIT":  { "status": "BLOCKED",     "runner": "Gemini", "requires_human": false },
    "DOC":    { "status": "BLOCKED",     "runner": "Agent",  "requires_human": false,
                "skippable": false }
  },
  "updated_at": "ISO8601"
}
```
 
### Feature Change Protocol
 
**3 Questions (answer before any change):**
```
1. What files will be touched?
2. What existing features could break?
3. How will it be tested?
Cannot answer all 3 → do not proceed.
```
 
| Type | Description | PLAN approval | Backup needed |
|---|---|---|---|
| **1 — Safe** | New thing, doesn't touch existing | Human reads plan.md, approves | No |
| **2 — Medium** | Modify existing function | Human reads plan.md, approves | Yes (.bak) |
| **3 — Breaking** | Architecture / format change | Human reads plan.md, approves | Yes + rollback plan |
 
---
 
## 🧠 MEMORY SYSTEM
 
All memory files live in `.agent/`. Create with empty schema if missing. Never delete.
 
### Short-Term Memory — `.agent/session_memory.json`
Tracks what the current session is doing. Written at every significant step.
Reset to empty at DOC phase completion.
 
```json
{
  "session_id": "2026-05-01-001",
  "started_at": "ISO8601",
  "task": "Translate chapter 12 of novel X",
  "current_step": "Stage 2: Refiner, chunk 7/23",
  "last_action": "Refiner.refine_full_text() → chunk 6 passed quality gate",
  "next_action": "Refiner.refine_full_text() → chunk 7",
  "open_files": ["src/agents/refiner.py"],
  "pending_decisions": [],
  "session_errors": [
    {
      "step": "chunk 4",
      "error": "OllamaTimeout",
      "resolved_by": "reduced chunk size + retry #1 succeeded"
    }
  ]
}
```
 
### Long-Term Memory — `.agent/long_term_memory.json`
Accumulates lessons across all sessions. Never reset. Written at DOC phase.
 
```json
{
  "last_updated": "ISO8601",
  "lessons": [
    {
      "date": "2026-05-01",
      "context": "Novel: GuDaoXianHong",
      "lesson": "qwen2.5:14b gives poor Myanmar literary quality for emotionally intense scenes at temp > 0.6",
      "action": "Always use temperature 0.45 for Stage 1, 0.35 for Stage 2 refinement"
    }
  ],
  "known_patterns": [
    {
      "pattern": "Quality score drops after chapter 20 in long novels",
      "cause": "Glossary grows too large → prompt exceeds context budget",
      "fix": "MemoryManager: enforce top_n=20 glossary terms after chapter 15"
    }
  ],
  "model_performance": {
    "qwen2.5:14b": { "avg_quality_score": 76.0, "chapters_tested": 20 },
    "qwen:7b":     { "avg_quality_score": 68.5, "chapters_tested": 15 }
  }
}
```
 
### Error Library — `.agent/error_library.json`
Known errors and their proven solutions. Agent checks this BEFORE retrying anything.

> **⚠️ DISK FILE IS AUTHORITATIVE.** The examples below are the initial schema only.
> The real file on disk currently has errors up to ERR-058. Always read `.agent/error_library.json`
> directly — do NOT rely on the template below for current error state.
 
```json
{
  "last_updated": "ISO8601",
  "errors": [
    {
      "id": "ERR-001",
      "error_type": "OllamaTimeout",
      "trigger": "Ollama response exceeds 300s timeout",
      "solution": "Reduce chunk size by 20% (e.g., 1500→1200 chars) and retry",
      "prevention": "Set chunk_size ≤ 1200 for models ≤ 7B parameters",
      "times_seen": 0,
      "last_seen": null
    },
    {
      "id": "ERR-002",
      "error_type": "LowMyanmarRatio",
      "trigger": "Myanmar char ratio < 70% after 3 retries — Claude translates idioms to English explanation instead",
      "solution": "Add to retry prompt: 'Do NOT explain. Translate the FEELING into Myanmar metaphor.'",
      "prevention": "Include this instruction in base system prompt for Stage 1",
      "times_seen": 0,
      "last_seen": null
    },
    {
      "id": "ERR-003",
      "error_type": "GlossaryNameMismatch",
      "trigger": "Model uses phonetic variant not in glossary",
      "solution": "Add variant as alias in glossary.json. Re-run postprocessor on saved file.",
      "prevention": "Inject glossary with strict instruction: 'Use EXACTLY these spellings. No variants.'",
      "times_seen": 0,
      "last_seen": null
    },
    {
      "id": "ERR-004",
      "error_type": "BengaliScriptLeak",
      "trigger": "Model outputs Bengali Unicode characters (U+0980–U+09FF) inside Myanmar text",
      "solution": "Run postprocessor regex to strip U+0980–U+09FF range. Flag chunk for re-translation.",
      "prevention": "Add to system prompt: 'Bengali script (U+0980–U+09FF) is STRICTLY FORBIDDEN. Myanmar Unicode only.'",
      "times_seen": 0,
      "last_seen": null
    },
    {
      "id": "ERR-005",
      "error_type": "ParagraphDuplication",
      "trigger": "chunk_overlap > 0 causes the same sentence at end of chunk N and start of chunk N+1 (overlap is now permanently disabled — ERR-005 is legacy)",
      "solution": "chunk_overlap is always 0. Use smart_chunk() from src/utils/chunker.py which never overlaps paragraphs. Boundary deduplication in postprocessor is defense-in-depth.",
      "prevention": "Chunker must split on paragraph boundaries only, never mid-paragraph by character count",
      "times_seen": 0,
      "last_seen": null
    },
    {
      "id": "ERR-006",
      "error_type": "OllamaOOM",
      "trigger": "Ollama crashes with out-of-memory on large chapters (> 2000 chars per chunk)",
      "solution": "Switch to smaller model (qwen:7b) for this chapter. Reduce chunk_size to 800.",
      "prevention": "Monitor GPU VRAM — if < 2GB free before chapter start, use qwen:7b automatically",
      "times_seen": 0,
      "last_seen": null
    }
  ]
}
```
 
### Context Compression Budget
```
Total Ollama prompt budget: ≤ 3000 tokens per call
  System instruction  : 400  tokens
  Glossary (top 20)   : 300  tokens  (LRU sorted by chapter recency)
  Rolling context     : 500  tokens  (last 3 chapter summaries ≤ 150 tok each)
  Current chunk       : 1500 tokens
  Output reserve      : 300  tokens
 
Enforcement: MemoryManager.get_top_n(n=20) hard cap. Never inject full glossary.
```

---

## 🛡 Code Drift Prevention (Mandatory)
 
> ဒီ rules ၃ ချက်မရှိရင် feature ထပ်ထည့်တိုင်း pipeline တဖြည်းဖြည်း ပျက်စီးမယ်။ Non-negotiable။
 
### 1. Modular Boundaries
 
တစ်ဖိုင်နဲ့တဖိုင် တိုက်ရိုက်မခေါ်ရ — `MemoryManager` ကိုသာ ဖြတ်ရမည်။
 
```
ALLOWED                             FORBIDDEN
──────────────────────────────      ──────────────────────────────
Translator → MemoryManager          Translator → glossary.json (direct)
Refiner    → MemoryManager          Checker    → context_memory.json (direct)
Checker    → MemoryManager          ContextUpdater → Translator (cross-agent)
```
 
**Rules:**
- Agent တစ်ခုက တစ်ခုကို import မလုပ်ရ (no cross-agent imports)
- Data files (`glossary.json`, `context_memory.json`) ကို `FileHandler` မဖြတ်ဘဲ မဖတ်ရ မရေးရ
- `MemoryManager` သည် data layer ၏ single gateway ဖြစ်သည်
### 2. Type Hints (Every function, no exceptions)
 
```python
# WRONG — drift ဖြစ်စေတဲ့ ပုံစံ
def translate(text, glossary, context):
    ...
 
# CORRECT — contract ရှင်းတယ်၊ AI မှားရေးဖို့ ခက်တယ်
def translate(
    text: str,
    glossary: dict[str, str],
    context: list[str],
) -> str:
    ...
```
 
**Required on:**
- All `src/agents/*.py` public methods
- All `src/memory/memory_manager.py` methods
- All `src/utils/*.py` methods
- Data models (use `TypedDict` or `dataclass`)
```python
# Data model example
from typing import TypedDict
 
class GlossaryTerm(TypedDict):
    id: str
    source: str
    target: str
    category: str        # "character" | "place" | "level" | "item"
    chapter_first_seen: int
    verified: bool
```
 
### 3. Automated Tests (Write test before or with code)
 
**Structure (259 tests, all passing — run `pytest tests/ -v --tb=short`):**
```
tests/
├── test_agents.py                   # Agent initialization and interface
├── test_chunker.py                  # smart_chunk(), get_rolling_context(), overlap=0
├── test_cn_mm_rules.py              # CN→MM linguistic rules
├── test_config.py                   # Config loading and validation
├── test_container.py                # Dependency injection container
├── test_glossary_sync.py            # Glossary sync agent
├── test_integration.py              # End-to-end: input → output file
├── test_json_extractor.py           # Safe JSON parsing
├── test_memory.py                   # add_term(), get_term(), FIFO, auto-approve
├── test_novel_v1.py                 # Full novel v1 workflow
├── test_pivot_stage2_guard.py       # EN guard — prevents English leaking into MM output
├── test_pivot_translator.py         # CN→EN→MM pivot workflow
├── test_postprocessor.py            # Script stripping, heading dedup, BOM handling
├── test_progress_logger.py          # Progress tracking
├── test_prompt_patch.py             # LANGUAGE_GUARD prompts
├── test_qa_tester.py                # QA validation agent
├── test_quality.py                  # Quality scoring
├── test_regression.py               # Regression suite
├── test_translation_reviewer.py     # 10+6 quality checks, fluency scorer
├── test_translator.py               # Translator.translate_paragraph()
├── test_workflow_routing.py         # way1/way2 auto-detection routing
└── test_translate/
    └── test_ch_en_mm_translation.py # Full chapter CN→EN→MM with log display
```
 
**Minimum test per function:**
 
```python
# test_memory_manager.py example
def test_new_term_goes_to_pending_not_glossary():
    mm = MemoryManager()
    mm.add_pending_term("新术语", "မြန်မာ", "item", chapter=5)
 
    assert mm.get_term("新术语") is None          # not in approved glossary
    pending = mm.get_pending_terms()
    assert any(t["source"] == "新术语" for t in pending)  # in pending only
 
def test_unknown_term_returns_placeholder():
    mm = MemoryManager()
    result = mm.get_term("未知词")
    assert result == "【?未知词?】"               # never None, never guessed
```
 
**Run before every commit:**
```bash
pytest tests/ -v --tb=short
```
 
**CI rule:** ဘယ် function အသစ်မဆို test မပါရင် Gemini reviewer က `NEEDS REVISION` ပြန်ရမည်။
 
---

## ✅ Best Practices

- **Never overwrite blindly:** Before any `glossary.json` update, `file_handler.py` creates a `.bak` backup automatically.
- **Category tagging:** Term Extractor must tag every new term (`character`, `place`, `level`, `item`). This enables targeted consistency checking per category.
- **Human-in-the-loop:** Review `glossary_pending.json` weekly. Approving terms keeps translation quality at 95%+.
- **Fallback rule:** If a term is missing from the glossary, the Translator must output `【?term?】` as a placeholder — never attempt a free-form guess. Placeholders are resolved in the next review cycle.
- **Atomic writes:** All JSON files are written atomically (temp file → rename) via `FileHandler` to prevent corruption on crash.
- **UTF-8-SIG encoding:** All file reads/writes use UTF-8-SIG to handle BOM characters correctly across platforms.

---
🔄 POST-IMPLEMENTATION GEMINI REVIEW WORKFLOW (MANDATORY)
⚠️ AFTER COMPLETING ANY TASK, YOU MUST EXECUTE THIS WORKFLOW BEFORE MARKING IT DONE.
DO NOT SKIP. DO NOT SUMMARIZE. OUTPUT ONLY THE REQUIRED BLOCKS.
 
STEP 0: LOAD GEMINI AGENT CONTEXT
Read `GEMINI.md` fully. It contains the official architecture boundaries, translation standards, and review protocols. You will now operate as the GEMINI REVIEW AGENT defined in that file. All checks must align with `GEMINI.md` rules.
 
STEP 1: REVIEWER A → Architecture & Logic Check (GEMINI AGENT MODE)
[ROLE] Senior Python Pipeline Engineer & Ollama Integration Specialist
[CONTEXT SOURCE] GEMINI.md → "Key Classes", "Mandatory Rules", "Code Drift Prevention"
[FOCUS] Type safety, error handling, chunking/memory leaks, glossary injection safety, non-breaking changes to main_fast.py & MemoryManager, test coverage gaps, strict adherence to Modular Boundaries (no cross-agent imports, MemoryManager gateway only).
[OUTPUT FORMAT] Strict text only (no markdown wrapping, no explanations):
=== REVIEWER A ===
STATUS: [PASS / FAIL]
ISSUES: [List exact issues or "None"]
RECOMMENDATIONS: [List fixes or "None"]
=== END REVIEWER A ===
 
STEP 2: REVIEWER B → Myanmar Translation & Quality Check (GEMINI AGENT MODE)
[ROLE] CN→MM Literary Translation Specialist & Wuxia/Xianxia Linguist
[CONTEXT SOURCE] GEMINI.md → "Translation Agent Prompts", "Memory & Glossary Systems", "Naming Rules"
[FOCUS] Glossary exact-match enforcement, SVO→SOV conversion, particle accuracy (သည်/ကို/မှာ), repetition loops, hallucinated names/terms, Markdown preservation, tone/register alignment, placeholder usage `【?term?】`, UTF-8-SIG consistency.
[MANDATORY CHECKS — each must explicitly PASS or FAIL]:
  ✓ SVO→SOV: No English/Chinese sentence order survived into Myanmar output
  ✓ Particle repetition: same particle appears ≤ 2× per paragraph
  ✓ Archaic words: သင်သည် / ဤ / ထို must NOT appear — use မင်း / ဒီ / အဲဒီ
  ✓ Bengali script block: U+0980–U+09FF character count = 0
  ✓ Placeholder guard: 【?term?】 tokens are preserved exactly, never resolved or guessed
  ✓ Paragraph duplication: no sentence appears at end of chunk N AND start of chunk N+1
  ✓ Dialogue pronouns: မင်း / ရှင် / ကျွန်တော် match character status hierarchy
  ✓ LLM quality score ≥ 70 (QualityAgent result from VERIFY phase)
[OUTPUT FORMAT] Strict text only (no markdown wrapping, no explanations):
=== REVIEWER B ===
STATUS: [PASS / FAIL]
ISSUES: [List exact issues or "None"]
RECOMMENDATIONS: [List fixes or "None"]
=== END REVIEWER B ===
 
STEP 3: CONSENSUS & SELF-CORRECTION LOOP
- Compare both STATUS values.
- If BOTH = PASS → Go to STEP 4.
- If EITHER = FAIL → Extract ALL ISSUES. Fix them in your code/output internally. Re-run STEP 1 & STEP 2 with the corrected version. (Max 2 retry cycles).
- If still failing after 2 retries → Skip to STEP 4 and mark REVISION_NEEDED.
STEP 4: FINAL STATUS & COMMIT GATE
Output EXACTLY ONE line. No extra text. No markdown.
FINAL_STATUS: READY_TO_COMMIT
or
FINAL_STATUS: REVISION_NEEDED
 
STEP 5: AUTO-COMMIT PROTOCOL (IF READY_TO_COMMIT)
- Run: git status --porcelain
- If changes exist → git add . && git commit -m "feat: <task_name> - <1-sentence summary>"
- Output: "✅ COMMIT_SUCCESS: <commit_hash_short>"
- If no changes → Output: "⚠️ SKIP_COMMIT: No file changes."
STEP 6: SESSION UPDATE
1. Update CURRENT_STATE.md with: task name, UTC timestamp, FINAL_STATUS
2. Update .agent/session_memory.json: mark step complete, clear current_step
3. If any new error type was encountered: add to .agent/error_library.json
4. If any lesson was learned: add to .agent/long_term_memory.json
5. Advance .agent/phase_gate.json to next phase
6. ONLY THEN output: ✅ TASK COMPLETE
## 🚫 HARD CONSTRAINTS
 
1. Never save a chapter with Myanmar ratio < 70% to `data/output/`.
2. Never save a chapter with LLM quality score < 70 to `data/output/`.
3. Never pass full chapter text as context — compressed summaries only (≤ 3000 token budget).
4. Never skip DOC phase — CHANGELOG must always be updated.
5. Never start BUILD without user "approve" on `plan.md`.
6. Always consult `.agent/error_library.json` before retrying a known error type.
7. Always write session state to `.agent/session_memory.json` before ending a session.
8. Always add new error patterns to `.agent/error_library.json` at DOC phase.
9. Never write to `data/glossary.json` directly — use `FileHandler` atomic write only.
10. Never create a file in `src/` not listed in the architecture tree without a PLAN phase.
---


## 🖥 CLI Usage

```bash
# Translate a single chapter (auto-detects way1 or way2)
python -m src.main --novel reverend-insanity --chapter 1

# Translate all chapters
python -m src.main --novel reverend-insanity --all

# Translate from a specific chapter onwards
python -m src.main --novel reverend-insanity --all --start 5

# Translate a chapter range
python -m src.main --novel reverend-insanity --chapter-range 9-15

# Run quality review on an existing translated file
python -m src.main --novel reverend-insanity --review data/output/reverend-insanity/reverend-insanity_chapter_0001.mm.md

# View a translated file in the terminal (Markdown reader)
python -m src.main --novel reverend-insanity --view data/output/reverend-insanity/reverend-insanity_chapter_0001.mm.md

# Rebuild the cumulative meta.json from all chapter files
python -m src.main --novel reverend-insanity --rebuild-meta

# Launch Streamlit Web UI
python -m src.main --ui

# Clean Python cache (if model behaves unexpectedly after code changes)
python -m src.main --clean

# Force way2 (CN→EN→MM pivot) explicitly
python -m src.main --novel reverend-insanity --chapter 1 --config config/settings.pivot.yaml
```
