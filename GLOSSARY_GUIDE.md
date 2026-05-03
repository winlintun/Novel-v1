# GLOSSARY_GUIDE.md - Glossary Management Guide

## Overview
The glossary system ensures consistent terminology across all translations of Chinese Wuxia/Xianxia novels to Myanmar (Burmese).

---

## Glossary Files

| File | Purpose | Location |
|------|---------|----------|
| `data/glossary.json` | Approved terms (auto-approved or human-reviewed) | Persistent |
| `data/glossary_pending.json` | New terms awaiting human review | Review queue |
| `data/context_memory.json` | Chapter context and story state | Runtime |

---

## Term Schema

### Approved Term (glossary.json)
```json
{
  "version": "1.0",
  "total_terms": 42,
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

### Pending Term (glossary_pending.json)
```json
{
  "pending_terms": [
    {
      "source": "新术语",
      "target": "မြန်မာ",
      "category": "item",
      "extracted_from_chapter": 12,
      "status": "pending"
    }
  ]
}
```

---

## Categories

| Category | Description | Examples |
|----------|-------------|----------|
| `character` | Character names | 罗青, 掌门 |
| `place` | Location names | 天龙城, 青云山 |
| `level` | Cultivation levels | 金丹, 元婴 |
| `item` | Items, weapons | 法宝, 灵丹 |
| `technique` | Skills, techniques | 御剑术, 炼丹 |
| `title` | Titles, honorifics | 长老, 宗主 |

---

## Actual Working Flow

### Translation Pipeline (5 Stages)

```
┌─────────────────────┐
│ 1. PREPROCESSING    │ → Clean text, detect language, chunk paragraphs
└──────────┬──────────┘
           ↓
┌─────────────────────┐
│ 2. TRANSLATION      │ → CN → MM via padauk-gemma:q8_0
└──────────┬──────────┘
           ↓
┌─────────────────────┐
│ 3. QUALITY CHECK    │ → Myanmar linguistic validation
└──────────┬──────────┘
           ↓
┌─────────────────────┐
│ 4. CONSISTENCY      │ → Glossary verification
└──────────┬──────────┘
           ↓
┌─────────────────────┐
│ 5. QA REVIEW        │ → Final validation (score ≥70)
└─────────────────────┘
```

### Stage Details

**Stage 1: Preprocessing**
- Clean markdown, normalize text
- Detect source language (CN/EN)
- Split into paragraph-safe chunks (no overlap)

**Stage 2: Translation**
- Translate Chinese → Myanmar using padauk-gemma:q8_0
- Uses glossary for term consistency
- SVO → SOV sentence structure conversion

**Stage 3: Quality Check (MyanmarQC)**
- Particle accuracy (သည်/ကို/မှာ)
- Archaic word detection (avoid ဤ, ထို)
- Bengali script blocking (U+0980–U+09FF)

**Stage 4: Consistency**
- Verify all names/places against glossary
- Replace mismatches with exact glossary terms

**Stage 5: QA Review**
- Myanmar ratio ≥ 70%
- Markdown structure preserved
- Glossary consistency score
- LLM quality score ≥ 70 (final gate)

**Post-Chapter: Context Update**
- Scan translated text for new proper nouns
- Extract to `glossary_pending.json`
- Human reviews and approves
- Approved terms move to `glossary.json`

---

### Pipeline Modes

| Mode | Stages | Description |
|------|--------|-------------|
| `full` | 7 stages | Preprocess → Translate → Refine → Reflect → QC → Consistency → QA |
| `default` | 6 stages | Preprocess → Translate → Refine → QC → Consistency → QA |
| `fast` | 3 stages | Preprocess → Translate → QC |
| `single_stage` | 5 stages | Preprocess → Translate → QC → Consistency → QA |

---

## Adding Terms

### Method 1: Direct Edit (glossary.json)
```json
{
  "terms": [
    {
      "id": "term_XXX",
      "source": "术语",
      "target": "မြန်မာ",
      "category": "character",
      "chapter_first_seen": 1,
      "verified": true
    }
  ]
}
```

### Method 2: Pending Review (glossary_pending.json)
```json
{
  "pending_terms": [
    {
      "source": "术语",
      "target": "မြန်မာ",
      "category": "character",
      "extracted_from_chapter": 5,
      "status": "pending"
    }
  ]
}
```
After review: Set `"status": "approved"` → Auto-sync to glossary.json

### Method 3: Auto-Generation
```bash
python -m src.main --novel "novel_name" --generate-glossary
```

---

## Naming Rules

| Type | Rule | Example |
|------|------|---------|
| Chinese Names | Phonetic (pinyin→Myanmar) | 罗青 → လူချင်း |
| Cultivation Terms | Keep English | Golden Core → Golden Core |
| Place Names | Hybrid (phonetic + meaning) | 天龙城 → ထျန်လုံမြို့ |
| Unknown Terms | Use placeholder | 【?term?】 |

---

## Best Practices

1. **Review Weekly** - Check `glossary_pending.json` every week
2. **Verify First** - Ensure translations are accurate before approval
3. **Consistency** - Same term = same translation throughout novel
4. **Categories** - Always tag with correct category
5. **Never Guess** - Use `【?term?】` placeholder for unknown terms
6. **Backup** - FileHandler auto-creates `.bak` on every write

---

## CLI Commands

```bash
# Translate single chapter
python -m src.main --novel 古道仙鸿 --chapter 1

# Translate all chapters
python -m src.main --novel 古道仙鸿 --all

# Generate glossary from novel
python -m src.main --novel 古道仙鸿 --generate-glossary

# Run with cache clean
./run.sh --novel 古道仙鸿 --chapter 1

# Clean cache only
./clean_cache.sh

# Diagnose setup
python diagnose.py
```

---

## Quality Gates

| Gate | Threshold | Action if Fail |
|------|-----------|----------------|
| Myanmar Ratio | ≥ 70% | Re-translate chunk |
| LLM Quality Score | ≥ 70 | Retry (max 2x) |
| Glossary Match | 100% | Replace with glossary terms |
| Bengali Script | 0 chars | Strip + re-translate |

---

## Troubleshooting

- **Missing terms**: Check `glossary_pending.json` for new extractions
- **Inconsistent names**: Edit `glossary.json` directly, re-run postprocessor
- **Low quality score**: Adjust temperature in `config/settings.yaml`
- **Ollama timeout**: Reduce chunk_size in config