# Fast Translation Mode Guide

This guide helps you translate novels **5-10x faster** using Ollama with optimized settings.

## Quick Start (Fast Mode)

```bash
# Use the fast configuration and entry point
python -m src.main_fast --novel 古道仙鸿 --chapter 1

# Or use fast mode with existing main.py
python -m src.main --novel 古道仙鸿 --chapter 1 --config config/settings.fast.yaml
```

## Speed Optimizations

| Feature | Standard Mode | Fast Mode | Speedup |
|---------|--------------|-----------|---------|
| **Model Size** | 14B (9GB) | 7B (4GB) | **2x** |
| **Translation Stages** | 2 (translate + refine) | 1 (single-stage) | **2x** |
| **Chunk Size** | 1500 chars | 3000 chars | **2x** |
| **Refinement** | 1 para/API call | 5 paras/API call | **5x** |
| **Streaming** | Disabled | Enabled | **~30%** |
| **Total Speedup** | - | - | **5-10x** |

## Time Comparison

For a typical chapter with 128 paragraphs:

| Mode | Translation | Refinement | Total |
|------|-------------|------------|-------|
| **Standard (14B, 2-stage)** | ~2 hours | ~3 hours | **~5 hours** |
| **Fast (7B, single-stage)** | ~30 min | ~20 min | **~50 min** |
| **Fast (7B, no refine)** | ~30 min | 0 | **~30 min** |

## Configuration Files

### 1. Fast Config (config/settings.fast.yaml)

```yaml
# Key differences from standard config
models:
  translator: "qwen2.5:7b"      # 2x faster than 14B
  timeout: 120                  # Shorter timeout

translation_pipeline:
  mode: "single_stage"          # Skip refinement stage

processing:
  chunk_size: 3000              # Larger chunks = fewer API calls
  stream: true                  # Enable streaming
  batch_processing:
    enabled: true
    batch_size: 5               # 5 paragraphs per API call
```

### 2. Standard Config (config/settings.yaml)

Use for best quality (slower):
```yaml
translation_pipeline:
  mode: "two_stage"             # Translate + Refine

models:
  translator: "qwen2.5:14b"     # Higher quality
```

## Usage Examples

### Single Chapter (Fast)
```bash
python -m src.main_fast --novel 古道仙鸿 --chapter 1
```

### All Chapters (Fast)
```bash
python -m src.main_fast --novel 古道仙鸿 --all
```

### From Chapter 10 Onwards
```bash
python -m src.main_fast --novel 古道仙鸿 --all --start 10
```

## Model Recommendations

### For Speed (Fast Mode)
- **qwen2.5:7b** - Best balance of speed and quality
- **qwen:7b** - Lightweight, very fast

### For Quality (Standard Mode)
- **qwen2.5:14b** - Best quality for Chinese-to-Myanmar

### Avoid (Wrong Language)
- alibayram/hunyuan:7b - Produces Thai
- yxchia/seallms-v3-7b - Produces Thai

## Performance Tips

### 1. Use Single-Stage Mode
```yaml
translation_pipeline:
  mode: "single_stage"  # 2x faster
```

### 2. Increase Chunk Size
```yaml
processing:
  chunk_size: 3000  # Fewer API calls
```

### 3. Enable Batch Refinement
```yaml
processing:
  batch_processing:
    batch_size: 5  # 5 paragraphs at once
```

### 4. Use Smaller Model
```yaml
models:
  translator: "qwen2.5:7b"  # 2x faster than 14B
```

### 5. Disable QA Testing
```yaml
qa_testing:
  enabled: false  # Skip quality checks for speed
```

## Troubleshooting

### "Model not available"
```bash
# Pull the model first
ollama pull qwen2.5:7b
```

### "Out of memory"
```bash
# Use smaller model
# Edit config/settings.fast.yaml:
# models:
#   translator: "qwen:7b"  # 4GB instead of 9GB
```

### "Translation timeout"
```bash
# Increase timeout in config
models:
  timeout: 180  # 3 minutes
```

### "Low quality output"
```yaml
# Switch back to two-stage or 14B model
translation_pipeline:
  mode: "two_stage"

models:
  translator: "qwen2.5:14b"
```

## Files Overview

| File | Purpose |
|------|---------|
| `src/main_fast.py` | Fast entry point with batch processing |
| `src/agents/fast_translator.py` | Optimized translator with larger chunks |
| `src/agents/fast_refiner.py` | Batch refinement (5 paragraphs at once) |
| `config/settings.fast.yaml` | Fast configuration file |

## Command Comparison

```bash
# Standard mode (5+ hours per chapter)
python -m src.main --novel 古道仙鸿 --chapter 1

# Fast mode (30-50 minutes per chapter)
python -m src.main_fast --novel 古道仙鸿 --chapter 1

# Fast mode with two-stage (1 hour per chapter, better quality)
# Edit config/settings.fast.yaml: mode: "two_stage"
python -m src.main_fast --novel 古道仙鸿 --chapter 1
```
