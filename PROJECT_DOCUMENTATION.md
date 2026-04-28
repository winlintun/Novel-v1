# Novel Translation Project - Complete Technical Documentation

## Project Overview

An AI-powered Chinese-to-Myanmar (Burmese) novel translation system specializing in Wuxia/Xianxia novels. The system uses a multi-stage agent pipeline with Ollama LLMs to translate web novels while preserving tone, style, literary depth, and strict terminology consistency.

---

## System Architecture

### Pipeline Flow

```
src/main.py (thin dispatcher)
  → src/cli/parser.py (parse arguments)
  → src/cli/commands.py (route to command)
  → src/pipeline/orchestrator.py (TranslationPipeline)
    → Load config/settings.yaml (via src/config/loader.py)
    → Initialize MemoryManager (load glossary.json, context_memory.json)
    → Preprocessor.load_and_preprocess()  → Chunks
    → Translator.translate_chunks()        → Stage 1: Raw translation
    → Refiner.refine_full_text()           → Stage 2: Literary editing
    → ReflectionAgent.reflect_and_improve() → Stage 3: Self-correction
    → MyanmarQualityChecker.check_quality() → Stage 4: Linguistic validation
    → Checker.check_chapter()             → Stage 5: Consistency check
    → QA Review                           → Stage 6: Final QA
    → TermExtractor (post-chapter)        → Extract new terms → glossary_pending.json
    → FileHandler.write_text()            → Save to data/output/
    → ContextUpdater.process_chapter()    → Update glossary.json, context_memory.json
```

### Dual Entry Points

1. **Standard Mode** (`src/main.py`): Full 6-stage pipeline with quality checks
2. **Fast Mode** (`src/main_fast.py`): Optimized single-stage translation for speed

---

## Directory Structure

```
novel_translation_project/
├── config/                         # Configuration files
│   ├── settings.yaml              # Main configuration
│   ├── settings.fast.yaml         # Fast mode config
│   ├── settings.pivot.yaml        # CN→EN→MM workflow config
│   ├── settings.english.yaml      # EN→MM workflow config
│   └── error_recovery.yaml        # Error recovery settings
│
├── data/                          # Data storage
│   ├── input/                     # Source chapter files (*.md)
│   │   └── {novel_name}/
│   │       └── {novel_name}_chapter_XXX.md
│   ├── output/                    # Translated output (*.mm.md)
│   ├── glossary.json              # Approved terminology database
│   ├── glossary_pending.json      # New terms awaiting review
│   └── context_memory.json        # Dynamic chapter context
│
├── logs/                          # Log files
│   ├── translation.log           # Main translation log
│   └── progress/                 # Per-chapter progress logs
│
├── src/                          # Source code
│   ├── agents/                   # Translation agents
│   ├── cli/                      # Command-line interface
│   ├── config/                   # Configuration management
│   ├── core/                     # Core functionality
│   ├── memory/                   # Memory management
│   ├── pipeline/                 # Pipeline orchestration
│   ├── types/                    # Type definitions
│   ├── utils/                    # Utility functions
│   ├── web/                      # Web UI launcher
│   ├── exceptions.py             # Exception hierarchy
│   ├── main.py                   # Standard entry point
│   └── main_fast.py              # Fast mode entry point
│
├── tests/                        # Test suite
├── ui/                          # Streamlit web interface
├── scripts/                     # Utility scripts
├── templates/                   # Chapter/novel templates
└── tools/                       # Additional tools
```

---

## Core Modules

### 1. Entry Points

#### `src/main.py` - Standard Entry Point

**Purpose**: Thin dispatcher that delegates to specialized modules

**Key Functions**:
- `main()` - Main entry point that parses arguments and routes commands

**Command Flow**:
```python
1. Parse arguments via cli/parser.py
2. Handle utility commands (--ui, --test)
3. Validate arguments
4. Run glossary generation if --generate-glossary
5. Run translation pipeline via cli/commands.py
```

**Usage**:
```bash
python -m src.main --novel "古道仙鸿" --chapter 1
python -m src.main --novel "古道仙鸿" --all
python -m src.main --ui
python -m src.main --test
```

---

#### `src/main_fast.py` - Fast Mode Entry Point

**Purpose**: Optimized for speed with Ollama - single stage, batch processing, larger chunks

**Key Functions**:
- `main()` - Fast translation main function
- `setup_logging()` - Setup logging with simpler format
- `cleanup_resources()` - Cleanup active resources on shutdown
- `signal_handler()` - Handle interrupt signals gracefully
- `load_fast_config()` - Load fast configuration
- `extract_chapter_num()` - Extract chapter number from filename

**Optimizations**:
- Single-stage translation (no separate refinement)
- Larger chunks (3000 chars vs 1500)
- Batch refinement (5 paragraphs at once)
- Streaming responses
- 7B models (faster than 14B)
- Optional model unloading after each chapter

