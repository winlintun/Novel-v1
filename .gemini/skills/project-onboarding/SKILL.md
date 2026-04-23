---
name: project-onboarding
description: Onboarding guide and architectural overview for the Novel Translation Project. Use this skill to understand the Chinese-to-Myanmar translation pipeline, the agent roles, project structure, and coding standards before modifying the codebase.
---

# Novel Translation Project Onboarding

This skill provides the core architectural context and operational guidelines for the Novel Translation Project, an AI-powered Chinese-to-Myanmar (Burmese) web novel translation system specializing in Wuxia/Xianxia novels.

## 1. System Architecture

The project runs a strict multi-stage translation pipeline orchestrated by `src/main.py`:

1. **Preprocess:** `src/agents/preprocessor.py` cleans Markdown and chunks Chinese input.
2. **Context Load:** `src/memory/memory_manager.py` loads `data/glossary.json` and `data/context_memory.json`.
3. **Translation (Stage 1):** `src/agents/translator.py` performs a literal, accurate Chinese-to-Myanmar translation using the glossary and previous context.
4. **Refinement (Stage 2):** `src/agents/refiner.py` rewrites the translation into natural, literary Myanmar prose.
5. **Consistency Check (Stage 3):** `src/agents/checker.py` verifies term consistency against the glossary.
6. **Final QA (Stage 4):** Validates narrative flow and markdown formatting.
7. **Term Extraction:** `src/agents/context_updater.py` extracts new proper nouns and outputs them to `data/glossary_pending.json` for human review.
8. **Save:** Output is saved to `data/output/`.

## 2. Mandatory Rules for Agents

When contributing to this project, you MUST adhere to the following rules:
- **Never bypass `MemoryManager`:** Agents (`Translator`, `Refiner`, etc.) must not read or write data files directly. All interaction goes through `MemoryManager`.
- **Use strict Type Hints:** All functions and methods must have full type hints. Use `TypedDict` or `dataclass` for data models.
- **Automated Tests:** Any new function requires a test in the `tests/` directory. Run tests (`pytest tests/`) before finalizing any code.
- **Workflow Protocol:** Before coding, read `CURRENT_STATE.md`. After coding, update `CURRENT_STATE.md`, mark the task as `[DONE]`, and initiate the parallel Code Review Workflow (Checking for bugs and security issues).

## 3. Directory Guide

- `src/main.py`: The CLI entry point.
- `src/agents/`: Core pipeline stages (Translator, Refiner, Checker, Preprocessor, ContextUpdater).
- `src/memory/`: `memory_manager.py` manages all states (glossary and sliding window context).
- `src/utils/`: Handlers for Ollama LLM interactions and File I/O.
- `data/input/`: Raw Chinese Markdown chapters.
- `data/output/`: Final Myanmar translated chapters.
- `data/glossary.json`: Approved terminology mappings.
- `data/context_memory.json`: Ongoing story context.
- `config/settings.yaml`: Controls the LLM models used for each stage, as well as pipeline settings like chunk sizes.

## 4. Usage

Translate via CLI:
```bash
python -m src.main --novel <NovelName> --chapter <ChapterNum>
```