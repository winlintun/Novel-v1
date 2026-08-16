# Product Requirements Document (PRD)
## Myanmar Novel Translation Pipeline (Ollama-Powered)

**Version:** 1.0  
**Date:** 2026-08-09  
**Status:** Draft  
**Target:** Chinese Web Novels (English Source → Burmese)

---

## 1. Executive Summary

Build a local-first, AI-assisted literary translation pipeline that converts English-source Chinese web novels into high-quality Burmese prose using Ollama LLMs. The system must preserve literary voice, enforce terminology consistency via a glossary, and produce output indistinguishable from professional human translation.

---

## 2. Goals & Objectives

| ID | Goal | Success Metric |
|----|------|----------------|
| G-01 | Produce literary-quality Burmese translations | Human reviewer "acceptance rate" ≥ 85% |
| G-02 | Maintain 100% glossary term consistency | Terminology accuracy = 100% (automated check) |
| G-03 | Reduce human translation effort by 70% | Words-per-hour vs pure human translation |
| G-04 | Operate fully offline (privacy) | Zero external API calls for core translation |
| G-05 | Support iterative quality improvement | Verifier + Auditor subagent feedback loop |

---

## 3. Scope

### In-Scope
- Markdown chapter ingestion and preservation
- Scene-based chunking with dialogue/narration detection
- Glossary-aware, few-shot prompted translation via Ollama
- Context buffer for cross-chunk style consistency
- Automated post-processing (normalization, quote fixing)
- Verifier subagent (term-level quality gate)
- Auditor subagent (chapter-level literary review)
- MCP service exposure for external tool integration
- TDD-driven development with regression test suite

### Out-of-Scope
- PDF/ePub ingestion (Phase 2)
- Real-time collaborative editing (Phase 3)
- Non-Burmese target languages
- Automatic glossary extraction (manual curation required)
- Payment/subscription systems

---

## 4. User Stories

**US-01** As a translator, I want the system to remember character names exactly, so that "Chen Ge" is always "ချန်ဂီ" and never "ချန်ဂေါ်".

**US-02** As a translator, I want dialogue to feel alive and narration to feel literary, so that readers experience a natural story flow.

**US-03** As a project manager, I want to see a quality grade (A-F) per chapter, so that I know which chapters need human rework.

**US-04** As a developer, I want all configuration to be JSON-driven, so that I can adjust style without touching code.

**US-05** As a reviewer, I want the system to highlight exactly where it violated glossary rules, so that I can approve or reject efficiently.

---

## 5. Functional Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-01 | Ingest English source Markdown files with YAML frontmatter | P0 |
| FR-02 | Split chapters into scene-based chunks (3-5 paragraphs, dialogue+narration mixed) | P0 |
| FR-03 | Inject glossary terms into prompts with exact Burmese mappings | P0 |
| FR-04 | Assemble few-shot examples from human-translated reference chapters | P0 |
| FR-05 | Integrate with Ollama API (local) for translation generation | P0 |
| FR-06 | Maintain a sliding context buffer (JSON) for style continuity | P0 |
| FR-07 | Post-process raw LLM output: normalize quotes, fix spacing, enforce markdown | P0 |
| FR-08 | Run Verifier subagent to detect glossary violations and voice inconsistencies | P1 |
| FR-09 | Run Auditor subagent to grade literary quality and coherence | P1 |
| FR-10 | Provide human review interface (side-by-side diff) | P1 |
| FR-11 | Track chapter state: `draft` → `verified` → `audited` → `approved` | P1 |
| FR-12 | Enforce style guide rules (dialogue vs narration register) | P1 |
| FR-13 | Support two-pass translation: Draft → Literary Polish | P1 |
| FR-14 | Expose pipeline steps as MCP tools | P2 |
| FR-15 | Generate TDD regression reports after each build iteration | P2 |

---

## 6. Non-Functional Requirements

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-01 | Local-only processing | No cloud LLM calls |
| NFR-02 | Offline capability | Full function without internet |
| NFR-03 | Extensibility | New models/rules added via config only |
| NFR-04 | Traceability | Every output chunk links to source + prompt version |
| NFR-05 | Reproducibility | Same input + config = same output (deterministic) |
| NFR-06 | Config-driven | All behavior controlled by JSON/YAML configs |
| NFR-07 | Error resilience | Failed chunks retry with fallback model; never crash pipeline |
| NFR-08 | Version control friendly | All artifacts are text (markdown/json); no binary blobs |

---

## 7. Architecture Overview

