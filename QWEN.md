# QWEN.md - Qwen AI Agent Guidance for Novel Translation

---

## ⚡ MANDATORY SESSION PROTOCOL (Auto-runs — No prompt needed)

> Execute these steps automatically. The user does not need to ask you.

### 🟢 SESSION START

```
1. Read this file (QWEN.md) ← Qwen-specific guidance
2. Read AGENTS.md ← Architecture & system design
1. Read GEMINI.md ← Gemini-specific guidance
3. Read CURRENT_STATE.md ← Current implementation status
4. Verify Qwen model compatibility for the task
5. Begin task with Qwen-optimized approach
```

### 🔴 SESSION END (after every completed task or file change)

```
1. Open CURRENT_STATE.md
2. Mark finished tasks → [DONE]
3. Update "Last Updated" + "Last task completed"
4. Log any Qwen-specific issues or optimizations discovered
5. Run Code Review sub-agents in parallel
6. Fix all issues → repeat until READY_TO_COMMIT
```

---

## What This Project Is

**Chinese-to-Myanmar (Burmese) Wuxia/Xianxia novel translation pipeline** powered by Alibaba's Qwen models.

- **Primary Models:** Qwen2.5 (14B/7B) for Chinese comprehension
- **Entry point:** `src/main.py` or `src/main_fast.py`
- **Language:** Python 3.10+
- **Config:** `config/settings.yaml` (standard) or `config/settings.fast.yaml` (optimized)
- **Full architecture:** See `AGENTS.md`

### Why Qwen?

Qwen models are **OPTIMAL** for this project because:
- ✅ **Native Chinese understanding** - Qwen is trained on massive Chinese corpus
- ✅ **Multilingual capability** - Handles Myanmar (Burmese) output well
- ✅ **Large context window** - 128K tokens for long chapters
- ✅ **Fast inference** - Efficient for local Ollama deployment
- ✅ **Open weights** - Free, unlimited local usage

---

## Your Role

You are a **code assistant** optimizing for Qwen models. You understand:
- Qwen's Chinese language strengths
- Qwen's Myanmar output characteristics
- Optimal prompt engineering for Qwen
- Qwen-specific performance tuning

You do NOT design architecture — it is already defined in `AGENTS.md`. You implement, fix, and extend within that architecture with Qwen optimizations.

---

## Qwen Model Reference

### Recommended Models

| Model | Size | VRAM | Speed | Quality | Use Case |
|-------|------|------|-------|---------|----------|
| **qwen2.5:14b** | 9GB | ~9GB VRAM | Medium | ⭐⭐⭐⭐⭐ Best | Production, final versions |
| **qwen2.5:7b** | 4GB | ~4GB VRAM | Fast | ⭐⭐⭐⭐ Good | Development, drafts |
| **qwen:7b** | 4GB | ~4GB VRAM | Fastest | ⭐⭐⭐ Okay | Testing, quick iterations |

### Model Selection Guide

```yaml
# For best quality (production)
models:
  translator: "qwen2.5:14b"
  editor: "qwen2.5:14b"

# For fast development
models:
  translator: "qwen2.5:7b"
  editor: "qwen2.5:7b"

# For quick testing only
models:
  translator: "qwen:7b"
```

### NOT Recommended

| Model | Issue |
|-------|-------|
| `alibayram/hunyuan:7b` | Outputs **THAI** instead of Myanmar ❌ |
| `yxchia/seallms-v3-7b` | Outputs **THAI** instead of Myanmar ❌ |
| `translategemma:12b` | May output wrong language ❌ |

---

## Qwen-Specific Prompt Engineering

### 1. LANGUAGE_GUARD is CRITICAL for Qwen

Qwen can sometimes output mixed languages. Always use the hardened prompt:

```python
LANGUAGE_GUARD = """CRITICAL LANGUAGE RULE — READ FIRST:
- Output language: Myanmar (Burmese) ONLY.
- Script: Myanmar Unicode (U+1000–U+109F). Example: မြန်မာဘာသာ
- FORBIDDEN output languages: Thai, Chinese, English, Japanese, Korean, any other.
- If you are unsure of a word, write 【?term?】 — do NOT switch to Thai or Chinese.
- Do NOT output <think>, <answer>, or any XML/HTML tags.
- Return ONLY the Myanmar translation. Zero preamble. Zero explanation.
"""
```

**Always prepend** `LANGUAGE_GUARD` to all system prompts when using Qwen.

### 2. Optimal Temperature for Qwen

