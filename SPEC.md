# SPEC.md — Single Source of Truth
## Myanmar Novel Translation Pipeline

**Version:** 1.0  
**Authority:** This document overrides all other specifications when conflict arises.  
**Last Updated:** 2026-08-09

---

## 1. System Boundary

The pipeline is a **closed system** bounded by:
- **Input Boundary**: English Markdown files (`chapter-en-XXXX.md`) with optional YAML frontmatter
- **Output Boundary**: Burmese Markdown files (`chapter-my-XXXX.md`) + `metadata.json` + `audit-report.json`
- **External Dependencies**: Ollama server (local), Filesystem (local), Git (optional)
- **Human Interface**: Reviewer approval at `audited` → `approved` transition

Nothing inside the boundary may call external cloud APIs. All LLM inference is local.

---

## 2. Component Interface Contracts

### 2.1 Orchestrator
```yaml
Input:
  - source_path: string  # Path to chapter-en-XXXX.md
  - config_dir: string   # Path to config/ directory
  - output_dir: string   # Path to output/ directory
Output:
  - burmese_md: string   # Final translated markdown
  - metadata: Metadata   # See Data Models
  - audit_report: AuditReport
Side Effects:
  - Writes files to output_dir
  - Updates context_buffer.json
  - Logs to pipeline.log
Error Handling:
  - If Ollama unreachable: retry 3×, then fail with code E_CONN
  - If chunk fails: mark chunk status FAILED, continue others, summary at end
```

### 2.2 Chunker (Pre-Processor)
```yaml
Input:
  - raw_markdown: string
  - max_chunk_paragraphs: int = 5
  - min_chunk_paragraphs: int = 2
  - overlap_paragraphs: int = 1
Output:
  - chunks: Chunk[]
Rules:
  - Dialogue blocks (consecutive lines starting with ") must stay in same chunk
  - Scene breaks (--- or blank line + setting change) force new chunk
  - Overlap: last N paragraphs of chunk[i] prepended to chunk[i+1] source
```

### 2.3 Prompt Builder
```yaml
Input:
  - chunk: Chunk
  - glossary: GlossaryEntry[]
  - context: ContextBuffer
  - few_shots: FewShotPair[]
  - rules: Rule[]
Output:
  - prompt: string  # Final prompt for Ollama
  - system_prompt: string
Constraints:
  - Total prompt tokens ≤ model context window - 512 (reserve for output)
  - Glossary terms sorted by length (longest first) to avoid partial matches
```

### 2.4 Translator (Ollama Interface)
```yaml
Input:
  - prompt: string
  - model: string = "gemma2:9b"
  - temperature: float = 0.3
  - num_ctx: int = 8192
Output:
  - raw_translation: string
  - tokens_used: int
  - duration_ms: int
Retry Policy:
  - HTTP 5xx: retry after 2s, 4s, 8s (exponential backoff)
  - Empty output: retry once with temperature 0.5
  - Malformed JSON: retry once
```

### 2.5 Post-Processor
```yaml
Input:
  - raw_translation: string
  - source_chunk: Chunk
Output:
  - normalized_translation: string
Operations:
  - Strip thinking tags: <think>...</think>
  - Normalize Burmese quotes: "..." → "..." (if source used ")
  - Fix spacing: no double spaces, proper line breaks
  - Enforce glossary: regex replace any glossary term variant with canonical form
```

### 2.6 Verifier Subagent
```yaml
Input:
  - source_text: string
  - translated_text: string
  - glossary: GlossaryEntry[]
  - rules: Rule[]
Output:
  - issues: Issue[]
  - corrected_text: string  # If auto-fixable
  - pass: bool
Issue Schema:
  - severity: critical | warning | info
  - category: glossary | voice | format | coherence
  - location: line_number | text_snippet
  - message: string
  - suggestion: string
```

### 2.7 Auditor Subagent
```yaml
Input:
  - full_chapter_source: string
  - full_chapter_translation: string
  - human_reference: string | null
Output:
  - report: AuditReport
AuditReport Schema:
  - grade: A | B | C | D | F
  - scores:
      flow: 0-100
      voice_consistency: 0-100
      terminology: 0-100
      literary_quality: 0-100
  - verdict: pass | fail | needs_human_review
  - suggestions: string[]
```

---

## 3. Data Models

