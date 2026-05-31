# AGENTS.md - OpenCode AI Agent Working Rules

This file defines how a coding agent should operate in this repository.
Its purpose is practical: write code, fix bugs, debug failures, verify changes,
and keep shared project state files current.

---

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
STEP 3: Verify the change with the most relevant tests, checks, or reproduction steps available
STEP 4: Leave the repository in a resumable state for the next agent
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

## Minimal Schemas For Missing Files

Create these if missing.

### `.agent/phase_gate.json`

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

### `.agent/session_memory.json`

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

### `.agent/long_term_memory.json`

```json
{
  "last_updated": "",
  "lessons": [],
  "known_patterns": []
}
```

### `.agent/error_library.json`

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

## Completion Standard

A task is complete when all of the following are true:

- The requested code or documentation change is implemented
- The relevant failure is fixed or the requested behavior exists
- Verification was run, or inability to verify was stated clearly
- `CURRENT_STATE.md` and `ERROR_LOG.md` were updated when required
- The repository is left in a state another agent can continue from

---

## Summary

This repository's agent contract is simple:

- Read context first
- Change only what is needed
- Debug from evidence
- Verify the result
- Update shared state files
- Leave clear handoff context
