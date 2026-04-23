# Novel Translation Pipeline

Chinese Xianxia Novel to Myanmar Translation System

## Project Structure

```
novel_translation_project/
├── config/
│   └── settings.yaml          # Model, Path, API Settings
├── data/
│   ├── input/                 # Chinese chapter files (novel_name_XXX.md)
│   ├── output/                # Myanmar translations
│   ├── glossary.json          # Terminology Database
│   └── context_memory.json    # Dynamic Chapter Context
├── logs/
│   └── translation.log        # Translation logs
├── src/
│   ├── agents/
│   │   ├── preprocessor.py    # Splits text, cleans markdown
│   │   ├── translator.py      # Core CN->MM Translation
│   │   ├── refiner.py         # Polishes Myanmar flow/tone
│   │   ├── checker.py         # Checks Glossary consistency
│   │   └── context_updater.py # Updates memory after chapter
│   ├── memory/
│   │   └── memory_manager.py  # Handles Glossary & Context loading/saving
│   ├── utils/
│   │   ├── ollama_client.py   # Wrapper for Ollama API
│   │   └── file_handler.py    # Read/Write files
│   └── main.py                # Entry point
├── tests/
│   ├── test_translator.py
│   └── test_integration.py
├── requirements.txt
└── README.md
```

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Prepare Input Files

Place Chinese chapter files in `data/input/`:
```
data/input/古道仙鸿_001.md
data/input/古道仙鸿_002.md
...
```

### 3. Configure Settings

Edit `config/settings.yaml`:
```yaml
models:
  translator: "qwen2.5:14b"    # Your Ollama model
  ollama_base_url: "http://localhost:11434"

paths:
  input_dir: "data/input"
  output_dir: "data/output"
```

### 4. Run Translation

Translate a single chapter:
```bash
python -m src.main --novel 古道仙鸿 --chapter 1
```

Translate all chapters:
```bash
python -m src.main --novel 古道仙鸿 --all
```

Start from specific chapter:
```bash
python -m src.main --novel 古道仙鸿 --all --start 10
```

Skip refinement (faster):
```bash
python -m src.main --novel 古道仙鸿 --chapter 1 --skip-refinement
```

## Requirements

- Python 3.10+
- Ollama installed and running
- Compatible models (qwen2.5:14b recommended)

## Architecture

### Agents Pipeline

1. **Preprocessor**: Loads chapter, splits into chunks with overlap
2. **Translator**: Core translation using Ollama with glossary/context injection
3. **Refiner**: Optional polishing for better flow and literary quality
4. **Checker**: Validates glossary consistency and quality metrics
5. **Context Updater**: Extracts entities and updates memory

### Memory System

- **Tier 1 - Glossary**: Persistent term database
- **Tier 2 - Context**: FIFO sliding window of recent translations
- **Tier 3 - Session**: Temporary user corrections

## Output

Translated files saved to:
```
data/output/{novel_name}/{novel_name}_{chapter:03d}_mm.md
```

## Testing

Run tests:
```bash
python -m pytest tests/
```

Or individual test files:
```bash
python tests/test_translator.py
python tests/test_integration.py
```

## Logs

Translation logs are saved to `logs/translation.log`

## License

MIT License