**Usage**:
```bash
python -m src.main_fast --novel "古道仙鸿" --chapter 1
python -m src.main_fast --novel "古道仙鸿" --all --unload-after-chapter
```

---

### 2. CLI Module (`src/cli/`)

#### `src/cli/parser.py` - Argument Parser

**Purpose**: Centralized argument parsing with support for all command types

**Key Functions**:
- `create_parser()` - Create and configure ArgumentParser
- `parse_arguments()` - Parse command line arguments
- `validate_arguments()` - Validate parsed arguments
- `get_chapter_list()` - Get list of chapters from arguments

**Arguments Supported**:
- Input Options: `--novel`, `--chapter`, `--input`, `--all`, `--start`, `--end`, `--chapter-range`
- Configuration: `--config`, `--model`, `--provider`
- Workflow: `--workflow`, `--lang`, `--two-stage`, `--skip-refinement`
- Pipeline: `--mode`, `--use-reflection`, `--no-quality-check`
- Output: `--output-dir`, `--no-metadata`
- Memory: `--unload-after-chapter`
- Utility: `--ui`, `--generate-glossary`, `--test`, `--clean`, `--version`

---

#### `src/cli/commands.py` - Command Handlers

**Purpose**: Implements command handlers for all CLI operations

**Key Functions**:
- `setup_logging()` - Configure logging with file and console handlers
- `run_translation_pipeline()` - Run the full translation pipeline
- `run_glossary_generation()` - Generate glossary from novel chapters
- `run_ui_launch()` - Launch the web UI
- `run_test()` - Run test translation with sample file
- `_resolve_workflow()` - Resolve workflow from arguments or auto-detect
- `_apply_workflow_config()` - Apply workflow-specific configuration

**Workflows**:
- `way1`: English → Myanmar direct (uses `padauk-gemma:q8_0`)
- `way2`: Chinese → English → Myanmar pivot (uses `alibayram/hunyuan:7b` for CN→EN, `padauk-gemma:q8_0` for EN→MM)

---

#### `src/cli/formatters.py` - Output Formatters

**Purpose**: Formatted output functions for CLI display

**Key Functions**:
- `print_box()` - Print formatted box with title and content
- `print_pipeline_status()` - Print pipeline step status with icons
- `print_translation_header()` - Print rich formatted translation header
- `print_pipeline_stages()` - Print pipeline stages based on configuration
- `print_progress_bar()` - Print progress bar
- `print_error()` / `print_warning()` / `print_success()` / `print_info()` - Print messages
- `print_section_header()` - Print section header
- `print_auto_detection_result()` - Print auto-detection results

---

### 3. Pipeline Orchestrator (`src/pipeline/`)

#### `src/pipeline/orchestrator.py` - Translation Pipeline

**Purpose**: Main translation pipeline orchestrator coordinating all agents

**Class**: `TranslationPipeline`

**Key Methods**:
- `__init__(config)` - Initialize pipeline with configuration
- `_signal_handler()` - Handle shutdown signals gracefully
- `translate_file(filepath)` - Translate a single file
- `translate_chapter(novel, chapter)` - Translate a single chapter
- `translate_novel(novel, chapters)` - Translate multiple chapters
- `_preprocess(text)` - Preprocess text into chunks
- `_translate_chunks(chunks)` - Translate chunks through all stages
- `_postprocess(chunks)` - Postprocess translated chunks
- `_save_output(input_path, text)` - Save translated output
- `_cleanup_resources()` - Cleanup resources and free RAM
- `cleanup()` - Public cleanup method

**Lazy-Loaded Properties**:
- `memory_manager` - 3-tier memory system
- `ollama_client` - Ollama API client
- `preprocessor` - Text preprocessing
- `translator` - Stage 1 translation
- `refiner` - Stage 2 refinement
- `reflection_agent` - Stage 3 self-correction
- `myanmar_checker` - Stage 4 quality check
- `checker` - Stage 5 consistency check
- `qa_tester` - Stage 6 QA review
- `context_updater` - Post-chapter context update

**Pipeline Stages**:
1. Preprocessing - Clean and chunk input text
2. Translation - Translate chunks
3. Refinement - Literary quality editing (optional)
4. Reflection - Self-correction (optional)
5. Quality Check - Myanmar linguistic validation
6. Consistency - Glossary verification
7. QA Review - Final validation

---

### 4. Configuration Module (`src/config/`)

#### `src/config/models.py` - Pydantic Models

**Purpose**: Validated configuration management with type checking

**Key Classes**:
- `ProcessingConfig` - Processing and chunking configuration
  - `chunk_size`, `chunk_overlap`, `temperature`, `top_p`, `top_k`, `repeat_penalty`, `max_retries`, `request_timeout`, `stream`

