# GEMINI.md - Project Context for Gemini AI

---

> **This file is a quick reference.** For full agent instructions, see **AGENTS.md**.

---

## ⚡ MANDATORY SESSION PROTOCOL

### SESSION START
```
1. Read GEMINI.md (this file)
2. Read AGENTS.md (full instructions)
3. Read CURRENT_STATE.md
4. Check Architecture Decisions in CURRENT_STATE.md
5. Begin task
```

### SESSION END (after every task)
```
1. Update CURRENT_STATE.md
2. Update ERROR_LOG.md if new error found
3. Run code review: ruff check src/ tests/ --select=E,F
4. Run tests: pytest tests/ -v
5. Leave repo in resumable state
```

---

## Quick Reference

| Item | Path/Command |
|------|--------------|
| Main entry | `python -m src.main --help` |
| Translate | `python -m src.main --novel X --chapter 1` |
| Tests | `pytest tests/ -v` |
| Lint | `ruff check src/ tests/ --select=E,F` |
| Web UI | `streamlit run ui/streamlit_app.py` |

---

## Key Rules (from AGENTS.md)

1. **Before any code:** Read `CURRENT_STATE.md`
2. **Never invent new file paths** — use paths defined in AGENTS.md
3. **After any change:** Run code review workflow
4. **When done:** Update CURRENT_STATE.md → mark task `[DONE]`

---

## File Path Reference

See **AGENTS.md → Directory Structure** for complete paths.

---

## Code Review Workflow

Per AGENTS.md, after implementation:
1. Reviewer A: Architecture + Logic (regression risk, API safety)
2. Reviewer B: Behavior + Quality (does requested behavior work?)
3. Fix any issues until `FINAL_STATUS: READY_TO_COMMIT`

See **AGENTS.md → POST-IMPLEMENTATION GEMINI REVIEW WORKFLOW** for full details.