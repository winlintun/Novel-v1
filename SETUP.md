# Setup Guide - Novel Translation System

Complete step-by-step guide to set up and run the Chinese/English-to-Burmese Novel Translation System.

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [First Translation](#first-translation)
5. [Advanced Setup](#advanced-setup)

---

## System Requirements

### Minimum Requirements

- **OS**: Linux, macOS, or Windows with WSL
- **Python**: 3.8 or higher
- **RAM**: 16GB (for 7B models)
- **Disk**: 10GB free space
- **Internet**: Required for cloud models and initial setup

### Recommended Requirements

- **RAM**: 32GB+ (for 14B+ models)
- **GPU**: NVIDIA GPU with 8GB+ VRAM (optional, speeds up local models)
- **Disk**: 50GB+ free space (for multiple models and novels)

---

## Installation

### Step 1: Install System Dependencies

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv git
```

**macOS:**
```bash
# Install Homebrew first from https://brew.sh
brew install python3 git
```

**Windows (WSL):**
```bash
# Install WSL2 and Ubuntu from Microsoft Store
# Then follow Ubuntu instructions above
```

### Step 2: Clone Repository

```bash
cd ~  # Or wherever you want to install
git clone <repository-url>
cd novel_translation_project
```

### Step 3: Create Python Virtual Environment

```bash
python3 -m venv venv

# Activate (Linux/macOS)
source venv/bin/activate

# Activate (Windows)
.\venv\Scripts\activate
```

You should see `(venv)` in your prompt.

### Step 4: Install Python Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

This installs:
- Flask (web reader)
- Requests (API calls)
- python-dotenv (environment management)
- pydantic (configuration)
- transformers, torch (for NLLB-200)
- And more...

### Step 5: Install Ollama (for Local Models)

**Linux:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

**macOS:**
```bash
brew install ollama
```

**Windows:**
Download from https://ollama.com/download/windows

**Verify Installation:**
```bash
ollama --version
```

### Step 6: Pull Translation Models

**Option A: Qwen (Recommended for Chinese)**
```bash
# 14B model (best quality, needs 10GB+ RAM)
ollama pull qwen2.5:14b

# 7B model (faster, needs 6GB+ RAM)
ollama pull qwen2.5:7b
```

**Option B: Gemma (Good for English)**
```bash
ollama pull gemma:12b
```

**Option C: NLLB-200 (Fastest, sentence-level)**
```bash
# NLLB uses HuggingFace, no Ollama needed
# Will download on first use (~2GB)
```

**List Downloaded Models:**
```bash
ollama list
```

---

## Configuration

### Step 1: Create Environment File

```bash
cp .env.example .env
```

### Step 2: Edit Configuration

Open `.env` in your favorite editor:

```bash
nano .env  # or vim, code, etc.
```

#### For Local Models (Ollama)

```bash
# Use local Ollama
AI_MODEL=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:14b

# Translation settings
SOURCE_LANGUAGE=Chinese
MAX_CHUNK_CHARS=1200
REQUEST_DELAY=0.5
```

#### For Cloud Models (OpenRouter)

```bash
# Use OpenRouter (requires API key)
AI_MODEL=openrouter
OPENROUTER_API_KEY=sk-or-v1-your-key-here
OPENROUTER_MODEL=google/gemini-2.0-flash-exp:free

# Translation settings
SOURCE_LANGUAGE=English
MAX_CHUNK_CHARS=1200
REQUEST_DELAY=1.0
```

#### For Cloud Models (Gemini)

```bash
# Use Google Gemini
AI_MODEL=gemini
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-2.0-flash

# Translation settings
SOURCE_LANGUAGE=Chinese
MAX_CHUNK_CHARS=1200
```

### Step 3: Test Configuration

```bash
# Test Ollama connection
ollama run qwen2.5:14b "Hello"

# Test configuration loading
python -c "from config.settings import load_config; print(load_config())"
```

---

## First Translation

### Step 1: Prepare Your Novel

**For Chinese Novels:**
1. Place `.txt` or `.md` file in `input_novels/`
2. Ensure UTF-8 encoding
3. Example: `input_novels/my_chinese_novel.txt`

**For English Novels:**
1. Place `.txt` or `.md` file in `input_novels/`
2. Set `SOURCE_LANGUAGE=English` in `.env`
3. Example: `input_novels/my_english_novel.txt`

### Step 2: Create Glossary (Optional but Recommended)

Before translating, create a glossary for consistent names:

```bash
# For English novels
python scripts/glossary_manager.py my_english_novel add "Character Name" "မြန်မာနာမည်"
python scripts/glossary_manager.py my_english_novel add "Place Name" "မြန်မာနေရာအမည်"

# Example
python scripts/glossary_manager.py dao-equaling-the-heavens add "Gu Wen" "ဂူဝမ်"
python scripts/glossary_manager.py dao-equaling-the-heavens add "Dragon Bridge" "လွန်ချျန်းတံတား"
```

View the glossary:
```bash
python scripts/glossary_manager.py my_english_novel list
```

### Step 3: Run Translation

**Basic Translation:**
```bash
python main.py
```

**Translate specific file:**
```bash
python main.py input_novels/my_novel.txt
```

**With options:**
```bash
python main.py --model ollama --max-chars 1200
```

### Step 4: Monitor Progress

You'll see output like:
```
============================================================
Translating: my_novel
Book ID: my_novel
============================================================

[1/7] Preprocessing...
✓ Preprocessed: 15420 characters

[2/7] Chunking...
┌──────────────────────────────────┐
│ Chunk Analysis                   │
│ Total paragraphs : 45            │
│ Total chunks     : 13            │
│ Min chunk chars  : 1150          │
│ Max chunk chars  : 1200          │
│ Avg chunk chars  : 1186          │
└──────────────────────────────────┘

[3/7] Loading glossary for: my_novel
✓ Glossary loaded: 5 names

[4/7] Loading translator: ollama
✓ Loaded: ollama (qwen2.5:14b)

[5/7] Translating 13 chunks...
...
```

### Step 5: Find Your Translation

Completed translations are in:
```
books/<novel_name>/chapters/<novel_name>_myanmar.md
```

Example:
```
books/my_novel/chapters/my_novel_myanmar.md
```

### Step 6: Read the Translation

**Option A: Web Reader**
```bash
python reader_app.py
# Open http://localhost:5000 in browser
```

**Option B: Direct File**
```bash
cat books/my_novel/chapters/my_novel_myanmar.md
```

---

## Advanced Setup

### Two-Stage Translation (Higher Quality)

Enable two-stage mode for better quality:

1. Edit `config/config.json`:
```json
{
  "translation_pipeline": {
    "mode": "two_stage"
  }
}
```

2. Run translation:
```bash
python main.py
```

This will:
- Stage 1: Raw literal translation
- Stage 2: Rewrite into natural, conversational Burmese

**Note:** Two-stage takes about 2x longer but produces much better quality.

### Using NLLB-200 (Fastest)

For fast sentence-level translation:

1. Set in `.env`:
```bash
AI_MODEL=nllb
```

2. First run will download the model (~2GB).

3. Run translation.

### Multiple Novels Pipeline

**Extract chapters first:**
```bash
python scripts/extract_chapters.py my_novel.txt
# Creates: english_chapters/my_novel/chapter_001.md, etc.
```

**Translate all chapters:**
```bash
python scripts/translate_chapters.py my_novel
# Translates all chapters one by one
```

**Full pipeline:**
```bash
python translate_novel.py my_novel
# Extract + Translate in one command
```

### GPU Acceleration (Optional)

If you have an NVIDIA GPU:

```bash
# Install CUDA-enabled PyTorch
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# Verify GPU is detected
python -c "import torch; print(torch.cuda.is_available())"
```

### Automatic Startup Script

Create `start.sh`:
```bash
#!/bin/bash
cd ~/novel_translation_project
source venv/bin/activate
python main.py
```

Make executable:
```bash
chmod +x start.sh
./start.sh
```

---

## Common Issues & Solutions

### Issue: "Ollama connection refused"

**Solution:**
```bash
# Start Ollama service
ollama serve

# In another terminal, run translation
python main.py
```

### Issue: "Out of memory"

**Solution:**
- Use smaller model (7B instead of 14B)
- Reduce chunk size: `--max-chars 800`
- Close other applications

### Issue: "Module not found"

**Solution:**
```bash
# Ensure virtual environment is activated
source venv/bin/activate

# Reinstall requirements
pip install -r requirements.txt
```

### Issue: "Translation has English words mixed in"

**Solution:**
```bash
# Run the fix script
python scripts/fix_translation.py books/novel/chapters/file.md

# Creates a fixed version: file_fixed.md
```

---

## Next Steps

1. **Read AGENTS.md** - Understand the AI prompts and how they work
2. **Read need_to_fix.md** - Learn how to improve translation quality
3. **Experiment** - Try different models and settings
4. **Contribute** - Add improvements and share with community

---

**Need Help?**
- Check [Troubleshooting](#common-issues--solutions)
- Review [README.md](README.md)
- Check logs in `working_data/logs/`

**Last Updated**: April 22, 2026
