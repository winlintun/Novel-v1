# Project Review — Novel Translation Pipeline
> Last updated: 2026-05-02 | Full code audit through every pipeline file

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

## Bugs — Status After Full Code Audit

### BUG 1 — ဤ/ထို Archaic Words — ✅ FIXED
- `replace_archaic_words()` in `postprocessor.py` uses Myanmar-specific lookbehind regex (not `\b`)
- Replaces ဤ→ဒီ, ထို→အဲဒီ, သင်သည်→မင်း in `clean_output()` step 8
- `undo_archaic_corruptions()` runs before replacement to fix old `\b`-based corruptions
- **Verified**: Correct Myanmar-safe regex in place. Future chapters will benefit.
- **Note**: `_check_archaic_words()` in `MyanmarQualityChecker` still flags ဤ/ထို on raw chunk output (before postprocessor). This deflates the per-chunk quality score shown during translation, but final output is correct.

### BUG 2 — Chapter Title Colon Format — ✅ FIXED
- `fix_chapter_heading_format()` handles both patterns:
  - `# အခန်း N ## Title` (Pattern 1, already existed)
  - `# အခန်း N: Title` → `# အခန်း N\n\n## Title` (Pattern 2, added)
- **Verified**: Both patterns confirmed in postprocessor.py.

### BUG 3 — Register Mixing Detection — ✅ FIXED
- `_check_tone()` now does per-paragraph analysis (splits on `\n\n`)
- Detects FORMAL_MARKERS (`['သည်', '၏', 'ဖြင့်', 'ပေသည်', 'သော', '၍']`) and CASUAL_MARKERS (`['တယ်', 'ဘူး', 'လို့', 'နဲ့', 'ပါတယ်', 'မယ်']`) in same paragraph
- Deducts 5pts per mixed paragraph
- **Verified**: Implementation confirmed in myanmar_quality_checker.py:199.
- **Known limitation**: Dialogue paragraphs that naturally mix registers (e.g., casual speech inside formal narration) will trigger false positives. Score deduction may be overstated for chapters with heavy dialogue.

### BUG 4 — preprocessor.py IndexError — ✅ ALREADY FIXED
- `overlap_counts` removed entirely; `create_chunks()` delegates to `smart_chunk()`.
- **Verified**: No overlap logic in chunker.py or preprocessor.py.

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

| Fix | Status | Notes |
|-----|--------|-------|
| Per-chunk 15-min timeout check | ✅ Implemented | orchestrator.py:751 — fires AFTER chunk completes |
| Chunk size 1500→2000 tokens | ✅ Prior | Reduces chunks by ~30% |
| Rolling context (400-token limit) | ✅ Verified | get_rolling_context() advances after each chunk |
| Token budget check (2600 token max) | ✅ Verified | orchestrator.py:652-664 |

### Timeout Limitation
The timeout check at orchestrator.py:751 is **post-hoc** — it runs after `translate_paragraph()` returns. It cannot interrupt a chunk that is mid-translation. A stuck model call will still run until the HTTP timeout (900s in `ProcessingConfig.request_timeout`). The 15-min guard only prevents the NEXT retry loop. To add true preemptive timeouts, threading or asyncio would be needed.

### Bottleneck
Translation (Step 2) is ~330s/chunk. Steps 5 (quality) and 6 (consistency) are <1s — confirmed heuristic checks, not LLM calls.

---

## Quality Issues — Remaining

### ⚠️ Issue 1 — Glossary Too Small (20 terms / 17 chapters)
Context_updater only adds ~1 term per chapter. Glossary needs growth.
`get_glossary_for_prompt()` is hardcoded to `limit=20` — as glossary grows past 20 terms, newer terms won't reach the translation prompt.
**Action**: Run `python -m src.main --novel reverend-insanity --generate-glossary --chapter-range 1-17` then `--auto-promote`.

### ⚠️ Issue 2 — 【?term?】 Placeholders in Ch 16, 17
Terms the model doesn't know. Will reduce as glossary grows.

### ⚠️ Issue 3 — Sentence-Ender Truncation (Ch 14–16)
Some lines end without `။`. May be chunk boundary artifact.
**Action**: Add postprocessor check for incomplete lines.

### ⚠️ Issue 4 — Duplicate Paragraph Boundary (Ch 17)
One duplicated paragraph — chunk overlap artifact. Overlap is always 0 but boundary dedup may need hardening.

---

## Code Audit Findings — New Issues Found

### MEDIUM Priority

#### M1 — `cloud_model` Field Still Present (`src/config/models.py:83`)
`ModelsConfig.cloud_model: str = Field(default="gemini-2.5-flash", ...)` was not removed.
The Ollama-only pipeline never reads this field, but it exists in the config class.
`ModelRouterConfig`, `GlossaryV3Config`, and `AppConfig.model_router/glossary_v3` were removed (✅), but `cloud_model` remains.
**Action**: Remove `cloud_model` field from `ModelsConfig`.

#### M2 — Dead Constant (`src/cli/commands.py:24`)
`DEFAULT_OVERLAP_SIZE = 100` — overlap was removed from the chunker. This constant is never used.
**Action**: Delete line 24 in `commands.py`.

#### M3 — `src/main_fast.py` Still Exists
Separate entry point with duplicated pipeline logic. Never runs via normal CLI.
**Action**: Delete `src/main_fast.py` or merge its unique logic into `src/main.py`.

#### M4 — `_check_tone()` False Positives on Dialogue
Dialogue paragraphs (which naturally mix formal narration markers and casual speech markers) get flagged as "register mixing." This inflates the warning count and deducts score unfairly on dialogue-heavy chapters.
**Action**: Skip register mixing check for paragraphs that contain quotation marks (`"..."`, `"..."`, `「...」`).