### 3.1 Chunk
```json
{
  "id": "ch01_sc03_ck02",
  "chapter_id": "ch01",
  "scene_id": "sc03",
  "sequence": 2,
  "type": "mixed",
  "source_text": "string",
  "translated_text": "string",
  "speakers": ["Chen Ge", "Xu Wan"],
  "preceding_overlap": "string",
  "status": "pending | translated | verified | failed",
  "tokens_in": 0,
  "tokens_out": 0
}
```

### 3.2 TranslationUnit
```json
{
  "unit_id": "uuid",
  "chapter_id": "ch01",
  "source_file": "chapter-en-0001.md",
  "output_file": "chapter-my-0001.md",
  "model": "gemma2:9b",
  "temperature": 0.3,
  "glossary_version": "1.2",
  "style_guide_version": "1.0",
  "chunks": [Chunk],
  "started_at": "ISO8601",
  "completed_at": "ISO8601",
  "final_grade": "B+"
}
```

### 3.3 GlossaryEntry
```json
{
  "term": "Chen Ge",
  "translation": "ချန်ဂီ",
  "category": "character | place | item | concept | honorific",
  "gender": "male | female | neutral",
  "formality": "informal | formal | mixed",
  "first_appearance_chapter": 1,
  "locked": true,
  "aliases": ["Chen Ge", "ChenGe"],
  "notes": "Main protagonist. Uses 'ငါ' in dialogue."
}
```

### 3.4 ContextBuffer
```json
{
  "chapter_id": "ch01",
  "scene_id": "sc03",
  "preceding_summary": "Chen Ge argues with Uncle Xu about rent.",
  "preceding_chunks": [
    {
      "chunk_id": "ch01_sc03_ck00",
      "translated_text": "...",
      "speakers": ["Uncle Xu"],
      "emotional_tone": "tense, pleading"
    }
  ],
  "active_speakers": {
    "Chen Ge": {"last_used_pronoun": "ငါ", "mood": "determined"},
    "Xu Wan": {"last_used_pronoun": "ကျွန်မ", "mood": "angry"}
  },
  "max_preceding_chunks": 2,
  "max_summary_tokens": 150
}
```

### 3.5 FewShotPair
```json
{
  "id": "fs_001",
  "category": "dialogue_male_informal | dialogue_female_polite | narration_literary",
  "source": "English text",
  "translation": "Burmese text",
  "context_note": "Chen Ge speaking to friends"
}
```

---

## 4. State Machine

```
[IDLE] ──► [CHUNKING] ──► [TRANSLATING] ──► [VERIFYING] ──► [AUDITING] ──► [APPROVED]
              │                │                  │               │
              ▼                ▼                  ▼               ▼
           [FAILED]        [RETRY]           [REVISE]        [NEEDS_HUMAN]
```

### State Definitions
- **IDLE**: Ready to accept chapter
- **CHUNKING**: Parsing and splitting source
- **TRANSLATING**: Ollama calls in progress
- **VERIFYING**: Verifier subagent scanning
- **AUDITING**: Auditor subagent reviewing full chapter
- **APPROVED**: Final output committed
- **FAILED**: Unrecoverable error (logged, human notified)
- **RETRY**: Temporary failure, automatic retry scheduled
- **REVISE**: Verifier found issues, sent back to translator
- **NEEDS_HUMAN**: Auditor grade < C or critical issues remain

### Transitions
| From | To | Trigger |
|------|-----|---------|
| IDLE | CHUNKING | `start_translation(chapter_path)` |
| CHUNKING | TRANSLATING | All chunks valid |
| TRANSLATING | VERIFYING | All chunks translated |
| VERIFYING | TRANSLATING | Issues found with auto-fix=false |
| VERIFYING | AUDITING | All chunks pass verification |
| AUDITING | APPROVED | Grade ≥ B and no critical issues |
| AUDITING | NEEDS_HUMAN | Grade < B or critical issues |
| NEEDS_HUMAN | APPROVED | Human reviewer approves |
| TRANSLATING | RETRY | Ollama timeout |
| RETRY | TRANSLATING | Retry attempt ≤ 3 |
| RETRY | FAILED | Retry attempt > 3 |

---

## 5. File Format Specifications

### 5.1 Source Markdown
```markdown
---
title: "Chapter 1: Dying House of Horrors"
novel: "My House of Horrors"
chapter: "Chapter 1"
index: "1"
source: "https://..."
---

# Chapter 1: Dying House of Horrors

"This is the first time..."
```

