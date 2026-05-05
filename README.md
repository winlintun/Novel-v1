# Novel Translation Pipeline

AI-powered Chinese/English-to-Myanmar (Burmese) novel translation pipeline using Ollama.

## Overview

This is a production-grade local novel translation system that translates Chinese and English novels into Myanmar (Burmese) language using local LLM inference via Ollama. The system specializes in Xianxia, Wuxia, and other East Asian fantasy genres with comprehensive quality gates, terminology management, and a Streamlit web UI.

## Features

- **Multi-language support**: Chinese→Myanmar and English→Myanmar translation
- **6-stage pipeline**: Preprocess → Translate → Refine → Reflect → Quality Check → QA Review
- **3-tier memory**: Glossary + Context + Session rules
- **Quality gates**: Myanmar ratio ≥70%, quality score ≥70
- **Per-novel glossary**: Isolated terminology per novel
- **Auto-promotion**: High-confidence terms auto-approved
- **Web UI**: Streamlit-based interface for translations

## Installation

```bash
# Clone and install dependencies
pip install -r requirements.txt

# Pull required Ollama models
ollama pull padauk-gemma:q8_0
ollama pull alibayram/hunyuan:7b  # For Chinese pivot (optional)
```

## Quick Start

### CLI Translation

```bash
# Single chapter
python -m src.main --novel reverend-insanity --chapter 1

# Multiple chapters
python -m src.main --novel reverend-insanity --all

# Chapter range
python -m src.main --novel reverend-insanity --chapter-range 1-10

# From specific chapter
python -m src.main --novel reverend-insanity --all --start 10

# Single file
python -m src.main --input data/input/ Novel/chapter_001.md
```

### Web UI

```bash
python -m src.main --ui
```

## File Structure

```
novel_translation_project/
├── src/
│   ├── main.py                 # Entry point, CLI dispatcher
│   ├── exceptions.py          # Custom exceptions
│   ├── cli/                  # CLI modules
│   │   ├── __init__.py
│   │   ├── parser.py         # Argument parsing
│   │   ├── commands.py     # Command handlers
│   │   └── formatters.py   # Output formatting
│   ├── agents/              # Translation agents
│   │   ├── __init__.py
│   │   ├── base_agent.py         # Base class for agents
│   │   ├── translator.py        # Core translator (stage 1)
│   │   ├── refiner.py           # Literary refiner (stage 2)
│   │   ├── reflection_agent.py  # Self-correction (stage 3)
│   │   ├── preprocessor.py   # Text preprocessing
│   │   ├── checker.py        # Glossary consistency
│   │   ├── myanmar_quality_checker.py  # Myanmar linguistic validation
│   │   ├── qa_tester.py   # QA validation (stage 6)
│   │   ├── context_updater.py  # Context extraction
│   │   ├── glossary_generator.py  # Term extraction
│   │   ├── glossary_sync.py   # Glossary management
│   │   ├── fast_translator.py  # Fast mode
│   │   ├── fast_refiner.py    # Fast refine
│   │   ├── pivot_translator.py  # Two-stage CN→EN→MM
│   │   ├── prompt_patch.py   # Prompt customization
│   │   └── prompts/          # Prompt rules
│   │       ├── __init__.py
│   │       ├── cn_mm_rules.py   # Chinese→Myanmar rules
│   │       └── en_mm_rules.py  # English→Myanmar rules
│   ├── pipeline/            # Pipeline orchestration
│   │   ├── __init__.py
│   │   └── orchestrator.py  # Main pipeline coordinator
│   ├── memory/              # Memory system
│   │   ├── __init__.py
│   │   └── memory_manager.py  # 3-tier memory
│   ├── config/              # Configuration
│   │   ├── __init__.py
│   │   ├── loader.py        # YAML config loading
│   │   └── models.py       # Pydantic models
│   ├── core/                # Core utilities
│   │   ├── __init__.py
│   │   └── container.py    # DI container
│   ├── types/               # Type definitions
│   │   ├── __init__.py
│   │   └── definitions.py # Type definitions
│   ├── utils/               # Utility modules
│   │   ├── __init__.py
│   │   ├── ollama_client.py       # Ollama API wrapper
│   │   ├── postprocessor.py      # Output cleaning
│   │   ├── postprocessor_patterns.py  # Regex patterns
│   │   ├── file_handler.py       # File I/O
│   │   ├── chunker.py          # Text chunking
│   │   ├── glossary_suggestor.py # Term suggestion
│   │   ├── glossary_matcher.py # Term matching
│   │   ├── translation_reviewer.py # Quality reports
│   │   ├── fluency_scorer.py    # Fluency scoring
│   │   ├── progress_logger.py  # Progress tracking
│   │   ├── performance_logger.py # Performance logging
│   │   ├── ram_monitor.py    # RAM monitoring
│   │   ├── cache_cleaner.py # Cache cleanup
│   │   ├── json_extractor.py # JSON extraction
│   │   └── progress_logger.py
│   └── web/                # Web UI
│       ├── __init__.py
│       └── launcher.py     # UI launcher
├── ui/                    # Streamlit UI
│   ├── pages/              # UI pages
│   │   └── ...
│   ├── utils/
│   └── streamlit_app.py    # Main UI
├── config/                # Configuration files
│   ├── settings.yaml      # Default config
│   ├── settings.pivot.yaml  # CN→EN→MM pivot
│   ├── settings.fast.yaml   # Fast mode
│   ├── settings.sailor2.yaml  # Sailor2 model
│   └── error_recovery.yaml # Error recovery
├── data/
│   ├── input/            # Source novels
│   │   └── {novel}/
│   │       └── *.md
│   └── output/           # Translated output
│       └── {novel}/
│           └── *.mm.md
├── tests/                # Test suite
│   └── test_*.py
├── logs/                 # Logs
│   ├── translation_*.log
│   └── report/          # Quality reports
├── .agent/              # Agent system
│   ├── phase_gate.json
│   ├── session_memory.json
│   ├── long_term_memory.json
│   └── error_library.json
└── README.md
```

