# Memory Management Guide

This guide explains how to properly manage memory when using the Novel Translation system with Ollama.

## The Problem

When you stop a translation (Ctrl+C), the Python process exits but Ollama server continues running with the model loaded in GPU/CPU memory. This can consume:

- **GPU VRAM**: 8-28GB depending on model size (14B model ~14GB, 7B model ~8GB)
- **System RAM**: ~137MB for Ollama server process + model cache

## Solutions

### Solution 1: Use --unload-after-chapter Flag (Recommended for Batch Translation)

When translating multiple chapters, unload the model from GPU after each chapter:

```bash
# Standard mode
python -m src.main --novel 古道仙鸿 --all --unload-after-chapter

# Fast mode
python -m src.main_fast --novel 古道仙鸿 --all --unload-after-chapter
```

**Pros**: Frees VRAM between chapters, allows other GPU tasks
**Cons**: Slightly slower (model reloads for each chapter)

### Solution 2: Stop Models After Translation

Use the cleanup tool to stop all running models:

```bash
# Stop all running models (keeps Ollama server running)
python -m tools.cleanup --stop-all

# Or stop a specific model
python -m tools.cleanup --stop-model qwen2.5:14b
```

### Solution 3: Stop Ollama Service Completely

To free all memory including the Ollama server:

```bash
# Using the cleanup tool
python -m tools.cleanup --stop-service

# Or manually
sudo systemctl stop ollama
```

### Solution 4: Check Status Before/After

Check Ollama status and memory usage:

```bash
# Show current status
python -m tools.cleanup --status

# Full cleanup with status report
python -m tools.cleanup --full
```

## Automatic Cleanup

The translation pipeline now includes automatic cleanup:

1. **Signal Handling**: Ctrl+C (SIGINT) now properly cleans up resources
2. **atexit Handler**: Normal exit cleans up resources
3. **Context Managers**: OllamaClient supports `with` statements

Example of using context manager:

```python
from src.utils.ollama_client import OllamaClient

with OllamaClient(model="qwen2.5:14b", unload_on_cleanup=True) as client:
    # Use client for translation
    result = client.chat("Translate this...")
# Model automatically unloaded here
```

## Memory Management Best Practices

### For Single Chapter Translation

```bash
# Model automatically unloads after translation
python -m src.main --novel 古道仙鸿 --chapter 1
```

### For Batch Translation (All Chapters)

```bash
# Option A: Keep model loaded (faster, uses more VRAM)
python -m src.main --novel 古道仙鸿 --all

# After translation, manually cleanup
python -m tools.cleanup --stop-all

# Option B: Unload between chapters (slower, frees VRAM)
python -m src.main --novel 古道仙鸿 --all --unload-after-chapter
```

### For Limited VRAM Systems

If you have limited GPU memory:

```bash
# 1. Use smaller model (7B instead of 14B)
# Edit config/settings.yaml: translator: "qwen2.5:7b"

# 2. Use fast mode (smaller chunks, more aggressive unloading)
python -m src.main_fast --novel 古道仙鸿 --chapter 1

# 3. Reduce chunk size in config/settings.yaml
# processing:
#   chunk_size: 1000  # Instead of 1500
```

## Troubleshooting

### Issue: "Cannot stop Ollama - permission denied"

Ollama may be running as a different user (e.g., 'ollama' user).

**Solutions**:
```bash
# Check who owns the process
ps aux | grep ollama

# If owned by 'ollama' user, you have options:
# 1. Stop models using cleanup tool (works without sudo)
python -m tools.cleanup --stop-all

# 2. Use sudo to stop service
sudo systemctl stop ollama

# 3. Ask system admin to add you to ollama group or give passwordless sudo
```

### Issue: Memory not freeing after stopping Ollama

Sometimes system caches hold memory. Try:

```bash
# Clear system caches (requires sudo)
sudo sync && sudo echo 3 > /proc/sys/vm/drop_caches

# Or just wait - Linux will reclaim memory as needed
```

### Issue: Translation interrupted, want to resume

```bash
# Check for partial translations
ls data/output/<novel_name>/chapters/*_PARTIAL.md

# Resume by running the same command
python -m src.main --novel 古道仙鸿 --chapter 5
```

## Quick Reference

| Command | Purpose |
|---------|---------|
| `python -m tools.cleanup --status` | Check Ollama status |
| `python -m tools.cleanup --stop-all` | Stop all models |
| `python -m tools.cleanup --stop-service` | Stop Ollama server |
| `python -m tools.cleanup --full` | Stop all + show status |
| `python -m src.main --unload-after-chapter` | Auto-unload per chapter |
| `sudo systemctl stop ollama` | Stop service manually |

## Technical Details

### How Cleanup Works

1. **OllamaClient.cleanup()**: Sets `keep_alive=0` to unload model from GPU
2. **Signal handlers**: Catch SIGINT/SIGTERM and cleanup before exit
3. **atexit**: Register cleanup for normal program exit
4. **MemoryManager.save_memory()**: Persist glossary/context on exit

### Memory Usage by Model

| Model | VRAM Usage | RAM Usage | Speed |
|-------|------------|-----------|-------|
| qwen2.5:7b | ~8 GB | ~5 GB | Fast |
| qwen2.5:14b | ~14 GB | ~8 GB | Medium |
| qwen2.5:32b | ~28 GB | ~16 GB | Slow |

### Files Created During Cleanup

- No files are deleted during cleanup
- Partial translations are saved with `_PARTIAL.md` suffix
- Memory state is saved to `data/glossary.json` and `data/context_memory.json`