```yaml
# For translation (consistent, accurate)
temperature: 0.3  # Qwen works best with lower temp for translation

# For refinement (slightly creative)
temperature: 0.4

# NOT recommended
temperature: 0.7  # Too creative, may hallucinate terms
temperature: 0.1  # Too rigid, awkward phrasing
```

### 3. Qwen-Optimized System Prompt Structure

```python
TRANSLATOR_SYSTEM_PROMPT = LANGUAGE_GUARD + """
You are an expert Chinese-to-Myanmar literary translator specializing in Wuxia/Xianxia novels.

STRICT RULES:
1. SYNTAX: Convert Chinese SVO structure to natural Myanmar SOV order.
2. TERMINOLOGY: Use EXACT terms from the provided GLOSSARY.
3. MARKDOWN: Preserve ALL formatting.
4. CONTEXT: Use PREVIOUS CONTEXT for pronoun resolution.
5. TONE: Formal/literary for narrative, natural spoken for dialogue.

GLOSSARY:
{glossary}

PREVIOUS CONTEXT:
{context}

INPUT TEXT (Chinese):
{input_text}
"""
```

### 4. Chunk Size for Qwen

```yaml
# Qwen2.5:14b can handle larger chunks
processing:
  chunk_size: 2000  # Optimal for 14B
  chunk_size: 3000  # Use with fast mode

# Qwen2.5:7b needs smaller chunks
processing:
  chunk_size: 1500  # Safer for 7B
```

---

## Qwen Performance Characteristics

### Inference Speed (approximate)

| Model | GPU | Tokens/sec | Chapter Time (128 paras) |
|-------|-----|------------|--------------------------|
| qwen2.5:14b | RTX 4090 | ~25-30 | ~2 hours |
| qwen2.5:14b | RTX 3060 | ~10-15 | ~4 hours |
| qwen2.5:7b | RTX 4090 | ~50-60 | ~1 hour |
| qwen2.5:7b | RTX 3060 | ~25-30 | ~2 hours |

### Memory Usage

```
qwen2.5:14b:  ~9GB VRAM (GPU)  + ~200MB RAM (Ollama server)
qwen2.5:7b:   ~4GB VRAM (GPU)  + ~200MB RAM (Ollama server)
qwen:7b:      ~4GB VRAM (GPU)  + ~200MB RAM (Ollama server)
```

### Context Window

- **Qwen2.5**: 128K tokens (can handle very long chapters)
- **Qwen**: 32K tokens (sufficient for most chapters)

---

## Common Qwen Issues & Solutions

### Issue 1: Thai Output

**Symptom:** Model outputs Thai script instead of Myanmar

**Solution:**
```python
# 1. Verify you're using Qwen (not Hunyuan/SeaLLMs)
# 2. Strengthen LANGUAGE_GUARD
# 3. Add explicit Myanmar examples in prompt

LANGUAGE_GUARD += """
CORRECT: မြန်မာဘာသာ (Myanmar)
WRONG: ภาษาไทย (Thai - NEVER output this)
"""
```

### Issue 2: Chinese Leakage

**Symptom:** Untranslated Chinese characters in output

**Solution:**
```python
# 1. Check glossary consistency
# 2. Use postprocessor to detect Chinese chars
# 3. Lower temperature

from src.utils.postprocessor import detect_language_leakage

leakage = detect_language_leakage(text)
if leakage["chinese_chars"] > 0:
    logger.warning("Chinese leakage detected")
```

### Issue 3: <think> Tags in Output

**Symptom:** Qwen outputs reasoning tags like `<think>...</think>`

**Solution:**
```python
# Already handled by postprocessor
from src.utils.postprocessor import clean_output

cleaned = clean_output(raw_qwen_output)  # Strips <think> tags
```

### Issue 4: Repetitive Output

**Symptom:** Qwen repeats phrases or sentences

**Solution:**
```yaml
processing:
  repeat_penalty: 1.1  # Increase to reduce repetition
  temperature: 0.35    # Slightly increase for variety
```

### Issue 5: Slow First Request

**Symptom:** First API call takes 1-2 minutes

**Cause:** Model loading into VRAM

**Solution:**
```bash
# Preload model before translation
ollama run qwen2.5:14b "Hello" --keepalive 10m

# Or accept the initial load time
```

---

## Qwen Best Practices

### 1. Use Batch Processing

Qwen handles batch prompts efficiently:

```python
# Instead of 167 individual calls
for para in paragraphs:
    result = translate(para)  # 167 API calls

# Use batch refinement (5x faster)
refiner = Refiner(ollama_client, batch_size=5)
results = refiner.refine_chapter(paragraphs)  # ~34 API calls
```

