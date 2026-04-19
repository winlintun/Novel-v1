# Full Combined OpenCode Prompt
# Chinese → Myanmar Novel Translator
# Generated for OpenCode AI

---

```
Build a production-ready Chinese → Myanmar novel translator pipeline.
Implement ALL sections below in order. Remove nothing.

════════════════════════════════════════════════════════
 1. PROJECT STRUCTURE
════════════════════════════════════════════════════════

novel_translator/
├── main.py                        ← orchestrator, auto-scan input_novels/
├── preprocessor.py                ← clean raw .txt input
├── chunker.py                     ← smart paragraph-boundary chunking
├── translator.py                  ← all model adapters + streaming
├── postprocessor.py               ← punctuation + name consistency fix
├── assembler.py                   ← merge chunks → final .md
├── .env.example                   ← all config keys
├── requirements.txt
├── names.json                     ← character name map (editable)
├── templates/
│   └── chapter_template.md        ← final .md layout
├── input_novels/                  ← drop .txt chapter files here
├── working_data/
│   ├── logs/                      ← per-run log files
│   └── checkpoints/
│       └── {chapter_name}/
│           ├── chunk_001.txt
│           ├── chunk_002.txt
│           └── ...
└── translated_novels/             ← final output .md files

════════════════════════════════════════════════════════
 2. .env.example
════════════════════════════════════════════════════════

# ── Model Selection ──────────────────────────────────
# Options: openrouter | gemini | deepseek | qwen | ollama
AI_MODEL=openrouter

# ── OpenRouter (one key = many free models) ──────────
OPENROUTER_API_KEY=your_key_here
OPENROUTER_MODEL=google/gemini-2.0-flash-exp:free
# OPENROUTER_MODEL=deepseek/deepseek-chat-v3-0324:free
# OPENROUTER_MODEL=meta-llama/llama-3.3-70b-instruct:free
# OPENROUTER_MODEL=qwen/qwen2.5-72b-instruct:free

# ── Google Gemini (AI Studio) ─────────────────────────
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.0-flash

# ── DeepSeek ─────────────────────────────────────────
DEEPSEEK_API_KEY=your_key_here
DEEPSEEK_MODEL=deepseek-chat

# ── Qwen (Alibaba DashScope) ──────────────────────────
QWEN_API_KEY=your_key_here
QWEN_MODEL=qwen-max

# ── Ollama (Local — Qwen3.5 7B or 14B) ───────────────
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:14b

# ── Chunking ──────────────────────────────────────────
MAX_CHUNK_CHARS=1800      # auto paragraph-boundary, no overlap

# ── Translation ───────────────────────────────────────
TARGET_LANGUAGE=Myanmar (Burmese)
SOURCE_LANGUAGE=Chinese
REQUEST_DELAY=1.0

# ── Quality ───────────────────────────────────────────
READABILITY_CHECK=true    # LLM readability report after assembly

════════════════════════════════════════════════════════
 3. PREPROCESSOR  (preprocessor.py)
════════════════════════════════════════════════════════

Implement preprocess(filepath) → str:

  Step 1: Detect and fix encoding (try UTF-8, GBK, GB2312)
  Step 2: Normalize line endings (CRLF → LF)
  Step 3: Remove common web-novel noise:
          - Site headers/footers (e.g. "本章完", "求收藏", "推荐票")
          - Repeated chapter title lines (keep first only)
          - Blank lines > 2 consecutive → collapse to 2
          - Strip leading/trailing whitespace per line
  Step 4: Print preprocessing report:
          ┌──────────────────────────────────┐
          │ Preprocessor Report              │
          │ Encoding detected : UTF-8        │
          │ Lines removed     : 12           │
          │ Noise patterns    : 5 removed    │
          │ Final char count  : 8,432        │
          └──────────────────────────────────┘

════════════════════════════════════════════════════════
 4. SMART AUTO-CHUNKER  (chunker.py)
════════════════════════════════════════════════════════

Implement auto_chunk(text, max_chars=1800) → list[str]:

  Step 1: Split text into paragraphs by "\n\n"
  Step 2: Group consecutive paragraphs into chunks
          - Each chunk stays UNDER max_chars total
          - NEVER split mid-paragraph
          - NO overlap between chunks
  Step 3: If a single paragraph > max_chars:
          - Split at sentence endings (。！？) only
          - Still no overlap
  Step 4: Print chunk analysis before translating:
          ┌──────────────────────────────────┐
          │ Chunk Analysis                   │
          │ Total paragraphs : 42            │
          │ Total chunks     : 8             │
          │ Min chunk chars  : 890           │
          │ Max chunk chars  : 1798          │
          │ Avg chunk chars  : 1340          │
          └──────────────────────────────────┘

Remove any fixed line-count or overlap logic entirely.
CLI: --max-chars (overrides MAX_CHUNK_CHARS in .env)

════════════════════════════════════════════════════════
 5. TRANSLATION ENGINE  (translator.py)
════════════════════════════════════════════════════════

── 5A. SYSTEM PROMPT TEMPLATE ───────────────────────

All models use this shared prompt template:

  "You are an expert literary translator.
   Translate the following Chinese xianxia/cultivation
   novel text into Myanmar (Burmese).

   Rules:
   1. Preserve the narrator's tone, style, and emotion exactly
   2. Keep character names in Pinyin (罗青 → Luo Qing)
   3. Keep place names in Pinyin with Myanmar suffix
   4. Translate cultivation terms meaningfully with context
   5. Output ONLY the translated Myanmar text
   6. No commentary, no explanations, no notes"

── 5B. MODEL ADAPTERS ────────────────────────────────

Implement 5 adapter classes, all with translate_stream():

  OpenRouterTranslator:
    URL: https://openrouter.ai/api/v1/chat/completions
    Required headers:
      "HTTP-Referer": "https://github.com/novel-translator"
      "X-Title":      "Novel Translator"
    stream=True

  GeminiTranslator:
    URL: https://generativelanguage.googleapis.com/v1beta/
         models/{model}:streamGenerateContent?key={key}
    stream=True via SSE

  DeepSeekTranslator:
    URL: https://api.deepseek.com/chat/completions
    OpenAI-compatible, stream=True

  QwenTranslator:
    URL: https://dashscope.aliyuncs.com/compatible-mode/
         v1/chat/completions
    OpenAI-compatible, stream=True

  OllamaTranslator (LOCAL — no API key needed):
    URL: {OLLAMA_BASE_URL}/api/chat
    Model: OLLAMA_MODEL (e.g. qwen2.5:14b)
    stream=True
    No API key required — runs on local machine

── 5C. STREAMING — Live Terminal Preview ─────────────

Each translate_stream() must:
  - Yield tokens as they arrive from API
  - Main loop prints: print(token, end="", flush=True)
  - After chunk done: print newline + char count

Terminal output per chunk:
  ──────────────────────────────────────────────
  [2/8] Translating • 1340 chars • openrouter
  ──────────────────────────────────────────────
  ရှေးခေတ် လမ်းကြောင်းပေါ်တွင် လော့ချင်းသည်...
  ကောင်းကင်ဘုံမှ နတ်ဘုရားများ ချင်ပြိုင်နေကြ...
  ✓ Done — 892 Myanmar chars written

════════════════════════════════════════════════════════
 6. CHECKPOINT SYSTEM
════════════════════════════════════════════════════════

Implement CheckpointManager class:
  checkpoint_dir = working_data/checkpoints/{chapter_name}/

  save(chunk_index, translated_text):
    → write chunk_{index:03d}.txt (UTF-8)

  load_all() → dict[int, str]:
    → read all existing checkpoint files

  is_done(chunk_index) → bool

  clear_all():
    → delete checkpoint folder after final assembly

Before each chunk:
  - If checkpoint exists → skip, reuse, print:
    [3/8] ✓ Checkpoint found — skipping

On resume (re-run same file):
  ┌─────────────────────────────────────────┐
  │ Resume detected!                        │
  │ Chunks already done : 3 / 8            │
  │ Continuing from     : chunk 4           │
  └─────────────────────────────────────────┘

════════════════════════════════════════════════════════
 7. POSTPROCESSOR  (postprocessor.py)
════════════════════════════════════════════════════════

Implement postprocess(text, names_json_path) → str:

  A) Punctuation fixes:
     "。" → "။"       "，" → "၊"
     "！" → "!"       "？" → "?"
     Collapse 3+ blank lines → 2
     Strip trailing whitespace per line

  B) Character name consistency:
     Load names.json:
       {"罗青": "လော့ချင်း", "小六子": "ရှောက်လျောက်"}
     Replace all variant spellings → canonical name
     Print fix report:
       ✓ 罗青 → လော့ချင်း  (12 occurrences fixed)
       ✓ 小六子 → ရှောက်လျောက် (4 occurrences fixed)

  C) Cleanup:
     Warn if any Chinese characters remain in output:
       ⚠ WARNING: 3 Chinese chars still found (line 14, 28, 55)
     Normalize Myanmar zero-width spaces

════════════════════════════════════════════════════════
 8. READABILITY CHECK
════════════════════════════════════════════════════════

Only if READABILITY_CHECK=true in .env.
Run ONCE after full assembly — NOT per chunk.

Call LLM with:
  System: "You are a Myanmar language editor."
  User:
    "Review this Myanmar translation excerpt and list:
     1. Unnatural sentence flow
     2. Missing Myanmar particles (တဲ့၊ပဲ၊တော့)
     3. Repeated awkward phrasing
     Return max 10 bullet points only. Be concise."

Print to terminal (do NOT auto-fix — human review only):
  ⚠ Readability Report:
    • Line 23: Particle missing after verb
    • Line 67: Repetitive sentence start pattern

Save report to: working_data/logs/{chapter}_readability.txt

════════════════════════════════════════════════════════
 9. ASSEMBLER  (assembler.py)
════════════════════════════════════════════════════════

Load templates/chapter_template.md and fill:

  # {original_title} — မြန်မာဘာသာပြန်
  **အခန်း**  : {chapter_number}
  **မော်ဒယ်** : {model_name}
  **ရက်စွဲ**  : {date}

  ---

  {translated_content}

  ---
  *ဤဘာသာပြန်ချက်ကို AI ဖြင့် ဘာသာပြန်ထားပါသည်။*

Save to: translated_novels/{chapter_name}_myanmar.md
After save: clear working_data/checkpoints/{chapter_name}/

════════════════════════════════════════════════════════
 10. ORCHESTRATOR  (main.py)
════════════════════════════════════════════════════════

Auto-scan input_novels/ for .txt files and process each:

  For each .txt file found:
    1. preprocess()         → clean text
    2. auto_chunk()         → smart paragraph chunks
    3. translate_stream()   → live preview per chunk
    4. checkpoint.save()    → after each chunk
    5. postprocess()        → punctuation + names
    6. readability_check()  → once, if enabled
    7. assemble()           → final .md

  Progress bar per chapter:
    Translating: chapter_001 [████████░░] 6/8 chunks

  Per-run log saved to:
    working_data/logs/{chapter}_{timestamp}.log

  Completion summary:
    ╔═════════════════════════════════════════╗
    ║         Translation Complete!           ║
    ║ Chapter   : 古道仙鸿_chapter_001        ║
    ║ Model     : openrouter (gemini-flash)   ║
    ║ Chunks    : 8 / 8                       ║
    ║ Time      : 2m 34s                      ║
    ║ Output    : translated_novels/          ║
    ║             chapter_001_myanmar.md      ║
    ╚═════════════════════════════════════════╝

════════════════════════════════════════════════════════
 11. CLI INTERFACE
════════════════════════════════════════════════════════

# Auto-scan and translate all files in input_novels/
python main.py

# Single file
python main.py input_novels/chapter_001.txt

# Switch model
python main.py --model openrouter
python main.py --model gemini
python main.py --model deepseek
python main.py --model ollama

# Chunking
python main.py --max-chars 1500

# Resume from checkpoint
python main.py --resume

# Skip readability check
python main.py --no-readability

# Custom names map
python main.py --names names.json

════════════════════════════════════════════════════════
 12. REQUIREMENTS.TXT
════════════════════════════════════════════════════════

requests>=2.31.0
python-dotenv>=1.0.0
tqdm>=4.66.0
flake8>=7.0.0
pylint>=3.0.0
pytest>=8.0.0

════════════════════════════════════════════════════════
 13. QUALITY TOOLS
════════════════════════════════════════════════════════

Add Makefile shortcuts:
  make lint     → runs flake8 + pylint on all .py files
  make test     → runs pytest tests/
  make run      → python main.py
  make resume   → python main.py --resume
```