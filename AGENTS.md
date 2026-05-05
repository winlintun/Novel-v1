# AGENTS.md

## Mandatory Session Protocol

These steps run automatically at the start and end of every session.

### Session Start

Perform these steps before making code changes:

```text
STEP 1: Read AGENTS.md
STEP 2: Read GEMINI.md
STEP 3: Read .agent/phase_gate.json
STEP 4: Read .agent/session_memory.json
STEP 5: Read .agent/long_term_memory.json
STEP 6: Read .agent/error_library.json
STEP 7: Read CURRENT_STATE.md
STEP 8: Read ERROR_LOG.md
STEP 9: Confirm the requested task does not conflict with CURRENT_STATE.md
STEP 10: Begin implementation, debugging, or investigation
```

If any required file is missing, create it using the schema in this document.

### Session End

Run these steps after any meaningful code or architecture change:

```text
STEP 1: Update CURRENT_STATE.md
STEP 2: Update ERROR_LOG.md if a new error, root cause, or fix was found
STEP 3: Run linter: ruff check src/ tests/ --select=E,F
STEP 4: Run relevant tests: pytest tests/ -v
STEP 5: Leave the repository in a resumable state for the next agent
```

### Trigger Conditions For Session-End Updates

Session-end updates are required when any of the following happens:

- A file in `src/`, `tests/`, `ui/`, `scripts/`, or config files was modified
- A bug was reproduced, investigated, fixed, or partially fixed
- A feature was implemented or behavior was changed
- A design or architecture decision was made

---

## Agent Role

The agent is a coding operator for this repository.

Primary responsibilities:

- Implement requested features
- Fix errors and regressions
- Debug failing behavior
- Add or adjust targeted tests
- Keep project state documentation accurate

Non-goals unless explicitly requested:

- Large product redesigns
- Broad architectural rewrites
- Unrelated cleanup
- Speculative refactors with no task-driven reason

---

## Core Working Rules

### 1. Solve The Requested Problem

- Work on the task the user asked for.
- Prefer a minimal correct fix over a broad rewrite.
- Do not drift into unrelated project work.

### 2. Debug From Evidence

- Reproduce first when possible.
- Read the relevant code before editing.
- Identify the root cause, not just the visible symptom.
- If the cause is still uncertain, state the uncertainty and reduce risk with tests or guards.

### 3. Keep Changes Local

- Touch the smallest reasonable set of files.
- Preserve existing APIs unless the task requires changing them.
- Do not rename stable modules, classes, or commands without a concrete reason.

### 4. Verify Before Declaring Success

- Run the narrowest useful verification first.
- Prefer targeted tests for the changed area.
- If no automated test exists, document the manual verification performed.
- If verification could not be run, state that clearly.

### 5. Do Not Corrupt User Work

- Never revert user changes you did not make unless explicitly asked.
- Never use destructive git commands unless explicitly approved.
- If the worktree contains unrelated edits, work around them carefully.

---

## Standard Execution Workflow

Use this sequence for most tasks:

```text
1. Read the relevant docs and state files
2. Inspect the relevant code paths
3. Reproduce the bug or understand the requested behavior
4. Trace the root cause
5. Implement the fix or requested change
6. Add or update tests when appropriate
7. Run verification
8. Update CURRENT_STATE.md and ERROR_LOG.md as needed
9. Report outcome, verification, and remaining risks
```

---

## Debugging Rules

When fixing an error or regression:

- Capture the failing command, test, log message, or stack trace when possible.
- Prefer fixing the real source of the bug instead of adding a shallow workaround.
- Add defensive handling only when it improves correctness, not to hide failures.
- When external systems are involved, ensure failures are surfaced with clear messages.
- Avoid infinite retries, hidden fallback loops, or silent exception swallowing.

### Required Debug Output Quality

Any bug fix should answer these questions in notes, docs, commit summary, or final response:

- What failed?
- Where did it fail?
- Why did it fail?
- What changed to fix it?
- How was the fix verified?

---

## Code Change Rules

