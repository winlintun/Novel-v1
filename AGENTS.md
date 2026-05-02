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
| tests/test_stability.py all pass | ❌ / ✅ | YYYY-MM-DD | (or equivalent coverage in existing tests) |
| src/exceptions.py exists | ❌ / ✅ | YYYY-MM-DD | |
| src/utils/ollama_client.py exists | ❌ / ✅ | YYYY-MM-DD | |
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

This project is an advanced, AI-powered **Chinese-to-Myanmar (Burmese) novel translation system** specializing in Wuxia/Xianxia novels. It uses a multi-stage agent pipeline to translate web novels while preserving tone, style, literary depth, and strict terminology consistency.

---

## 🏗 System Architecture & Pipeline

The translation process follows a strict 6-stage pipeline orchestrated by `src/pipeline/orchestrator.py`:

```
src/main.py (thin dispatcher)
  → src/cli/parser.py (parse arguments)
  → src/cli/commands.py (route to command)
  → src/pipeline/orchestrator.py (TranslationPipeline)
    → Load config/settings.yaml (via src/config/loader.py)
    → Initialize MemoryManager (load glossary.json, context_memory.json)
    → Preprocessor.load_and_preprocess()  → Chunks
    → Translator.translate_chunks()        → Stage 1: Raw translation
    → Refiner.refine_full_text()           → Stage 2: Literary editing
    → ReflectionAgent.reflect_and_improve() → Stage 3: Self-correction
    → MyanmarQualityChecker.check_quality() → Stage 4: Linguistic validation
    → Checker.check_chapter()             → Stage 5: Consistency check
    → QA Review                           → Stage 6: Final QA
    → TermExtractor (post-chapter)        → Extract new terms → glossary_pending.json
    → GlossaryGenerator (optional/pre)    → Auto-extract terms from novel source
    → FileHandler.write_text()            → Save to data/output/
    → ContextUpdater.process_chapter()    → Update glossary.json, context_memory.json
```

**Note:** As of v2.0, the monolithic `main.py` has been refactored into modular components under `src/cli/`, `src/pipeline/`, `src/config/`, `src/core/`, and `src/types/`.

1. **Preprocess:** Clean and normalize input text, split into paragraph-safe chunks with `smart_chunk()` (no overlap).
2. **Context & Glossary Loading:**
   - `MemoryManager`: 3-tier memory system (Glossary → Context → Session rules).
   - `data/glossary.json`: Enforces strict terminology consistency.
   - `data/context_memory.json`: Remembers ongoing story and character relationships.
3. **Translate (Stage 1):** Translator Agent produces an accurate, literal translation.
4. **Edit (Stage 2):** Editor Agent rewrites for natural flow and literary quality.
5. **Reflection (Stage 3):** Reflection Agent performs self-critique and improves the translation iteratively.
6. **Myanmar Quality Check (Stage 4):** Custom checker validates tone, naturalness, and particle accuracy.
7. **Consistency Check (Stage 5):** Consistency Checker verifies all terms against the glossary.
8. **QA Review (Stage 6):** Final Reviewer validates logical flow, tone, and formatting.
9. **Term Extraction (Post-Chapter):** Term Extractor scans for new proper nouns and routes them to `glossary_pending.json` for human review.
10. **Assemble:** Save to `data/output/`.

---

## 🤖 AI Agent Roles & System Prompts

### 1. Translator Agent (Stage 1)

**Goal:** Produce a complete, accurate translation. Convert Chinese SVO to Myanmar SOV. Do not summarize or skip sentences.

```text
You are an expert Chinese-to-Myanmar literary translator specializing in Wuxia/Xianxia novels.

STRICT RULES:
1. SYNTAX: Convert Chinese SVO structure to natural Myanmar SOV order. Do NOT translate word-by-word.
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
| 1 | Glossary | `data/glossary.json` | Persistent across all chapters |
| 2 | Context | `data/context_memory.json` + FIFO buffer | Slides per chapter |
| 3 | Session Rules | Runtime only | Current session only |

### Glossary Schema (`data/glossary.json`)

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

### Pending Glossary Schema (`data/glossary_pending.json`)

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

### Context Manager (`data/context_memory.json`)

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

```yaml
models:
  translator: "padauk-gemma:q8_0"   # Primary MM output model (current default)
  editor: "padauk-gemma:q8_0"       # Current default
  checker: "qwen:7b"                # Fast validation
  ollama_base_url: "http://localhost:11434"
  timeout: 300