- `ModelsConfig` - Model configuration for pipeline stages
  - `translator`, `editor`, `checker`, `refiner`, `cloud_model`, `provider`, `ollama_base_url`, `timeout`, `use_gpu`, `gpu_layers`, `main_gpu`

- `ModelRolesConfig` - Model role assignments
  - Lists of suitable models for: `translator`, `refiner`, `checker`, `qa_final`, `glossary_sync`

- `ModelRouterConfig` - Automatic fallback configuration
  - `enabled`, `max_fallback_depth`, `retry_on_failure`, `vram_budget_gb`

- `TranslationPipelineConfig` - Pipeline mode configuration
  - `mode` (full/lite/fast/single_stage/two_stage), `use_reflection`, `stage1_model`, `stage2_model`, `reflection_model`

- `PathsConfig` - File path configuration
  - `input_dir`, `output_dir`, `books_dir`, `glossary_file`, `context_memory_file`, `log_file`, `templates_dir`

- `ProjectConfig` - Project metadata
  - `name`, `novel_genre`, `source_language`, `target_language`

- `OutputConfig` - Output formatting
  - `format`, `preserve_formatting`, `add_metadata`, `add_translator_notes`

- `QATestingConfig` - QA testing
  - `enabled`, `auto_retry`, `fail_on_placeholders`, `markdown_strict`, `min_myanmar_ratio`

- `MyanmarReadabilityConfig` - Myanmar readability
  - `enabled`, `min_myanmar_ratio`, `block_on_fail`, `flag_on_fail`

- `GlossaryV3Config` - Glossary v3 advanced
  - `enabled`, `path`, `lazy_load`, `cache_ttl_minutes`, `max_prompt_entries`, `alias_matching`, `exception_rules`, `include_examples`, `track_usage`, `priority_threshold`, `prompt_format`

- `FastConfig` - Fast mode configuration
  - `enabled`, `translator`, `editor`, `checker`, `refiner`, `chunk_size`, `temperature`, `repeat_penalty`, `num_ctx`

- `AppConfig` - Root configuration combining all sub-configs

---

#### `src/config/loader.py` - Configuration Loader

**Purpose**: Load and validate configuration from YAML files

**Key Functions**:
- `load_config(config_path)` - Load and validate configuration from YAML
- `load_config_from_dict(config_dict)` - Load from dictionary
- `_find_config_file()` - Find configuration using default search paths
- `get_default_config()` - Get default configuration
- `save_config(config, output_path)` - Save configuration to YAML
- `merge_configs(base_config, override_dict)` - Merge override values
- `_deep_merge(base, override)` - Deep merge dictionaries

**Search Paths**:
1. `config/settings.yaml`
2. `config/settings.yml`
3. `settings.yaml`
4. `settings.yml`
5. `$NOVEL_CONFIG_PATH` environment variable

---

### 5. Agents Module (`src/agents/`)

#### `src/agents/base_agent.py` - Base Agent Class

**Purpose**: Base class providing common functionality for all agents

**Class**: `BaseAgent`

**Key Methods**:
- `__init__(ollama_client, memory_manager, config)` - Initialize agent
- `_setup_logging()` - Setup agent-specific logging
- `log_info(message)` / `log_warning(message)` / `log_error(message, exception)` - Logging helpers
- `handle_error(error, context)` - Centralized error handling
- `validate_config(required_keys)` - Validate required config keys
- `get_config(key, default)` - Get config value with default

---

#### `src/agents/translator.py` - Translator Agent (Stage 1)

**Purpose**: Translates Chinese/English text to Myanmar using LLM

**Class**: `Translator(BaseAgent)`

**Key Functions**:
- `get_language_prompt(source_lang)` - Get system prompt based on source language

**Key Methods**:
- `__init__(ollama_client, memory_manager, config)` - Initialize translator
- `get_system_prompt(source_lang)` - Get system prompt for language
- `build_prompt(text)` - Build translation prompt with memory context
- `translate_paragraph(paragraph, chapter_num)` - Translate single paragraph with retry logic
- `translate_with_fallback(text, source_lang, chapter_num)` - Translate with fallback
- `get_fallback_prompt(source_lang)` - Get fallback prompt
- `translate_chunks(chunks, chapter_num, progress_logger)` - Translate multiple chunks
- `translate_chapter(chunks, chapter_num)` - Translate pre-processed chunks

**Features**:
- Language-specific prompts (Chinese vs English)
- Glossary and context injection
- Language leakage detection and retry
- Empty response handling
- Quality validation

---

#### `src/agents/refiner.py` - Refiner Agent (Stage 2)

**Purpose**: Polishes Myanmar translation for better flow and literary quality

**Class**: `Refiner(BaseAgent)`

