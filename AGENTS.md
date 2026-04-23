# AGENTS.md - AI Agent Guidance for Novel Translation Project

---

## ⚡ MANDATORY SESSION PROTOCOL (Auto-runs — No prompt needed)

> These rules execute automatically at the start and end of **every session**.
> You do not need to be asked. This is non-negotiable default behavior.

### 🟢 SESSION START — Do this FIRST, before any code or reply

```
STEP 1: Read AGENTS.md          ← you are here
STEP 2: Read GEMINI.md          ← tool-specific rules
STEP 3: Read CURRENT_STATE.md   ← what is done / not done / blocked
STEP 4: Silently confirm the task against Architecture Decisions in CURRENT_STATE.md
STEP 5: Proceed with the task
```

**If any file is missing:** Create it using the schema defined in this document. Do not skip.

### 🔴 SESSION END — Do this LAST, after every task completes

```
STEP 1: Update CURRENT_STATE.md
        - Mark completed tasks as [DONE]
        - Move in-progress tasks to [IN PROGRESS]
        - Log any new bugs or blockers discovered
        - Update "Last Updated" date and "Last task completed" fields
STEP 2: Run Code Review Workflow (sub-agents A + B in parallel)
STEP 3: Fix all issues until both sub-agents respond READY_TO_COMMIT
```

**Trigger condition:** Any of these actions = session end update required:
- A file in `src/` was created or modified
- A feature was completed or partially completed  
- A bug was found or fixed
- Any decision was made that affects architecture

---

## Project Overview

This project is an advanced, AI-powered **Chinese-to-Myanmar (Burmese) novel translation system** specializing in Wuxia/Xianxia novels. It uses a multi-stage agent pipeline to translate web novels while preserving tone, style, literary depth, and strict terminology consistency.

---

## 🏗 System Architecture & Pipeline

The translation process follows a strict 4-stage pipeline orchestrated by `src/main.py`:

```
main.py
  → Load config/settings.yaml
  → Initialize MemoryManager (load glossary.json, context_memory.json)
  → Preprocessor.load_and_preprocess()  → Chunks
  → Translator.translate_chunks()        → Stage 1: Raw translation
  → Refiner.refine_full_text()           → Stage 2: Literary editing
  → Checker.check_chapter()             → Stage 3: Consistency check
  → QA Review                           → Stage 4: Final QA
  → TermExtractor (post-chapter)        → Extract new terms → glossary_pending.json
  → FileHandler.write_text()            → Save to data/output/
  → ContextUpdater.process_chapter()    → Update glossary.json, context_memory.json
```

1. **Preprocess:** Clean and normalize input text, split into paragraph-safe chunks with sliding window overlap.
2. **Context & Glossary Loading:**
   - `MemoryManager`: 3-tier memory system (Glossary → Context → Session rules).
   - `data/glossary.json`: Enforces strict terminology consistency.
   - `data/context_memory.json`: Remembers ongoing story and character relationships.
3. **Translate (Stage 1):** Translator Agent produces an accurate, literal translation.
4. **Edit (Stage 2):** Editor Agent rewrites for natural flow and literary quality.
5. **Consistency Check (Stage 3):** Consistency Checker verifies all terms against the glossary.
6. **QA Review (Stage 4):** Final Reviewer validates logical flow, tone, and formatting.
7. **Term Extraction (Post-Chapter):** Term Extractor scans for new proper nouns and routes them to `glossary_pending.json` for human review.
8. **Assemble:** Save to `data/output/`.

---

## 🤖 AI Agent Roles & System Prompts

### 1. Translator Agent (Stage 1)

**Goal:** Produce a complete, accurate translation. Convert Chinese SVO to Myanmar SOV. Do not summarize or skip sentences.

```text
You are an expert Chinese-to-Myanmar literary translator specializing in Wuxia/Xianxia novels.

STRICT RULES:
1. SYNTAX: Convert Chinese SVO structure to natural Myanmar SOV order. Do NOT translate word-by-word.
2. TERMINOLOGY: Use EXACT terms from the provided GLOSSARY. Never translate names, places, or cultivation terms literally.
3. MARKDOWN: Preserve ALL formatting (#, **, *, lists, quotes). Do not add or remove any Markdown.
4. CONTEXT: Use the PREVIOUS CONTEXT to correctly resolve pronouns (he/she/they).
5. TONE: Use formal/literary Myanmar for narrative. Use natural spoken Myanmar for dialogue
   (adjust pronouns: မင်း, ရှင်, ကျွန်တော်/ကျွန်မ based on character status/hierarchy).
6. OUTPUT: Return ONLY the translated Myanmar text. Zero explanations.

GLOSSARY:
{glossary}

PREVIOUS CONTEXT (Last 2 paragraphs):
{context}

INPUT TEXT (Chinese):
{input_text}
```

