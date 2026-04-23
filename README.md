# Novel Translation Pipeline

Chinese Xianxia Novel to Myanmar Translation System.

This project is an advanced, AI-powered **Chinese-to-Myanmar (Burmese) novel translation system** specializing in Wuxia/Xianxia novels. It uses a multi-stage agent pipeline to translate web novels while preserving tone, style, literary depth, and strict terminology consistency.

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
├── logs/                      # Translation logs
├── src/
│   ├── agents/
│   │   ├── preprocessor.py    # Splits text, cleans markdown
│   │   ├── translator.py      # Stage 1: Core CN->MM Translation
│   │   ├── refiner.py         # Stage 2: Polishes Myanmar flow/tone
│   │   ├── checker.py         # Quality & Glossary validation
│   │   └── context_updater.py # Updates memory after chapter
│   ├── memory/
│   │   └── memory_manager.py  # Handles Glossary & Context loading/saving
│   ├── utils/
│   │   ├── ollama_client.py   # Wrapper for Ollama API
│   │   ├── file_handler.py    # Read/Write files
│   │   └── postprocessor.py   # Unicode and punctuation fixes
│   └── main.py                # Pipeline entry point
├── tests/                     # Unit and integration tests
├── CURRENT_STATE.md           # Progress and Known Issues
├── USER_GUIDE.md              # Detailed usage instructions
├── AGENTS.md                  # Agent architecture and protocols
├── requirements.txt
└── README.md
```

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Prepare Input Files

Place Chinese chapter files in `data/input/{novel_name}/`:
```
data/input/古道仙鸿/古道仙鸿_chapter_001.md
data/input/古道仙鸿/古道仙鸿_chapter_002.md
...
```

### 3. Configure Settings

Edit `config/settings.yaml` to specify your models and paths. Default is set to use local Ollama with `qwen2.5:14b`.

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

Translate a specific file directly:
```bash
python -m src.main --input data/input/古道仙鸿/古道仙鸿_chapter_001.md
```

Enable two-stage translation (literary refinement):
```bash
python -m src.main --novel 古道仙鸿 --chapter 1 --two-stage
```

## Features

- **Multi-Stage Pipeline**: Uses specialized agents for preprocessing, translation, refinement, and checking.
- **Glossary Enforcement**: Ensures consistent translation of character names, cultivation levels, and items.
- **Context Awareness**: Maintains a sliding window of recent chapter context to ensure continuity.
- **Graceful Shutdown**: Handles `Ctrl+C` by saving partial progress, allowing you to resume later.
- **Quality Assurance**: Automated checks for Myanmar Unicode validity and glossary consistency.
- **Sensitive Data Masking**: Automatically masks API keys in log files.

## Documentation

- [USER_GUIDE.md](./USER_GUIDE.md): Detailed usage instructions and configuration options.
- [AGENTS.md](./AGENTS.md): Technical details on the agent architecture and design patterns.
- [CURRENT_STATE.md](./CURRENT_STATE.md): Current project status, completed tasks, and roadmap.

## Testing

Run the full test suite:
```bash
python -m pytest tests/
```

Or run specific tests:
```bash
python tests/test_agents.py
python tests/test_memory.py
```

## License

MIT License