### LOW Priority

#### L1 — `get_glossary_for_prompt(limit=20)` Won't Scale
As the glossary grows past 20 terms, later entries won't reach the translation prompt.
**Action**: Sort by `chapter_last_seen` (most recent first) before slicing, so freshest terms stay in the window.

#### L2 — `translator.py:translate_chunks()` Missing Rolling Context
`Translator.translate_chunks()` (line 364) calls `translate_paragraph()` without `rolling_context`. The orchestrator's own `_translate_chunks()` is used in normal operation and does pass rolling context correctly. But if `Translator.translate_chapter()` is called directly, rolling context is silently lost.
**Action**: Low risk for current usage; worth fixing for correctness.

---

## Architecture State

| Area | Status | Notes |
|------|--------|-------|
| Core pipeline (way1 EN→MM) | ✅ Working | padauk-gemma:q8_0 |
| Core pipeline (way2 CN→EN→MM) | ✅ Working | hunyuan:7b → padauk-gemma:q8_0 |
| CLI commands | ✅ Full-featured | translate, view, review, stats, auto-promote, test, UI |
| Tests | ✅ 254 pass | 35% coverage floor (target: 50%) |
| CI/CD | ✅ Ruff blocking + coverage | 35% floor, Python 3.10–3.13 matrix |
| Web UI | ✅ 6 pages | Quickstart, Translate, Progress, Glossary, Settings, Reader |
| Glossary deduplication | ✅ | Levenshtein < 3 → warn; Myanmar text validation |
| Register mixing detection | ✅ | Per-paragraph formal vs casual (with dialogue false positive caveat) |
| Per-chunk timeout check | ✅ | 15-min post-hoc ceiling (can't interrupt mid-translation) |
| Rolling context | ✅ | 400-token tail passed chunk-to-chunk; token budget 2600 enforced |
| Colon heading fix | ✅ | `# N: Title` → H1+H2 confirmed |
| Archaic word fix | ✅ | Myanmar-safe lookbehind regex confirmed |
| Dead config cleanup | ✅ | ModelRouterConfig, GlossaryV3Config, AppConfig.model_router/glossary_v3 removed |
| cloud_model in ModelsConfig | ⚠️ REMAINING | Field still present, never used (src/config/models.py:83) |
| DEFAULT_OVERLAP_SIZE constant | ⚠️ DEAD CODE | commands.py:24 — never used, overlap removed |
| main_fast.py | ⚠️ UNRESOLVED | Separate entry point with duplicated logic |

---

## TODO — Remaining

### HIGH
- [ ] **Add `--rebuild-meta` CLI command** — scan output dir, rebuild per-novel meta.json (BUG 5)
- [ ] **Strengthen paragraph boundary dedup** in postprocessor (Ch 17 had one duplicate)

### MEDIUM
- [ ] **Build glossary properly**: run `--generate-glossary --chapter-range 1-17` + `--auto-promote`
- [ ] **Remove `cloud_model` from ModelsConfig** (`src/config/models.py:83`)
- [ ] **Delete `DEFAULT_OVERLAP_SIZE` constant** (`src/cli/commands.py:24`)
- [ ] **Integrate or delete `src/main_fast.py`** — separate entry point with duplicated pipeline logic
- [ ] **Fix `_check_tone()` dialogue false positives** — skip register check inside quoted paragraphs
- [ ] **Add sentence-ender truncation check** to postprocessor (Issue 3)
- [ ] **Raise coverage floor**: 35% → 50% (add tests for untested modules)

### LOW
- [ ] **Sort glossary by recency** in `get_glossary_for_prompt()` so fresh terms appear first
- [ ] **Fix `translator.py:translate_chunks()`** to pass `rolling_context` (correctness fix)
- [ ] **Add per-novel model override** in settings.yaml
- [ ] **EPUB export** — compile chapters into single ebook
- [ ] **Parallel chapter processing** — ThreadPoolExecutor with glossary write lock
- [ ] **Preemptive chunk timeout** — threading/asyncio to interrupt stuck translations before they complete

---

## Quick Reference — Key Files

| What | File |
|------|------|
| Archaic word replacement | `src/utils/postprocessor.py` (line 431) |
| Chapter heading format fix | `src/utils/postprocessor.py` (line 270) |
| Register mixing detection | `src/agents/myanmar_quality_checker.py` (line 199) |
| Per-chunk timeout check | `src/pipeline/orchestrator.py` (line 751) |
| Rolling context advance | `src/pipeline/orchestrator.py` (line 785) |
| Token budget check | `src/pipeline/orchestrator.py` (line 652) |
| Glossary deduplication | `src/memory/memory_manager.py` (_edit_distance, _is_valid_myanmar_text) |
| Glossary prompt injection | `src/memory/memory_manager.py:302` (get_glossary_for_prompt, limit=20) |
| Pipeline stage coordination | `src/pipeline/orchestrator.py` |
| Translator agent (rolling context) | `src/agents/translator.py:translate_paragraph()` |
| Refiner agent (batch mode) | `src/agents/refiner.py:refine_batch()` |
| Context updater (entity extract) | `src/agents/context_updater.py:extract_entities()` |
| Postprocessor pipeline | `src/utils/postprocessor.py` (clean_output) |
| Quality review reports | `src/utils/translation_reviewer.py` |
| CLI commands | `src/cli/commands.py` |
| Workflow config (way1/way2) | `src/cli/commands.py:_apply_workflow_config()` |
| Config defaults | `config/settings.yaml` |
| CI workflow | `.github/workflows/ci.yml` |
| Dead cloud_model field | `src/config/models.py:83` |