## Command Reference

### Translation Commands

| Command | Description |
|---------|-------------|
| `--novel X --chapter N` | Translate single chapter |
| `--novel X --all` | Translate all chapters |
| `--novel X --chapter-range 1-10` | Translate range |
| `--novel X --start N` | Start from chapter N |
| `--input PATH` | Translate single file |
| `--mode full/lite/fast` | Pipeline mode |
| `--workflow way1/way2` | Translation workflow |

### Workflow Options

| Workflow | Description |
|----------|-------------|
| `way1` | English→Myanmar direct |
| `way2` | Chinese→English→Myanmar pivot |

### Utility Commands

| Command | Description |
|---------|-------------|
| `--ui` | Launch web UI |
| `--review FILE` | Quality review |
| `--view FILE` | View output |
| `--stats --novel X` | Score trends |
| `--generate-glossary` | Generate glossary |
| `--auto-promote` | Auto-promote terms |
| `--approve-glossary` | Bulk approve terms |
| `--clean` | ~~Clear cache~~ (use `./clean_run.sh`) |
| `--test` | Run test |
| `--rebuild-meta` | Rebuild metadata |

### Configuration Options

| Option | Description |
|--------|-------------|
| `--config FILE` | Config file path |
| `--model NAME` | Override model |
| `--output-dir DIR` | Output directory |

## Module Reference

### Entry Point

#### `src/main.py`

Main dispatcher that delegates to specialized modules.

```python
def main() -> int
```

**Functions:**

- `main()` - Main entry point

---

### CLI Modules

#### `src/cli/parser.py`

Argument parser with support for translation, configuration, workflow selection.

```python
def create_parser() -> argparse.ArgumentParser
def parse_arguments(args: Optional[List[str]] = None) -> argparse.Namespace
def validate_arguments(args: argparse.Namespace) -> None
def get_chapter_list(args: argparse.Namespace) -> List[int]
```

#### `src/cli/commands.py`

Command handlers for translation pipeline.

```python
def run_translation_pipeline(args: argparse.Namespace) -> int
def run_glossary_generation(args: argparse.Namespace) -> int
def run_glossary_promotion(args: argparse.Namespace) -> int
def run_glossary_approval(args: argparse.Namespace) -> int
def run_ui_launch(args: argparse.Namespace) -> int
def run_test(args: argparse.Namespace) -> int
def run_view_file(args: argparse.Namespace) -> int
def run_review(args: argparse.Namespace) -> int
def run_stats(args: argparse.Namespace) -> int
def run_rebuild_meta(args: argparse.Namespace) -> int
def _discover_chapters(novel_dir: Path) -> List[int]
def setup_logging(log_file: Optional[str] = None) -> logging.Logger
def _resolve_workflow(args) -> Optional[str]
def _apply_workflow_config(config, workflow, logger) -> AppConfig
```

