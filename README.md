# Chinese/English-to-Burmese Novel Translation System

An AI-powered novel translation pipeline that automatically translates **Chinese OR English** novels into **natural, conversational Burmese (Myanmar language)**. Optimized for web novels, wuxia/xianxia stories, and other literary works while preserving the original tone, style, and emotional depth.

## 🌟 Key Features

- **🌐 Multi-Language Source**: Supports both **Chinese** and **English** source novels
- **🔄 Two-Stage Translation**: Raw translation + Literary rewrite for natural Burmese
- **📚 Per-Novel Glossaries**: Each novel gets its own character name glossary (`glossaries/novel_name.json`)
- **🤖 Multi-Model Support**: Ollama (local), OpenRouter, Gemini, NLLB-200, and more
- **📖 Natural Burmese**: Optimized prompts for conversational, emotionally resonant translations
- **💾 Checkpoint Resume**: Never lose progress - resume interrupted translations anytime
- **🔍 Quality Checks**: Automated Myanmar readability validation
- **⚡ Streaming Output**: Real-time token streaming with live progress
- **🌐 Web Reader**: Built-in web reader to read translated novels

## 📁 Project Structure

```
novel_translation_project/
│
├── main.py                     # Main orchestrator (entry point)
├── reader_app.py               # Web reader for translated novels
├── translate_novel.py          # Full novel pipeline (extract + translate)
├── translate_manual.py         # Manual chapter-by-chapter translation
├── AGENTS.md                   # AI agent guidance and prompts
├── need_to_fix.md              # Translation quality guide
├── README.md                   # This file
├── SETUP.md                    # Detailed setup guide
├── requirements.txt            # Python dependencies
├── .env.example                # Environment template
│
├── config/
│   ├── settings.py             # Pydantic configuration validation
│   └── config.json             # Runtime configuration
│
├── scripts/                    # Translation pipeline modules
│   ├── __init__.py
│   ├── preprocessor.py         # Clean & normalize text
│   ├── chunker.py              # Smart text chunking
│   ├── translator.py           # AI translation engine
│   ├── rewriter.py             # Two-stage rewrite for quality
│   ├── glossary_manager.py     # Per-novel glossary management
│   ├── checkpoint.py           # Save/resume progress
│   ├── postprocessor.py        # Fix punctuation & names
│   ├── assembler.py            # Assemble final document
│   ├── myanmar_checker.py      # Quality control
│   └── fix_translation.py      # Fix poor translations
│
├── templates/                  # HTML templates for web reader
├── input_novels/               # Drop novels here (.txt/.md)
├── books/                      # Final translations (organized by book)
├── glossaries/                 # Per-novel glossaries (*.json)
├── chinese_chapters/           # Extracted Chinese chapters
├── english_chapters/           # Extracted English chapters
│
└── working_data/               # Temporary files (gitignored)
    ├── checkpoints/            # Resume state
    ├── logs/                   # Translation logs
    └── readability_reports/    # Quality reports
```

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Git
- Ollama (for local LLM) OR API keys for cloud models
- 16GB+ RAM (32GB recommended for large models)

### Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd novel_translation_project
   ```

2. **Create virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # Windows: .\venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and model selection
   ```

5. **Pull Ollama model (if using local):**
   ```bash
   ollama pull qwen2.5:14b
   # OR for better quality
   ollama pull gemma:12b
   ```

### Basic Usage

```bash
# Translate all files in input_novels/
python main.py

# Translate specific file
python main.py input_novels/my_novel.txt

# Use specific model
python main.py --model openrouter
python main.py --model gemini
python main.py --model ollama

# Adjust chunk size
python main.py --max-chars 1200

# Skip readability check
python main.py --no-readability
```

### Two-Stage Translation (Higher Quality)

Enable in `config/config.json`:
```json
{
  "translation_pipeline": {
    "mode": "two_stage"
  }
}
```

This runs:
1. **Stage 1**: Raw literal translation
2. **Stage 2**: Literary rewrite into natural Burmese

## 📖 Translation Workflow

```
1. PREPROCESS   → Clean text, detect encoding, remove noise
2. CHUNK        → Split into paragraph-safe chunks
3. GLOSSARY     → Load per-novel character name glossary
4. TRANSLATE    → AI translation with context awareness
5. REWRITE      → (Two-stage) Polish into natural Burmese
6. POSTPROCESS  → Fix punctuation and enforce glossary
7. ASSEMBLE     → Merge into final Markdown file
8. SAVE         → Update glossary with new names
```

## 📚 Glossary System (Character Name Consistency)

Each novel gets its own glossary file: `glossaries/<novel_name>.json`

