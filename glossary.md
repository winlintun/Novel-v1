# Glossary Extraction System — Complete Guide

## Overview

This project uses a **multi-stage, AI-powered glossary extraction pipeline** to automatically identify, translate, and manage terminology from Chinese/English Wuxia/Xianxia novels into Myanmar (Burmese). The system is designed to work **per-novel**, meaning each novel gets its own isolated glossary database.

---

## Architecture

```
Source Chapter (CN/EN)
        │
        ▼
┌─────────────────────────────────────────────────┐
│  Stage 1: GlossaryGenerator (Pre-translation)   │
│  - LLM extracts terms from source text          │
│  - Outputs v3.2.1 schema JSON                   │
│  - Saves to glossary_pending.json               │
└─────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────┐
│  Stage 2: ContextUpdater (Post-translation)     │
│  - LLM extracts entities from translated text   │
│  - Adds new terms to pending glossary           │
│  - Updates chapter context memory               │
└─────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────┐
│  Stage 3: GlossarySyncAgent (Consistency)       │
│  - Detects inconsistent translations            │
│  - Proposes merge for duplicates                │
│  - Flags variants for human review              │
└─────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────┐
│  Stage 4: MemoryManager (Storage & Approval)    │
│  - Pending → Approved promotion                 │
│  - Auto-approve by confidence score             │
│  - Myanmar text validation                      │
│  - SQLite or JSON backend                       │
└─────────────────────────────────────────────────┘
```

---

## File Locations

| File | Purpose |
|------|---------|
| `src/agents/glossary_generator.py` | Main term extraction agent (pre-translation) |
| `src/agents/context_updater.py` | Post-translation entity extraction |
| `src/agents/glossary_sync.py` | Consistency checking & deduplication |
| `src/memory/memory_manager.py` | 3-tier memory system (glossary + context + rules) |
| `src/utils/glossary_matcher.py` | Dynamic term matching during translation |
| `src/utils/glossary_suggestor.py` | Confidence-scored term suggestions |
| `data/output/{novel}/glossary/glossary.json` | Approved glossary (per-novel) |
| `data/output/{novel}/glossary/glossary_pending.json` | Pending terms awaiting review |
| `data/output/{novel}/glossary/context_memory.json` | Chapter context & active characters |

---

## Stage 1: GlossaryGenerator (Pre-Translation Extraction)

### How It Works

1. **Input**: Source chapter file (Chinese or English Markdown)
2. **Process**: Sends first 4000 characters to Ollama LLM (`padauk-gemma`) with a structured extraction prompt
3. **Output**: JSON matching v3.2.1 schema with categorized terms
4. **Save**: Terms go to `glossary_pending.json` (NOT directly to approved glossary)

### Extraction Categories

| Category | Prefix | Examples |
|----------|--------|----------|
| `character` | `char_` | 方源 (Fang Yuan), 古月 (Gu Yue) |
| `location` | `loc_` | 青茅山 (Qing Mao Mountain), 古月村 (Gu Yue Village) |
| `organization` | `org_` | 古月一族 (Gu Yue Clan), 影宗 (Shadow Sect) |
| `item_artifact` | `item_` | 春秋蝉 (Spring Autumn Cicada), 仙蛊 (Immortal Gu) |
| `technique` | `tech_` | 血海魔功 (Blood Sea Demonic Art) |
| `power_level` | `lvl_` | 一转 (Rank 1), 蛊师 (Gu Master) |
| `cultivation_concept` | `cult_` | 天道 (Heavenly Dao), 真元 (True Essence) |
| `title_honorific` | `title_` | 前辈 (Senior), 尊者 (Venerable) |
| `event` | `event_` | 三转考核 (Three-Turn Assessment) |

### v3.2.1 Schema Structure

```json
{
  "extraction_meta": {
    "schema_version": "3.2.1",
    "source_language": "Chinese",
    "total_terms_found": 15,
    "overall_confidence": "high"
  },
  "terms": [
    {
      "id": "char_001",
      "source_term": "方源",
      "target_term": "ဖန်ယွမ်",
      "aliases_en": ["Fang Yuan"],
      "aliases_cn": ["方源"],
      "category": "character",
      "translation_rule": "transliterate",
      "priority": 1,
      "gender": "male",
      "affiliation": ["古月一族"],
      "status": "pending",
      "usage_frequency": "high",
      "chapter_first_seen": 1,
      "description": "Main protagonist, reincarnated 500 years",
      "context_variants": {
        "formal":   {"self": "ကျွန်တော်", "target": "ခင်ဗျား", "honorific": "ဆရာ"},
        "casual":   {"self": "ငါ",        "target": "မင်း",     "honorific": ""},
        "hostile":  {"self": "ငါ",        "target": "နင်",      "honorific": "မိစ္ဆာကောင်"}
      },
      "relationships": [],
      "usage_example": {
        "source": "方源睁开眼睛。",
        "target": ""
      },
      "confidence": 0.95,
      "notes": "Main character — always priority 1"
    }
  ]
}
```

### Key Code Path

```python
# src/agents/glossary_generator.py
generator = GlossaryGenerator(ollama_client, memory_manager, config)
terms = generator.extract_terms(text, source_lang="Chinese")
generator.save_to_pending(terms, chapter_num=1)
```

---

## Stage 2: ContextUpdater (Post-Translation Extraction)

### How It Works

After a chapter is translated, the `ContextUpdater` agent:

1. Reads the **original source text** (first 3000 chars)
2. Sends it to Ollama with the `EXTRACTOR_SYSTEM_PROMPT`
3. Extracts new entities that may have been missed in Stage 1
4. Adds them to `glossary_pending.json`
5. Updates chapter context memory (active characters, recent events)

### Key Code Path

