novel_translation_project/
├── config/
│   └── settings.yaml          # Model, Path, API Settings
├── data/
│   ├── input/
│   │   ├── novel_name_001.md
│   │   └── ...
│   ├── output/
│   │   └── ...
│   ├── glossary.json          # Terminology Database
│   └── context_memory.json    # Dynamic Chapter Context
├── logs/
│   └── translation.log
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