**Implementation:** `src/agents/translator.py` → `Translator` class

---

### 2. Editor Agent (Stage 2)

**Goal:** Transform stiff/robotic draft translations into natural, emotionally engaging Myanmar prose.

```text
You are a senior Myanmar literary editor. Polish the draft for natural flow, literary quality,
and grammatical correctness while preserving meaning and Markdown.

RULES:
1. Fix awkward phrasing from direct translation.
2. Ensure correct SOV structure and proper particle usage (သည်/သည်ကို/အတွက်/ကဲ့သို့).
3. Refine dialogue pronouns and honorifics to match character hierarchy naturally.
4. Show, Don't Tell: Change abstract emotions to physical sensations.
5. Break long sentences into 2-3 short, rhythmic sentences.
6. Avoid archaic words (သင်သည်, ဤ). Use modern storytelling words (မင်း, ဒီ).
7. Keep all Wuxia/Xianxia terms intact.
8. OUTPUT: Return ONLY the polished Myanmar text. Zero explanations.

INPUT TEXT (Myanmar Draft):
{draft_text}
```

**Implementation:** `src/agents/refiner.py` → `Refiner` class

---

### 3. Consistency Checker Agent (Stage 3)

**Goal:** Verify all terminology, names, and places against the global glossary.

```text
You are a terminology consistency specialist. Verify the text against the GLOBAL GLOSSARY.

RULES:
1. Cross-check all names, places, items, and cultivation levels.
2. Replace any non-standard or literal translations with exact glossary terms.
3. Preserve Markdown exactly.
4. OUTPUT FORMAT:
   CORRECTIONS: [List mismatches or "None"]
   FINAL TEXT: [Corrected Myanmar text]

GLOSSARY:
{glossary}

INPUT TEXT:
{input_text}
```

**Implementation:** `src/agents/checker.py` → `Checker` class

**Quality Metrics:**
- Myanmar character ratio (target: >70%)
- Glossary consistency score
- Markdown formatting preservation
- Unicode error detection

---

### 4. QA / Final Reviewer Agent (Stage 4)

**Goal:** Final human-readable quality gate before saving output.

```text
You are a final QA reviewer for novel translation.

RULES:
1. Check for logical flow, missing sentences, or meaning drift.
2. Verify narrative/dialogue tone consistency.
3. Ensure Markdown is intact.
4. OUTPUT FORMAT:
   STATUS: [APPROVED / NEEDS REVISION]
   ISSUES: [Brief list or "None"]
   FINAL TEXT: [Myanmar text]

INPUT TEXT:
{input_text}
```

---

### 5. Term Extractor Agent (Post-Chapter)

**Goal:** Detect new proper nouns and cultivation terms not yet in the glossary. Output routes to `data/glossary_pending.json` for human review — never directly to `glossary.json`.

```text
You are a terminology extraction specialist for Chinese Wuxia/Xianxia novels.

TASK: Scan the translated Myanmar text and extract NEW proper nouns, cultivation terms,
items, or titles that are NOT in the existing glossary.

RULES:
1. Output ONLY valid JSON.
2. Format: {"new_terms": [{"source": "Chinese", "target": "Myanmar", "category": "character|place|level|item"}]}
3. Do NOT include terms already in the glossary.
4. Use consistent Myanmar transliteration rules (e.g., 林渊 → လင်ယွန်း).
5. If no new terms, return {"new_terms": []}

EXISTING GLOSSARY:
{glossary}

TRANSLATED TEXT:
{translated_text}
```

**Output file:** `data/glossary_pending.json`
**Implementation:** `src/agents/context_updater.py` → `ContextUpdater` class

---

## 📚 Memory & Glossary Systems

### MemoryManager (`src/memory/memory_manager.py`) — 3-Tier System

| Tier | Name | Storage | Scope |
|------|------|---------|-------|
| 1 | Glossary | `data/glossary.json` | Persistent across all chapters |
| 2 | Context | `data/context_memory.json` + FIFO buffer | Slides per chapter |
| 3 | Session Rules | Runtime only | Current session only |

### Glossary Schema (`data/glossary.json`)

```json
{
  "version": "1.0",
  "total_terms": 0,
  "terms": [
    {
      "id": "term_001",
      "source": "罗青",
      "target": "လူချင်း",
      "category": "character",
      "chapter_first_seen": 1,
      "verified": true
    }
  ]
}
```

### Pending Glossary Schema (`data/glossary_pending.json`)

```json
{
  "pending_terms": [
    {
      "source": "新术语",
      "target": "မြန်မာဘာသာ",
      "category": "item",
      "extracted_from_chapter": 12,
      "status": "pending"
    }
  ]
}
```