### 2. Enable Streaming for UI Feedback

```python
# For better user experience
for chunk in ollama_client.chat_stream(prompt, system_prompt):
    print(chunk, end='', flush=True)  # Real-time output
```

### 3. Proper Cleanup After Use

```python
# Always cleanup to free VRAM
client = OllamaClient(model="qwen2.5:14b", unload_on_cleanup=True)
try:
    result = client.chat(prompt, system_prompt)
finally:
    client.cleanup()  # Unloads from GPU
```

### 4. Use Context Manager

```python
# Automatic cleanup
with OllamaClient(model="qwen2.5:14b", unload_on_cleanup=True) as client:
    result = client.chat(prompt, system_prompt)
# Model automatically unloaded here
```

---

## Qwen Model Commands

### Pull Models

```bash
# Best quality (recommended)
ollama pull qwen2.5:14b

# Fast/good quality
ollama pull qwen2.5:7b

# Lightweight
ollama pull qwen:7b
```

### Verify Installation

```bash
# List installed models
ollama list

# Test model
echo "你好" | ollama run qwen2.5:14b

# Check VRAM usage
nvidia-smi  # If using NVIDIA GPU
```

### Unload Model (Free VRAM)

```bash
# Method 1: Using cleanup tool
python -m tools.cleanup --stop-all

# Method 2: Direct Ollama command
ollama run qwen2.5:14b "" --keepalive 0

# Method 3: Stop Ollama service
sudo systemctl stop ollama
```

---

## File Path Reference (Do not deviate)

| Purpose | Path |
|--------|------|
| Main entry | `src/main.py` |
| Fast entry | `src/main_fast.py` |
| Qwen client | `src/utils/ollama_client.py` |
| Translator agent | `src/agents/translator.py` |
| Refiner agent | `src/agents/refiner.py` |
| Hardened prompts | `src/agents/prompt_patch.py` |
| Postprocessor | `src/utils/postprocessor.py` |
| Cleanup tool | `tools/cleanup.py` |
| Standard config | `config/settings.yaml` |
| Fast config | `config/settings.fast.yaml` |

---

## Key Classes (Do not change names)

- `OllamaClient` — `src/utils/ollama_client.py` (Qwen API wrapper)
- `Translator` — `src/agents/translator.py` (Stage 1)
- `Refiner` — `src/agents/refiner.py` (Stage 2, with batch support)
- `FastTranslator` — `src/agents/fast_translator.py` (Optimized for Qwen)
- `FastRefiner` — `src/agents/fast_refiner.py` (Batch processing)
- `MemoryManager` — `src/memory/memory_manager.py` (Context & glossary)

---

## Quick Start with Qwen

```bash
# 1. Install Qwen model
ollama pull qwen2.5:14b

# 2. Test translation (single chapter, standard quality)
python -m src.main --novel 古道仙鸿 --chapter 1

# 3. Fast translation (7B model, single-stage)
python -m src.main_fast --novel 古道仙鸿 --chapter 1

# 4. Batch translation with memory cleanup
python -m src.main_fast --novel 古道仙鸿 --all --unload-after-chapter
```

---

## Troubleshooting Qwen Issues

| Problem | Check | Solution |
|---------|-------|----------|
| Thai output | Model name | Verify using `qwen2.5:14b`, not `hunyuan` |
| Slow inference | GPU usage | Check `nvidia-smi`, reduce model size |
| Out of memory | VRAM | Use 7B instead of 14B, or enable `--unload-after-chapter` |
| Chinese leakage | Postprocessor | Verify `clean_output()` is called |
| Repetition | Config | Increase `repeat_penalty` to 1.15 |
| Timeout | Chunk size | Reduce `chunk_size` to 1500 |

---

## Performance Optimization Checklist

Before running large batch translations:

- [ ] Qwen model downloaded: `ollama list | grep qwen`
- [ ] GPU has sufficient VRAM (14B needs 9GB, 7B needs 4GB)
- [ ] Using appropriate config (fast.yaml for speed)
- [ ] Batch processing enabled for refinement
- [ ] Cleanup tool ready for memory management
- [ ] Log directory exists: `mkdir -p logs`

---

## See Also

- **Architecture:** `AGENTS.md`
- **Current Status:** `CURRENT_STATE.md`
- **Memory Management:** `docs/MEMORY_MANAGEMENT.md`
- **Fast Mode Guide:** `docs/FAST_MODE.md`
- **User Guide:** `USER_GUIDE.md`
