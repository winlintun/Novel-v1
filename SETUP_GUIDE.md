# Setup Guide - Chinese to Burmese Novel Translator

Complete setup instructions for the Novel Translation Project.

> **Date:** April 22, 2026  
> **Target:** Python developers and AI translation users  
> **Build:** Fully custom — no external translation framework required

---

## Table of Contents

1. [What This Project Does](#1-what-this-project-does)
2. [Project Structure](#2-project-structure)
3. [Prerequisites](#3-prerequisites)
4. [Installation](#4-installation)
5. [Configuration](#5-configuration)
6. [Running the Application](#6-running-the-application)
7. [Troubleshooting](#7-troubleshooting)

---

## 1. What This Project Does

This is an **AI-powered Chinese-to-Burmese novel translation pipeline**. 

### Simple Flow

```
[Chinese .md] → [AI Translation] → [Myanmar .md] → [Reader App]
```

### Detailed Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│  INPUT → PREPROCESS → CHUNK → TRANSLATE → POSTPROCESS → OUTPUT  │
└─────────────────────────────────────────────────────────────────┘

1. INPUT      → Read Chinese .md files from input_novels/
2. CHUNK      → Split into ≤1000 char segments (NOT whole novel at once)
3. TRANSLATE  → AI translates each chunk with context retention
4. OUTPUT     → Save Myanmar .md to books/{book_id}/chapters/
5. READER     → Browse and read via Web UI
```

### Key Features

- **Simple Pipeline**: `.md → AI translate → new .md → reader app`
- **Segmented Translation**: Never throw the whole novel at AI at once
- **Supported Models**:
  - **Ollama (Local)**: Qwen 3.5 (7B/14B), TranslateGemma, Kimi-K2.6
  - **Online**: Gemini, OpenRouter
- **Context Retention**: Sliding window maintains narrative consistency
- **Name Consistency**: Maintains character/place names via `names.json`
- **Web Reader**: Built-in Flask app for reading translations

---

## 2. Project Structure

```
novel_translation_project/
│
├── main.py                     # Main entry point - translates .md files
├── reader_app.py               # Flask web UI for reading
├── input_novels/               # Drop Chinese .md files here
├── books/                      # Translated output (structured for Reader)
│   ├── book1/
│   │   ├── metadata.json       # Book info & chapter list
│   │   └── chapters/
│   │       ├── chapter1.md     # Translated chapter
│   │       └── chapter2.md
│   └── book2/
│       └── ...
│
├── config/
│   ├── config.json             # Model & translation settings
│   └── settings.py             # Configuration validation
│
├── scripts/                    # Translation modules
│   ├── translator.py           # AI model adapters
│   ├── chunker.py              # Text segmentation
│   ├── assembler.py            # Output assembly
│   └── ...
│
├── templates/                  # HTML templates for Reader
├── names.json                  # Character name mappings
└── .env                        # API keys & settings
```

---

## 3. Prerequisites

### Hardware

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| RAM | 16 GB | 32 GB |
| Storage | 30 GB free | 60 GB free |
| CPU | 4-core modern | 8-core or better |

> **16 GB RAM tip**: Use smaller models (7B) and reduce chunk size to 1000.

### Software

- **Python** 3.8+
- **Git**
- **Ollama** (optional, for local models)

---

## 4. Installation

### Step 1: Setup Environment

```bash
cd novel_translation_project
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Step 2: Configure

```bash
cp .env.example .env
# Edit .env with your settings
nano .env
```

### Step 3: (Optional) Setup Ollama for Local Models

```bash
# Install Ollama from https://ollama.com

# Pull a translation model
ollama pull qwen2.5:14b
# or
ollama pull translategemma:12b
# or
ollama run kimi-k2.6:cloud

# Start Ollama
ollama serve
```

---

## 5. Configuration

### 5.1 Environment (.env)

```bash
# Choose AI backend
AI_MODEL=ollama  # Options: ollama | openrouter | gemini

# Ollama (Local)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:14b
# Other options: translategemma, translategemma:12b, kimi-k2.6:cloud

# API Keys (for cloud models)
OPENROUTER_API_KEY=your_key
GEMINI_API_KEY=your_key

# Translation Settings
MAX_CHUNK_CHARS=1000    # IMPORTANT: Segmented translation!
REQUEST_DELAY=1.0
READABILITY_CHECK=true
```

### 5.2 Models Reference

#### Local (Ollama)

| Model | Size | Quality | Command |
|-------|------|---------|---------|
| Qwen 3.5 | 7B | Good | `ollama pull qwen2.5:7b` |
| Qwen 3.5 | 14B | Excellent | `ollama pull qwen2.5:14b` |
| TranslateGemma | 12B | Good | `ollama pull translategemma:12b` |
| Kimi K2.6 | Cloud | Excellent | `ollama run kimi-k2.6:cloud` |

#### Online (API)

| Service | Model | Free Tier |
|---------|-------|-----------|
| OpenRouter | Various | Yes |
| Gemini | gemini-2.0-flash | Yes |

### 5.3 Character Names (names.json)

Add name mappings for consistent translation:

```json
{
  "罗青": "လော်ချင်",
  "蟠龙山": "ပန်လုံတောင်",
  "魔教": "မိစ္ဆာဂိုဏ်း"
}
```

---

## 6. Running the Application

### 6.1 Translate Novels

```bash
# 1. Place Chinese .md files in input_novels/
cp my_novel.md input_novels/

# 2. Run translation
python main.py

# Output goes to: books/{book_name}/chapters/
```

**Options:**

```bash
# Translate specific file
python main.py input_novels/novel.md

# Use different model
python main.py --model openrouter

# Adjust chunk size (lower = less memory)
python main.py --max-chars 1000
```

### 6.2 Segmented Translation (Important!)

**Never throw the whole novel at AI at once!**

The system automatically splits text into chunks:

```python
# From scripts/chunker.py
def split_text(text, max_len=1000):
    return [text[i:i+max_len] for i in range(0, len(text), max_len)]
```

Default: `MAX_CHUNK_CHARS=1000` (adjust in .env)

### 6.3 Read Translations

```bash
# Start web reader
python reader_app.py

# Open browser
http://localhost:5000
```

**Reader Features:**
- Book library view
- Chapter navigation (Next/Prev)
- Font size control
- Dark mode
- Reading progress save/resume

---

## 7. Troubleshooting

| Problem | Solution |
|---------|----------|
| Out of memory | Reduce `MAX_CHUNK_CHARS` to 800-1000 |
| Translation too slow | Use smaller model or cloud API |
| Model not found | Run `ollama pull <model>` |
| API errors | Check API keys in .env |
| Burmese shows boxes | Install Padauk font |
| Resume failed | Delete checkpoint files in `working_data/checkpoints/` |

### Quick Checks

```bash
# Test Ollama
curl http://localhost:11434/api/tags

# Validate config
python config/settings.py validate

# Check available models
ollama list
```

---

## Flow Summary

```
┌─────────────────────────────────────────────┐
│  1. Add Chinese .md to input_novels/        │
│  2. Run: python main.py                     │
│  3. Check: books/{book}/chapters/           │
│  4. Read: python reader_app.py              │
└─────────────────────────────────────────────┘
```

**Remember:** 
- Use segmented translation (chunks ≤1000 chars)
- Edit names.json before translating
- The pipeline: `.md → AI → .md → Reader`

---

*Last Updated: April 22, 2026*