**Key Methods**:
- `__init__(ollama_client, batch_size, config)` - Initialize refiner
- `refine_paragraph(text)` - Refine single paragraph (legacy)
- `refine_batch(paragraphs)` - Refine multiple paragraphs in single API call
- `refine_chapter(paragraphs)` - Refine using batch processing
- `refine_full_text(text)` - Refine entire chapter

**Batch Processing**:
- Processes 5 paragraphs at once (configurable)
- Uses `---PARA---` separator
- Fallback to individual processing on failure

---

#### `src/agents/preprocessor.py` - Preprocessor Agent

**Purpose**: Preprocesses novel chapters for translation

**Class**: `Preprocessor(BaseAgent)`

**Key Methods**:
- `__init__(chunk_size, overlap_size, ollama_client, memory_manager, config)` - Initialize preprocessor
- `detect_language(text)` - Detect language (chinese, english, unknown)
- `_llm_detect_language(client, text)` - LLM-based language detection
- `estimate_tokens(text)` - Estimate token count for Chinese text
- `split_into_paragraphs(text)` - Split text into paragraphs
- `create_chunks(text)` - Create chunks with sliding window overlap
- `clean_markdown(text)` - Clean and normalize markdown formatting
- `load_and_preprocess(filepath)` - Load and preprocess chapter file
- `get_chapter_info(filepath)` - Extract chapter information from filename

**Chunk Format**:
```python
{
    'chunk_id': int,
    'text': str,
    'size': int  # estimated tokens
}
```

---

#### `src/agents/checker.py` - Consistency Checker (Stage 5)

**Purpose**: Validates translation quality and glossary consistency

**Class**: `Checker(BaseAgent)`

**Key Methods**:
- `__init__(memory_manager, config)` - Initialize checker
- `check_glossary_consistency(text)` - Check if glossary terms are used consistently
- `check_markdown_formatting(original, translated)` - Check markdown preservation
- `check_myanmar_unicode(text)` - Check for Unicode issues
- `calculate_quality_score(text)` - Calculate quality score (0-100)
- `check_chapter(original, translated)` - Run all checks on a chapter
- `generate_report(chapter_num, result)` - Generate human-readable report

**Quality Metrics**:
- Myanmar character ratio
- Sentence count
- Formatting preservation
- Error markers detection

---

#### `src/agents/reflection_agent.py` - Reflection Agent (Stage 3)

**Purpose**: Self-correction specialist that analyzes and improves translations

**Class**: `ReflectionAgent(BaseAgent)`

**Key Methods**:
- `__init__(ollama_client, config)` - Initialize reflection agent
- `analyze(text, source_text)` - Analyze translation for issues
- `_parse_response(response, original)` - Parse LLM response for improvements
- `reflect_and_improve(text, source_text, max_iterations)` - Iteratively improve translation
- `check_consistency(text, glossary_terms)` - Check consistency with glossary
- `compare_with_source(source, translation)` - Compare for completeness

**Output Format**:
```
IMPROVEMENTS: [List of issues]
SUGGESTIONS: [How to fix]
FINAL_TEXT: [Improved version]
```

---

#### `src/agents/qa_tester.py` - QA Tester Agent (Stage 6)

**Purpose**: Automated quality assurance for translated chapters

**Class**: `QATesterAgent(BaseAgent)`

**Key Methods**:
- `__init__(memory_manager, config)` - Initialize QA tester
- `validate_output(text, chapter_num)` - Run all QA checks
- `_check_markdown(text)` - Validate markdown structure
- `_check_glossary_consistency(text)` - Check glossary consistency
- `_calculate_myanmar_ratio(text)` - Calculate Myanmar character ratio
- `_find_placeholders(text)` - Find unresolved placeholders
- `_validate_chapter_title(text, expected_chapter)` - Validate chapter title

**Checks**:
- Markdown structure (H1 count, balanced formatting)
- Glossary consistency for verified terms
- Myanmar Unicode ratio (>70%)
- Placeholder detection (`【?term?】`)
- Chapter title format validation

---

#### `src/agents/myanmar_quality_checker.py` - Myanmar Quality Checker (Stage 4)

**Purpose**: Custom checker for Myanmar-specific quality issues

**Class**: `MyanmarQualityChecker(BaseAgent)`

**Key Methods**:
- `__init__(ollama_client, memory_manager, config)` - Initialize checker
- `check_quality(text)` - Comprehensive quality check
- `_check_archaic_words(text)` - Check for archaic words
- `_check_repetition(text)` - Check for excessive repetition
- `_check_sentence_flow(text)` - Check sentence flow issues
- `_check_particles(text)` - Check particle usage
- `_check_unnatural_phrasing(text)` - Check unnatural patterns
- `_check_tone(text)` - Check tone consistency
- `_calculate_naturalness(text)` - Calculate naturalness score
- `check_dialogue_tone(text, character_hierarchy)` - Check dialogue appropriateness
- `suggest_improvements(text)` - Generate improvement suggestions