#### `src/cli/formatters.py`

Output formatters for CLI display.

---

### Pipeline

#### `src/pipeline/orchestrator.py`

Main pipeline coordinator.

```python
class TranslationPipeline:
    def __init__(self, config: AppConfig)
    def set_progress_callback(self, callback: Optional[Callable])
    def translate_file(self, filepath: str, novel_name: Optional[str] = None) -> Dict
    def translate_chapter(self, novel: str, chapter: int) -> Dict
    def translate_novel(self, novel: str, chapters: Optional[List[int]] = None) -> List[Dict]
    def cleanup(self) -> None
```

**Properties:**

- `memory_manager` - Lazy-loaded MemoryManager
- `ollama_client` - Lazy-loaded OllamaClient
- `preprocessor` - Lazy-loaded Preprocessor
- `translator` - Lazy-loaded Translator
- `refiner` - Lazy-loaded Refiner
- `reflection_agent` - Lazy-loaded ReflectionAgent
- `myanmar_checker` - Lazy-loaded MyanmarQualityChecker
- `checker` - Lazy-loaded Checker
- `qa_tester` - Lazy-loaded QATesterAgent
- `context_updater` - Lazy-loaded ContextUpdater

**Private Methods:**

- `_preprocess(text, chapter_label)` - Preprocess text into chunks
- `_translate_chunks(chunks)` - Translate with rolling context
- `_postprocess(chunks)` - Postprocess translated chunks
- `_save_output(input_path, text, extra_meta)` - Save output
- `_auto_review(output_path, translated_text)` - Run auto review
- `_cleanup_resources()` - Free RAM
- `_calc_myanmar_ratio(text)` - Calculate Myanmar char ratio
- `_deduplicate_chunks(chunks)` - Remove duplicate paragraphs

---

### Agents

#### `src/agents/base_agent.py`

Base class for all agents.

```python
class BaseAgent:
    def __init__(self, ollama_client, memory_manager, config)
    def log_info(self, message: str) -> None
    def log_warning(self, message: str) -> None
    def log_error(self, message: str, exception: Optional[Exception] = None) -> None
    def handle_error(self, error: Exception, context: str = "") -> None
    def validate_config(self, required_keys: list) -> bool
    def get_config(self, key: str, default: Any = None) -> Any
```

#### `src/agents/translator.py`

Core translator agent for Chinese/English to Myanmar.

```python
def get_language_prompt(source_lang: str, model_name: str = "") -> str

class Translator(BaseAgent):
    def __init__(self, ollama_client, memory_manager, config)
    def get_system_prompt(self, source_lang: str = "english") -> str
    def build_prompt(self, text: str, rolling_context: str = "") -> str
    def translate_paragraph(self, paragraph: str, chapter_num: int = 0, rolling_context: str = "") -> str
    def translate_with_fallback(self, text: str, source_lang: str = "english", chapter_num: int = 0) -> str
    def translate_chunks(self, chunks: List[Dict], chapter_num: int = 0, progress_logger = None) -> List[str]
    def translate_chapter(self, chunks: List[Dict[str, Any]], chapter_num: int = 0) -> str
```

#### `src/agents/refiner.py`

Literary refinement agent.

```python
class Refiner(BaseAgent):
    def __init__(self, ollama_client, batch_size, config, memory_manager)
    def refine_paragraph(self, text: str) -> str
    def refine_chunks(self, chunks: List[str]) -> List[str]
    def refine_chapter(self, text: str) -> str
```

#### `src/agents/reflection_agent.py`

Self-correction reflection agent.

```python
class ReflectionAgent(BaseAgent):
    def __init__(self, ollama_client, config, memory_manager)
    def reflect_and_improve(self, text: str, source_text: str = "") -> str
```

#### `src/agents/preprocessor.py`

Text preprocessing.

```python
class Preprocessor:
    def __init__(self, chunk_size: int = 1500)
    def strip_metadata(self, text: str) -> str
    def clean_markdown(self, text: str) -> str
    def create_chunks(self, text: str) -> List[Dict[str, Any]]
    def detect_language(self, text: str) -> str
```

#### `src/agents/checker.py`

Glossary consistency checker.