### Safety

- Prefer explicit error handling around file I/O, parsing, network calls, subprocesses, and external services.
- Use bounded retries with clear exit conditions where retry behavior exists.
- Avoid hidden mutable global state.
- Keep timeouts explicit for external or long-running operations when the codebase already supports them.

### Style

- Match the existing style of the repository.
- Reuse existing helpers before adding new abstractions.
- Add short comments only where the logic is not obvious.
- Do not add boilerplate abstractions without a demonstrated need.

### Tests

- Add tests for bug fixes when the repository already has a relevant test location and pattern.
- Prefer small focused tests tied to the changed behavior.
- Do not rewrite large test suites unless required by the task.

---

## File And State Management

The following files are part of the shared agent handoff system:

- `CURRENT_STATE.md`
- `ERROR_LOG.md`
- `.agent/phase_gate.json`
- `.agent/session_memory.json`
- `.agent/long_term_memory.json`
- `.agent/error_library.json`

Keep them current enough that another agent can continue without asking for basic context.

### CURRENT_STATE.md Expectations

Update when behavior or task status changes.

Track at minimum:

- Last updated date
- Last completed task
- Current in-progress work
- Known blockers
- Architecture or workflow decisions that matter for future work

### ERROR_LOG.md Expectations

Update when a real issue is discovered or resolved.

Track at minimum:

- Error ID or short title
- Date
- Files involved
- Symptom
- Root cause
- Fix
- Status
- Verification

---

## 🔒 STABILITY FIRST — Non-Negotiable (Read Before Any Code)

> **This section is a prerequisite.**
> Before adding any new feature, the agent MUST verify every check in this
> section passes. If even one check fails — stop, fix it, verify again, then proceed.
> No exceptions. No "I'll fix it later."

---

## 🛡 Code Drift Prevention (Mandatory)

These rules exist to prevent gradual architecture decay. They apply to every change, including small bug fixes.

### 1. Respect Module Boundaries

Allowed data flow:

```text
Agent/CLI/UI -> service/helper -> MemoryManager/FileHandler -> disk
```

Forbidden patterns:

- Agent modules reading or writing glossary, context, or session JSON files directly
- Cross-agent coupling that bypasses shared helpers or state managers
- New code paths that duplicate logic already owned by `src/memory/`, `src/utils/`, or existing CLI modules

Required behavior:

- Use `MemoryManager` for glossary/context state access
- Use `FileHandler` or existing repository file utilities for persistent writes
- Prefer extending an existing module over creating a parallel implementation

### 2. Preserve Stable Interfaces

- Do not rename public modules, classes, methods, CLI flags, or config keys without a task-driven reason
- If behavior changes, keep the existing call shape when possible and add guards or adapters instead of breaking callers
- If a breaking change is unavoidable, document the impact in `CURRENT_STATE.md` and include a rollback plan

### 3. Match Existing Patterns

- Reuse current repository patterns for config loading, path handling, logging, tests, and error handling
- Keep new abstractions small and justified by the task
- Prefer typed, explicit parameters over hidden state or side-channel behavior
- Do not introduce a second way to do the same thing unless the old path is being actively replaced

### 4. Protect Verification Coverage

- Any behavior change should have the narrowest useful verification step
- If the repo already has a relevant test file, update or extend it instead of relying only on manual checks
- If no test is added, state why and document the manual verification performed

### 5. Document Decisions That Affect Future Agents

- Update `CURRENT_STATE.md` when workflow, architecture, or task status changes
- Update `ERROR_LOG.md` when a real bug, root cause, or fix is identified
- Update `.agent/session_memory.json` so the next agent can resume without rediscovering context

---

## 🚦 PHASE GATE SYSTEM

Every feature or bug fix follows this lifecycle. No shortcuts.

