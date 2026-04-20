# Gemini CLI Context: Chinese-to-Burmese Novel Translation System

## Project Overview
This project is a fully self-contained, AI-powered novel translation pipeline written in Python. It automatically translates Chinese web novels and literary works into Burmese (Myanmar script) while preserving the original tone, style, and emotional depth. It relies on local LLMs via **Ollama** (e.g., `qwen3:7b`), eliminating the need for external cloud APIs or translation frameworks.

The pipeline automates the entire process:
1. Scanning `input_novels/` for text files.
2. Preprocessing and cleaning text.
3. Chunking text with overlaps.
4. Translating via Ollama with live token streaming and automatic checkpoints.
5. Running Myanmar script readability and quality checks.
6. Postprocessing for punctuation and character name consistency (using `names.json`).
7. Assembling the translated chunks into a polished Markdown document in `translated_novels/`.

## Technologies and Dependencies
- **Language**: Python 3.8+
- **Core Dependencies**: `ollama`, `tqdm`, `regex`, `pyicu` (plus others in `requirements.txt`).
- **AI Backend**: Ollama (runs locally, e.g., `qwen3:7b`, `qwen3:14b`).
- **Build/Task Runner**: `Makefile`.

## Building and Running

### Prerequisites
1. Ensure Ollama is installed and running (`ollama serve`).
2. Pull the desired model (e.g., `ollama pull qwen3:7b`).
3. Create a virtual environment and install dependencies:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: .\venv\Scripts\activate
   make install              # Or: pip install -r requirements.txt
   ```

### Execution Commands
- **Run Pipeline**: `python main.py` or `make run`. This will automatically process novels placed in the `input_novels/` directory.
- **Resume Pipeline**: `make resume` or `python main.py --resume`. The system uses checkpoints stored in `working_data/checkpoints/` to safely resume cancelled or interrupted translations.
- **Clean Temporary Data**: `make clean`. This removes checkpoints and logs.

## Development Conventions
- **Code Style**: Enforced via `flake8` and `pylint`. You can run the linters using `make lint`.
- **Testing**: Tests are written using `pytest` and can be executed via `make test`.
- **AI Agent Context**: The project incorporates specific context files for AI agents:
  - `AGENT.md`: Defines the translator agent role.
  - `SKILL.md`: Defines the core translation prompt and skill instructions.
  - `REVIEWER_AGENT.md`: Code review agent guidelines.
- **Graceful Shutdown**: The script handles `Ctrl+C` gracefully by finishing the current streaming token, saving a checkpoint, and cleanly exiting.

## Important Directories
- `input_novels/`: Place raw Chinese `.txt` or `.md` files here.
- `translated_novels/`: Final assembled Burmese `.md` files are output here.
- `working_data/`: Contains intermediate data like `chunks/`, `translated_chunks/`, `checkpoints/`, `readability_reports/`, `preview/`, and `logs/`.
- `config/`: Contains `settings.py` and `config.json` for managing model parameters and pipeline configurations.
- `scripts/`: Holds the individual modular steps of the translation pipeline (e.g., `chunker.py`, `translator.py`, `myanmar_checker.py`, `assembler.py`).
