# Chinese-to-Burmese Novel Translation System

An AI-powered novel translation pipeline that automatically translates Chinese novels into Burmese (Myanmar language). Optimized for web novels, wuxia/xianxia stories, and other Chinese literary works while preserving the original tone, style, and emotional depth.

## Key Features

- **Multi-Model Support**: Works with Ollama (local), OpenRouter, Gemini, DeepSeek, and Qwen
- **Streaming Translation**: Real-time token streaming with live progress display
- **Checkpoint Resume**: Never lose progress - resume interrupted translations anytime
- **WebSocket Progress**: Browser-based real-time translation monitoring
- **Myanmar Readability Checks**: Automated quality validation for Burmese output
- **Name Consistency**: Maintains consistent character/place names across all chapters via `names.json`
- **Batch Processing**: Queue and translate multiple novels in sequence
- **Error Recovery**: Automatic retry with exponential backoff

## Project Structure

```
novel_translation_project/
│
├── main.py                     # Main orchestrator (entry point)
├── AGENTS.md                   # AI agent guidance and context
├── README.md                   # This file
├── requirements.txt            # Python dependencies
├── Makefile                    # Build automation
├── .env.example                # Environment template
├── .gitignore                  # Git ignore rules
│
├── config/
│   ├── settings.py             # Pydantic configuration validation
│   └── config.json             # Runtime configuration
│
├── scripts/                    # Translation pipeline modules
│   ├── __init__.py
│   ├── preprocessor.py         # Step 1: Clean & normalize text
│   ├── chunker.py              # Step 2: Split into chunks
│   ├── translator.py           # Step 3: AI translation engine
│   ├── checkpoint.py           # Step 4: Save/resume progress
│   ├── postprocessor.py        # Step 5: Fix names & punctuation
│   ├── assembler.py            # Step 6: Assemble final document
│   └── myanmar_checker.py      # Quality control checker
│
├── templates/
│   ├── chapter_template.md     # Chapter formatting template
│   └── novel_template.md       # Full novel structure template
│
├── input_novels/               # Drop Chinese novels here (.md/.txt)
├── translated_novels/          # Final Burmese translations (.md)
├── chinese_chapters/             # Extracted chapter storage
├── data_file/                    # Data storage
│
└── working_data/               # Temporary files (gitignored)
    ├── checkpoints/            # Resume state files
    ├── chunks/                 # Pre-translation text chunks
    ├── translated_chunks/      # Post-translation chunks
    ├── preview/                # Live preview files
    ├── readability_reports/    # Quality check reports
    ├── logs/                   # Translation logs
    └── clean/                  # Cleaned text files
```

## Quick Start

### Prerequisites

- Python 3.8+
- Git
- Ollama (for local LLM) or API keys for cloud models
- 16GB+ RAM (32GB recommended)

### Installation

1. **Clone or navigate to the project:**
   ```bash
   cd novel_translation_project
   ```

2. **Create virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: .\venv\Scripts\activate
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
   ```

### Usage

#### Basic Translation

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
python main.py --max-chars 2000

# Skip readability check
python main.py --no-readability
```

#### Manual Chapter Translation

```bash
# Check status
python translate_manual.py novel_name --status

# Translate specific chapter
python translate_manual.py novel_name --chapter 1

# Translate next pending chapter
python translate_manual.py novel_name --next

# List all chapters
python translate_manual.py novel_name --list
```

#### Novel Translation (Extract + Translate)

```bash
# Process single novel
python translate_novel.py novel_name

# Process all novels
python translate_novel.py --all
```

#### Using Make Commands

```bash
make install    # Install dependencies
make run        # Run main.py
make clean      # Clean checkpoints and logs
make lint       # Run linters
make test       # Run tests
```

## Translation Workflow

When you run `main.py`, the following 7-step pipeline executes automatically:

```
1. SCAN       → Check input_novels/ for Chinese text files
2. PREPROCESS → Clean text, enforce UTF-8, remove noise
3. CHUNK      → Split into 1500-2000 character chunks with overlap
4. TRANSLATE  → Use AI to translate each chunk (streaming)
5. CHECKPOINT → Save progress after each chunk (resume anytime)
6. POSTPROCESS→ Fix character names using names.json
7. ASSEMBLE   → Merge all chunks into final Markdown file
```

## Configuration

### Environment Variables (.env)

```bash
# Model Selection: openrouter | gemini | deepseek | qwen | ollama
AI_MODEL=ollama

# API Keys (for cloud models)
OPENROUTER_API_KEY=your_key_here
GEMINI_API_KEY=your_key_here
DEEPSEEK_API_KEY=your_key_here
QWEN_API_KEY=your_key_here

# Ollama (Local)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:14b

# Translation Settings
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
  "myanmar_readability": {
    "enabled": true,
    "min_myanmar_ratio": 0.7,
    "flag_on_fail": true,
    "block_on_fail": false
  }
}
```

### Character Names (names.json)

Maintain consistent translations for characters, places, and terms:

```json
{
  "罗青": "လော်ချင်",
  "蟠龙山": "ပန်လုံတောင်",
  "魔教": "မိစ္ဆာဂိုဏ်း"
}
```

## Quality Assurance

The system performs automated checks on each translated chunk:

| Check | Pass Condition |
|-------|----------------|
| Myanmar script ratio | ≥ 70% Myanmar Unicode (U+1000–U+109F) |
| No Chinese leakage | Zero Chinese characters (U+4E00–U+9FFF) |
| Sentence boundary | At least one `။` marker present |
| Minimum length | Output ≥ 30% of input length |
| Encoding integrity | No replacement characters (U+FFFD) |

## Models

### Recommended Models

| Model | RAM Usage | Quality | Best For |
|-------|-----------|---------|----------|
| `qwen2.5:14b` | ~10 GB | Excellent | Local, high quality |
| `qwen2.5:7b` | ~6 GB | Good | Local, lower RAM |
| `gemini-2.0-flash` | Cloud | Excellent | API, fast |
| `deepseek-chat` | Cloud | Excellent | API, reasoning |

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Out of memory | Use 7B model or reduce chunk_size |
| Model not found | Run `ollama pull <model>` |
| API errors | Check API keys in .env |
| Chinese in output | Set `block_on_fail: true` in config |
| Resume failed | Delete checkpoint file in `working_data/checkpoints/` |

## Technologies Used

- **Python 3.8+** - Core language
- **Flask/Socket.IO** - Web UI and real-time progress
- **Ollama** - Local LLM runner
- **Requests** - API clients
- **Pydantic** - Configuration validation
- **python-dotenv** - Environment management

## License

This project is for personal/educational use.

## Contributing

When contributing:
1. Follow the existing code style
2. Update documentation as needed
3. Test your changes thoroughly
4. Update names.json for new novel-specific terms

---

**Last Updated**: April 21, 2026  
**Project**: Novel Translation System  
**Language Pair**: Chinese (Simplified) → Burmese (Myanmar)