```
┌─────────────────┐
│  English Source │  (Markdown + YAML frontmatter)
│   (Markdown)    │
└────────┬────────┘
         ▼
┌─────────────────────────┐
│   [Pre-Processor]       │  → Dialogue/Narration tagging
│   - Scene Chunker       │  → Speaker identification
│   - Type Classifier     │  → Overlap injection
└────────┬────────────────┘
         ▼
┌─────────────────────────┐
│   [Prompt Builder]      │  → Glossary injection
│   - Few-shot selector   │  → Context buffer prepend
│   - Rule loader         │  → Micro-prompt assembly
└────────┬────────────────┘
         ▼
┌─────────────────────────┐
│   [Ollama LLM]          │  → Draft Translation
│   - Draft Model         │  → Literary Polish Model
│   - Refine Model        │  (Temperature 0.3)
└────────┬────────────────┘
         ▼
┌─────────────────────────┐
│   [Post-Processor]      │  → Markdown normalization
│   - Format normalizer   │  → Quote fixing
│   - Term enforcer       │  → Whitespace cleanup
└────────┬────────────────┘
         ▼
┌─────────────────────────┐
│   [Verifier Subagent]   │  → Glossary scan
│   - Term checker        │  → Voice consistency
│   - Format validator    │  → Issue report
└────────┬────────────────┘
         ▼
┌─────────────────────────┐
│   [Auditor Subagent]    │  → Literary grade (A-F)
│   - Holistic reviewer   │  → Coherence check
│   - Style comparator    │  → Pass/Fail verdict
└────────┬────────────────┘
         ▼
┌─────────────────────────┐
│   [Output]              │  → chapter-XXX-my.md
│   Burmese Markdown      │  → metadata.json
│   + Metadata            │  → audit-report.json
└─────────────────────────┘
```

---

## 8. Data Flow

1. **Ingest**: `chapter-en-0001.md` → parsed into paragraphs
2. **Chunk**: Paragraphs grouped by scene boundaries (dialogue blocks preserved)
3. **Context**: Preceding 2 chunks + scene summary loaded from `context_buffer.json`
4. **Prompt**: System prompt + Glossary + Few-shot examples + Context + Source chunk → assembled
5. **Translate**: Ollama generates Burmese draft
6. **Polish**: Second micro-prompt refines for literary quality
7. **Normalize**: Post-processor fixes markdown, enforces quotes
8. **Verify**: Verifier scans for glossary violations; auto-corrects if confidence > 90%
9. **Audit**: Auditor reads full chapter; assigns grade
10. **Export**: Final markdown + metadata + audit report written to disk

---

## 9. Iterative Build Plan

### Phase 1: MVP — "Translate & Save" (Week 1-2)
- Basic chunking (fixed 3-paragraph chunks)
- Single-pass translation with simple prompt
- Glossary JSON loaded and injected
- Output saved as markdown
- **Success Gate**: Chapter translates end-to-end without error

### Phase 2: Quality — "Context & Consistency" (Week 3-4)
- Scene-based chunking with overlap
- Context buffer (sliding window)
- Two-pass translation (Draft → Polish)
- Few-shot prompt assembly from human reference
- Post-processor normalization
- **Success Gate**: Glossary accuracy ≥ 98% vs human reference

### Phase 3: Agents — "Verify & Audit" (Week 5-6)
- Verifier subagent implementation
- Auditor subagent implementation
- State machine (`draft` → `verified` → `audited`)
- Human review interface (side-by-side)
- **Success Gate**: Verifier catches ≥ 90% of intentional glossary errors

### Phase 4: Platform — "MCP & Automation" (Week 7-8)
- MCP service exposing all tools
- TDD regression suite automated
- Config-driven rule engine
- Batch processing (multi-chapter queue)
- **Success Gate**: Full pipeline runs via MCP commands only

---

## 10. Success Metrics

| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| Terminology Accuracy | 100% | Automated glossary scan |
| Style Consistency Score | ≥ 85% | Auditor grade + human review |
| Human Edit Distance | ≤ 15% | Levenshtein vs human reference |
| Pipeline Throughput | ≥ 500 words/hour | End-to-end timing |
| Verifier Precision | ≥ 90% | True positives / All flagged issues |
| Auditor Correlation | ≥ 0.8 | Auditor grade vs human grade (Pearson) |

---

## 11. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Ollama model hallucinates names | High | Glossary enforcer + Verifier subagent |
| Context window overflow | Medium | Chunk size limits + Context summarization |
| Literary style drifts across chunks | High | Context buffer + Two-pass polish |
| Model produces robotic Burmese | High | Few-shot human examples + Literary polish prompt |
| Local GPU insufficient | Medium | Support CPU fallback + model quantization |
| Human reference inconsistent | Medium | Lock glossary after curation; style guide document |

---

## 12. Glossary & Style Lock

All character names, place names, and special terms shall be locked after Phase 2. Any change requires:
1. Auditor approval
2. Retroactive update to all previous chapters (batch job)
3. Version bump in `glossary.json`

---

*End of PRD*