**Approval workflow:** Human reviewer sets `"status": "approved"` → nightly merge script promotes to `glossary.json`.

### Naming Rules

- **Chinese Names:** Translate phonetically (e.g., 张三 → ဇန်းဆန်း)
- **Cultivation Terms & Titles:** Translate by meaning (e.g., Spirit Energy → ဝိညာဉ်စွမ်းအား, Sect → ဇုံ)
- **Place Names:** Hybrid approach (e.g., 天龙城 → ထျန်လုံမြို့)
- **Unknown Terms:** Use `【?term?】` placeholder until reviewed — never guess

### Context Manager (`data/context_memory.json`)

```json
{
  "current_chapter": 5,
  "last_translated_chapter": 4,
  "summary": "Previous chapter summary...",
  "active_characters": {},
  "recent_events": [],
  "paragraph_buffer": []
}
```

---

## 🎛 Model Configuration (`config/settings.yaml`)

```yaml
models:
  translator: "qwen2.5:14b"   # Stage 1: Strong Chinese comprehension
  editor: "qwen2.5:14b"       # Stage 2: Literary rewriting
  checker: "qwen:7b"          # Stage 3 & 4: Fast validation
  ollama_base_url: "http://localhost:11434"
  timeout: 300

processing:
  chunk_size: 1500
  overlap_size: 100
  max_retries: 3
  temperature: 0.45           # Creativity for natural Myanmar phrasing
  top_p: 0.92
  top_k: 50
  repeat_penalty: 1.1         # Prevents character repetition — critical for Myanmar LLM output
```

---

## 📁 Directory Structure

```
novel_translation_project/
├── config/
│   └── settings.yaml
├── data/
│   ├── input/                    # Chinese chapter files (*.md)
│   ├── output/                   # Myanmar translations (*.md)
│   ├── glossary.json             # Approved terminology database
│   ├── glossary_pending.json     # New terms awaiting human review
│   └── context_memory.json       # Dynamic chapter context
├── logs/
│   └── translation.log
├── src/
│   ├── agents/
│   │   ├── preprocessor.py       # Chunking and markdown cleaning
│   │   ├── translator.py         # Stage 1: CN→MM translation
│   │   ├── refiner.py            # Stage 2: Literary editing
│   │   ├── checker.py            # Stage 3 & 4: QA validation
│   │   └── context_updater.py    # Term extraction and memory updates
│   ├── memory/
│   │   └── memory_manager.py     # 3-tier memory system
│   ├── utils/
│   │   ├── ollama_client.py      # Ollama API wrapper
│   │   └── file_handler.py       # File I/O (UTF-8-SIG, atomic writes)
│   └── main.py                   # Entry point and pipeline orchestration
├── tests/
│   ├── test_translator.py
│   └── test_integration.py
├── requirements.txt
└── README.md
```

## 🛡 Code Drift Prevention (Mandatory)
 
> ဒီ rules ၃ ချက်မရှိရင် feature ထပ်ထည့်တိုင်း pipeline တဖြည်းဖြည်း ပျက်စီးမယ်။ Non-negotiable။
 
### 1. Modular Boundaries
 
တစ်ဖိုင်နဲ့တဖိုင် တိုက်ရိုက်မခေါ်ရ — `MemoryManager` ကိုသာ ဖြတ်ရမည်။
 
```
ALLOWED                             FORBIDDEN
──────────────────────────────      ──────────────────────────────
Translator → MemoryManager          Translator → glossary.json (direct)
Refiner    → MemoryManager          Checker    → context_memory.json (direct)
Checker    → MemoryManager          ContextUpdater → Translator (cross-agent)
```
 
**Rules:**
- Agent တစ်ခုက တစ်ခုကို import မလုပ်ရ (no cross-agent imports)
- Data files (`glossary.json`, `context_memory.json`) ကို `FileHandler` မဖြတ်ဘဲ မဖတ်ရ မရေးရ
- `MemoryManager` သည် data layer ၏ single gateway ဖြစ်သည်
### 2. Type Hints (Every function, no exceptions)
 
```python
# WRONG — drift ဖြစ်စေတဲ့ ပုံစံ
def translate(text, glossary, context):
    ...
 
# CORRECT — contract ရှင်းတယ်၊ AI မှားရေးဖို့ ခက်တယ်
def translate(
    text: str,
    glossary: dict[str, str],
    context: list[str],
) -> str:
    ...
```
 
