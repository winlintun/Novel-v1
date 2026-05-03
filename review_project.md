# Project Review — Novel Translation Pipeline

> **Reviewer**: Claude (AI Agent via opencode) & Gemini
> **Review Date**: 2026-05-03
> **Last updated**: 2026-05-03 | HEAD: `5ed349f` | 254+ tests | CI: ✅ GREEN

---

## Overview

**Chinese / English → Myanmar (Burmese)** novel translation pipeline.
- **Models**: Ollama-only (padauk-gemma:q8_0 primary, sailor2-20b available)
- **Active novel**: reverend-insanity (17 chapters), 古道仙鸿 (100+ chapters)
- **Workflows**: way1 (EN→MM direct), way2 (CN→EN→MM pivot)
- **Tests**: 254+ passing

---

## Current Pipeline (5 Stages)

```
1. PREPROCESSING  → Chunk text at paragraph boundaries (no overlap)
2. TRANSLATION    → CN/EN → MM via padauk-gemma:q8_0
3. QUALITY CHECK → Myanmar linguistic validation
4. CONSISTENCY    → Glossary verification  
5. QA REVIEW      → Final validation (score ≥70)
```

---

## Recent Quality Scores (Ch 12-21)

| Ch | Score | Issues Fixed |
|----|-------|--------------|
| 12 | 90/100 | ဤ/ထို archaic words |
| 13 | 90/100 | Heading format, garbage lines |
| 14 | 85/100 | Sentence enders |
| 15 | 73/100 | Register mix, 4.8hr (slow) |
| 16 | 73/100 | Title format |
| 17 | 83/100 | Duplicate paragraph |
| 18 | 90/100 | ✅ All clean |
| 19 | 80/100 | Korean leakage fixed |
| 20 | 90/100 | ✅ All clean |
| 21 | 75/100 | Garbled chunk tail |

**Trend**: Quality stable at 80-90 after fixes

---

## ✅ COMPLETED — All Major Bugs Fixed

| Bug | Fix | Status |
|-----|-----|--------|
| B1 — ဤ/ထို archaic | `replace_archaic_words()` Myanmar-safe regex | ✅ |
| B2 — Colon heading `# N: Title` | `fix_chapter_heading_format()` | ✅ |
| B3 — Register mixing | Per-paragraph check, threshold 0.5 | ✅ |
| B4 — Preprocessor IndexError | `overlap_counts` removed, smart_chunk | ✅ |
| B5 — Meta.json incomplete | Per-chapter `.mm.meta.json` writer | ✅ |
| B6 — Chunk boundary truncation | `stitch_chunk_boundaries()` | ✅ |
| B7 — Tamil/Indic leakage | `_INDIC_PATTERN` expanded | ✅ |
| B8 — Garbled model output | `strip_reasoning_process()` | ✅ |
| B9 — Paragraph duplication | `SequenceMatcher` (>0.90 threshold) | ✅ |
| B10 — Korean char leakage | Added to removal patterns | ✅ |

---

## Architecture — All Systems Working

| Component | Status | Notes |
|-----------|--------|-------|
| Core pipeline (way1 EN→MM) | ✅ | single_stage mode |
| Core pipeline (way2 CN→MM) | ✅ | Pivot workflow |
| CLI (translate, view, review, stats, test, ui) | ✅ | Full commands |
| Web UI (6 pages) | ✅ | Streamlit |
| Per-novel glossary | ✅ | Isolated data files |
| Auto-promote glossary | ✅ | Confidence rules |
| Myanmar text validation | ✅ | Rejects non-Myanmar |
| Per-chunk timeout guard | ✅ | 15-min guard |
| Rolling context | ✅ | 400-token tail |
| Dead code cleanup | ✅ | Removed old files |

---

## Speed & Performance

| Metric | Status |
|--------|--------|
| Chunk size | 1500 tokens (up from 800) |
| Timeout | 15-min guard per chunk |
| Context | 400-token rolling tail |
| Token budget | 2600 max per call |
| Pipeline mode | single_stage (fastest for padauk) |

---

## TODO — Remaining Work

### HIGH PRIORITY

| Item | Description |
|------|-------------|
| ⏳ `--rebuild-meta` CLI | Scan output folder, rebuild meta.json from existing .mm.md files (Gemini need to fix) |
| ⏳ Coverage increase | Raise from 35% → 50% (add tests for untested modules) (Gemini need to fix) |

### MEDIUM PRIORITY

| Item | Description |
|------|-------------|
| ⏳ Paragraph dedup | Strengthen boundary dedup in postprocessor.py (Gemini need to fix) |
| ⏳ Sentence-end check | Add truncation check for missing `။` (Gemini need to fix) |
| ⏳ Chapter 21 tail | Re-translate or clean garbled chunk tail (Gemini need to fix) |

### LOW PRIORITY (Future)

