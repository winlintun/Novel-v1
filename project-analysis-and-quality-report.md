# Project Analysis & Quality Report

Project: **web-novel EN → Myanmar (Burmese) translation pipeline**
Novel under test: **My House of Horrors** (chapter 1, `ch001`)
Report updated: 2026-08-11 · Model: `padauk-gemma:q8_0` (local ollama)

---

## 1. What Was Done So Far

1. **Bootstrapped the pipeline** — spec (`SPEC.md`), prompts (`prompts/prompt.md`),
   glossary, state machine (`orchestrator`), sub-agents (`translator`, `verifier`,
   `auditor`), storage (`fleet.db`, per-chunk metadata).
2. **Ran chapter 1 end-to-end** via the orchestrator:
   - 15 chunks (overlapping window ~266–1,869 input tokens each)
   - 6 **verified**, 9 **failed** (verifier reject)
   - Started `07:26:18`, completed `13:53:51` (~6.5 h, offline model)
3. **Committed an output chapter** — `output/my_house_of_horrors/chapter-my-1.md`
   (91 paragraphs). **Note:** this commit predates the fixes below and still
   carries the defects documented in §7; it must be re-run with `--force`.
4. **Verified + fixed the new_todo.md bug list** (see §4).
5. **Implemented todo.md assembly-time gates** (see §5).
6. **Fleet + audit reports generated** (see §6) with `stop_the_line: true`.

---

## 2. Pipeline Architecture (as built)

```
books/<novel>/chapter-####.md (human EN)
        │ chunker (overlap window)
        ▼
   orchestrator (state machine)
        │  chunk  →  translator (ollama /api/generate)
        │             draft+polish, glossary-exact, JSON-only
        ▼
   verifier (per-chunk rules: glossary R-GLOSS-01, script R-FORBID-05,
             echo-of-source, incomplete, duplicates R-STRUCT-02)
        │  pass → verified / fail → fix-mode re-translate (all findings fed back)
        ▼
   ASSEMBLY GATES (todo.md §2/§3)  ← NEW
        │  script whitelist (HARD) · near-dup suppression (SOFT) ·
        │  completeness (HARD) · naming-consistency (advisory)
        ▼
   hygiene normalize (§7) · audit (A–F) · commit (state-aware)
        ▼
   chapter-my-N.md · metadata.json · fleet-report.json · audit-report.json
```

- **Backend:** local `ollama` `/api/generate`, `think=false`, `keep_alive=-1`,
  `temperature=0.2`, `num_predict` scaled to input.
- **Resume-safe:** progress committed after every batch and on `Ctrl+C`.
- **Read-only inputs:** `books/`, glossary, `.env` are never mutated.

---

## 3. Chapter-1 Run Data (as recorded pre-fix)

| Field | Value |
|---|---|
| chapter_id | `ch001` |
| source | `books\my_house_of_horrors\chapter-0001.md` |
| chunks | 15 (6 verified / 9 failed) |
| model | `padauk-gemma:q8_0` |
| glossary_version | `ac29854b1f91` |
| prompt_version | `9efae0207a13` |
| recorded state | `APPROVED` *(wrong — Bug B + metadata bug, see §4)* |
| final_grade | B+ (weighted 83.3) |
| output_paragraphs | 91 |

Chunk status detail:

```
ch001_sc00_ck00 failed  ck01 failed  ck02 failed  ck03 verified
ck04 failed  ck05 failed  ck06 verified  ck07 verified  ck08 failed
ck09 verified  ck10 failed  ck11 verified  ck12 verified
ck13 failed  ck14 failed
```

---

## 4. new_todo.md Bug Status — ALL FIXED