| Phase      | Runner                | Trigger               | Auto or Manual                            |
| ---------- | --------------------- | --------------------- | ----------------------------------------- |
| **PLAN**   | Agent                 | User requests feature | ⛔ **USER MUST APPROVE** `.agent/plan.md` |
| **BUILD**  | Agent                 | User says "approve"   | ✅ AUTO                                   |
| **TEST**   | Agent                 | BUILD completes       | ✅ AUTO                                   |
| **VERIFY** | QualityAgent (Ollama) | TEST passes           | ✅ AUTO (score-gated)                     |
| **AUDIT**  | Gemini Code Reviewer  | VERIFY passes         | ✅ AUTO                                   |
| **DOC**    | Agent                 | AUDIT passes          | ✅ AUTO — **never skip**                  |

### Feature Change Protocol

**3 Questions (answer before any change):**

```
1. What files will be touched?
2. What existing features could break?
3. How will it be tested?
Cannot answer all 3 → do not proceed.
```

| Type             | Description                       | PLAN approval                 | Backup needed       |
| ---------------- | --------------------------------- | ----------------------------- | ------------------- |
| **1 — Safe**     | New thing, doesn't touch existing | Human reads plan.md, approves | No                  |
| **2 — Medium**   | Modify existing function          | Human reads plan.md, approves | Yes (.bak)          |
| **3 — Breaking** | Architecture / format change      | Human reads plan.md, approves | Yes + rollback plan |

---

## 🧠 MEMORY SYSTEM

All memory files live in `.agent/`. Create with empty schema if missing. Never delete.

### phase_gate.json Schema (`.agent/phase_gate.json`)

```json
{
  "current_phase": "BUILD",
  "task": "",
  "updated_at": "",
  "phases": {
    "PLAN": { "status": "PENDING" },
    "BUILD": { "status": "PENDING" },
    "TEST": { "status": "PENDING" },
    "VERIFY": { "status": "PENDING" },
    "DOC": { "status": "PENDING" }
  }
}
```

### Short-Term Memory — `.agent/session_memory.json`

Tracks what the current session is doing. Written at every significant step.
Reset to empty at DOC phase completion.

```json
{
  "session_id": "",
  "started_at": "",
  "task": "",
  "current_step": "",
  "last_action": "",
  "next_action": "",
  "open_files": [],
  "pending_decisions": [],
  "session_errors": []
}
```

### Long-Term Memory — `.agent/long_term_memory.json`

Accumulates lessons across all sessions. Never reset. Written at DOC phase.

```json
{
  "last_updated": "",
  "lessons": [],
  "known_patterns": []
}
```

### Error Library — `.agent/error_library.json`

Known errors and their proven solutions. Agent checks this BEFORE retrying anything.

> **⚠️ DISK FILE IS AUTHORITATIVE.** The examples below are the initial schema only.
> The real file on disk currently has errors up to ERR-058. Always read `.agent/error_library.json`
> directly — do NOT rely on the template below for current error state.

```json
{
  "last_updated": "",
  "errors": []
}
```

### `CURRENT_STATE.md`

```markdown
# CURRENT_STATE.md

## Last Updated

- Date:
- Last task completed:

## In Progress

- None

## Known Issues

- None

## Architecture Decisions

- None
```

### `ERROR_LOG.md`

```markdown
# ERROR_LOG.md

## Errors

- None
```

---

## Decision Guidelines

When multiple valid approaches exist:

1. Choose the option with the lowest regression risk.
2. Choose the smallest change that fully solves the problem.
3. Prefer patterns already used in the repository.
4. Prefer maintainability over cleverness.
5. If a tradeoff remains, document it briefly.

---

## 🔄 POST-IMPLEMENTATION GEMINI REVIEW WORKFLOW (MANDATORY)

After completing any meaningful implementation or bug fix, run this workflow before declaring the task complete.

### Step 0: Load Gemini Context

- Re-read `GEMINI.md`
- Re-check `CURRENT_STATE.md`, `.agent/phase_gate.json`, and the files you changed
- Confirm the change still fits the repository architecture and current task state

### Step 1: Reviewer A — Architecture And Logic Check

Role:

- Senior Python and repository architecture reviewer

Focus:

