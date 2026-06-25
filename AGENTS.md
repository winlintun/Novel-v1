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


---

## 🛡 Code Drift Prevention (Mandatory)
 
> ဒီ rules ၃ ချက်မရှိရင် feature ထပ်ထည့်တိုင်း pipeline တဖြည်းဖြည်း ပျက်စီးမယ်။ Non-negotiable။
 
### 1. Modular Boundaries
 
တစ်ဖိုင်နဲ့တဖိုင် တိုက်ရိုက်မခေါ်ရ — `MemoryManager` ကိုသာ ဖြတ်ရမည်။
 
```
ALLOWED                             FORBIDDEN
──────────────────────────────      ──────────────────────────────
Translator → MemoryManager          Translator → glossary_terms database table (direct)
Refiner    → MemoryManager          Checker    → context_memory.json (direct)
Checker    → MemoryManager          ContextUpdater → Translator (cross-agent)
```
 
**Rules:**
- Agent တစ်ခုက တစ်ခုကို import မလုပ်ရ (no cross-agent imports)
- Data files (`glossary_terms database table`, `context_memory.json`) ကို `FileHandler` မဖြတ်ဘဲ မဖတ်ရ မရေးရ
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
 
**Structure (441 tests, all passing — run `pytest tests/ -v --tb=short`):**
```
tests/
├── test_agents.py                   # Agent initialization and interface
├── test_chunker.py                  # smart_chunk(), get_rolling_context(), overlap=0
├── test_cn_mm_rules.py              # CN→MM linguistic rules
├── test_config.py                   # Config loading and validation
├── test_cultural_injector.py        # Runtime cultural rule injection
├── test_db_migrator.py              # Database migration
├── test_db_repositories.py          # DB repository pattern
├── test_db_schema.py                # DB schema management
├── test_glossary_generator.py       # Glossary generation
├── test_integration.py              # End-to-end: input → output file
├── test_json_extractor.py           # Safe JSON parsing
├── test_memory.py                   # add_term(), get_term(), FIFO, auto-approve
├── test_memory_sql.py               # MemoryManager SQL backend
├── test_model_registry.py           # Model performance tracking
├── test_myanmar_quality_checker.py  # Myanmar linguistic validation
├── test_novel_v1.py                 # Full novel v1 workflow
├── test_postprocessor.py            # Script stripping, heading dedup, BOM handling
├── test_progress_logger.py          # Progress tracking
├── test_qa_tester.py                # QA validation agent
├── test_quality.py                  # Quality scoring
├── test_reflection_agent.py         # Self-correction agent
├── test_sync_external.py            # External glossary sync
├── test_training.py                 # Dataset loading, splitting, adapter paths
├── test_translation_reviewer.py     # 10+6 quality checks, fluency scorer
├── test_translator.py               # Translator.translate_paragraph()
├── test_versioning.py               # Chapter version tracking
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

## 🎯 TRANSLATION QUALITY LESSONS (hard-won — do not re-learn)

1. **PROMPT BUDGET IS SCARCE on the 8B local model — subtract, don't add.**
   Stacking signal into the prompt (glossary terms, RAG examples, rule blocks,
   collocations) past ~3–4 strong cues *degrades* overall coherence (content
   loss, garbled spellings, dialogue slips) even while it fixes individual terms.
   Measured: auto-review fell 98→95→93 as each layer was added; de-crowding
   (glossary injection 20→8/chunk, RAG 5→3) recovered it. Defaults reflect this —
   `rag.top_k: 3`, glossary injection capped at 8/chunk in
   `MemoryManager.get_all_memory_for_prompt`. **The durable path to human-like
   output is fine-tuning on the 83k-pair corpus, NOT a heavier prompt.**
2. **The auto-review score is NOT a quality gauge.** It is fluency/ratio-based and
   has scored corrupted output 100/100 while missing register mixing, mid-syllable
   Latin leaks, and content loss. Verify the actual *text* (and the BGE-M3 adequacy
   score), not the headline number.
3. **Glossary novel_id must match the translated slug.** The slug `a-will-eternal1`
   resolves to novel_id `novel_a_will_eternal1`; the rich glossary lived under the
   sibling `novel_a_will_eternal` (no trailing 1), so the pipeline read an empty
   glossary and mangled every name. Before blaming the model for bad names/places,
   confirm the glossary actually exists under the resolved novel_id.
---

