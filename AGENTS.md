# AGENTS.md - AI Agent Guidance for Novel Translation Project

## Project Overview

This is a **Chinese-to-Burmese novel translation system** built in Python. The system uses AI models (local via Ollama or cloud APIs) to translate Chinese web novels and literary works into Burmese while preserving tone, style, and emotional depth.

---

## Quick Reference

- **Main Entry Point**: `main.py` - Orchestrates the entire translation pipeline
- **Configuration**: `.env` for API keys, `config/config.json` for runtime settings
- **Scripts**: `scripts/` folder contains modular pipeline components
- **Input**: Place Chinese novels in `input_novels/` (.txt or .md)
- **Output**: Burmese translations appear in `translated_novels/`

---

## Agent Roles

### 1. Translation Agent

**Role**: Professional Literary Translator (Chinese → Burmese)

**Responsibilities**:
- Faithfully translate Chinese text to natural, literary Burmese
- Maintain original tone (formal, colloquial, poetic)
- Adapt cultural references appropriately
- Ensure consistent naming across all chunks
- Output clean, UTF-8 encoded Burmese text

**Guidelines**:
- **NO Explanations**: Do not add translator notes or commentary.
- **NO Conversational Filler**: Absolutely no phrases like "Here is the translation" or "Sure, I can help."
- **Direct Output**: Provide only the translated Burmese text.
- **NO Mixed Language**: Never output Chinese characters.
- **Literary Quality**: Avoid literal word-for-word translations, but do not hallucinate new events.
- **Myanmar Script**: Use only Myanmar Unicode (U+1000–U+109F).
- **Strict Glossary**: Always enforce the mappings from the novel's glossary file (`glossaries/<novel_name>.json`).

### Glossary / Character Name Consistency System

The project uses a **per-novel glossary system** to ensure character names and terminology remain consistent throughout translation:

**Storage Location**: `glossaries/<novel_name>.json`
- Each novel gets its own glossary file (e.g., `glossaries/novel_one.json`)
- Format: `{"names": {"Chinese Name": "Burmese Name"}, "metadata": {...}}`

**Automatic Features**:
1. **Load**: Glossary is automatically loaded at start of each chapter translation
2. **Inject**: All name mappings are injected into the system prompt
3. **Update**: After each chapter, new potential names are extracted and glossary is saved
4. **Persistence**: Glossary accumulates across chapters for the same novel

**Manual Management**:
```bash
# View glossary for a novel
python scripts/glossary_manager.py novel_name list

# Add a name manually
python scripts/glossary_manager.py novel_name add "魏无羡" "ဝေ့ဝူရှျန်"

# View statistics
python scripts/glossary_manager.py novel_name stats

# Extract potential names from a file
python scripts/glossary_manager.py novel_name extract input_novels/chapter.txt
```

**Fallback**: If no novel-specific glossary exists, system falls back to global `names.json`

**Prompt Template**:
```text
SYSTEM:
You are an expert literary translator specializing in Chinese to Myanmar (Burmese) translation.
CRITICAL INSTRUCTIONS:
1. You MUST translate the provided Chinese text into MYANMAR LANGUAGE (Burmese) using Myanmar Unicode script.
2. Output ONLY the raw Burmese translation. NO conversational filler. NO English. NO Chinese. NO "Here is the translation:".
3. Maintain the literary style and tone of a xianxia/wuxia novel.
4. Do not summarize; translate everything contextually.
[GLOSSARY INJECTED HERE]

USER:
Chinese Text to Translate:
[CHINESE_TEXT_CHUNK]

Burmese Translation:
```