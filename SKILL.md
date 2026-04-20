# Skill: Novel Translation

## Description
This skill enables the agent to perform high-quality literary translation from Chinese to Burmese (Myanmar script). It is optimized for processing long-form novel content in chunks while maintaining stylistic consistency, and producing output that passes Myanmar readability validation.

---

## Prompt Template

Every chunk is sent to the LLM using the following prompt. Do not modify this template without updating `scripts/translate_chunk.py` accordingly.

```
SYSTEM:
You are a professional literary translator.
Translate the following Chinese novel text to Burmese (Myanmar script).
Keep the tone, style, and emotions of the original.
Do NOT add chapter titles, headings, or explanations.
Output ONLY the Burmese translation. No Chinese characters. No romanization.

USER:
[CHINESE_TEXT_CHUNK]
```

---

## Implementation Details

### 1. Pre-processing
- **Script**: `scripts/preprocess_novel.py`
- **Input**: Raw Chinese `.txt` file from `input_novels/`
- **Actions**:
  - Remove headers, footers, watermarks, and ad text
  - Normalize whitespace and line endings
  - Enforce UTF-8 encoding
  - Detect and log chapter boundaries if present
- **Output**: Clean `.txt` saved to `working_data/clean/`

### 2. Translation Status Check
- **Handled by**: `main.py` on startup
- **Logic**:
  - If `translated_novels/<name>_burmese.md` exists AND checkpoint is `completed` → **skip**
  - If checkpoint exists but is incomplete → **resume from last saved chunk**
  - If no checkpoint exists → **start from chunk 1**
- **Output**: Status shown in terminal

### 3. Chunking
- **Script**: `scripts/chunk_text.py`
- **Action**: Divide the cleaned novel into segments of 1000–2000 characters
- **Overlap**: 100-character overlap between adjacent chunks to preserve narrative continuity
- **Config**: `chunk_size` and `chunk_overlap` in `config/config.json`
- **Output**: Individual chunk files saved to `working_data/chunks/`

### 4. Translation Execution (Streaming)
- **Script**: `scripts/translate_chunk.py`
- **Action**: Iterate through all chunks in `working_data/chunks/` and apply the prompt template above
- **Streaming**:
  - Calls Ollama with `stream=True`
  - Each token is emitted as it is generated
  - Tokens are also written to `working_data/preview/<novel_name>_preview.md` every 10 tokens
- **Checkpoint**: After each chunk completes, progress is saved to `working_data/checkpoints/<novel_name>.json`
- **Cancel safety**: If `Ctrl+C` is pressed, the current token is flushed and the checkpoint is saved before exit
- **Model**: Configured in `config/config.json` under `"model"` (default: `qwen3:7b`)
- **Output**: Translated chunks saved to `working_data/translated_chunks/`

### 5. Myanmar Readability Check
- **Script**: `scripts/myanmar_checker.py`
- **Runs**: Automatically after each chunk is translated
- **Checks**:

  | Check | Pass Condition |
  |---|---|
  | Myanmar script ratio | ≥ 70% of characters are Myanmar Unicode (U+1000–U+109F) |
  | No Chinese leakage | Zero Chinese characters (U+4E00–U+9FFF) in output |
  | Sentence boundary | At least one `။` marker present |
  | Minimum length | Output ≥ 30% the length of input |
  | Encoding integrity | No replacement characters (U+FFFD) |

- **On pass**: Logged to readability report
- **On fail**: Orange FLAGGED indicator; behavior controlled by `config.json`:
  - `flag_on_fail: true` → mark and continue
  - `block_on_fail: true` → retranslate once before continuing
- **Report**: `working_data/readability_reports/<novel_name>_readability.json`

### 6. Post-processing
- **Script**: `scripts/postprocess_translation.py`
- **Actions**:
  - Fix common Myanmar punctuation issues
  - Enforce consistent character and location name translations across all chunks
  - Remove any leftover Chinese characters that slipped through
  - Normalize paragraph spacing

### 7. Assembly & Formatting
- **Script**: `scripts/assemble_novel.py`
- **Action**: Merge all translated chunks from `working_data/translated_chunks/` into a single `.md` file
- **Output format**:

```markdown
---
title: "ဝတ္ထုခေါင်းစဉ်"
source_title: "小说标题"
language: Burmese (Myanmar Script)
source_language: Chinese
translated_date: YYYY-MM-DD
font_recommendation: "Padauk, Noto Sans Myanmar"
total_chapters: N
---

# ဝတ္ထုခေါင်းစဉ်

---

## အခန်း ၁ — နိဒါန်းပျိုး

စာပိုဒ်တစ်ခု...

စာပိုဒ်နှစ်ခု...

---

## အခန်း ၂

...
```

- **Rules**:
  - YAML front matter with full metadata
  - `#` for novel title
  - `## အခန်း N` for each chapter using Burmese numeral script (၁ ၂ ၃…)
  - One blank line between paragraphs
  - `---` horizontal rule between chapters
  - UTF-8 encoding enforced
- **Output**: Final file saved to `translated_novels/<novel_name>_burmese.md`

---


## Configuration Reference (`config/config.json`)

```json
{
  "model": "qwen3:7b",
  "provider": "ollama",
  "ollama_endpoint": "http://localhost:11434/api/generate",
  "source_language": "Chinese",
  "target_language": "Burmese",
  "chunk_size": 1500,
  "chunk_overlap": 100,
  "stream": true,
  "preview_update_every_n_tokens": 10,
  "request_timeout": 900,
  "auto_open_browser": true,
  "myanmar_readability": {
    "enabled": true,
    "min_myanmar_ratio": 0.7,
    "flag_on_fail": true,
    "block_on_fail": false
  }
}
```

---

## Quality Control Summary

| Stage | Script | What it catches |
|---|---|---|
| Pre-processing | `preprocess_novel.py` | Encoding errors, noise, malformed input |
| Readability check | `myanmar_checker.py` | Mixed language, empty output, bad encoding |
| Post-processing | `postprocess_translation.py` | Punctuation issues, name inconsistencies |
| Final validation | `assemble_novel.py` | Missing chunks, structure errors in output `.md` |