```python
class Checker(BaseAgent):
    def __init__(self, memory_manager, config)
    def check_glossary_consistency(self, text: str) -> List[str]
    def check_mixed_scripts(self, text: str) -> List[str]
```

#### `src/agents/myanmar_quality_checker.py`

Myanmar linguistic quality validation.

```python
class MyanmarQualityChecker(BaseAgent):
    def __init__(self, ollama_client, memory_manager, config)
    def check_quality(self, text: str) -> Dict[str, Any]
```

#### `src/agents/qa_tester.py`

QA validation agent.

```python
class QATesterAgent(BaseAgent):
    def __init__(self, memory_manager, config)
    def validate_output(self, text: str, chapter_num: int = 0) -> Dict[str, Any]
```

#### `src/agents/context_updater.py`

Context extraction and update.

```python
class ContextUpdater(BaseAgent):
    def __init__(self, ollama_client, memory_manager, config)
    def process_chapter(self, original_text: str, translated_text: str, chapter_num: int = 0) -> Dict
```

#### `src/agents/glossary_generator.py`

Glossary term extraction.

```python
class GlossaryGenerator:
    def __init__(self, client, memory, config)
    def generate_from_chapter(self, chapter_file: str, chapter_num: int = 0) -> int
    def generate_from_text(self, text: str, chapter_num: int = 0) -> List[Dict]
```

#### `src/agents/glossary_sync.py`

Glossary synchronization.

```python
class GlossarySync:
    def __init__(self, memory_manager)
    def sync_to_novel(self, novel_name: str) -> bool
    def sync_from_novel(self, novel_name: str) -> bool
```

#### `src/agents/fast_translator.py`

Fast single-stage translator.

```python
class FastTranslator(BaseAgent):
    def __init__(self, ollama_client, memory_manager, config)
    def translate(self, text: str) -> str
```

#### `src/agents/fast_refiner.py`

Fast literary refiner.

```python
class FastRefiner(BaseAgent):
    def __init__(self, ollama_client, config)
    def refine(self, text: str) -> str
```

#### `src/agents/pivot_translator.py`

Two-stage Chinese→English→Myanmar translator.

```python
class PivotTranslator(BaseAgent):
    def __init__(self, ollama_client, memory_manager, config)
    def translate(self, text: str, source_lang: str = "chinese") -> str
```

---

### Memory

#### `src/memory/memory_manager.py`

3-tier memory system.

```python
class MemoryManager:
    def __init__(self, glossary_path, context_path, novel_name, use_universal)
    
    # Tier 1: Glossary
    def add_term(self, source: str, target: str, category: str, chapter: int) -> bool
    def update_term(self, source: str, new_target: str, chapter: int) -> bool
    def get_term(self, source: str) -> Optional[str]
    def get_glossary_for_prompt(self, limit: int = 20) -> str
    def get_all_terms(self) -> List[Dict]
    
    # Tier 2: Context
    def update_chapter_context(self, chapter_num: int, translated_text: str, summary: str)
    def push_to_buffer(self, translated_text: str)
    def get_context_buffer(self, count: int = 3) -> str
    def clear_buffer(self) -> None
    def get_summary(self) -> str
    
    # Tier 3: Session
    def add_session_rule(self, incorrect: str, correct: str)
    def get_session_rules(self) -> str
    def promote_rule_to_glossary(self, incorrect: str, correct: str, chapter: int)
    
    # Pending Terms
    def add_pending_term(self, source: str, target: str, category: str, chapter: int) -> bool
    def get_pending_terms(self) -> List[Dict]
    def promote_pending_to_glossary(self, source: str, chapter: int, verified: bool) -> bool
    def reject_pending_term(self, source: str) -> bool
    def bulk_approve_all_pending(self) -> int
    def auto_approve_pending_terms(self) -> int
    def auto_approve_by_confidence(self, confidence_threshold: float) -> int
    
    # Memory I/O
    def save_memory(self) -> None
    def get_all_memory_for_prompt(self) -> Dict[str, str]
    
    # Validation
    @staticmethod
    def _is_valid_myanmar_text(text: str, min_ratio: float) -> bool
    @staticmethod
    def _edit_distance(s1: str, s2: str) -> int
```

---

### Configuration

#### `src/config/loader.py`

YAML configuration loader.