- Regression risk in touched modules
- API compatibility and call-site safety
- Error handling, state flow, and file I/O correctness
- Whether the change violated Code Drift Prevention rules
- Whether tests and verification are adequate for the scope

Required output format:

```text
=== REVIEWER A ===
STATUS: PASS | FAIL
ISSUES:
- ...
RECOMMENDATIONS:
- ...
=== END REVIEWER A ===
```

If there are no issues, write `None` under both `ISSUES` and `RECOMMENDATIONS`.

### Step 2: Reviewer B — Behavior And Quality Check

Role:

- Feature/bugfix behavior reviewer focused on user-visible correctness

Focus:

- Whether the requested behavior now works
- Whether edge cases or failure paths remain exposed
- Whether docs, prompts, configs, or UX-facing text still match actual behavior
- Whether verification proves the fix instead of only exercising happy paths

Required output format:

```text
=== REVIEWER B ===
STATUS: PASS | FAIL
ISSUES:
- ...
RECOMMENDATIONS:
- ...
=== END REVIEWER B ===
```

If there are no issues, write `None` under both `ISSUES` and `RECOMMENDATIONS`.

### Step 3: Consensus And Self-Correction Loop

- If both reviewers pass, continue to Step 4
- If either reviewer fails, fix the issues and re-run the review
- Repeat until the result is `READY_TO_COMMIT` or the remaining risk is explicitly documented

### Step 4: Final Gate

Use exactly one of these outcomes:

```text
FINAL_STATUS: READY_TO_COMMIT
```

or

```text
FINAL_STATUS: REVISION_NEEDED
```

### Step 5: Auto-commit protocol (If `READY_TO_COMMIT`)

- Run: git status --porcelain
- If changes exist → git add . && git commit -m "feat: <task_name> - <1-sentence summary>"
- Output: "COMMIT_SUCCESS: <commit_hash_short>"
- If no changes → Output: "SKIP_COMMIT: No file changes."

### Step 6: Session Update

Before closing the task:

- Update `CURRENT_STATE.md`
- Update `ERROR_LOG.md` if needed
- Update `.agent/session_memory.json`
- Update `.agent/error_library.json` and `.agent/long_term_memory.json` when new durable knowledge was discovered
- Leave the repository in a resumable state

---

## Completion Standard

A task is complete when all of the following are true:

- The requested code or documentation change is implemented
- The relevant failure is fixed or the requested behavior exists
- Verification was run, or inability to verify was stated clearly
- `CURRENT_STATE.md` and `ERROR_LOG.md` were updated when required
- The repository is left in a state another agent can continue from

## Quick Commands

Run from project root:

```bash
# Show available commands
python -m src.main --help

# Translate - see --help for options
python -m src.main --novel wayfarer --chapter 1
python -m src.main --novel wayfarer --chapter-range 1-10

# Tests
pytest tests/ -v
ruff check src/ tests/ --select=E,F

# Web UI
streamlit run ui/streamlit_app.py
```

## Important Notes

- **Ollama required**: Must have `ollama` running locally with `padauk-gemma:q8_0` model pulled before translation works
- **Config variants**: Use `--config config/settings.pivot.yaml` for Chinese→English→Myanmar pivot workflow, `--config config/settings.fast.yaml` for CPU-only mode
- **Glossary persistence**: Per-novel glossary lives in `data/output/{novel}/glossary/glossary.json` — edits here persist across sessions
- **Agent memory**: Files in `.agent/` (phase_gate.json, session_memory.json, long_term_memory.json, error_library.json) are managed by the agent system, do not edit manually
- **Output location**: Translated chapters go to `data/output/{novel}/{novel}_chapter_N.mm.md`

## Architecture

- 6-stage pipeline: Translate → Refine → Reflect → Quality Check → Consistency → QA
- 3-tier memory: Glossary (persistent) + Context (FIFO per-chapter) + Pending (unreviewed)
- Entry point: `src/main.py` CLI module

## Testing

- run with `pytest tests/ -v`
- Lint with `ruff check src/ tests/ --select=E,F`
