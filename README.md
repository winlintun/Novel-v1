# Chinese/English-to-Burmese Novel Translation System

An AI-powered novel translation pipeline that translates **Chinese OR English** novels into **natural, conversational Burmese (Myanmar)**. Features a two-stage translation pipeline with context injection for consistent, high-quality output.

## 🌟 Key Features

- **🌐 Multi-Language Source**: Supports both **Chinese** and **English** source novels
- **🔄 Two-Stage Translation**: NLLB-200 raw translation + qwen:7b literary rewrite
- **💉 Context Injection**: Characters + Story + Previous chapters injected into prompts
- **📚 Per-Novel Glossaries**: Automatic character name consistency
- **🤖 Multi-Model Support**: Ollama (local), OpenRouter, Gemini, NLLB-200
- **📖 Web Reader**: Built-in Flask web reader with progress tracking
- **🔍 Quality Checks**: Automated Myanmar readability validation
- **⚡ Streaming Output**: Real-time token streaming
- **💾 Context Memory**: Tracks characters and story across chapters

## 📁 Project Structure

```
novel_translation_project/
│
├── main.py                     # Main orchestrator (entry point)
├── reader_app.py               # Web reader for translated novels
├── test.py                     # Comprehensive test suite (92 tests)
├── AGENTS.md                   # AI agent guidance and prompts
├── README.md                   # This file
├── requirements.txt            # Python dependencies
├── .env.example                # Environment template
│
├── config/
│   └── config.json             # Runtime configuration
│
├── scripts/                    # Translation pipeline modules
│   ├── translator.py           # AI translation engine (NLLB, Ollama, Gemini)
│   ├── rewriter.py             # Two-stage rewrite for quality
│   ├── context_manager.py      # Characters + Story + Chapter tracking
│   ├── glossary_manager.py     # Per-novel glossary management
│   ├── preprocessor.py         # Clean & normalize text
│   ├── chunker.py              # Smart text chunking
│   ├── postprocessor.py        # Fix punctuation & names
│   ├── fix_translation.py      # Auto-fix common translation issues
│   ├── assembler.py            # Assemble final document
│   └── myanmar_checker.py      # Quality control
│
├── templates/                  # HTML templates for web reader
│   ├── index.html              # Library view
│   ├── chapters.html           # Chapter list
│   └── reader.html             # Reading interface
│
├── books/                      # Final translations (organized by book)
│   └── {novel_name}/
│       ├── metadata.json       # Book metadata
│       └── chapters/
│           └── *_myanmar.md    # Translated chapters
│
├── glossaries/                 # Per-novel glossaries (*.json)
├── context/                    # Per-novel context (characters, story)
├── english_chapters/           # Source: English novels
│   └── {novel_name}/
│       └── {novel}_chapter_*.md
├── chinese_chapters/           # Source: Chinese novels
│   └── {novel_name}/
│       └── {novel}_chapter_*.md
│
└── working_data/               # Temporary files
    ├── logs/                   # Translation logs
    └── progress.json           # Reader progress
```

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Git
- 16GB+ RAM (32GB recommended)
- Ollama (for local models) OR API keys for cloud models

### Installation

```bash
# 1. Clone repository
git clone <repository-url>
cd novel_translation_project

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your API keys and settings

# 5. Pull Ollama model (if using local)
ollama pull qwen:7b
```

### Configuration

Edit `config/config.json`:

```json
{
  "translation_pipeline": {
    "mode": "two_stage",
    "stage1_model": "nllb",
    "stage2_model": "ollama:qwen:7b"
  },
  "source_language": "English"
}
```

### Usage

```bash
# Translate a specific novel
python main.py --novel dao-equaling-the-heavens --source-lang English

# Translate all novels in chapter directories
python main.py --source-lang English

# Run tests
python test.py

# Start web reader
python reader_app.py
# Open http://localhost:5000
```

## 📖 Translation Workflow

```
┌─────────────────────────────────────────────────────────────┐
│  CONTEXT → TRANSLATE → REWRITE → POSTPROCESS → OUTPUT       │
└─────────────────────────────────────────────────────────────┘

1. LOAD CONTEXT     → Characters + Story + Previous chapters
2. PREPROCESS       → Clean text, detect encoding
3. CHUNK            → Split into paragraph-safe chunks
4. STAGE 1 (NLLB)   → Raw literal translation
5. STAGE 2 (qwen)   → Rewrite into natural, emotional Burmese
6. POSTPROCESS      → Fix punctuation, enforce glossary
7. UPDATE CONTEXT   → Save new characters and chapter summary
8. ASSEMBLE         → Merge into final document
```

## 📚 Context Injection System

The system maintains context across chapters for consistency:

### Characters Tracking
- Original names and Burmese translations
- Physical descriptions and traits
- First appearance chapter
- Relationships between characters

### Story Tracking
- Major story events
- Plot progression
- Chapter summaries

### Context Format
```
## CHARACTERS
- Gu Wen (ဂူဝမ်): Main protagonist
- Marquis Wen (ဝမ်တိုင်): Noble

## STORY CONTEXT
- Ch 1: Gu Wen summoned by employer

## PREVIOUS CHAPTERS
- Chapter 1: Summary of previous events
```

## 📚 Glossary System

Each novel gets its own glossary: `glossaries/{novel_name}.json`

```bash
# Add a character name
python scripts/glossary_manager.py novel_name add "Gu Wen" "ဂူဝမ်"

# View glossary
python scripts/glossary_manager.py novel_name list

# Show statistics
python scripts/glossary_manager.py novel_name stats
```

### Example Glossary
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

## 🌐 Web Reader

Read translated novels with a beautiful web interface:

```bash
python reader_app.py
# Open http://localhost:5000
```

Features:
- 📚 Library view of all books
- 📑 Chapter list with progress
- 📖 Clean reading interface
- 💾 Saves reading position
- ⬅️➡️ Previous/Next navigation

## ⚙️ Configuration

### Environment Variables (`.env`)

```bash
# Model Selection
AI_MODEL=ollama

# API Keys (for cloud models)
OPENROUTER_API_KEY=your_key_here
GEMINI_API_KEY=your_key_here

# Ollama (Local)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen:7b

# Translation Settings
SOURCE_LANGUAGE=English
MAX_CHUNK_CHARS=1000
REQUEST_DELAY=0.5
```

### Runtime Configuration (`config/config.json`)

```json
{
  "model": "qwen:7b",
  "provider": "ollama",
  "source_language": "English",
  "chunk_size": 1000,
  "chunk_overlap": 100,
  "stream": true,
  "translation_pipeline": {
    "mode": "two_stage",
    "stage1_model": "nllb",
    "stage2_model": "ollama:qwen:7b"
  },
  "myanmar_readability": {
    "enabled": true,
    "min_myanmar_ratio": 0.7
  }
}
```

## 🔍 Quality Assurance

Automated checks ensure translation quality:

| Check | Pass Condition |
|-------|----------------|
| Myanmar ratio | ≥ 70% Myanmar Unicode |
| No source leakage | Zero Chinese/English characters |
| Sentence boundaries | At least one `။` marker |
| Encoding integrity | No replacement characters |

## 🧪 Testing

Run the comprehensive test suite:

```bash
# All tests (92 tests)
python test.py

# Specific category
python test.py --category reader
python test.py --category glossary
python test.py --category quality
```

## 🛠️ Fixing Translation Issues

Auto-fix common problems:

```bash
python scripts/fix_translation.py books/novel/chapters/file.md
# Creates: books/novel/chapters/file_fixed.md
```

Fixes:
- Metadata text in output
- English phrases not translated
- Weird character repetitions
- Dialogue format issues

## 🧠 Model Configuration

Current recommended pipeline:

| Stage | Model | Purpose |
|-------|-------|---------|
| Stage 1 | NLLB-200 | Fast raw translation |
| Stage 2 | qwen:7b | Natural, emotional rewrite |

Alternative models:

| Model | RAM | Best For |
|-------|-----|----------|
| `qwen:7b` | ~6GB | Stage 2 rewrite |
| `qwen2.5:14b` | ~10GB | Single-stage translation |
| `gemma:12b` | ~8GB | English source |
| `nllb-200` | ~2GB | Stage 1 raw translation |

## 🐛 Troubleshooting

| Problem | Solution |
|---------|----------|
| Out of memory | Reduce chunk_size to 800 |
| Model not found | Run `ollama pull qwen:7b` |
| API errors | Check API keys in .env |
| Names inconsistent | Update glossary |
| Translation has English | Run `scripts/fix_translation.py` |
| Reader not loading | Check books/{novel}/metadata.json exists |

## 📄 Documentation

- **[AGENTS.md](AGENTS.md)** - AI agent guidance and prompts
- **[need_to_fix.md](need_to_fix.md)** - Translation quality guide

## 📜 License

This project is for personal/educational use.

---

**Last Updated**: April 22, 2026  
**Version**: 2.2  
**Language Pairs**: Chinese → Burmese, English → Burmese

### Recent Updates (v2.2)
- ✅ Added context injection system (Characters + Story + Chapters)
- ✅ Updated pipeline: Stage1=NLLB200, Stage2=qwen:7b
- ✅ Added comprehensive test suite (92 tests)
- ✅ Fixed reader_app.py Flask compatibility
- ✅ Removed names.json fallback, using glossaries only