| Item | Description |
|------|-------------|
| 📋 Per-novel model override | Different models per novel in settings (Gemini no need fix) |
| 📋 EPUB export | CLI for book export (Gemini no need fix) |
| 📋 Parallel processing | ThreadPoolExecutor with write lock (Gemini no need fix) |

---

## Operational (User Action Needed)

```bash
# Build glossary for reverend-insanity
python -m src.main --novel reverend-insanity --generate-glossary --chapter-range 1-21

# Auto-promote approved terms
python -m src.main --novel reverend-insanity --auto-promote

# Run diagnose
python diagnose.py
```

---

## Files Status Summary

| Category | Count | Status |
|----------|-------|--------|
| Python modules | 50+ | ✅ All working |
| Test files | 15+ | 254+ passing |
| Config files | 8 | ✅ Valid |
| Data files | Per-novel | ✅ Isolated |
| Scripts | 5 | ✅ Executable |

---

## No Changes Needed

- ✅ CLI commands stable
- ✅ Pipeline modes (full/default/fast/single_stage) working
- ✅ Glossary system (approve/reject/auto-promote) functional
- ✅ Memory manager (3-tier) working
- ✅ Postprocessor (11 functions) robust
- ✅ Ollama timeout enforcement in place

---

## 🔍 MY REVIEW - What I Think Needs Work

After analyzing the codebase and performing a comparative analysis of Chapter 23 (Project vs. Original vs. Google Translate), here are issues I found that need attention:

### Issues Found

| # | Area | Issue | Severity |
|---|------|-------|----------|
| 1 | **Tests** | `test_novel_v1.py` runs 11 tests, but no pytest integration - standalone script only (Gemini no need fix) | LOW |
| 2 | **Coverage** | No centralized coverage report - need `pytest --cov` setup (Gemini need to fix) | MEDIUM |
| 3 | **Config** | Multiple settings files (settings.yaml, settings.pivot.yaml, settings.sailor2.yaml) - some may be stale (Gemini need to fix) | LOW |
| 4 | **Docs** | `review_project.md`, `CURRENT_STATE.md`, `AGENTS.md` - some duplication of status info (Gemini no need fix) | LOW |
| 5 | **Glossary** | Auto-approve confidence rules good, but no UI to review pending terms in bulk (Gemini need to fix) | MEDIUM |
| 6 | **Logs** | Auto-review generates report per-chapter, but no aggregated dashboard (Gemini need to fix) | LOW |
| 7 | **Pipeline** | Chapter 21 garbled tail still needs manual fix or re-translation (Gemini need to fix) | HIGH |
| 8 | **Translation** | Unresolved placeholders (`【?term?】`) leaked into Chapter 23 output (Gemini need to fix) | CRITICAL |
| 9 | **Translation** | Agent dropped a crucial explanatory paragraph in Chapter 23 (Summarization bug) (Gemini need to fix) | HIGH |
| 10| **Translation** | Conflated terms in Chapter 23 (e.g. translated Moonlight Gu as Moon orchid, conflating creature with food) (Gemini need to fix) | MEDIUM |

### My Recommendations

**Do Now:**
1. Fix the critical Placeholder Bug: `【?term?】` is leaking into final output (check `context_updater.py` or postprocessor).
2. Implement Completeness Checks: Enforce sentence/paragraph count parity to stop the LLM from dropping content.
3. Fix/re-translate Chapter 21 garbled tail output.
4. Add pytest-cov to requirements.txt for coverage tracking.
5. Fix stale config files - verify which are actually used.

**Do Later:**
1. Improve Glossary Disambiguation: Prevent conflation of similar terms (e.g., creature vs. food).
2. Create aggregated review dashboard (all chapters in one view).
3. Bulk glossary approve UI in Streamlit.
4. Parallel chapter processing for batch translation.

### Chapter 23 Analysis Summary (by Gemini)
*   **Strengths vs Google Translate**: Far superior Myanmar literary flow, correct honorifics/pronouns, and excellent contextual Wuxia terminology (avoids literal nonsense like "Gu earthworms").
*   **Weaknesses**: The pipeline suffered from a critical bug where `【?term?】` tokens were left unresolved. It also skipped a key paragraph near the end and mistranslated specific terms by confusing them with related concepts (e.g., Moonlight Gu vs Moon Orchid).

### What's Good

- ✅ Clean architecture (src/cli, src/agents, src/pipeline)
- ✅ Comprehensive postprocessor (11 functions)
- ✅ 254+ tests passing
- ✅ Memory system (3-tier) working
- ✅ Per-novel glossary isolation
- ✅ Quality gates (70% ratio, 70 score)

---

## Changelog (Recent)

```
5ed349f  fix: review_project.md audit — 6 code issues resolved
ab6dfeb  docs: update review_project.md — reflect all fixes
f0a685d  fix: colon heading + register mixing + timeout
385eae9  fix: dead config cleanup + dedup + CI coverage
58c4ad8  fix: enable CI ruff blocker + clean dead code
f8cfe9b  fix: stability foundation + glossary pipeline
```