# Setup Guide - Chinese to Burmese Novel Translator

Complete setup instructions for the Novel Translation Project.

> **Date:** April 21, 2026  
> **Target:** Python developers and AI translation users  
> **Build:** Fully custom — no external translation framework required

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Hardware Requirements](#2-hardware-requirements)
3. [Software Requirements](#3-software-requirements)
4. [Step-by-Step Installation](#4-step-by-step-installation)
5. [Configuration](#5-configuration)
6. [Running the Application](#6-running-the-application)
7. [Troubleshooting](#7-troubleshooting)

---

## 1. Prerequisites

### What This System Does

When you run `main.py`, it handles the entire workflow:

```
1. Scan input_novels/ for all *.txt and *.md files
2. For each novel — check if already translated (skip if done)
3. Preprocess the novel (clean text, enforce UTF-8)
4. Split into chunks (1500-2000 chars with overlap)
5. Translate each chunk via AI with live streaming
6. Save checkpoint after every chunk (safe to cancel anytime)
7. Run Myanmar readability check on each chunk
8. Postprocess (fix punctuation, character name consistency)
9. Assemble all chunks into final .md file
10. Write output to translated_novels/
```

---

## 2. Hardware Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| RAM | 16 GB | 32 GB |
| Storage | 30 GB free | 60 GB free |
| CPU | 4-core modern | 8-core or better |
| GPU (optional) | — | 4 GB+ VRAM speeds up inference |

> **16 GB RAM tip:** Use quantized models (q4_K_M). Close other heavy apps while translating. Stick to chunk_size: 1500 or lower.

---

## 3. Software Requirements

### 3.1 Core Software

| Software | Version | Install |
|----------|---------|---------|
| Python | 3.8+ | [python.org](https://www.python.org/downloads/) |
| Git | Latest | [git-scm.com](https://git-scm.com/) |
| Ollama (optional) | Latest | [ollama.com](https://ollama.com/) |

### 3.2 Python Dependencies

```bash
pip install -r requirements.txt
```

| Package | Purpose |
|---------|---------|
| `requests` | HTTP client for API calls |
| `python-dotenv` | Environment variable management |
| `pydantic` | Configuration validation |
| `ollama` | Ollama Python client |
| `flask` | Web UI framework |
| `flask-socketio` | Real-time WebSocket communication |
| `eventlet` | Async server for WebSocket |
| `gevent` | Alternative async server |
| `tqdm` | Progress bars |

---

## 4. Step-by-Step Installation

### Step 1: Create Project Directory

```bash
mkdir novel_translation_project
cd novel_translation_project
```

### Step 2: Create Virtual Environment

```bash
python3 -m venv venv

# macOS / Linux
source venv/bin/activate

# Windows
.\venv\Scripts\activate
```

### Step 3: Install Python Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Install Ollama (Optional - for local models)

```bash
# Verify Ollama is installed
ollama --version

# Pull your translation model
ollama pull qwen2.5:14b

# Ollama runs automatically after install
# If not running, start manually:
ollama serve
```

### Step 5: Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your settings
nano .env  # or use your preferred editor
```

### Step 6: Verify Configuration

```bash
# Validate config.json
python config/settings.py validate
```

---

## 5. Configuration

### Environment Variables (.env)

```bash
# ── Model Selection ──────────────────────────────────
# Options: openrouter | gemini | deepseek | qwen | ollama
AI_MODEL=ollama

# ── SSL Verification ─────────────────────────────────
VERIFY_SSL=true

# ── OpenRouter (one key = many free models) ───────────
OPENROUTER_API_KEY=your_key_here
OPENROUTER_MODEL=google/gemini-2.0-flash-exp:free

# ── Google Gemini (AI Studio) ────────────────────────
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.0-flash

# ── DeepSeek ─────────────────────────────────────────
DEEPSEEK_API_KEY=your_key_here
DEEPSEEK_MODEL=deepseek-chat

# ── Qwen (Alibaba DashScope) ─────────────────────────
QWEN_API_KEY=your_key_here
QWEN_MODEL=qwen-max

# ── Ollama (Local) ───────────────────────────────────
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:14b

# ── Translation Settings ──────────────────────────────
MAX_CHUNK_CHARS=1800
REQUEST_DELAY=1.0
READABILITY_CHECK=true
```

### Runtime Configuration (config/config.json)

```json
{
  "model": "qwen2.5:14b",
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

**Key settings explained:**

| Setting | Description |
|---------|-------------|
| `chunk_size` | Characters per chunk. Keep 1500-2000 for 16 GB RAM |
| `chunk_overlap` | Chars shared between chunks for narrative flow |
| `min_myanmar_ratio` | Minimum Myanmar script ratio (0.0-1.0) |
| `flag_on_fail` | Mark failing chunks in report |
| `block_on_fail` | Retranslate failing chunks before continuing |

### Character Names (names.json)

Add your novel's character names for consistent translation:

```json
{
  "罗青": "လော်ချင်",
  "蟠龙山": "ပန်လုံတောင်",
  "魔教": "မိစ္ဆာဂိုဏ်း"
}
```

---

## 6. Running the Application

### Start Translation

```bash
# Translate all files in input_novels/
python main.py

# Translate specific file
python main.py input_novels/novel.txt

# Use different model
python main.py --model openrouter
python main.py --model gemini

# Adjust settings
python main.py --max-chars 2000 --no-readability
```

### Using Make Commands

```bash
make install    # Install dependencies
make run        # Run main.py
make resume     # Resume from checkpoint
make clean      # Clean checkpoints and logs
make lint       # Run linters
make test       # Run tests
```

### Drop New Novels While Running

Place a new `.txt` or `.md` file in `input_novels/` at any time. The system detects it on the next scan cycle.

### Resume Translation

If translation is interrupted, run `python main.py` again. It automatically resumes from the last checkpoint.

---

## 7. Troubleshooting

| Problem | Cause | Solution |
|---------|-------|----------|
| `ollama: command not found` | Ollama not in PATH | Reinstall from ollama.com, restart terminal |
| Model not found | Model not pulled | `ollama pull qwen2.5:14b` |
| Out of memory | Model too large | Use 7B model, reduce chunk_size |
| Burmese shows as boxes | Font missing | Install Padauk or Noto Sans Myanmar |
| API errors | Invalid key | Check API keys in .env |
| Resume failed | Corrupt checkpoint | Delete checkpoint JSON and restart |
| SSL errors | Certificate issues | Set `VERIFY_SSL=false` in .env (insecure) |

### Quick Diagnostics

```bash
# Test Ollama connection
curl http://localhost:11434/api/tags

# Check Python environment
python --version
pip list | grep -E "(requests|flask|ollama)"

# Validate configuration
python config/settings.py validate

# Check available models
ollama list
```

---

## References

1. Ollama — https://ollama.com/
2. Qwen models — https://ollama.com/library/qwen
3. Myanmar Unicode — https://www.unicode.org/charts/PDF/U1000.pdf
4. Padauk Font — https://software.sil.org/padauk/

---

*Place this file in the root of your project alongside AGENTS.md and README.md.*

**Last Updated**: April 21, 2026
