# Project Review — Novel Translation Pipeline
> Last updated: 2026-05-02 18:30Z | Commits through `f0a685d`

---

## Overview

**Chinese / English → Myanmar (Burmese)** novel translation pipeline.
**Ollama-only** (no cloud API). Active novel: reverend-insanity (17 chapters translated).
Two workflows: way1 (EN→MM, padauk-gemma:q8_0), way2 (CN→EN→MM pivot).

---

## Real Data Summary — Chapters 12–17

### Quality Scores (from review reports)

| Chapter | Score | Pipeline | Model | Duration | Chunks | Warnings |
|---------|-------|----------|-------|----------|--------|----------|
| 12 | 90/100 | unknown | unknown | 0s (retroactive) | — | ဤ/ထို only |
| 13 | 90/100 | unknown | unknown | 0s (retroactive) | — | ဤ/ထို only |
| 14 | 85/100 | single_stage | padauk-gemma:q8_0 | 5025s (84 min) | 15 | ဤ/ထို, sentence enders |
| 15 | 73/100 | single_stage | padauk-gemma:q8_0 | **17235s (4.8 hr)** | 11 | ဤ/ထို, register mix, sentence enders |
| 16 | 73/100 | single_stage | padauk-gemma:q8_0 | 4496s (75 min) | 12 | ဤ/ထို, register mix, sentence enders, title format |
| 17 | 83/100 | single_stage | padauk-gemma:q8_0 | 5370s (90 min) | 16 | ဤ/ထို, title format, duplicate paragraph |

**Trend: 90 → 90 → 85 → 73 → 73 → 83** (degrading then recovering)

---

## Bugs — Status After Fixes (Commit `f0a685d`)

### BUG 1 — ဤ/ထို Archaic Words — ✅ FIXED
- `replace_archaic_words()` in `postprocessor.py` replaces ဤ→ဒီ, ထို→အဲဒီ on final output
- MyanmarQualityChecker detects and deducts 5pts per occurrence
- `clean_output()` pipeline calls it at line 741
- **Status**: Code fixed. Existing chapters (12–17) need re-cleaning or re-translation to benefit.

### BUG 2 — Chapter Title Colon Format — ✅ FIXED
- `fix_chapter_heading_format()` now handles two patterns:
  - `# အခန်း N ## Title` (old, already handled)
  - `# အခန်း N: Title` → `# အခန်း N\n\n## Title` (new, added in `f0a685d`)
- **Status**: Fixed. Future chapters will get correct formatting.

### BUG 3 — Register Mixing Detection — ✅ FIXED
- `myanmar_quality_checker._check_tone()` now does per-paragraph register analysis
- Detects သည်/၏/ဖြင့်/ပေသည် (formal) + တယ်/ဘူး/လို့/နဲ့ (casual) in same paragraph
- Deducts 5pts per mixed paragraph
- `check_quality()` reports count in score/issue output
- Register instruction already present in translator prompt (lines 64, 111)
- **Status**: Fixed. Score gap between internal checker and review should narrow.

### BUG 4 — preprocessor.py IndexError — ✅ ALREADY FIXED
- `overlap_counts` variable removed entirely in smart_chunk refactor (commit `40dcde0`)
- `create_chunks()` now delegates to `smart_chunk()` which has no overlap logic
- **Status**: No action needed. Edge case cannot recur.

### BUG 5 — Meta.json Incomplete — ⏳ PENDING
- Only chapters 14–17 tracked in `reverend-insanity.mm.meta.json`
- Chapters 1–13 used old filename format and were never registered
- **Action**: Add `--rebuild-meta` CLI command to scan output dir and rebuild meta.json

---

## Speed Analysis

### Per-Chunk Timings

| Chapter | Chunks | Avg time/chunk | Total |
|---------|--------|----------------|-------|
| 17 | 16 | 337s (5.6 min) | 90 min |
| 14 | 15 | 335s (5.6 min) | 84 min |
| 16 | 12 | 375s (6.25 min) | 75 min |
| 15 | 11 | **1567s (26 min)** | **4.8 hr ← anomaly** |

### Speed Fixes Applied

| Fix | Status | Commit |
|-----|--------|--------|
| Per-chunk 15-min timeout | ✅ `f0a685d` | Prevents 4.8hr sessions from stuck retries |
| Chunk size 1500→2000 tokens | ✅ Prior | Reduces chunks by ~30% |
| Q4_K_M / Q5_K_M quantization | ⏭ SKIPPED | Not needed |

