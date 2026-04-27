# User Guide - Novel Translation System
# မြန်မာဘာသာပြန် စနစ် အသုံးပြုမှု လမ်းညွှန်

## 📋 Table of Contents
1. [Quick Start](#quick-start)
2. [Using Local Ollama Model](#using-local-ollama-model)
3. [Using Cloud API (Gemini/OpenRouter)](#using-cloud-api)
4. [Translation Mode: One-Step vs Two-Step](#translation-mode)
5. [Output Format](#output-format)
6. [Troubleshooting](#troubleshooting)

---

## 🚀 Quick Start

### 1. Setup Your Novel
Place Chinese chapter files in `data/input/your_novel_name/`:
```
data/input/
└── 古道仙鸿/
    ├── 古道仙鸿_chapter_001.md
    ├── 古道仙鸿_chapter_002.md
    └── ...
```

### 2. Run Translation
```bash
# Translate single chapter
python -m src.main --novel 古道仙鸿 --chapter 1

# Translate all chapters
python -m src.main --novel 古道仙鸿 --all

# Translate from chapter 10 onwards
python -m src.main --novel 古道仙鸿 --all --start 10

# NEW: Run a quick test translation with sample data
python -m src.main --test

# NEW: Launch the Web UI (Streamlit)
python -m src.main --ui

# NEW: Automatically generate glossary from novel chapters
python -m src.main --novel 古道仙鸿 --generate-glossary
```

---

## 📖 Glossary Generation

Before starting a full translation, it's highly recommended to generate a glossary of key terms (character names, places, items). This ensures consistency throughout the novel.

### Generate Glossary
```bash
python -m src.main --novel 古道仙鸿 --generate-glossary
```
**This command will:**
1. Scan the first few chapters of your novel.
2. Extract important proper nouns and cultivation terms.
3. Propose Myanmar transliterations for them.
4. Save them to `data/glossary_pending.json`.

**After generation:**
- Open `data/glossary_pending.json`.
- Review the proposed terms.
- Approved terms should be moved to `data/glossary.json` (or you can approve them via the Web UI if implemented).

---

## 🌐 Using the Web UI

The project includes a user-friendly Web UI built with Streamlit. It allows you to configure models, select novels, and monitor translation progress visually.

### Launching the UI
```bash
python -m src.main --ui
```
This will start the Streamlit server and open the UI in your default web browser (usually at `http://localhost:8501`).

### UI Features
- **Translate Tab**: Select a novel from `data/input`, choose the translation mode (Single/Two Stage), and start the process.
- **Glossary Tab**: View approved terms and pending terms extracted by the agents.
- **Progress Tab**: Monitor the real-time progress of ongoing and recent translations.

---

## 🧪 Testing with Sample Data

If you want to verify your setup (Ollama, models, and pipeline) without translating a full novel, you can use the built-in test mode.

### Run Sample Test
```bash
python -m src.main --test
```
**This command will:**
1. Check for `data/input/sample.md` (and create a basic one if missing).
2. Auto-select the English→Myanmar translation configuration.
3. Run the full pipeline (Translate → Refine → Quality Check).
4. Save the result to `data/output/sample_mm.md`.

### Run Custom File Test
You can also test any specific file:
```bash
python -m src.main --input your_file.md --lang zh  # for Chinese
python -m src.main --input your_file.md --lang en  # for English
```

---

## 🖥️ Using Local Ollama Model

### Step 1: Install Ollama
```bash
# Download from https://ollama.ai
# Or use command line:
curl -fsSL https://ollama.com/install.sh | sh
```

### Step 2: Pull a Model
```bash
# Recommended models for Chinese→Myanmar:
ollama pull qwen2.5:14b    # Good quality (9GB)
# Or use the local Padauk-Gemma model (Best EN/CN -> MM):
ollama create padauk-gemma:q8_0 -f Modelfile  # See project for Modelfile


# Verify model is installed
ollama list
```

### Step 3: Configure settings.yaml
```yaml
models:
  provider: "ollama"
  translator: "qwen2.5:14b"     # Your downloaded model
  editor: "qwen2.5:14b"
  refiner: "qwen:7b"
  checker: "qwen:7b"
  ollama_base_url: "http://localhost:11434"
```

### Step 4: Start Ollama Server
```bash
# Terminal 1: Start Ollama server
ollama serve

# Terminal 2: Run translation
python -m src.main --novel 古道仙鸿 --chapter 1
```

---

## ☁️ Using Cloud API

### Option A: Google Gemini (Recommended)

#### 1. Get API Key
- Visit: https://makersuite.google.com/app/apikey
- Create new API key
- Copy the key

#### 2. Set Environment Variable
```bash
# Linux/Mac
export GEMINI_API_KEY="your_api_key_here"

# Windows CMD
set GEMINI_API_KEY=your_api_key_here

# Or create .env file in project root
echo "GEMINI_API_KEY=your_api_key_here" > .env
```

#### 3. Update settings.yaml
```yaml
models:
  provider: "gemini"
  cloud_model: "gemini-2.5-flash"
  
translation_pipeline:
  mode: "two_stage"
  stage1_model: "gemini-2.5-flash"
  stage2_model: "gemini-2.5-flash"
```

### Option B: OpenRouter (Free Tier Available)

#### 1. Get API Key
- Visit: https://openrouter.ai/keys
- Sign up and create API key

#### 2. Set Environment Variable
```bash
export OPENROUTER_API_KEY="your_api_key_here"
```

#### 3. Update settings.yaml
```yaml
models:
  provider: "openrouter"
  cloud_model: "google/gemini-2.5-flash-exp:free"
  
translation_pipeline:
  mode: "two_stage"
  stage1_model: "openrouter:google/gemini-2.5-flash-exp:free"
  stage2_model: "openrouter:google/gemini-2.5-flash-exp:free"
```

---

## ⚙️ Translation Mode: One-Step, Two-Step, and Pivot

### Pivot Mode (CN→EN→MM) (New/Recommended for Complex Texts) 🌟
**How it works:**
1. **Stage 1** - Chinese to English: Uses a high-capability model (`qwen2.5:14b`) to accurately translate the complex Chinese text into English, preserving names in Pinyin.
2. **Stage 2** - English to Myanmar: Uses a model tuned for Myanmar generation (`qwen:7b`) to translate the English text into natural Myanmar SOV prose.

**Pros:**
- Drastically reduces "language confusion" where models output mixed Chinese/Myanmar.
- High accuracy leveraging the strong CN→EN capabilities of larger models.
- Can run on mid-range hardware by sequentially loading a 14B then a 7B model.

**Cons:**
- Slower than single-stage.
- Requires two different model passes.

**When to use:** Highly complex Wuxia/Xianxia text where direct CN→MM translation yields garbage or mixed-language output.

**Configuration:**
Use the dedicated pivot config file:
```bash
python -m src.main --config config/settings.pivot.yaml --novel 古道仙鸿 --chapter 1
```

---

### Two-Stage Mode (Standard) ✅
**How it works:**
1. **Stage 1** - Raw Translation: Chinese → Myanmar (literal translation)
2. **Stage 2** - Literary Rewrite: Improve flow, naturalness, style

**Pros:**
- Better literary quality
- More natural Myanmar prose
- Corrects awkward phrasing

**Cons:**
- 2x slower (two API calls per chunk)

**When to use:** Novels, stories, when direct CN→MM translation quality is already decent.

**Configuration:**
```yaml
translation_pipeline:
  mode: "two_stage"
```

---

### Single-Stage Mode ⚡
**How it works:**
- Direct translation in one pass

**Pros:**
- 2x faster
- Lower API costs

**Cons:**
- May have robotic/awkward phrasing
- Less literary polish

**When to use:** Technical docs, quick drafts, large volumes

**CLI Override:**
```bash
# Force single-stage for one run
python -m src.main --novel 古道仙鸿 --chapter 1 --single-stage

# Force two-stage for one run
python -m src.main --novel 古道仙鸿 --chapter 1 --two-stage
```

---

## 📝 Output Format

### Pretty Markdown Output
The system generates beautifully formatted Markdown files:

**Output Location:**
```
data/output/
└── 古道仙鸿/
    └── chapters/
        ├── 古道仙鸿_chapter_001_mm.md
        ├── 古道仙鸿_chapter_002_mm.md
        └── ...
```

### Sample Output Format:
```markdown
<!-- 
Translation Progress:
- Chapter: 古道仙鸿_chapter_001
- Chunks Completed: 5/5
- Timestamp: 2025-01-20T10:30:00
- Status: COMPLETE
-->

# 第一章 - မြန်မာခေါင်းစဉ်

## ဤသည်အခန်းခေါင်းစဉ်ဖြစ်သည်

ပထမအပိုင်းတွင် စာရေးသူသည်...

**ထိုသို့** အရေးကြီးသော အချက်များကို အစီအစဉ်တကျ ရှင်းလင်းတင်ပြထားသည်။

---

စာသားများကို အရည်အသွေးမြင့်စွာ ဘာသာပြန်ဆိုထားသည်။
```

### Formatting Features:
- ✅ **Chapter headers** (`#`, `##`, `###`) preserved
- ✅ **Bold text** (`**text**`) preserved
- ✅ **Italic text** (`*text*`) preserved
- ✅ **Lists** (`-`, `1.`) preserved
- ✅ **Blockquotes** (`>`) preserved
- ✅ **Myanmar Unicode** properly encoded (UTF-8)
- ✅ **Metadata header** with translation info

### Viewing the Output:
```bash
# Open with any Markdown viewer
code data/output/古道仙鸿/chapters/古道仙鸿_chapter_001_mm.md

# Or convert to PDF (optional)
pandoc data/output/古道仙鸿/chapters/古道仙鸿_chapter_001_mm.md -o output.pdf
```

---

## 🔧 Troubleshooting

### Issue: "Model not available"
```
Error: Model qwen2.5:14b not available in Ollama
```
**Solution:**
```bash
# Download the model
ollama pull qwen2.5:14b

# Or use a different model
ollama list  # See available models
# Then update settings.yaml
```

### Issue: "Connection refused"
```
Error: Cannot connect to Ollama
```
**Solution:**
```bash
# Start Ollama server in another terminal
ollama serve

# Or check if port is correct
# Update settings.yaml:
ollama_base_url: "http://localhost:11434"
```

### Issue: "API key not set"
```
Error: GEMINI_API_KEY not found
```
**Solution:**
```bash
# Set the environment variable
export GEMINI_API_KEY="your_key_here"

# Or create .env file
echo "GEMINI_API_KEY=your_key_here" > .env
```

### Issue: Translation is too slow
**Solutions:**
1. Use single-stage mode: `--single-stage`
2. Use smaller model: `qwen:7b` instead of `qwen2.5:14b`
3. Increase chunk size: `chunk_size: 2000`
4. Reduce overlap: `chunk_overlap: 50`

### Issue: Output has Chinese characters
**Solutions:**
1. Check `myanmar_readability.min_myanmar_ratio` in settings.yaml
2. Increase temperature slightly: `temperature: 0.4`
3. Use better model: `qwen2.5:14b`

---

## 📊 Model Comparison

| Model | Speed | Quality | Size | Best For |
|-------|-------|---------|------|----------|
| qwen2.5:14b | Medium | Excellent | 9GB | Production novels, Pivot Stage 1 (CN→EN) |
| qwen2.5:7b | Fast | Good | 4GB | Quick drafts |
| qwen:7b | Very Fast | Okay | 4GB | Testing, Pivot Stage 2 (EN→MM) |
| Gemini Flash | Fast | Excellent | Cloud | High quality, no local GPU |
| OpenRouter | Fast | Good | Cloud | Free tier available |

---

## 💡 Pro Tips

1. **Start small:** Test with 1-2 chapters first
2. **Use two-stage** for final novels
3. **Use single-stage** for bulk processing
4. **Check glossary:** Add character names to `data/glossary.json` for consistency
5. **Review output:** Always spot-check a few chapters before bulk processing

---

## 🆘 Need Help?

Check logs for detailed error messages:
```bash
tail -f logs/translation.log
```

Or run with verbose output:
```bash
python -m src.main --novel 古道仙鸿 --chapter 1 --verbose
```

## How to Run Tests
### Option 1: Run All Tests
`py -m unittest discover tests -v`

### Option 2: Run Specific Test File
`py -m unittest tests.test_agents -v`
`py -m unittest tests.test_integration -v`
`py -m unittest tests.test_translator -v`

### Option 3: Run Single Test
**Run Specific test class**
`py -m unittest tests.test_agents.TestTranslator -v`

**Run Specific test method**
`py -m unittest tests.test_agents.TestTranslator.test_build_prompt -v`