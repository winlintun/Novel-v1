# OpenCode AI — Chinese to Burmese Novel Translator
## Project Setup Guide

> **Author:** Novel Translation Project  
> **Date:** April 19, 2026  
> **Target:** OpenCode AI agent with local Ollama LLM  
> **Build:** Fully custom — no external translation framework required

---

## Table of Contents

1. [Overview](#1-overview)
2. [Hardware Requirements](#2-hardware-requirements)
3. [Software Requirements](#3-software-requirements)
4. [Project Structure](#4-project-structure)
5. [Step-by-Step Setup](#5-step-by-step-setup)
6. [Model Setup (Ollama)](#6-model-setup-ollama)
7. [OpenCode AI Agent Files](#7-opencode-ai-agent-files)
8. [Running the Project](#8-running-the-project)
9. [Feature Guide](#9-feature-guide)
10. [Myanmar Readability Checker](#10-myanmar-readability-checker)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. Overview

This project is a **fully self-contained** Chinese-to-Burmese novel translator built from scratch. It uses a local LLM via Ollama and runs entirely on your machine — no external translation framework, no cloud API required.

### What `main.py` does automatically

When you run `main.py`, it handles the entire workflow without any manual steps:

```
1.  Scan input_novels/ for all *.txt files
2.  For each novel — check if already translated (skip if done)
3.  Preprocess the novel (clean text, enforce UTF-8)
4.  Split into chunks (1000–2000 chars with overlap)
5.  Auto-open the web UI in your browser (localhost:5000)
6.  Translate each chunk via Ollama with live streaming
7.  Show real-time progress in the web UI and terminal
8.  Stream translated Burmese tokens to live preview as LLM generates
9.  Save a checkpoint after every chunk (safe to cancel anytime)
10. Run Myanmar readability check on each translated chunk
11. Postprocess (fix punctuation, character name consistency)
12. Assemble all chunks into a final pretty .md file
13. Write final output to translated_novels/
```

### Architecture

```
input_novels/
  └── my_novel.txt
         │
         ▼
  [ Already translated? ] ──YES──→ Skip, show status in web UI
         │ NO
         ▼
  preprocess_novel.py     Clean + UTF-8
         │
         ▼
  chunk_text.py           Split 1000–2000 chars, slight overlap
         │
         ▼
  translate_chunk.py      Ollama stream=True → tokens → live preview
         │                                  → web UI streaming panel
         │                                  → checkpoint saved per chunk
         ▼
  myanmar_checker.py      Readability check on each translated chunk
         │
         ▼
  postprocess.py          Punctuation + name consistency fix
         │
         ▼
  assemble_novel.py       Merge → pretty Burmese .md
         │
         ▼
  translated_novels/
    └── my_novel_burmese.md
```

---

## 2. Hardware Requirements

| Component | Minimum | Recommended |
|---|---|---|
| RAM | 16 GB | 32 GB |
| Storage | 30 GB free | 60 GB free |
| CPU | 4-core modern | 8-core or better |
| GPU (optional) | — | 4 GB+ VRAM speeds up inference significantly |

> **16 GB RAM tip:** Use quantized models (`q4_K_M`). Close other heavy apps while translating. Stick to `chunk_size: 1500` or lower.

---

## 3. Software Requirements

### 3.1 Core Software

| Software | Version | Install |
|---|---|---|
| Python | 3.8+ | [python.org](https://www.python.org/downloads/) |
| Git | Latest | [git-scm.com](https://git-scm.com/) |
| Ollama | Latest | [ollama.com](https://ollama.com/) |

### 3.2 Python Dependencies

Install everything in one command after activating your virtual environment:

```bash
pip install ollama flask flask-socketio tqdm regex pyicu
```

| Package | Purpose |
|---|---|
| `ollama` | Python client — calls local LLM, supports streaming |
| `flask` | Web server for the live UI |
| `flask-socketio` | WebSocket push — sends live tokens to the browser |
| `tqdm` | Terminal progress bar |
| `regex` | Advanced Unicode regex for Myanmar script validation |
| `pyicu` | ICU Unicode library for Myanmar word/sentence boundary detection |

> **Note on `pyicu`:** On Windows, install via `pip install PyICU` with the prebuilt wheel. On Ubuntu: `sudo apt install python3-icu` then `pip install pyicu`.

---

## 4. Project Structure

```
novel_translation_project/
│
├── main.py                         ← The only file you need to run
├── web_ui.py                       ← Flask web server (auto-started by main.py)
├── AGENT.md                        ← OpenCode AI: agent role
├── SKILL.md                        ← OpenCode AI: translation skill & prompt
├── REVIEWER_AGENT.md               ← OpenCode AI: code review agent
├── SETUP_GUIDE_OPENCODE.md         ← This file
│
├── config/
│   └── config.json                 ← All settings (model, chunk size, ports…)
│
├── scripts/
│   ├── preprocess_novel.py         ← Clean raw .txt (encoding, noise removal)
│   ├── chunk_text.py               ← Using nltk.sent_tokenize(text), Split into overlapping chunks
│   ├── translate_chunk.py          ← Ollama stream → live preview + checkpoint
│   ├── myanmar_checker.py          ← Readability checker for translated output
│   ├── postprocess_translation.py  ← Fix punctuation & character names
│   └── assemble_novel.py           ← Merge chunks → pretty .md
│
├── templates/
│   ├── novel_template.md           ← Full novel Markdown structure
│   └── chapter_template.md         ← Per-chapter formatting
│
├── input_novels/                   ← Drop your Chinese .txt files here
├── translated_novels/              ← Final .md files appear here
│
└── working_data/
    ├── chunks/                     ← Chinese text chunks (pre-translation)
    ├── translated_chunks/          ← Translated Burmese chunks (raw)
    ├── preview/                    ← Live in-progress .md (readable anytime)
    ├── readability_reports/        ← Myanmar checker output per chunk
    ├── logs/                       ← Full translation logs
    └── checkpoints/                ← JSON resume state per novel
```

---

## 5. Step-by-Step Setup

### Step 1 — Create the project folder

```bash
mkdir novel_translation_project
cd novel_translation_project
```

### Step 2 — Create all subdirectories

```bash
mkdir -p config scripts templates input_novels translated_novels
mkdir -p working_data/chunks working_data/translated_chunks
mkdir -p working_data/preview working_data/readability_reports
mkdir -p working_data/logs working_data/checkpoints
```

### Step 3 — Create virtual environment

```bash
python3 -m venv venv

# macOS / Linux
source venv/bin/activate

# Windows
.\venv\Scripts\activate
```

### Step 4 — Install Python dependencies

```bash
pip install ollama flask flask-socketio tqdm regex pyicu
```

### Step 5 — Create `config/config.json`

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
  "web_ui_port": 5000,
  "auto_open_browser": true,
  "myanmar_readability": {
    "enabled": true,
    "min_myanmar_ratio": 0.7,
    "flag_on_fail": true,
    "block_on_fail": false
  }
}
```

**Key settings explained:**

| Setting | Description |
|---|---|
| `chunk_size` | Characters per chunk. Keep 1000–2000 for 16 GB RAM |
| `chunk_overlap` | Chars shared between chunks to preserve narrative flow |
| `preview_update_every_n_tokens` | How often the web UI refreshes during streaming |
| `auto_open_browser` | `main.py` opens `localhost:5000` automatically on start |
| `min_myanmar_ratio` | Fraction of output that must be Myanmar script (0.0–1.0) |
| `flag_on_fail` | Mark failing chunks in the readability report |
| `block_on_fail` | If `true`, retranslate failing chunks instead of continuing |

### Step 6 — Place OpenCode AI agent files

Copy these four files into the root of `novel_translation_project/`:

```
AGENT.md
SKILL.md
REVIEWER_AGENT.md
SETUP_GUIDE_OPENCODE.md   ← this file
```

OpenCode AI reads these automatically when you open the project folder.

### Step 7 — Install and start Ollama

```bash
# Verify Ollama is installed
ollama --version

# Pull your translation model (see Section 6 for options)
ollama pull qwen3:7b

# Ollama starts automatically as a background service after install.
# If it's not running, start it manually:
ollama serve
```

---

## 6. Model Setup (Ollama)

### Recommended Models for Chinese → Burmese

| Model | RAM Usage | Quality | Command |
|---|---|---|---|
| `qwen3:7b` | ~6 GB | Good | `ollama pull qwen3:7b` |
| `qwen3:14b` | ~10 GB | Better | `ollama pull qwen3:14b` |
| `qwen3:7b-q4_K_M` | ~4.5 GB | Good (quantized) | `ollama pull qwen3:7b-q4_K_M` |

> **For 16 GB RAM:** Use `qwen3:7b` or `qwen3:7b-q4_K_M`. The 14B model is possible but leaves little RAM for other processes.

### Alternative — MyanmarGPT via Hugging Face

If you want a Burmese-native model, `MyanmarGPT-Big` (1.42B) can be used in `translate_chunk.py` instead of Ollama. It loads automatically the first time:

```python
from transformers import AutoTokenizer, AutoModelForCausalLM
tokenizer = AutoTokenizer.from_pretrained("jojo-ai-mst/MyanmarGPT-Big")
model = AutoModelForCausalLM.from_pretrained("jojo-ai-mst/MyanmarGPT-Big")
```

Set `"provider": "myanmargpt"` in `config.json` to switch to this model.

> **Note:** Streaming is not supported with MyanmarGPT. The live preview will update per-chunk instead of per-token.

### Verify your model is ready

```bash
ollama list
# Should show: qwen3:7b  (or whichever model you pulled)
```

---

## 7. OpenCode AI Agent Files

Three files define how OpenCode AI behaves in this project.

### `AGENT.md` — Agent Role Definition

Tells OpenCode AI it is a **Professional Literary Translator** (Chinese → Burmese). Key instructions:

- Preserve the author's tone, style, and emotional depth
- Output only Burmese Myanmar script — no explanations, no Chinese
- Maintain consistent character and place name translations across the entire novel
- Follow the project workflow defined in this guide

### `SKILL.md` — Translation Skill & Prompt Template

Every chunk is translated using this exact prompt:

```
SYSTEM:
You are a professional literary translator.
Translate the following Chinese novel text to Burmese (Myanmar script).
Keep the tone, style, and emotions of the original.
Do NOT add explanations. Output only the Burmese translation.

USER:
[CHINESE_TEXT_CHUNK]
```

### `REVIEWER_AGENT.md` — Code Review Agent

A secondary agent for auditing the project scripts. Activate it in OpenCode AI when you want to:

- Review `scripts/` for bugs or inefficiencies
- Validate that checkpoints and data flow correctly between stages
- Run automated checks with `flake8` or `pytest`

---

## 8. Running the Project

### Start everything with one command

```bash
python main.py
```

**What happens immediately:**

```
[SCAN]    Found 3 novel(s) in input_novels/
[STATUS]  romance_novel.txt       → not translated yet
[STATUS]  wuxia_story.txt         → already translated ✓ (skip)
[STATUS]  detective_story.txt     → partially done, resuming from chunk 87/210
[BROWSER] Opening http://localhost:5000 ...
[START]   Translating: romance_novel.txt
[CHUNK]   1/340 ─────────────────────────── 0.3%
```

The browser opens automatically. You do not need to run anything else.

### Drop new novels while running

Place a new `.txt` file in `input_novels/` at any time. `main.py` detects it on its next scan cycle (every 60 seconds) and adds it to the queue.

### Already-translated detection

`main.py` checks two things for each `.txt` file:

1. Does `translated_novels/<name>_burmese.md` already exist?
2. Does `working_data/checkpoints/<name>.json` show `"status": "completed"`?

If both are true → skip and mark green in the web UI.  
If checkpoint exists but incomplete → resume from last saved chunk.  
If neither exists → start fresh from chunk 1.

---

## 9. Feature Guide

### Feature 1 — Scan and Skip Already-Translated Novels

On startup, `main.py` scans every `.txt` in `input_novels/` and classifies each as:

| Status | Condition | Action |
|---|---|---|
| Done ✓ | Output `.md` exists + checkpoint `completed` | Skip entirely |
| Resuming ↻ | Checkpoint exists but not completed | Resume from last chunk |
| New | No checkpoint found | Start from chunk 1 |

All statuses are visible in the web UI queue panel.

### Feature 2 — Live Progress in Web UI

The web UI at `http://localhost:5000` (opens automatically) shows:

- Progress bar with chunk X of Y and percentage
- Estimated time remaining (calculated from rolling average chunk speed)
- Current Chinese source text alongside the live Burmese output
- Status badges for every novel in the queue
- Readability check result badge per chunk (green PASS / orange FLAGGED)

### Feature 3 — Live Streaming of Translated Text

As the LLM generates each Burmese token, it is sent simultaneously to:

1. **The browser** — tokens appear word-by-word in the streaming panel via WebSocket
2. **The preview file** — `working_data/preview/<novel_name>_preview.md` is updated every 10 tokens

You can open the preview file in any Markdown viewer at any time to read the in-progress translation — even the chunk currently being generated.

```
working_data/preview/romance_novel_preview.md   ← open this anytime
```

### Feature 4 — Cancel Anytime, Resume Anytime

**To cancel:** click **Stop** in the web UI, or press `Ctrl+C` in the terminal.

The program will:

1. Finish writing the current streaming token
2. Save checkpoint to `working_data/checkpoints/<novel_name>.json`
3. Shut down the web server cleanly
4. Exit

**To resume:** run `python main.py` again.

```
[RESUME]  romance_novel.txt — checkpoint found at chunk 141/340. Resuming...
```

No chunk is ever translated twice. Already-completed chunks are loaded from `working_data/translated_chunks/` directly.

### Feature 5 — Pretty Burmese Markdown Output

The final file in `translated_novels/` follows this structure:

```markdown
---
title: "ဝတ္ထုခေါင်းစဉ်"
source_title: "小说标题"
language: Burmese (Myanmar Script)
source_language: Chinese
translated_date: 2026-04-19
font_recommendation: "Padauk, Noto Sans Myanmar"
total_chapters: 24
---

# ဝတ္ထုခေါင်းစဉ်

---

## အခန်း ၁ — နိဒါန်းပျိုး

ပထမစာပိုဒ် မြန်မာဘာသာဖြင့်...

ဒုတိယစာပိုဒ် မြန်မာဘာသာဖြင့်...

---

## အခန်း ၂

...
```

Formatting rules applied by `assemble_novel.py`:

- YAML front matter with full metadata
- `#` for novel title
- `## အခန်း N` chapter headings using Burmese numeral script (၁ ၂ ၃…)
- One blank line between every paragraph
- `---` horizontal rule between chapters
- UTF-8 enforced throughout
- Zero Chinese characters in the final output

---

## 10. Myanmar Readability Checker

`scripts/myanmar_checker.py` runs automatically after each chunk is translated and reports whether the output is readable Burmese.

### What it checks

| Check | Pass condition |
|---|---|
| Myanmar script ratio | ≥ 70% of characters are Myanmar Unicode (U+1000–U+109F) |
| No Chinese leakage | Zero Chinese characters (U+4E00–U+9FFF) in output |
| Sentence boundary | At least one valid Myanmar sentence-ending marker (`။`) present |
| Minimum length | Output is ≥ 30% the length of input (catches empty/truncated responses) |
| Encoding integrity | No replacement characters (U+FFFD) — all bytes valid UTF-8 Myanmar |

### Terminal output per chunk

```
[CHECKER] Chunk 47/340 → PASS   (Myanmar: 94%, Sentences: 12, Length: OK)
[CHECKER] Chunk 48/340 → FLAGGED  (Myanmar: 31% — possible mixed-language output)
```

### Readability reports

Full JSON reports are saved after each novel:

```
working_data/readability_reports/<novel_name>_readability.json
```

To view a summary after translation:

```bash
python scripts/myanmar_checker.py --report working_data/readability_reports/romance_novel_readability.json
```

Output:

```
Readability Report — romance_novel.txt
Total chunks :  340
Passed       :  335  (98.5%)
Flagged      :    5  (1.5%)

Flagged chunks: 48, 112, 203, 267, 301
→ Review files in working_data/translated_chunks/
```

### Behavior on failure (configured in `config.json`)

| Setting | Effect |
|---|---|
| `flag_on_fail: true` | Marks chunk orange in web UI and report, continues translating |
| `block_on_fail: true` | Automatically retranslates the failing chunk once before continuing |

---

## 11. Troubleshooting

| Problem | Cause | Solution |
|---|---|---|
| `ollama: command not found` | Ollama not in PATH | Reinstall from [ollama.com](https://ollama.com/), restart terminal |
| Model not found | Model not pulled yet | `ollama pull qwen3:7b` |
| Out of memory during translation | Model too large for RAM | Switch to `qwen3:7b-q4_K_M`, reduce `chunk_size` |
| Web UI doesn't open | Port 5000 in use | Change `web_ui_port` to `5001` in `config.json` |
| Burmese text shows as boxes | Myanmar font missing | Install **Padauk** or **Noto Sans Myanmar** |
| Preview file not updating | `stream` is false | Set `"stream": true` in `config.json` |
| Novel not resuming | Checkpoint missing/corrupt | Delete the `.json` in `checkpoints/` and restart |
| High readability failure rate | Wrong model or bad prompt | Try `qwen3:14b`, review the prompt in `SKILL.md` |
| `pyicu` install fails (Windows) | Binary dependency | `pip install PyICU` with prebuilt wheel from [PyPI](https://pypi.org/project/PyICU/) |
| Chinese characters remain in output | LLM ignored the prompt | Set `block_on_fail: true` in config to auto-retry |

---

## Quick Reference

```bash
# 1. Activate environment
source venv/bin/activate          # macOS / Linux
.\venv\Scripts\activate           # Windows

# 2. Ensure Ollama is running
ollama serve                      # only if not already running as a service

# 3. Drop your novel into the input folder
cp my_chinese_novel.txt input_novels/

# 4. Run everything — one command
python main.py
# → Scans input_novels/ and skips already-translated files
# → Web UI opens automatically at http://localhost:5000
# → Watch live progress and streaming translation in browser
# → Press Stop button or Ctrl+C to cancel safely at any time
# → Run again to resume from checkpoint
```

---

## References

1. Ollama — https://ollama.com/
2. Qwen model library — https://ollama.com/library/qwen3
3. MyanmarGPT-Big — https://huggingface.co/jojo-ai-mst/MyanmarGPT-Big
4. Flask-SocketIO — https://flask-socketio.readthedocs.io/
5. Myanmar Unicode Block — https://www.unicode.org/charts/PDF/U1000.pdf
6. Padauk Myanmar Font — https://software.sil.org/padauk/
7. Noto Sans Myanmar — https://fonts.google.com/noto/specimen/Noto+Sans+Myanmar

---

*Place this file in the root of `novel_translation_project/` alongside `AGENT.md`, `SKILL.md`, and `REVIEWER_AGENT.md`. OpenCode AI reads all four files as project context.*