### Bottleneck
Translation (Step 2) is ~330s/chunk. Steps 5 (quality) and 6 (consistency) are <1s — not LLM calls.

---

## Quality Issues — Remaining

### ⚠️ Issue 1 — Glossary Too Small (20 terms / 17 chapters)
Context_updater only adds ~1 term per chapter. Glossary needs growth.
**Action**: Run `python -m src.main --novel reverend-insanity --generate-glossary --chapter-range 1-17` then `--auto-promote`.

### ⚠️ Issue 2 — 【?term?】 Placeholders in Ch 16, 17
Terms the model doesn't know. Will reduce as glossary grows.

### ⚠️ Issue 3 — Sentence-Ender Truncation (Ch 14–16)
Some lines end without `။`. May be chunk boundary artifact.
**Action**: Add postprocessor check for incomplete lines.

### ⚠️ Issue 4 — Duplicate Paragraph Boundary (Ch 17)
One duplicated paragraph — chunk overlap artifact. Overlap is always 0 but boundary dedup may need hardening.

---

## Architecture State

| Area | Status | Notes |
|------|--------|-------|
| Core pipeline (way1 EN→MM) | ✅ Working | padauk-gemma:q8_0 |
| Core pipeline (way2 CN→EN→MM) | ✅ Working | hunyuan:7b → padauk-gemma:q8_0 |
| CLI commands | ✅ Full-featured | translate, view, review, stats, auto-promote, test, UI |
| Tests | ✅ 254 pass | 35% coverage floor (target: 50%) |
| CI/CD | ✅ Ruff blocking + coverage | 35% floor |
| Web UI | ✅ 6 pages | Quickstart, Translate, Progress, Glossary, Settings, Reader |
| Glossary deduplication | ✅ | Levenshtein < 3 → warn |
| Register mixing detection | ✅ `f0a685d` | Per-paragraph formal vs casual |
| Per-chunk timeout | ✅ `f0a685d` | 15-min ceiling |
| Colon heading fix | ✅ `f0a685d` | `# N: Title` → H1+H2 |
| Dead config cleanup | ✅ `385eae9` | ModelRouterConfig, GlossaryV3Config, cloud_model removed |
| Cloud provider references | ✅ `385eae9` | gemini/openrouter stripped |
| cn_mm_rules1.py duplicate | ✅ `385eae9` | Deleted |
| Q4_K_M/Q5_K_M | ⏭ Skipped | Not needed |

---

## TODO — Remaining

### HIGH
- [ ] **Add `--rebuild-meta` CLI command** — scan output dir, rebuild per-novel meta.json
- [ ] **Strengthen paragraph boundary dedup** in postprocessor (Ch 17 had one duplicate)

### MEDIUM
- [ ] **Build glossary properly**: run `--generate-glossary --chapter-range 1-17` + `--auto-promote`
- [ ] **Add sentence-ender truncation check** to postprocessor
- [ ] **Integrate or delete `src/main_fast.py`** — separate entry point with duplicated pipeline logic
- [ ] **Raise coverage floor**: 35% → 50% (add tests for untested modules)

### LOW
- [ ] **Add per-novel model override** in settings.yaml
- [ ] **EPUB export** — compile chapters into single ebook
- [ ] **Parallel chapter processing** — ThreadPoolExecutor with glossary write lock

---

## Quick Reference — Key Files

| What | File |
|------|------|
| Archaic word replacement | `src/utils/postprocessor.py` (line 431) |
| Chapter heading format fix | `src/utils/postprocessor.py` (line 270) |
| Register mixing detection | `src/agents/myanmar_quality_checker.py` (line 190) |
| Per-chunk timeout | `src/pipeline/orchestrator.py` (line 740) |
| Glossary deduplication | `src/memory/memory_manager.py` (_edit_distance) |
| Pipeline stage coordination | `src/pipeline/orchestrator.py` |
| Translator agent (CN→MM) | `src/agents/translator.py` |
| Refiner agent (literary edit) | `src/agents/refiner.py` |
| Postprocessor pipeline | `src/utils/postprocessor.py` (clean_output) |
| Quality review reports | `src/utils/translation_reviewer.py` |
| CLI commands | `src/cli/commands.py` |
| Config defaults | `config/settings.yaml` |
| CI workflow | `.github/workflows/ci.yml` |
