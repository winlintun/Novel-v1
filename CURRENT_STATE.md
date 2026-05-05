# CURRENT_STATE.md - Implementation Progress

> **FOR AI AGENTS:** Read this file before any code. Full error history: see ERROR_LOG.md.

---

## Last Updated
- Date: 2026-05-06
- Last task completed: Refactored web UI from Streamlit to Flask - new Flask app with 6 templates, updated launcher to support both Flask and Streamlit, added Flask to requirements.txt

## In Progress
- None

## Known Issues
- None

## Architecture Decisions
- Extracted regex patterns from postprocessor.py to src/utils/postprocessor_patterns.py for better organization
- Added pattern imports to translation_reviewer.py to reduce duplication
- All 412 tests pass, 53% coverage

---

## Quick Reference

| Item | Command |
|------|---------|
| Tests | `pytest tests/ -v` |
| Lint | `ruff check src/ tests/ --select=E,F` |
| Web UI | `streamlit run ui/streamlit_app.py` |

---

## Notes

- For full task history (2024-2025), see ERROR_LOG.md
- AGENTS.md has complete session protocol
- GEMINI.md is a quick reference pointing to AGENTS.md
- 365 tests running (updated from 282 in previous docs)
- 49% test coverage
- ruff.toml added to manage E501 line-length ignores for regex-heavy files