| # | Bug / item | Status | Where |
|---|---|---|---|
| A | **Verifier feedback gap** — fix-mode prompt must feed back **all** critical/fatal/error findings, not just `R-GLOSS-01` | ✅ **FIXED** (was already in code) | `src/pipeline/orchestrator.py:316` collects all `critical/fatal/error`; passed via `fix_issues=` at `orchestrator.py:331` |
| B | **False APPROVED** — a partially-failed chapter must be `NEEDS_HUMAN`, never `APPROVED` | ✅ **FIXED** (was already in code) | `orchestrator.py:435` (audit path) and `:446` (audit-skip path) force `NEEDS_HUMAN` when any chunk fails |
| C | **Failed text leaked into output** — only verified chunks may be assembled | ✅ **FIXED** (was already in code) | `orchestrator.py:411` filters `chunk.status == "verified"` before assembly |
| §3 | **Script whitelist gate at assembly** | ✅ **IMPLEMENTED NOW** | `src/pipeline/assembly.py::assembly_script_gate`; wired at `orchestrator.py:426` |
| §3 | **Near-duplicate suppression** | ✅ **IMPLEMENTED NOW** | `assembly.py::dedup_assembled_paras`; wired at `orchestrator.py:420` |
| §3 | **Completeness gate on assembled text** | ✅ **IMPLEMENTED NOW** | `assembly.py::assembly_completeness`; wired at `orchestrator.py:433` |
| §7 | **Punctuation / dash / ellipsis / quote normalization** | ✅ **IMPLEMENTED NOW** | `assembly.py::normalize_hygiene`; applied post-gate at `orchestrator.py:445` |
| §7 | **Strip stray ASCII art** (`_______________`) | ✅ **IMPLEMENTED NOW** | `assembly.py::normalize_hygiene` (divider-line removal) |
| §7 | **Loanword transliteration** (`Level` → အဆင့်) + explicit Latin allowlist | ✅ **IMPLEMENTED NOW** | `assembly.py::translate_loanwords` + `Glossary.loanword_allowlist`; allowlist in `config/.../glossary_*.json` meta |

### Additional bug found & fixed during this pass

| Bug | Symptom | Fix |
|---|---|---|
| **metadata state always APPROVED** | `_commit()` hardcoded `unit.state = APPROVED`; `metadata.json` never recorded `NEEDS_HUMAN` even when the run decided `NEEDS_HUMAN` (the recorded chapter-1 metadata says `APPROVED` for a chapter with 9 failed chunks) | `_commit()` now accepts `state=` and persists the real `final_state` (`orchestrator.py:552`) |
| **verifier had no foreign-script check** | todo.md assumed a per-chunk script check existed; the verifier only caught Latin (`R-FORBID-03`), so Thai/Bengali could pass a chunk | Added `R-FORBID-05` (fatal) using `has_foreign_script()` (`verifier.py:170`) + rule in `config/rules.json` |

---

## 5. Assembly Gates (todo.md §2/§3) — Implemented

New module `src/pipeline/assembly.py` runs **once on the fully assembled chapter**,
closing the per-chunk-only coverage gap:

| Gate | Type | Behavior |
|---|---|---|
| `assembly_script_gate(text, loanword_allowlist)` | **HARD** | Every char must be Myanmar (U+1000–U+109F, U+AA60–U+AA7F), punctuation/numbers/whitespace; Latin letter runs allowed only when in the glossary loanword allowlist. Rejects Thai, Bengali, Devanagari, Hangul, etc. |
| `dedup_assembled_paras(paras, threshold=0.85, lookback=5)` | **SOFT** | Drops paragraphs >85% similar to a recent sibling (overlap-window artifacts); logs to `metadata.json` + console |
| `assembly_completeness(paras, source_paras)` | **HARD** | Re-runs `looks_incomplete()` on the assembled body |
| `check_naming_consistency(text, index)` | **advisory** | Flags an entity rendered with >2 distinct Myanmar spellings (the `Shu Shu` / `park manager` drift) |
| `normalize_hygiene(text)` + `translate_loanwords(text)` | **post** | Unified `—` dash, `…` ellipsis, `“ ”` quotes; strips `____` dividers; collapses whitespace. Applied **after** the gates so it can never mask a leak |

**Failure handling:** if the script or completeness gate fails, the chapter is
forced to `NEEDS_HUMAN`, the polluted body is **not** written, and the assembly
reason is recorded in `metadata.json["assembly"]`.

**Loanword allowlist:** `glossary_*.json` top-level meta now carries
`"loanword_allowlist": ["HP", "NPC", "QQ", "ID", "Level"]`; `Glossary.loanword_allowlist()`
exposes it to the gate.

---

## 6. Fleet & Audit Reports (pre-fix chapter, as recorded)

### Fleet report — auto-pause triggered (`stop_the_line: true`)

| Alert | Level | Value | Threshold | Meaning |
|---|---|---|---|---|
| SPC-REJECT | **PAUSE** (3) | reject 60.0% | > 15% | Verifier rejects more than it accepts |
| SPC-FALLBACK | **DEGRADED** (2) | fallback 66.7% | > 20% | Model degraded / unstable output |
| SPC-GRADE | **INVESTIGATE** (1) | avg grade 83.3 | < 85.0 | Auditor grade under target |

### Audit report (as recorded)

| Dimension | Score |
|---|---|
| Flow | 85 |
| Voice consistency | 78 |
| Terminology | 90 |
| Literary quality | 82 |
| **Weighted total** | **83.3 → B+ (pass)** |

