# GLOSSARY_GUIDE.md - Glossary Management

## Overview
The glossary system ensures consistent terminology across all translations.

## Glossary Files

| File | Purpose |
|------|---------|
| `data/glossary.json` | Approved terms (auto-approved or human-reviewed) |
| `data/glossary_pending.json` | New terms awaiting human review |

## Term Schema

### Approved Term (glossary.json)
```json
{
  "id": "term_001",
  "source": "罗青",
  "target": "လူချင်း",
  "category": "character",
  "chapter_first_seen": 1,
  "verified": true
}
```

### Pending Term (glossary_pending.json)
```json
{
  "source": "新术语",
  "target": "မြန်မာ",
  "category": "item",
  "extracted_from_chapter": 12,
  "status": "pending"
}
```

## Categories
- `character` - Character names
- `place` - Location names
- `level` - Cultivation levels (e.g., Golden Core, Nascent Soul)
- `item` - Items, weapons, treasures
- `technique` - Skills, techniques
- `title` - Titles, honorifics

## Adding Terms Manually

### Method 1: Direct Edit
Edit `data/glossary.json`:
```json
{
  "terms": [
    {
      "id": "term_XXX",
      "source": "_term_",
      "target": "မြန်မာ",
      "category": "character",
      "chapter_first_seen": 1,
      "verified": true
    }
  ]
}
```

### Method 2: Pending Review
Add to `data/glossary_pending.json`:
```json
{
  "pending_terms": [
    {
      "source": "_term_",
      "target": "မြန်မာ",
      "category": "character",
      "extracted_from_chapter": 5,
      "status": "pending"
    }
  ]
}
```

Then set `"status": "approved"` after review.

## Auto Glossary Generation

The Term Extractor (ContextUpdater) automatically:
1. Scans translated text for new proper nouns
2. Extracts them to `glossary_pending.json`
3. Human reviews and approves
4. Approved terms move to `glossary.json`

## Naming Rules

| Type | Rule | Example |
|------|------|---------|
| Chinese Names | Phonetic (pinyin→Myanmar) | 罗青 → လူချင်း |
| Cultivation Terms | Keep English | Golden Core, Divine Sense |
| Place Names | Hybrid | 天龙城 → ထျန်လုံမြို့ |
| Unknown Terms | Use placeholder | 【?term?】 |

## Best Practices

1. **Review Weekly** - Check `glossary_pending.json` regularly
2. **Verify First** - Ensure translations are accurate before approval
3. **Consistency** - Keep same translation throughout novel
4. **Categories** - Always tag with correct category