**Checks**:
- Archaic words (သင်သည်, ဤ, ထို)
- Modern alternatives (မင်း, ဒီ, အဲဒါ)
- Particle repetition (hallucination detection)
- Sentence length
- Tone consistency (Formal/Informal)
- Mixed language (English leakage)

---

#### `src/agents/context_updater.py` - Context Updater Agent

**Purpose**: Updates memory after chapter translation

**Class**: `ContextUpdater(BaseAgent)`

**Key Methods**:
- `__init__(ollama_client, memory_manager, config)` - Initialize updater
- `extract_entities(text)` - Extract entities using LLM
- `update_glossary(entities, chapter_num)` - Add entities to glossary
- `update_chapter_context(chapter_num, translated_text)` - Update context memory
- `process_chapter(original_text, translated_text, chapter_num)` - Full post-processing

**Entity Categories**:
- `characters` - Character names
- `cultivation_realms` - Cultivation levels
- `sects_organizations` - Sects and places
- `items_artifacts` - Items and artifacts

---

#### `src/agents/glossary_generator.py` - Glossary Generator Agent

**Purpose**: Auto-extract key terminology from novel's first chapters

**Key Methods**:
- Generate glossary entries from chapter files
- Propose transliterations for Chinese names
- Save to `glossary_pending.json`

---

#### `src/agents/fast_translator.py` - Fast Translator Agent

**Purpose**: Optimized translator for fast mode

**Features**:
- Single-stage translation
- Larger chunks (3000 chars)
- Streaming support
- Minimal context overhead

---

#### `src/agents/fast_refiner.py` - Fast Refiner Agent

**Purpose**: Optimized refiner for fast mode

**Features**:
- Batch refinement (5 paragraphs at once)
- Minimal API calls
- Quick quality pass

---

### 6. Memory Module (`src/memory/`)

#### `src/memory/memory_manager.py` - Memory Manager

**Purpose**: 3-Tier Memory Management System

**Class**: `MemoryManager`

**Tiers**:
1. **Tier 1 - Global Glossary** (`data/glossary.json`): Persistent across all chapters
2. **Tier 2 - Chapter Context** (`data/context_memory.json`): FIFO sliding window per chapter
3. **Tier 3 - Session Rules** (Runtime only): Dynamic corrections for current session

**Key Methods**:
- `__init__(glossary_path, context_path)` - Initialize memory manager
- `_load_memory()` - Load all memory files
- `save_memory()` - Save all memory to disk

**Glossary Operations**:
- `add_term(source, target, category, chapter)` - Add new term
- `update_term(source, new_target, chapter)` - Update existing term
- `get_term(source)` - Get target translation
- `get_glossary_for_prompt(limit)` - Get formatted glossary for prompts
- `get_all_terms()` - Get all glossary terms
- `_sanitize_for_prompt(text)` - Sanitize for LLM prompts

**Context Memory Operations**:
- `update_chapter_context(chapter_num, summary)` - Update after chapter
- `push_to_buffer(translated_text)` - Add to FIFO buffer
- `get_context_buffer(count)` - Get recent translations
- `clear_buffer()` - Clear paragraph buffer
- `get_summary()` - Get chapter summary

**Session Rules**:
- `add_session_rule(incorrect, correct)` - Add temporary rule
- `get_session_rules()` - Get formatted rules
- `promote_rule_to_glossary(incorrect, correct, chapter)` - Promote to permanent

**Pending Terms**:
- `add_pending_term(source, target, category, chapter)` - Add to pending glossary

**Prompt Integration**:
- `get_all_memory_for_prompt()` - Get all tiers formatted for prompts

**Glossary Schema**:
```json
{
  "version": "1.0",
  "total_terms": 0,
  "terms": [
    {
      "id": "term_001",
      "source": "罗青",
      "target": "လူချင်း",
      "category": "character",
      "chapter_first_seen": 1,
      "verified": true
    }
  ]
}
```

---

#### `src/memory/rag_memory.py` - RAG Memory

**Purpose**: Retrieval-Augmented Generation memory for context

**Features**:
- Semantic search for relevant context
- Character relationship tracking
- Event history

---

### 7. Utilities Module (`src/utils/`)

#### `src/utils/ollama_client.py` - Ollama Client

**Purpose**: Wrapper for Ollama API with retry logic and resource cleanup

**Class**: `OllamaClient`