```python
# src/agents/context_updater.py
updater = ContextUpdater(ollama_client, memory_manager, config)
result = updater.process_chapter(original_text, translated_text, chapter_num=1)
# Returns: entities_found, new_terms_added, characters, realms, sects, items
```

---

## Stage 3: GlossarySyncAgent (Consistency Checking)

### Two Functions

1. **`check_consistency()`**: Scans translated Myanmar text for terms that don't match approved glossary entries
2. **`propose_merges()`**: Compares pending terms against approved glossary to find duplicates/variants

### Example Output

```json
{
  "inconsistencies": [
    {
      "term_in_text": "ဖန့်ယွမ်",
      "glossary_term": "ဖန်ယွမ်",
      "suggestion": "replace_with_approved"
    }
  ],
  "new_candidates": [
    {
      "source_cn": "新词",
      "proposed_mm": "ကမ်းလှမ်းချက်",
      "category": "item",
      "confidence": 0.85
    }
  ]
}
```

---

## Stage 4: MemoryManager (Storage & Approval)

### 3-Tier Memory System

| Tier | Name | Purpose |
|------|------|---------|
| Tier 1 | Glossary | Approved terminology (persistent) |
| Tier 2 | Context Memory | Chapter summaries, active characters, FIFO buffer |
| Tier 3 | Session Rules | Temporary correction rules (session-only) |

### Approval Workflows

#### Manual Approval
Edit `glossary_pending.json` and change `"status": "pending"` to `"status": "approved"`. Next pipeline run auto-promotes.

#### Auto-Approve by Confidence
```python
# Promotes terms with confidence >= 0.75
memory.auto_approve_by_confidence(confidence_threshold=0.75)
```

Confidence scoring rules:
- Seen in ≥3 chapters → +0.40
- Seen in ≥2 chapters → +0.25
- Category is character/place → +0.20
- Target is not placeholder → +0.15
- Proper Myanmar (no Latin) → +0.10
- Chinese name pattern (2-3 chars) → +0.10

#### Bulk Approve All
```python
memory.bulk_approve_all_pending()
```

### Myanmar Validation

All target terms are validated before storage:
```python
# Checks Myanmar Unicode ratio (U+1000-U+109F, U+AA60-U+AA7F, U+A9E0-U+A9FF)
# Minimum 50% Myanmar characters required
# Placeholders like 【?term?】 bypass validation
```

---

## GlossaryMatcher (Runtime Injection)

During translation, `GlossaryMatcher` dynamically selects relevant terms:

```python
# src/utils/glossary_matcher.py
matcher = GlossaryMatcher(glossary_path)
relevant = matcher.get_relevant_terms(chapter_text)
snippet = matcher.get_relevant_glossary_snippet(chapter_text, max_entries=20)
```

Returns a compact markdown table injected into the translation prompt:
```
[GLOSSARY - USE EXACT TRANSLATIONS]
| Chinese | Myanmar | Category | Notes |
|---------|---------|----------|-------|
| 方源 | ဖန်ယွမ် | character | - |
| 蛊师 | ဂူးဆရာ | power_level | - |
```

---

## GlossarySuggestor (Heuristic Suggestions)

Provides confidence-scored term suggestions without LLM:

```python
# src/utils/glossary_suggestor.py
suggestions = suggest_new_terms(text, glossary_path)
# Returns list of {source, suggested_target, confidence, requires_review}
```

---

## Data Flow Summary

```
Chapter File (.md)
    │
    ├──► GlossaryGenerator.extract_terms()
    │       │
    │       ├──► Ollama LLM (padauk-gemma)
    │       │       │
    │       │       └──► v3.2.1 JSON response
    │       │
    │       └──► MemoryManager.save_to_pending()
    │               │
    │               └──► glossary_pending.json
    │
    ├──► Translation Pipeline (uses GlossaryMatcher for term injection)
    │
    └──► ContextUpdater.process_chapter()
            │
            ├──► Extract entities from source
            ├──► Add new terms to pending
            └──► Update context_memory.json

Human Review:
    glossary_pending.json → edit status → auto-promote → glossary.json
```

---

## Backend Options

### JSON Backend (Default)
- Files stored in `data/output/{novel}/glossary/`
- Atomic writes via FileHandler (temp → rename)
- UTF-8-SIG encoding

### SQLite Backend (Optional)
- Enabled via `use_sql=True` in MemoryManager
- Database: `data/novel_translation.db`
- Supports global xianxia terms shared across novels
- Repositories: `GlossaryRepository`, `ChapterRepository`, `ContextRepository`

---

## Prompt Template

The extraction prompt (`GLOSSARY_EXTRACTION_PROMPT`) enforces:

1. **Phonetic mapping rules**: Chinese → Myanmar transliteration patterns
   - F/ph → ဖ, X/Sh → ရှ/ချ, Q → ချ, Zh/Ch → ချ/ဂျ
   - -ing/-eng → -င်း/-န်, -an/-en → -န်/-မ်, -ao → -ေါ, -ou → -ိုး

2. **Translation rules**:
   - Characters/locations → transliterate or hybrid
   - Cultivation/power terms → translate meaning
   - Techniques → translate

3. **Unicode safety**: Myanmar Unicode ONLY (U+1000-U+109F), no Thai/Bengali/Chinese/English in target_term

4. **Fallback**: Unknown terms → `【?term?】` placeholder

---

## Error Handling

| Error | Solution |
|-------|----------|
| LLM returns invalid JSON | `extract_json_from_response()` with fallback |
| Empty text input | Returns empty term list |
| Non-Myanmar target | Rejected by `_is_valid_myanmar_text()` |
| Duplicate term | Skipped, logged with count |
| Placeholder target | Skipped (not saved to pending) |