### Managing Glossaries

```bash
# List glossary for a novel
python scripts/glossary_manager.py novel_name list

# Add a name manually
python scripts/glossary_manager.py novel_name add "Gu Wen" "ဂူဝမ်"

# View statistics
python scripts/glossary_manager.py novel_name stats

# List all available glossaries
python scripts/glossary_manager.py
```

### Example Glossary (`glossaries/my_novel.json`)

```json
{
  "names": {
    "Gu Wen": "ဂူဝမ်",
    "Marquis Wen": "ဝမ်တိုင်",
    "Bianjing": "ဘိန်းကျိင်",
    "Dragon Bridge": "လွန်ချျန်းတံတား"
  },
  "metadata": {
    "novel_name": "my_novel",
    "created_at": "2026-04-22T10:00:00",
    "updated_at": "2026-04-22T12:00:00",
    "total_names": 4,
    "chapter_count": 10
  }
}
```

## ⚙️ Configuration

### Environment Variables (`.env`)

```bash
# Model Selection: openrouter | gemini | ollama | nllb
AI_MODEL=ollama

# API Keys (for cloud models)
OPENROUTER_API_KEY=your_key_here
GEMINI_API_KEY=your_key_here

# Ollama (Local)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:14b

# Translation Settings
MAX_CHUNK_CHARS=1200
REQUEST_DELAY=0.5
SOURCE_LANGUAGE=Chinese  # or English
```

### Runtime Configuration (`config/config.json`)

```json
{
  "model": "qwen2.5:14b",
  "provider": "ollama",
  "source_language": "Chinese",
  "chunk_size": 1200,
  "chunk_overlap": 100,
  "stream": true,
  "translation_pipeline": {
    "mode": "single_stage"
  },
  "myanmar_readability": {
    "enabled": true,
    "min_myanmar_ratio": 0.7
  }
}
```

## 🌐 Web Reader

Read translated novels in your browser:

```bash
python reader_app.py
# Open http://localhost:5000
```

Features:
- Library view of all translated books
- Chapter list with progress tracking
- Clean reading interface
- Saves reading position

## 🔍 Quality Assurance

Automated checks on each translation:

| Check | Pass Condition |
|-------|----------------|
| Myanmar script ratio | ≥ 70% Myanmar Unicode |
| No source leakage | Zero Chinese/English characters |
| Sentence boundaries | At least one `။` marker |
| Minimum length | Output ≥ 30% of input |
| Encoding integrity | No replacement characters |

## 🛠️ Fixing Poor Translations

If a translation has issues (English mixed in, weird repetitions, etc.):

```bash
# Auto-fix common issues
python scripts/fix_translation.py books/novel/chapters/file.md

# Creates: books/novel/chapters/file_fixed.md
```

This fixes:
- Metadata text in output
- English phrases not translated
- Weird character repetitions
- Inconsistent character names
- Dialogue format issues

## 🧠 Recommended Models

| Model | RAM | Quality | Speed | Best For |
|-------|-----|---------|-------|----------|
| `qwen2.5:14b` | ~10GB | ⭐⭐⭐⭐⭐ | Medium | Local, best quality |
| `gemma:12b` | ~8GB | ⭐⭐⭐⭐ | Medium | Local, good balance |
| `gemini-2.0-flash` | Cloud | ⭐⭐⭐⭐⭐ | Fast | API, fast & quality |
| `nllb-200` | ~2GB | ⭐⭐⭐ | Fast | Two-stage pipeline |

## 🐛 Troubleshooting

| Problem | Solution |
|---------|----------|
| Out of memory | Use 7B model or reduce chunk_size |
| Model not found | Run `ollama pull <model>` |
| API errors | Check API keys in .env |
| Names inconsistent | Update glossary: `python scripts/glossary_manager.py novel_name add "Name" "မြန်မာနာမည်"` |
| Translation has English | Run `python scripts/fix_translation.py <file.md>` |
| Resume failed | Delete checkpoint in `working_data/checkpoints/` |

## 📄 Documentation

- **[SETUP.md](SETUP.md)** - Detailed installation and setup guide
- **[AGENTS.md](AGENTS.md)** - AI agent guidance and prompt engineering
- **[need_to_fix.md](need_to_fix.md)** - Translation quality improvement guide

## 📜 License

This project is for personal/educational use.

## 🤝 Contributing

When contributing:
1. Follow the existing code style
2. Update documentation as needed
3. Test your changes thoroughly
4. Update glossaries for new novel-specific terms

---

**Last Updated**: April 22, 2026  
**Version**: 2.0  
**Language Pairs**: Chinese → Burmese, English → Burmese