**Required on:**
- All `src/agents/*.py` public methods
- All `src/memory/memory_manager.py` methods
- All `src/utils/*.py` methods
- Data models (use `TypedDict` or `dataclass`)
```python
# Data model example
from typing import TypedDict
 
class GlossaryTerm(TypedDict):
    id: str
    source: str
    target: str
    category: str        # "character" | "place" | "level" | "item"
    chapter_first_seen: int
    verified: bool
```
 
### 3. Automated Tests (Write test before or with code)
 
**Structure:**
```
tests/
├── test_translator.py       # Translator.translate_paragraph()
├── test_refiner.py          # Refiner.refine_paragraph()
├── test_checker.py          # Checker.check_chapter(), quality score
├── test_memory_manager.py   # add_term(), get_term(), FIFO buffer
├── test_context_updater.py  # extract_entities(), pending glossary routing
├── test_file_handler.py     # atomic write, UTF-8-SIG, .bak backup
└── test_integration.py      # End-to-end: input → output file
```
 
**Minimum test per function:**
 
```python
# test_memory_manager.py example
def test_new_term_goes_to_pending_not_glossary():
    mm = MemoryManager()
    mm.add_pending_term("新术语", "မြန်မာ", "item", chapter=5)
 
    assert mm.get_term("新术语") is None          # not in approved glossary
    pending = mm.get_pending_terms()
    assert any(t["source"] == "新术语" for t in pending)  # in pending only
 
def test_unknown_term_returns_placeholder():
    mm = MemoryManager()
    result = mm.get_term("未知词")
    assert result == "【?未知词?】"               # never None, never guessed
```
 
**Run before every commit:**
```bash
pytest tests/ -v --tb=short
```
 
**CI rule:** ဘယ် function အသစ်မဆို test မပါရင် Gemini reviewer က `NEEDS REVISION` ပြန်ရမည်။
 
---

## ✅ Best Practices

- **Never overwrite blindly:** Before any `glossary.json` update, `file_handler.py` creates a `.bak` backup automatically.
- **Category tagging:** Term Extractor must tag every new term (`character`, `place`, `level`, `item`). This enables targeted consistency checking per category.
- **Human-in-the-loop:** Review `glossary_pending.json` weekly. Approving terms keeps translation quality at 95%+.
- **Fallback rule:** If a term is missing from the glossary, the Translator must output `【?term?】` as a placeholder — never attempt a free-form guess. Placeholders are resolved in the next review cycle.
- **Atomic writes:** All JSON files are written atomically (temp file → rename) via `FileHandler` to prevent corruption on crash.
- **UTF-8-SIG encoding:** All file reads/writes use UTF-8-SIG to handle BOM characters correctly across platforms.

---
## 🔍 Code Review Workflow (Post-Implementation)
 
> **Trigger:** Automatically after every feature, fix, or refactor. No prompt needed.
 
### Step-by-step Loop
 
```
┌─────────────────────────────────────────────────────┐
│  STEP 1 — OpenCode implements                       │
│  Feature / fix / refactor task ကို ပြီးမြောက်သည်    │
└────────────────────────┬────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│  STEP 2 — Gemini reviews (run TWO in parallel)      │
│                                                     │
│  gemini run "Review the latest diff/changes for    │
│  bugs and code quality. List all issues found,     │
│  or respond with READY_TO_COMMIT if none."         │
│                                                     │
│  gemini run "Review the latest diff/changes for   │
│  security issues only. List all issues found,     │
│  or respond with READY_TO_COMMIT if none."        │
└────────────────────────┬────────────────────────────┘
                         │
             ┌───────────┴───────────┐
             │                       │
     Issues found?             Both say
             │                READY_TO_COMMIT
             ▼                       │
┌────────────────────────┐           ▼
│  STEP 3 — OpenCode     │   ┌───────────────────┐
│  fixes ALL issues from │   │  STEP 5 — Commit  │
│  both Gemini agents    │   │  ယုံကြည်မှုဖြင့်   │
└────────────┬───────────┘   │  commit လုပ်သည်   │
             │               └───────────────────┘
             ▼
        STEP 4 — Repeat
        Go back to STEP 2
```
 
### Rules
 
- Gemini agents run **in parallel**, not sequentially.
- OpenCode must fix **all** issues from **both** agents before looping.
- Only commit when **both** agents respond `READY_TO_COMMIT` in the same round.
- Do not commit if even one agent still has issues outstanding.
---

## 🖥 CLI Usage

```bash
# Translate a single chapter
python -m src.main --novel 古道仙鸿 --chapter 1

# Translate all chapters
python -m src.main --novel 古道仙鸿 --all

# Translate from a specific chapter onwards
python -m src.main --novel 古道仙鸿 --all --start 5

# Skip Stage 2 refinement (faster, lower quality)
python -m src.main --novel 古道仙鸿 --chapter 1 --skip-refinement
```