**Key Methods**:
- `__init__(model, base_url, temperature, top_p, top_k, repeat_penalty, max_retries, timeout, unload_on_cleanup, use_generate_endpoint, num_ctx, keep_alive, use_gpu, gpu_layers, main_gpu)` - Initialize client
- `__enter__()` / `__exit__()` - Context manager support
- `cleanup()` - Cleanup resources and optionally unload model
- `_unload_model(model_name)` - Explicitly unload a model
- `unload_all_models()` - Force unload all models
- `chat(prompt, system_prompt, stream)` - Send chat request with retry
- `chat_stream(prompt, system_prompt)` - Stream chat response
- `check_model_available()` - Check if model is available
- `unload_model()` - Explicitly unload model from GPU

**Endpoints**:
- `/api/chat` (default) - Conversation-style API
- `/api/generate` (optional) - Single-turn generation

**Features**:
- Exponential backoff with jitter
- Rate limit handling (429 errors)
- GPU configuration support
- Automatic model unloading
- Bug fix for `padauk-gemma` thinking field

---

#### `src/utils/file_handler.py` - File Handler

**Purpose**: Handles all file I/O with proper encoding

**Class**: `FileHandler`

**Static Methods**:
- `read_text(filepath)` - Read text with UTF-8-SIG encoding
- `write_text(filepath, content)` - Write text with UTF-8-SIG encoding
- `read_json(filepath)` - Read JSON with BOM handling
- `write_json(filepath, data)` - Write JSON atomically
- `read_yaml(filepath)` - Read YAML configuration
- `list_chapters(input_dir, novel_name)` - List chapter files for a novel
- `ensure_dir(directory)` - Ensure directory exists

**Features**:
- UTF-8-SIG encoding for BOM handling
- Atomic JSON writes (temp file → rename)
- Multiple file naming pattern support
- Numeric sorting by chapter number

**File Patterns**:
1. `{novel_name}_chapter_XXX.md` (new format)
2. `{novel_name}_XXX.md` (legacy format)
3. `{novel_dir}/{novel_name}_chapter_XXX.md` (subdirectory)

---

#### `src/utils/postprocessor.py` - Postprocessor

**Purpose**: Cleans raw LLM output before saving

**Key Functions**:
- `strip_reasoning_tags(text)` - Remove `<think>`, `<answer>` tags
- `strip_header_artifacts(text)` - Remove stray metadata lines
- `strip_reasoning_process(text)` - Remove thinking process sections
- `detect_language_leakage(text)` - Count non-Myanmar characters
- `myanmar_char_ratio(text)` - Calculate Myanmar character ratio
- `remove_chinese_characters(text)` - Remove Chinese characters
- `remove_latin_words(text)` - Remove Latin/English words
- `clean_output(raw, aggressive)` - Full postprocessing pipeline
- `validate_output(text, chapter)` - Run quality checks
- `is_valid_myanmar_syllable(text)` - Check syllable structure
- `detect_repetition(text, threshold)` - Detect repetitive patterns
- `check_repetition(text, threshold)` - Check excessive repetition

**Class**: `Postprocessor`
- `__init__(aggressive)` - Initialize with mode
- `clean(text)` - Clean raw LLM output

**Tag Patterns Removed**:
- `<think>...</think>`
- `<answer>` / `</answer>`
- HTML comments
- Header artifacts ("MYANMAR TRANSLATION:", etc.)
- Reasoning process sections

**Quality Checks**:
- Thai character detection
- Chinese character detection
- English word counting
- Myanmar ratio calculation

---

#### `src/utils/json_extractor.py` - JSON Extractor

**Purpose**: Safely extract JSON from LLM responses

**Key Functions**:
- `safe_parse_terms(raw_response)` - Parse JSON with error handling
- Handle malformed JSON gracefully
- Extract from markdown code blocks
- Return empty list on failure

---

#### `src/utils/progress_logger.py` - Progress Logger

**Purpose**: Real-time progress tracking and logging

**Features**:
- Log chunk translations
- Track processing stages
- Generate progress reports

---

#### `src/utils/glossary_matcher.py` - Glossary Matcher

**Purpose**: Match and replace terms in text

**Features**:
- Exact match replacement
- Alias matching
- Case-insensitive matching

---

#### `src/utils/glossary_suggestor.py` - Glossary Suggestor

**Purpose**: Suggest new glossary terms from text

**Features**:
- Pattern-based detection
- LLM-based extraction
- Confidence scoring

---

#### `src/utils/model_router.py` - Model Router

**Purpose**: Automatic model fallback and selection

**Features**:
- VRAM budget checking
- Model availability detection
- Automatic fallback chain

---

#### `src/utils/ram_monitor.py` - RAM Monitor

**Purpose**: Monitor system RAM usage

**Features**:
- Memory usage tracking
- Alert on high usage
- Optimization suggestions

---

#### `src/utils/cache_cleaner.py` - Cache Cleaner

**Purpose**: Clean Python cache files

**Features**:
- Remove `__pycache__` directories
- Remove `.pyc` files
- Report cleaning results

---

#### `src/utils/glossary_v3_loader.py` - Glossary V3 Loader