### 5.2 Output Markdown
```markdown
---
title: "အခန်း ၁ - သေမင်းတော်၏ အိမ်"
novel: "ကျွန်ုပ်၏ သရဲစံအိမ်"
chapter: "အခန်း ၁"
index: "1"
translated_by: "ollama-gemma2-9b"
verified: true
audited: true
grade: "B+"
glossary_version: "1.2"
---

# အခန်း ၁ - သေမင်းတော်၏ အိမ်

"ဒီလောက် ကြောက်ဖို့မကောင်းတဲ့..."
```

### 5.3 Metadata JSON
```json
{
  "unit_id": "uuid",
  "chapter_id": "ch01",
  "state": "APPROVED",
  "model": "gemma2:9b",
  "temperature": 0.3,
  "tokens_total": 15420,
  "duration_seconds": 340,
  "chunks_count": 12,
  "issues_found": 3,
  "issues_auto_fixed": 3,
  "auditor_grade": "B+",
  "glossary_hits": 47,
  "created_at": "2026-08-09T22:00:00+08:00"
}
```

---

## 6. Error Handling Matrix

| Error Code | Scenario | Retry | Fallback | Human Alert |
|------------|----------|-------|----------|-------------|
| E_CONN | Ollama server down | Yes (3×) | Switch model | After final retry |
| E_TIMEOUT | Generation > 120s | Yes (2×) | Increase timeout | No |
| E_EMPTY | Model returns empty | Yes (1×) | Temp 0.5 | If still empty |
| E_FORMAT | Output not valid markdown | No | Post-processor fix | If fix fails |
| E_GLOSSARY | Term missing in output | No | Auto-insert + flag | If auto-insert fails |
| E_CONTEXT | Context buffer corrupt | No | Rebuild from last good | Yes |

---

## 7. Versioning & Traceability

Every output file must contain:
- `glossary_version`: Hash of `config/glossary.json`
- `style_guide_version`: Hash of `config/style_guide.json`
- `prompt_version`: Hash of `prompts/` directory
- `model`: Exact Ollama model tag (e.g., `gemma2:9b-instruct-q4_K_M`)

This ensures **reproducibility**: given the same source + config hashes + model, the output must be identical.

---

## 8. Micro-Prompting Strategy

Instead of one monolithic prompt, each chunk undergoes **4 micro-prompts**:

### Micro-Prompt 1: Analyze & Tag
**Purpose**: Identify speakers, emotional tone, scene type  
**Input**: Source chunk  
**Output**: JSON with `speakers`, `tone`, `type` (dialogue-heavy / narration-heavy / mixed)

### Micro-Prompt 2: Draft Translate
**Purpose**: Produce faithful, literal translation  
**Input**: Source chunk + Glossary + Context + Few-shots  
**Output**: Burmese draft (may be slightly robotic)

### Micro-Prompt 3: Literary Polish
**Purpose**: Transform draft into literary prose  
**Input**: Draft + Style Guide + Human reference snippets  
**Output**: Polished Burmese (natural, flowing)

### Micro-Prompt 4: Format Normalize
**Purpose**: Ensure markdown compliance and glossary exactness  
**Input**: Polished text  
**Output**: Final normalized text ready for verification

**Why micro-prompts?**
- Reduces cognitive load per LLM call
- Allows targeted retry (if polish fails, retry only MP3)
- Easier to debug (inspect intermediate outputs)
- Verifier can check MP2 (accuracy) and MP3 (style) separately

---

## 9. Context Buffer Management

### 9.1 Storage
`context_buffer.json` lives in project root. Structure is a dictionary keyed by `chapter_id`.

### 9.2 Sliding Window
- Keep last **2 chunks** verbatim in buffer
- Summarize chunks older than 2 (max 150 tokens)
- If scene changes, flush buffer and start new scene summary

### 9.3 Update Policy
- After each chunk is **approved** by Verifier, append to buffer
- If chunk is **revised**, update buffer with revised version
- Buffer is **read-only** during translation of current chunk

### 9.4 Eviction
- When chapter completes, archive buffer to `archive/context/ch01.json`
- Active buffer only holds current chapter

---

## 10. Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-08-09 | Use scene-based chunking | Preserves dialogue blocks and narrative flow |
| 2026-08-09 | Two-pass translation (Draft → Polish) | Separates accuracy from artistry |
| 2026-08-09 | Temperature 0.3 | Balances creativity with determinism |
| 2026-08-09 | Verifier before Auditor | Catch term-level errors before holistic review |
| 2026-08-09 | JSON context buffer (not in-memory) | Survives crashes; enables resume |

---

*End of SPEC.md*