Auditor's own suggestions independently flag the same problems the new gates now
address: duplicate paragraphs, register mixing, repetitive `တောက်!`, and
inconsistent manager naming.

---

## 7. Output Quality Findings (committed `chapter-my-1.md` — PRE-FIX artifact)

This file was produced **before** the fixes; it documents the exact failures the
new gates are designed to prevent. **It must be regenerated with `--force`.**

### 7.1 Foreign-script leaks (HARD — now blocked by R-FORBID-05 + assembly gate)

| Line | Script | Evidence |
|---|---|---|
| 21 | **Thai** | `...တစ္ဆေဆိုတာ တကယ်မရှိဘူး!` contains `หรอก` |
| 107 | **Bengali** | `...သစ်စတွေနဲ့ ဖုန်မှုန့်တွေကြားမှာ...` contains `কাঁচ` |
| 23 | **Latin** | `...ဂိမ်း Level တက်ဖို့...` — English **"Level"** kept verbatim |

### 7.2 Duplicate / repeated paragraphs

| Lines | Note |
|---|---|
| 61 / 63 | **exact** duplicate `“ငါ ဘယ်လောက်ထိ သည်းခံနိုင်ဦးမလဲ မသိဘူး”` |
| 77 / 79, 95 / 97, 119 / 121, 131 / 133, 145 / 147 | near-duplicate pairs |
| 181 / 183, 193 / 195 | story-card entries repeated |

### 7.3 Format / punctuation hygiene

- Line 151: stray `_______________` divider.
- Mixed dashes (`–` / `—` / `-`), mixed quotes (`“ ”` and `‘ ’`), inconsistent ellipsis.

### 7.4 Glossary / terminology

- Terminology 90 is the strongest dimension, but the `Shu Shu` / `park manager`
  drift shows glossary **context** isn't uniformly applied across chunks.

---

## 8. Root-Cause Summary

1. **Model instability under this prompt/glossary set** — 9/15 chunks failed
   verification; 66.7% fallback rate ⇒ `padauk-gemma:q8_0` on novel-length EN
   input is marginal. Passing chunks cluster at lower token counts → length-dependent degradation.
2. **Validation was half-enforced** — the verifier lacked a foreign-script check,
   and there was no assembly-time gate, so chunk-boundary duplicates and
   per-chunk false negatives reached the file.
3. **State/recording bugs** — `metadata.json` always said `APPROVED`; partial
   failures didn't reach the persisted state.
4. **Chunk-overlap duplication** — repeated paragraphs pass the assembler
   unchanged.

---

## 9. Recommendations & Status (priority order)

1. ✅ **Do not run more chapters while `stop_the_line` is active** — now backed by
   code, not just policy.
2. ✅ **Bugs A–C fixed** and covered by tests.
3. ✅ **Assembly gates + hygiene implemented** (todo.md §2/§3/§7) with unit +
   integration tests.
4. ⏳ **Re-run chapter 1 with `--force`** — the committed `chapter-my-1.md` is a
   pre-fix artifact and must be regenerated through the new gates.
5. ⏳ **Evaluate model alternatives** — benchmark the same 9 failed chunks on
   `gemma4:31b` / `qwen3.6-27b`; prefer the model that drops reject rate < 15%.
   If all struggle, shrink the chunk window (passing chunks were low-token).
6. ⏳ **Regenerate fleet + audit reports** after the clean re-run; confirm
   `SPC-REJECT < 15%`, `SPC-FALLBACK < 20%`, `SPC-GRADE ≥ 85`,
   `stop_the_line: false` — only then scale to chapter 2.

---

## 10. Artifacts

| Artifact | Path |
|---|---|
| Committed chapter (PRE-FIX — re-run with `--force`) | `output\my_house_of_horrors\chapter-my-1.md` |
| Per-chunk metadata | `output\my_house_of_horrors\metadata.json` |
| Fleet report | `output\my_house_of_horrors\fleet-report.json` |
| Audit report | `output\my_house_of_horrors\audit-report.json` |
| **New: assembly gates** | `src\pipeline\assembly.py` |
| Assembly gate tests | `tests\test_assembly.py` |
| Style guide | `prompts\prompt.md` |
| Glossary (+ loanword allowlist) | `config\my_house_of_horrors\glossary_my_house_of_horrors.json` |
| Rules (incl. R-FORBID-05) | `config\rules.json` |

---

## 11. Test Status

`python -m pytest tests/ -q` → **174 passed** (was 154; +18 assembly-gate tests,
+1 orchestrator script-gate integration test, +1 verifier R-FORBID-05 test).