**Purpose**: Load advanced glossary v3 format

**Features**:
- Lazy loading
- Cache management
- Priority-based selection

---

#### `src/utils/glossary_v3_manager.py` - Glossary V3 Manager

**Purpose**: Manage glossary v3 entries

**Features**:
- Exception rule handling
- Usage tracking
- Term prioritization

---

### 8. Types Module (`src/types/`)

#### `src/types/definitions.py` - Type Definitions

**Purpose**: TypedDict definitions for complex data structures

**Types**:
- `GlossaryTerm` - Schema for glossary entries
- `PendingGlossaryTerm` - Schema for pending terms
- `TranslationChunk` - Schema for translation chunks
- `PipelineResult` - Schema for pipeline results
- `ContextMemory` - Schema for context memory
- `ModelConfig` - Schema for model configuration
- `ProcessingConfig` - Schema for processing config
- `TranslationPipelineConfig` - Schema for pipeline config
- `QualityMetrics` - Schema for quality metrics
- `AgentMetadata` - Schema for agent metadata

---

### 9. Exceptions Module (`src/exceptions.py`)

**Purpose**: Structured error handling with context-aware exceptions

**Exception Hierarchy**:
```
NovelTranslationError (base)
├── ModelError - Model-related errors (Ollama API, cloud API, timeouts)
├── GlossaryError - Glossary errors (corruption, lookup failures)
├── ValidationError - Validation errors (config, input, output quality)
├── ResourceError - Resource errors (file I/O, memory, network)
├── PipelineError - Pipeline orchestration errors
└── ConfigurationError - Configuration errors
```

**Base Class Features**:
- `message` - Human-readable description
- `context` - Additional debugging data
- `error_code` - Categorization code
- `to_dict()` - Convert to dictionary for logging

---

### 10. Web Module (`src/web/`)

#### `src/web/launcher.py` - Web UI Launcher

**Purpose**: Launch Streamlit web interface

**Key Functions**:
- `launch_web_ui(args)` - Launch the web UI
- Check Streamlit availability
- Run streamlit_app.py

---

## Data Files

### `data/glossary.json`

**Purpose**: Approved terminology database

**Schema**:
```json
{
  "version": "1.0",
  "total_terms": 0,
  "terms": [
    {
      "id": "term_001",
      "source": "罗青",
      "target": "လူချင်း",
      "category": "character",
      "chapter_first_seen": 1,
      "chapter_last_seen": 1,
      "verified": true,
      "added_at": "2024-01-01T00:00:00",
      "updated_at": "2024-01-01T00:00:00"
    }
  ]
}
```

**Categories**:
- `character` - Character names
- `place` - Locations, cities, sects
- `level` - Cultivation levels
- `item` - Items, artifacts, treasures
- `general` - General terms

---

### `data/glossary_pending.json`

**Purpose**: New terms awaiting human review

**Schema**:
```json
{
  "pending_terms": [
    {
      "source": "新术语",
      "target": "မြန်မာဘာသာ",
      "category": "item",
      "extracted_from_chapter": 12,
      "status": "pending",
      "added_at": "2024-01-01T00:00:00"
    }
  ]
}
```

**Workflow**:
1. Term Extractor adds new terms
2. Human reviewer sets `status: "approved"`
3. Nightly merge promotes to `glossary.json`

---

### `data/context_memory.json`

**Purpose**: Dynamic chapter context

**Schema**:
```json
{
  "current_chapter": 5,
  "last_translated_chapter": 4,
  "summary": "Previous chapter summary...",
  "active_characters": {
    "罗青": {"status": "protagonist", "location": "天龙城"}
  },
  "recent_events": ["Event 1", "Event 2"],
  "paragraph_buffer": ["Recent paragraph 1", "Recent paragraph 2"]
}
```

---

## Configuration File (`config/settings.yaml`)

### Example Configuration

```yaml
project:
  name: novel_translation
  novel_genre: Xianxia/Cultivation
  source_language: en-US  # or zh-CN for Chinese
  target_language: my-MM

models:
  provider: ollama
  translator: padauk-gemma:q8_0
  editor: padauk-gemma:q8_0
  checker: qwen:7b
  refiner: padauk-gemma:q8_0
  ollama_base_url: http://localhost:11434
  timeout: 300
  use_gpu: true
  gpu_layers: -1  # -1 = auto
  main_gpu: 0

processing:
  chunk_size: 2000
  chunk_overlap: 50
  temperature: 0.3
  top_p: 0.92
  top_k: 50
  repeat_penalty: 1.3
  max_retries: 2
  request_timeout: 300
  stream: true

translation_pipeline:
  mode: lite  # full, lite, fast, single_stage, two_stage
  use_reflection: false
  stage1_model: padauk-gemma:q8_0
  stage2_model: padauk-gemma:q8_0

paths:
  input_dir: data/input
  output_dir: data/output
  glossary_file: data/glossary.json
  context_memory_file: data/context_memory.json

output:
  format: markdown
  preserve_formatting: true
  add_metadata: true

qa_testing:
  enabled: true
  min_myanmar_ratio: 0.7
  markdown_strict: true
```

