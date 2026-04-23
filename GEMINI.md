# GEMINI.md - Project Context for Gemini AI

---

## ⚡ MANDATORY SESSION PROTOCOL (Auto-runs — No prompt needed)

> Execute these steps automatically. The user does not need to ask you.

### 🟢 SESSION START

```
1. Read this file (GEMINI.md)
2. Read AGENTS.md
2. Read QWEN.md
3. Read CURRENT_STATE.md
4. Check Architecture Decisions — confirm your task does not violate any
5. Begin task
```

### 🔴 SESSION END (after every completed task or file change)

```
1. Open CURRENT_STATE.md
2. Mark finished tasks → [DONE]
3. Update "Last Updated" + "Last task completed"
4. Log any new bugs or decisions under Known Issues / Architecture Decisions
5. Run Code Review sub-agents A + B in parallel (see AGENTS.md → Code Review Workflow)
6. Fix all issues → repeat until READY_TO_COMMIT
```

---


## What This Project Is

Chinese-to-Myanmar Wuxia/Xianxia novel translation pipeline.
- **Entry point:** `src/main.py`
- **Language:** Python
- **Config:** `config/settings.yaml`
- **Full architecture:** See `AGENTS.md`

## Your Role

You are a **code assistant** for this pipeline. You do NOT design architecture — it is already defined in `AGENTS.md`. You implement, fix, and extend within that architecture.

## Mandatory Rules

1. **Before any code:** Read `CURRENT_STATE.md` to know what is done and what is not.
2. **Never invent new file paths.** Use only paths defined in `AGENTS.md` → Directory Structure.
3. **Never rename classes or methods** that already exist in implemented files.
4. **After any implementation:** Run the Code Review Workflow defined in `AGENTS.md`.
5. **After completing a feature:** Update `CURRENT_STATE.md` → mark task as `[DONE]`.

## File Path Reference (Do not deviate)

| Purpose | Path |
|--------|------|
| Main entry | `src/main.py` |
| Translation agent | `src/agents/translator.py` |
| Editor agent | `src/agents/refiner.py` |
| Checker agent | `src/agents/checker.py` |
| Context updater | `src/agents/context_updater.py` |
| Memory manager | `src/memory/memory_manager.py` |
| Ollama client | `src/utils/ollama_client.py` |
| File handler | `src/utils/file_handler.py` |
| Approved glossary | `data/glossary.json` |
| Pending glossary | `data/glossary_pending.json` |
| Chapter context | `data/context_memory.json` |
| Config | `config/settings.yaml` |

## Key Classes (Do not change names)

- `Preprocessor` — `src/agents/preprocessor.py`
- `Translator` — `src/agents/translator.py`
- `Refiner` — `src/agents/refiner.py`
- `Checker` — `src/agents/checker.py`
- `ContextUpdater` — `src/agents/context_updater.py`
- `MemoryManager` — `src/memory/memory_manager.py`
- `OllamaClient` — `src/utils/ollama_client.py`
- `FileHandler` — `src/utils/file_handler.py`