```python
def load_config(config_path: Optional[Union[str, Path]] = None) -> AppConfig
def load_config_from_dict(config_dict: Dict[str, Any]) -> AppConfig
def get_default_config() -> AppConfig
def save_config(config: AppConfig, output_path: Union[str, Path]) -> None
def merge_configs(base_config: AppConfig, override_dict: Dict[str, Any]) -> AppConfig
```

#### `src/config/models.py`

Pydantic configuration models.

```python
class AppConfig(BaseModel):
    project: ProjectConfig
    models: ModelsConfig
    processing: ProcessingConfig
    translation_pipeline: PipelineConfig
    paths: PathsConfig
    output: OutputConfig
```

---

### Utilities

#### `src/utils/ollama_client.py`

Ollama API wrapper.

```python
class OllamaClient:
    def __init__(self, model, base_url, temperature, top_p, top_k, repeat_penalty,
                 max_retries, timeout, unload_on_cleanup, use_generate_endpoint, num_ctx,
                 keep_alive, use_gpu, gpu_layers, main_gpu):
    
    def chat(self, prompt: str, system_prompt: str = "") -> str
    def generate(self, prompt: str, system_prompt: str = "") -> str
    def stream(self, prompt: str, system_prompt: str = "") -> Iterator[str]
    def unload_model(self) -> None
    def unload_all_models(self) -> None
    def cleanup(self) -> None
    def get_model_info(self) -> Dict
```

#### `src/utils/postprocessor.py`

Output cleaning and validation.

```python
def strip_reasoning_tags(text: str) -> str
def strip_header_artifacts(text: str) -> str
def strip_reasoning_process(text: str) -> str
def remove_indic_characters(text: str) -> str
def remove_korean(text: str) -> str
def remove_chinese(text: str) -> str
def remove_non_myanmar_scripts(text: str) -> str
def fix_chapter_heading_format(text: str) -> str
def remove_duplicate_headings(text: str) -> str
def replace_archaic_words(text: str) -> str
def fix_degraded_placeholders(text: str) -> str
def stitch_chunk_boundaries(text: str) -> str
def validate_output(text: str, chapter_num: int) -> Dict
def detect_language_leakage(text: str) -> Dict

class Postprocessor:
    def __init__(self, aggressive: bool = False)
    def clean(self, text: str) -> str
```

#### `src/utils/file_handler.py`

File I/O operations.

```python
class FileHandler:
    @staticmethod
    def read_text(path: str, encoding: str = "utf-8-sig") -> str
    @staticmethod
    def write_text(path: str, content: str, encoding: str = "utf-8") -> None
    @staticmethod
    def read_json(path: str) -> Dict
    @staticmethod
    def write_json(path: str, data: Dict) -> None
    @staticmethod
    def ensure_dir(path: str) -> None
    @staticmethod
    def list_files(directory: str, pattern: str = "*.md") -> List[str]
```

#### `src/utils/chunker.py`

Text chunking utilities.

```python
def smart_chunk(text: str, max_tokens: int = 1500) -> List[str]
def estimate_tokens(text: str) -> int
def get_rolling_context(text: str, max_context_tokens: int = 400) -> str
def split_into_sentences(text: str) -> List[str]
```

#### `src/utils/translation_reviewer.py`

Quality review and reporting.

```python
def review_and_report(output_path: str, log_file: Optional[str] = None) -> Tuple[ReviewReport, str]
```

---

## Configuration Files

### `config/settings.yaml`

Default configuration for English→Myanmar translation.

### `config/settings.pivot.yaml`

Configuration for Chinese→English→Myanmar pivot workflow.

### `config/settings.fast.yaml`

Fast mode configuration (CPU-only).

### `config/settings.sailor2.yaml`

Sailor2 model configuration.

### `config/error_recovery.yaml`

Error recovery settings (reference only).

## Output Files

### Translated Chapters

```
data/output/{novel}/{novel}_chapter_{XXX}.mm.md
data/output/{novel}/{novel}.mm.meta.json       # Cumulative metadata
```

### Quality Reports

```
logs/report/{novel}_chapter_{XXX}_review_{timestamp}.md
```

### Glossary

```
data/output/{novel}/glossary/glossary.json         # Approved terms
data/output/{novel}/glossary/glossary_pending.json  # Pending review
data/output/{novel}/glossary/context_memory.json  # Context buffer
```

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_translator.py -v

# Run with coverage
pytest tests/ --cov=src
```

## Linting

```bash
# Lint source code
ruff check src/ tests/ --select=E,F
```

## License

MIT License