processing:
  chunk_size: 1500
  max_retries: 2
  temperature: 0.2            # Current stable setting for padauk-gemma
  top_p: 0.95
  top_k: 40
  repeat_penalty: 1.15
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
│   └── settings.yaml
├── data/
│   ├── input/                    # Chinese chapter files (*.md)
│   ├── output/                   # Myanmar translations (*.md)
│   ├── glossary.json             # Approved terminology database
│   ├── glossary_pending.json     # New terms awaiting human review
│   └── context_memory.json       # Dynamic chapter context
├── logs/
│   └── translation.log
├── src/
│   ├── agents/
│   │   ├── preprocessor.py       # Chunking and markdown cleaning
│   │   ├── translator.py         # Stage 1: CN→MM translation
│   │   ├── refiner.py            # Stage 2: Literary editing
│   │   ├── checker.py            # Stage 3 & 4: QA validation
│   │   ├── reflection_agent.py   # Self-correction agent
│   │   ├── myanmar_quality_checker.py  # Linguistic validation
│   │   ├── qa_tester.py          # QA validation agent
│   │   └── context_updater.py    # Term extraction and memory updates
│   ├── cli/                      # NEW: CLI module (refactored from main.py)
│   │   ├── parser.py             # Argument parsing
│   │   ├── formatters.py         # Output formatting
│   │   └── commands.py           # Command handlers
│   ├── config/                   # NEW: Configuration module
│   │   ├── models.py             # Pydantic config models
│   │   └── loader.py             # Config loading with validation
│   ├── core/                     # NEW: Core functionality
│   │   └── container.py          # Dependency injection container
│   ├── memory/
│   │   └── memory_manager.py     # 3-tier memory system
│   ├── pipeline/                 # NEW: Pipeline orchestration
│   │   └── orchestrator.py       # TranslationPipeline coordinator
│   ├── types/                    # NEW: Type definitions
│   │   └── definitions.py        # TypedDict for data structures
│   ├── utils/
│   │   ├── ollama_client.py      # Ollama API wrapper
│   │   ├── file_handler.py       # File I/O (UTF-8-SIG, atomic writes)
│   │   └── postprocessor.py      # Output cleaning
│   ├── web/                      # NEW: Web UI launcher
│   │   └── launcher.py           # Streamlit launcher
│   ├── exceptions.py             # NEW: Exception hierarchy
│   └── main.py                   # Entry point (thin dispatcher)
├── tests/
│   ├── test_translator.py
│   ├── test_workflow_routing.py
│   └── test_integration.py
├── requirements.txt
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
 
**Structure:**
```
tests/
├── test_translator.py       # Translator.translate_paragraph()
├── test_refiner.py          # Refiner.refine_paragraph()
├── test_checker.py          # Checker.check_chapter(), quality score
├── test_memory_manager.py   # add_term(), get_term(), FIFO buffer
├── test_context_updater.py  # extract_entities(), pending glossary routing
├── test_file_handler.py     # atomic write, UTF-8-SIG, .bak backup
├── test_workflow_routing.py # way1/way2 workflow resolution
├── test_config.py           # Config loading and validation (add me)
├── test_pipeline.py         # Pipeline orchestration (add me)
└── test_integration.py      # End-to-end: input → output file
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
# Translate a single chapter
python -m src.main --novel 古道仙鸿 --chapter 1

# Translate all chapters
python -m src.main --novel 古道仙鸿 --all

# Translate from a specific chapter onwards
python -m src.main --novel 古道仙鸿 --all --start 5

# Skip Stage 2 refinement (faster, lower quality)
python -m src.main --novel 古道仙鸿 --chapter 1 --skip-refinement
```
