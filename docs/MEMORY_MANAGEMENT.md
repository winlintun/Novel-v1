# Memory Management Guide

This guide explains how to properly manage memory when using the Novel Translation system with Ollama.

## The Problem

When you stop a translation process (Ctrl+C or kill), the Ollama server continues running and keeps models loaded in memory. This can consume significant RAM/VRAM:

- **14B models**: ~9GB VRAM
- **7B models**: ~4GB VRAM
- **Ollama server**: ~100-200MB RAM

## Quick Solutions

### 1. Free GPU Memory (Keep Ollama Running)

Unload models but keep Ollama service available:

```bash
python -m tools.cleanup --stop-all
```

This frees GPU VRAM but Ollama remains ready for new requests.

### 2. Stop Ollama Completely (Free All Memory)

Stop the Ollama service entirely:

```bash
python -m tools.cleanup --stop-service
```

This frees all memory but you'll need to restart Ollama to translate again.

### 3. Check Current Status

See what's using memory:

```bash
python -m tools.cleanup --status
```

## Automatic Memory Management

### During Translation

Use the `--unload-after-chapter` flag for automatic cleanup:

```bash
# Automatically unload model after each chapter
python -m src.main --novel 古道仙鸿 --all --unload-after-chapter

# Fast mode with automatic cleanup
python -m src.main_fast --novel 古道仙鸿 --all --unload-after-chapter
```

### Using Context Manager (Code)

When using OllamaClient in your code, use context managers for automatic cleanup:

```python
from src.utils.ollama_client import OllamaClient

# Automatic cleanup on exit
with OllamaClient(model="qwen2.5:7b", unload_on_cleanup=True) as client:
    result = client.chat("Translate this text")
    # Model is automatically unloaded when exiting the block

# Or manually cleanup
client = OllamaClient(model="qwen2.5:7b")
try:
    result = client.chat("Translate this text")
finally:
    client.cleanup()  # Explicit cleanup
```

## Model Size Comparison

| Model | VRAM | Speed | Quality | Use Case |
|-------|------|-------|---------|----------|
| qwen2.5:14b | ~9GB | Slow | Best | Final versions |
| qwen2.5:7b | ~4GB | Fast | Good | Drafts, testing |
| qwen:7b | ~4GB | Fastest | Okay | Quick tests |

## Best Practices

### For Single Chapter Translation

```bash
# 1. Translate
python -m src.main_fast --novel 古道仙鸿 --chapter 1

# 2. When done, free memory
python -m tools.cleanup --stop-all
```

### For Batch Translation

```bash
# Use automatic cleanup between chapters
python -m src.main_fast --novel 古道仙鸿 --all --unload-after-chapter
```

### For Limited VRAM (< 8GB)

```bash
# Use 7B model instead of 14B
# Edit config/settings.fast.yaml:
# models:
#   translator: "qwen2.5:7b"

python -m src.main_fast --novel 古道仙鸿 --chapter 1
```

## Troubleshooting

### "Out of Memory" Errors

1. Stop all models: `python -m tools.cleanup --stop-all`
2. Use smaller model (7B instead of 14B)
3. Reduce chunk size in config
4. Clear system swap: `sudo swapoff -a && sudo swapon -a`

### "Model Not Responding"

1. Check status: `python -m tools.cleanup --status`
2. Stop and restart Ollama:
   ```bash
   python -m tools.cleanup --stop-service
   ollama serve
   ```

### System Running Slowly

1. Check memory: `free -h`
2. Stop Ollama: `python -m tools.cleanup --stop-service`
3. Check for zombie processes: `ps aux | grep ollama`

## Command Reference

| Command | Description |
|---------|-------------|
| `python -m tools.cleanup --status` | Check Ollama and memory status |
| `python -m tools.cleanup --stop-all` | Stop all running models |
| `python -m tools.cleanup --stop-service` | Stop Ollama service |
| `python -m tools.cleanup --full` | Full cleanup + status report |
| `python -m tools.cleanup --tips` | Show memory management tips |

## Manual Cleanup (If Automated Fails)

### Stop Ollama Manually

```bash
# Method 1: Systemd
sudo systemctl stop ollama

# Method 2: Kill process
sudo pkill -f "ollama serve"

# Method 3: Find and kill specific PID
ps aux | grep ollama
sudo kill -9 <PID>
```

### Clear GPU Memory

```bash
# Unload specific model
ollama run qwen2.5:14b "" --keepalive 0

# Or use nvidia-smi (if using NVIDIA GPU)
nvidia-smi --gpu-reset
```

## Summary

1. **After translation**: Run `python -m tools.cleanup --stop-all`
2. **If system slow**: Run `python -m tools.cleanup --stop-service`
3. **For batch jobs**: Use `--unload-after-chapter` flag
4. **In code**: Use `OllamaClient` with `unload_on_cleanup=True` or context managers
