# Context vs Glossaries - Relationship Guide

## Overview

The project uses two complementary systems for managing novel translation data:

1. **Glossaries** (`glossaries/{novel_name}.json`)
2. **Context** (`context/{novel_name}/`)

Understanding their relationship helps maintain consistency across translations.

---

## Glossaries (`glossaries/`)

**Purpose**: Primary storage for name mappings used during translation.

**File**: `glossaries/{novel_name}.json`

**Structure**:
```json
{
  "names": {
    "Gu Wen": "ဂူဝမ်",
    "Marquis Wen": "ဝမ်တိုင်",
    "Bianjing": "ဘိန်းကျိင်"
  },
  "metadata": {
    "novel_name": "dao-equaling-the-heavens",
    "total_names": 3,
    "chapter_count": 10
  }
}
```

**Used By**:
- Translation system prompt (injected for name consistency)
- Post-processor (name enforcement)
- GlossaryManager class

**When to Update**:
- When you discover new character names
- When you want to enforce consistent name translations
- Before starting a new chapter

---

## Context (`context/`)

**Purpose**: Track characters, story events, and chapter summaries for context injection.

**Directory**: `context/{novel_name}/`

**Files**:
```
context/{novel_name}/
├── characters.json    # Character details (traits, relationships, appearances)
├── story.json         # Story events and plot progression
└── chapters.json      # Chapter summaries and metadata
```

### characters.json
```json
{
  "characters": {
    "Gu Wen": {
      "name": "Gu Wen",
      "burmese_name": "ဂူဝမ်",
      "description": "Main protagonist, weak constitution",
      "first_appearance": 1,
      "importance": "major",
      "traits": ["intelligent", "sickly"],
      "relationships": {
        "Marquis Wen": "father"
      }
    }
  }
}
```

### story.json
```json
{
  "events": [
    {
      "chapter": 1,
      "title": "Summoned by Employer",
      "summary": "Gu Wen is summoned to the prince mansion",
      "importance": "major",
      "characters_involved": ["Gu Wen"]
    }
  ]
}
```

### chapters.json
```json
{
  "chapters": {
    "1": {
      "chapter_num": 1,
      "title": "Chapter 1: Gu Wen",
      "summary": "Gu Wen travels through Bianjing...",
      "characters_appearing": ["Gu Wen"],
      "translation_status": "translated"
    }
  }
}
```

**Used By**:
- Context injection system (injected into translation prompts)
- ContextManager class
- Reader app (for reading progress)

**When to Update**:
- After translating each chapter (auto-updated)
- When new characters appear
- When major story events occur

---

## Relationship Between Systems

```
┌─────────────────────────────────────────────────────────────┐
│                     Name Converter                          │
│                  (scripts/name_converter.py)                 │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              │                               │
              ▼                               ▼
┌─────────────────────────────┐  ┌─────────────────────────────┐
│       GLOSSARIES            │  │         CONTEXT             │
│    (glossaries/)            │  │      (context/)             │
│                             │  │                             │
│ • Primary name storage      │  │ • Character details         │
│ • Used in translation       │  │ • Story tracking            │
│ • Enforced post-process     │  │ • Chapter summaries         │
│                             │  │                             │
│ File: {novel}.json          │  │ Files:                      │
│                             │  │   - characters.json         │
│ {                           │  │   - story.json              │
│   "names": {                │  │   - chapters.json           │
│     "Name": "မြန်မာ"        │  │                             │
│   }                         │  │                             │
│ }                           │  │                             │
└─────────────────────────────┘  └─────────────────────────────┘
              │                               │
              └───────────────┬───────────────┘
                              │
                              ▼
              ┌───────────────────────────────┐
              │      TRANSLATION PIPELINE     │
              │                               │
              │  1. Load glossary names       │
              │     → Inject into prompt      │
              │                               │
              │  2. Load context              │
              │     → Inject characters       │
              │     → Inject story events     │
              │                               │
              │  3. Translate with context    │
              │                               │
              │  4. Update context            │
              │     → New characters          │
              │     → Chapter summary         │
              │                               │
              └───────────────────────────────┘
```

### How They Work Together

1. **Glossary provides names** → Used in system prompt for translation
2. **Context provides details** → Characters, story, previous chapters
3. **Both synced** → NameConverter keeps them in sync

---

## Using the Name Converter

### 1. Interactive Mode

```bash
python scripts/name_converter.py --novel dao-equaling-the-heavens --interactive
```

Commands:
- `add` - Add a new name manually
- `list` - Show all names
- `convert` - Convert text with known names
- `learn` - Auto-learn from chapter
- `sync` - Sync glossary and context
- `export` - Export to JSON file
- `import` - Import from JSON file

### 2. Auto-Learn from Chapter

```bash
# Learn from source chapter only
python scripts/name_converter.py \
  --novel dao-equaling-the-heavens \
  --source-lang English \
  --learn-from english_chapters/dao-equaling-the-heavens/chapter_001.md

# Learn with parallel text (better accuracy)
python scripts/name_converter.py \
  --novel dao-equaling-the-heavens \
  --learn-from english_chapters/dao-equaling-the-heavens/chapter_001.md \
  --translated books/dao-equaling-the-heavens/chapters/chapter_001_myanmar.md
```

### 3. Convert Names in File

```bash
python scripts/name_converter.py \
  --novel dao-equaling-the-heavens \
  --convert-file input.txt \
  --output output.txt
```

### 4. Sync Systems

```bash
# Sync glossary → context
python scripts/name_converter.py \
  --novel dao-equaling-the-heavens \
  --sync
```

### 5. Export/Import

```bash
# Export all names
python scripts/name_converter.py \
  --novel dao-equaling-the-heavens \
  --export dao_names.json

# Import names (with overwrite)
python scripts/name_converter.py \
  --novel dao-equaling-the-heavens \
  --import-file dao_names.json
```

---

## Best Practices

### 1. Before Starting Translation

```bash
# 1. Create initial glossary from known names
python scripts/name_converter.py --novel my_novel --interactive
# Then use 'add' command to add known names

# 2. Sync to context
python scripts/name_converter.py --novel my_novel --sync
```

### 2. During Translation

- Names are auto-extracted and added to glossary
- Context is auto-updated after each chapter
- Review and correct names periodically

### 3. After Translation

```bash
# Export final glossary for future reference
python scripts/name_converter.py \
  --novel my_novel \
  --export my_novel_glossary_final.json
```

### 4. For Sequels/Related Novels

```bash
# Import existing glossary as starting point
python scripts/name_converter.py \
  --novel sequel_novel \
  --import-file original_novel_glossary.json
```

---

## Quick Reference

| Task | Command |
|------|---------|
| Add name manually | `--interactive` → `add` |
| Auto-learn from chapter | `--learn-from chapter.md` |
| Sync systems | `--sync` |
| Convert text | `--convert-file input.txt --output output.txt` |
| Export names | `--export names.json` |
| Import names | `--import-file names.json` |
| List all names | `--interactive` → `list` |

---

## File Locations

```
project/
├── glossaries/
│   └── {novel_name}.json          # Name mappings
├── context/
│   └── {novel_name}/
│       ├── characters.json        # Character details
│       ├── story.json            # Story events
│       └── chapters.json         # Chapter summaries
└── scripts/
    └── name_converter.py         # This tool
```