---

## Usage Examples

### Translate Single Chapter

```bash
python -m src.main --novel "古道仙鸿" --chapter 1
```

### Translate All Chapters

```bash
python -m src.main --novel "古道仙鸿" --all
```

### Translate From Chapter 10 Onwards

```bash
python -m src.main --novel "古道仙鸿" --all --start 10
```

### Fast Mode Translation

```bash
python -m src.main_fast --novel "古道仙鸿" --chapter 1
```

### Generate Glossary

```bash
python -m src.main --novel "古道仙鸿" --generate-glossary --chapter-range 1-5
```

### Launch Web UI

```bash
python -m src.main --ui
```

### Test Translation

```bash
python -m src.main --test
```

### Clean Cache

```bash
python -m src.main --clean --novel "古道仙鸿" --chapter 1
```

---

## Key Features

### 1. Workflow Support

- **way1**: English → Myanmar direct (padauk-gemma:q8_0)
- **way2**: Chinese → English → Myanmar pivot (alibayram/hunyuan:7b + padauk-gemma:q8_0)

### 2. Pipeline Modes

- **full**: 6-stage pipeline (Translate → Refine → Reflect → Quality → Consistency → QA)
- **lite**: 3-stage pipeline (Translate → Refine → Quality)
- **fast**: 2-stage pipeline (Translate → Quality)
- **single_stage**: Direct translation only
- **two_stage**: CN→EN→MM with separate models

### 3. Quality Checks

- Myanmar Unicode ratio validation (>70%)
- Glossary consistency verification
- Markdown formatting preservation
- Placeholder detection (`【?term?】`)
- Repetition detection
- Language leakage detection

### 4. Memory System

- 3-tier memory (Glossary → Context → Session Rules)
- FIFO paragraph buffer for context
- Automatic glossary updates
- Persistent state across sessions

### 5. Resource Management

- Automatic cleanup on shutdown
- Model unloading to free VRAM
- Signal handling for graceful exit
- Progress logging

---

## Model Requirements

### Recommended Models

1. **padauk-gemma:q8_0** - Best for Myanmar output quality
2. **qwen2.5:14b** - Good Chinese comprehension
3. **qwen2.5:7b** - Faster alternative
4. **qwen:7b** - Quality checking and reflection
5. **alibayram/hunyuan:7b** - Chinese to English translation

### Installation

```bash
ollama pull padauk-gemma:q8_0
ollama pull qwen2.5:14b
ollama pull qwen:7b
ollama pull alibayram/hunyuan:7b
```

---

## File Naming Conventions

### Input Files

```
data/input/{novel_name}/{novel_name}_chapter_XXX.md
```

Examples:
- `data/input/古道仙鸿/古道仙鸿_chapter_001.md`
- `data/input/古道仙鸿/古道仙鸿_chapter_002.md`

### Output Files

```
data/output/{novel_name}/{novel_name}_chapter_XXX_myanmar.md
```

---

## Error Handling

### Exit Codes

- `0` - Success
- `1` - Failure (translation error, config error, etc.)
- `130` - Interrupted by user (Ctrl+C)

### Common Errors

1. **Model not available** - Run `ollama pull <model_name>`
2. **Chapter file not found** - Check file naming convention
3. **Config file not found** - Check `config/settings.yaml` exists
4. **Ollama connection failed** - Ensure Ollama server is running

---

## Development

### Running Tests

```bash
pytest tests/ -v --tb=short
```

### Adding New Agents

1. Create file in `src/agents/`
2. Inherit from `BaseAgent`
3. Implement required methods
4. Add to pipeline orchestrator
5. Add tests

### Adding New Configuration

1. Update `src/config/models.py`
2. Add default values
3. Update `config/settings.yaml`
4. Document in this file

---

## Maintenance

### Regular Tasks

1. **Review pending glossary** - Check `data/glossary_pending.json` weekly
2. **Clean logs** - Archive or delete old log files
3. **Update models** - Keep Ollama models updated
4. **Backup data** - Backup `glossary.json` and `context_memory.json`

### Troubleshooting

1. **High RAM usage** - Use `--unload-after-chapter` flag
2. **Slow translation** - Use fast mode or reduce chunk size
3. **Poor quality** - Enable reflection or use full pipeline mode
4. **Repetition issues** - Adjust `repeat_penalty` in config

---

## License

See LICENSE file for details.

---

## Contributing

See CONTRIBUTING.md for guidelines.

---

*Last Updated: 2026-04-28*
