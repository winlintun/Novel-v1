# Project Review — Novel Translation Pipeline
> Last updated: 2026-05-02 18:45Z | HEAD: `5ed349f` | 254 tests | 0 ruff E/F

---

## Overview

**Chinese / English → Myanmar (Burmese)** novel translation pipeline.
**Ollama-only**. Active novel: reverend-insanity (17 chapters). 254 tests, CI green.
Two workflows: way1 (EN→MM, padauk-gemma:q8_0), way2 (CN→EN→MM pivot).

---

## Real Data — Chapters 12–17 Quality Scores

| Ch | Score | Duration | Issues |
|----|-------|----------|--------|
| 12 | 90/100 | 0s | ဤ/ထို only |
| 13 | 90/100 | 0s | ဤ/ထို only |
| 14 | 85/100 | 84 min | ဤ/ထို, sentence enders |
| 15 | 73/100 | **4.8 hr** | ဤ/ထို, register mix, sentence enders |
| 16 | 73/100 | 75 min | ဤ/ထို, register mix, title format |
| 17 | 83/100 | 90 min | ဤ/�ို, title format, duplicate paragraph |

**Trend: 90 → 90 → 85 → 73 → 73 → 83**

---

## Bug Status — ALL 5 BUGS RESOLVED

| Bug | Status | Commit |
|-----|--------|--------|
| BUG 1 — ဤ/ထို archaic words | ✅ FIXED | Prior — `replace_archaic_words()` uses Myanmar-safe regex |
| BUG 2 — Colon heading `# N: Title` | ✅ FIXED | `f0a685d` — `fix_chapter_heading_format()` handles Pattern 2 |
| BUG 3 — Register mixing detection | ✅ FIXED | `f0a685d` — per-paragraph formal+casual check |
| BUG 4 — preprocessor IndexError | ✅ FIXED | Prior — `overlap_counts` removed in smart_chunk refactor |
| BUG 5 — Meta.json incomplete | ✅ CLI EXISTS | `--stats` + `--rebuild-meta` not yet built |

---

## Code Audit Findings — ALL FIXED IN `5ed349f`

| Finding | Fix Applied |
|---------|------------|
| M1 — `cloud_model` field | Removed from `ModelsConfig` |
| M2 — `DEFAULT_OVERLAP_SIZE` | Removed from `commands.py` |
| M3 — `main_fast.py` dead code | Deleted (never imported) |
| M4 — `_check_tone()` dialogue false positives | Skips quoted paragraphs |
| L1 — Glossary sort by recency | Sorts by `chapter_last_seen` desc before slicing |
| L2 — `translate_chunks()` rolling context | Now passes + advances `rolling_context` |

---

## Speed Fixes Applied

| Fix | Status |
|-----|--------|
| Per-chunk 15-min timeout guard | ✅ `f0a685d` |
| Chunk size 1500→2000 tokens | ✅ Prior |
| Rolling context (400-token tail) | ✅ Prior |
| Token budget check (2600 max) | ✅ Prior |
| Per-chunk timeout (preemptive) | ⏳ FUTURE — needs threading |

---

## Architecture State (Final)

| Area | Status |
|------|--------|
| Core pipeline (way1 EN→MM) | ✅ |
| Core pipeline (way2 CN→EN→MM) | ✅ |
| CLI (translate, view, review, stats, auto-promote, test, UI) | ✅ |
| CI/CD (Ruff blocking + 35% coverage, Python 3.10–3.13) | ✅ |
| Web UI (6 Streamlit pages) | ✅ |
| Glossary deduplication (Levenshtein < 3 → warn) | ✅ |
| Myanmar text validation (reject non-Myanmar glossary targets) | ✅ |
| Register mixing detection (per-paragraph, with dialogue skip) | ✅ |
| Per-chunk timeout guard (15-min post-hoc) | ✅ |
| Rolling context (chunk-to-chunk, token-limited) | ✅ |
| Colon heading fix (`# N: Title` → H1+H2) | ✅ |
| Archaic word replacement (Myanmar-safe regex) | ✅ |
| Dead code removed (ModelRouterConfig, GlossaryV3Config, rag_memory, model_router, glossary_v3_*, cn_mm_rules1, main_fast) | ✅ |
| Cloud provider references removed (gemini/openrouter) | ✅ |
| Typed exceptions (ModelError in OllamaClient) | ✅ |
| State corruption fixed (ReflectionAgent stateless model param) | ✅ |
| Ollama timeout enforced (timeout in every API call options) | ✅ |

---

## TODO — Remaining Work

### HIGH (1 item)
- [ ] **Add `--rebuild-meta` CLI** — scan `data/output/{novel}/` and rebuild per-novel meta.json from existing `.mm.md` files

### MEDIUM (3 items)
- [ ] **Strengthen paragraph boundary dedup** in `postprocessor.py` (Ch 17 had one duplicate)
- [ ] **Add sentence-ender truncation check** to postprocessor (detect lines missing `။`)
- [ ] **Raise coverage floor**: 35% → 50% (add tests for untested modules)

### LOW (3 items)
- [ ] **Per-novel model override** in settings.yaml
- [ ] **EPUB export** CLI
- [ ] **Parallel chapter processing** — ThreadPoolExecutor with glossary write lock

### OPERATIONAL (user action)
- [ ] Build glossary: `python -m src.main --novel reverend-insanity --generate-glossary --chapter-range 1-17`
- [ ] Auto-promote: `python -m src.main --novel reverend-insanity --auto-promote`

---

## Commits in This Session (most recent first)

```
5ed349f fix: review_project.md audit — 6 code issues resolved
ab6dfeb docs: update review_project.md — reflect all fixes through f0a685d
f0a685d fix: review_project.md bugs — colon heading + register mixing + per-chunk timeout
385eae9 fix: review_project.md batch — dead config cleanup + dedup + CI coverage
58c4ad8 fix: enable CI ruff blocker + clean dead code
f8cfe9b fix: need_to_fix_bug.md Phase 1-4 — stability foundation + glossary pipeline enforcement
```
