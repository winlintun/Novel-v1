# ဝတ္ထုဘာသာပြန် Pipeline (Novel Translation Pipeline)

AI စွမ်းအင်သုံး အင်္ဂလိပ်/တရုတ် → မြန်မာ ဝတ္ထုဘာသာပြန်စနစ်။ Local LLM (Ollama) ကို အသုံးပြု၍ Xianxia, Wuxia, Fantasy ဝတ္ထုများကို အရည်အသွေးမြင့် ဘာသာပြန်ဆိုနိုင်ရန် တည်ဆောက်ထားပါသည်။

---

## 📖 Project ခြုံငုံသုံးသပ်ချက်

ဤ project သည် **အင်္ဂလိပ် (EN) နှင့် တရုတ် (CN) ဘာသာစကား** နှစ်မျိုးလုံးမှ **မြန်မာဘာသာ (MM)** သို့ ဝတ္ထုများကို ဘာသာပြန်ဆိုနိုင်သော production-grade system တစ်ခုဖြစ်သည်။

**အဓိကအင်္ဂါရပ်များ:**

- **Multi-language support**: EN→MM (way1) နှင့် CN→EN→MM (way2) ဘာသာပြန်လမ်းကြောင်း ၂ မျိုး
- **Auto-detection**: Input ဖိုင်၏ ဘာသာစကားကို auto-detect လုပ်၍ သင့်တော်သော workflow ကို အလိုအလျောက် ရွေးချယ်ခြင်း
- **8-stage pipeline**: Preprocess → Translate → Refine → Reflect → Quality → Consistency → FictionEditor → QA
- **3-tier memory**: Glossary (ဝေါဟာရ) + Context (အကြောင်းအရာ) + Session (အစည်းအဝေး) memory စနစ်
- **Per-novel glossary**: ဝတ္ထုတစ်ပုဒ်ချင်းစီအတွက် သီးသန့် glossary term များ
- **Quality gates**: Myanmar ratio ≥ 70%, quality score ≥ 70/100, fluency scorer
- **Flask Web UI**: Dashboard, Translate, Editor, Reader, Cleanup ပါဝင်သော graphical interface
- **Version Control**: Chapter snapshot, rollback, diff, glossary sync job
- **Audit Logging**: ပြောင်းလဲမှုမှန်သမျှကို ခြေရာခံနိုင်ခြင်း
- **LoRA Fine-tuning**: လူသားအဆင့်သတ်မှတ်ထားသော translation pair များဖြင့် model ကို fine-tune လုပ်နိုင်ခြင်း
- **SQLite Database**: ၁၀ ခုသော table များဖြင့် structured data storage
- **RAG Retrieval**: ChromaDB + SQLite semantic retrieval for few-shot translation examples

---

## ⚙️ Installation (တပ်ဆင်ခြင်း)

### Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com/) (local LLM server)
- 16GB+ RAM (သို့) GPU with 8GB+ VRAM

### Steps

```bash
# 1. Clone repository
git clone <repository-url>
cd novel_translation_project

# 2. Python virtual environment ဖန်တီးပါ
python3 -m venv venv
source venv/bin/activate  # Linux/Mac

# 3. Dependencies တပ်ဆင်ပါ
pip install -r requirements.txt

# 4. Ollama ကို install လုပ်ပါ (https://ollama.com)
# Ollama ကို background service အဖြစ် run ထားရန် လိုအပ်ပါသည်။

# 5. Myanmar translation model များကို pull လုပ်ပါ
ollama pull padauk-gemma:q8_0     # PRIMARY Myanmar model (RECOMMENDED)

# 6. Optional models
ollama pull alibayram/hunyuan:7b  # CN→EN pivot (way2 အတွက်)
ollama pull qwen:7b               # Validation/checking အတွက်

# 7. Project structure ကို verify လုပ်ပါ
python -m src.main --test
```

### Hardware Requirements (Model အလိုက် VRAM အကြမ်းဖျင်း)

| Model | VRAM ခန့်မှန်း |
|---|---|
| padauk-gemma:q8_0 | ~8 GB |
| sailor2-20b:latest | ~11 GB |
| sailor2:8b | ~6 GB |
| yxchia/seallms-v3-7b:Q4_K_M | ~5 GB |
| alibayram/hunyuan:7b | ~5 GB |
| qwen:7b | ~5 GB |

---

## 🔧 Configuration (ပြင်ဆင်သတ်မှတ်ခြင်း)

### Main Config Files

| File | Description |
|---|---|
| `config/settings.yaml` | Default config (EN→MM direct, padauk-gemma) |
| `config/settings.pivot.yaml` | CN→EN→MM pivot (hunyuan:7b + padauk-gemma) |
| `config/settings.fast.yaml` | Fast mode config |
| `config/models.skeleton.yaml` | Model selection config (Web UI အတွက်) |

### settings.yaml Structure

```yaml
# Model settings
models:
  translator: "padauk-gemma:q8_0"   # Translation model
  editor: "padauk-gemma:q8_0"       # Editing/refinement model
  refiner: "padauk-gemma:q8_0"      # Refinement model
  checker: "padauk-gemma:q8_0"      # Quality checker model
  provider: "ollama"                 # LLM provider
  timeout: 300                       # API timeout (seconds)

# Pipeline settings
translation_pipeline:
  mode: "single_stage"               # single_stage | lite | fast | full | two_stage

# Processing
processing:
  chunk_size: 1200                   # Characters per chunk
  temperature: 0.2                   # Model temperature (padauk-gemma ≤ 0.2)
  repeat_penalty: 1.3                # Repetition penalty
  max_retries: 2                     # Max retry attempts

# Storage
storage:
  backend: "sqlite"                  # json | sqlite
  db_path: "data/novel_translation.db"

# Quality gates
myanmar_readability:
  enabled: true
  min_myanmar_ratio: 0.70            # 70% Myanmar characters required
```

### Skeleton Model Config

Web UI နှင့် CLI အတွက် model ကို `config/models.skeleton.yaml` တွင် ရွေးချယ်နိုင်သည်။

```yaml
active_model: padauk-gemma-q8        # Default model key

models:
  padauk-gemma-q8:
    name: padauk-gemma:q8_0
    temperature: 0.2
    max_tokens: 4096
    repeat_penalty: 1.3
    chunk_size: 2500
```

CLI မှတစ်ဆင့် model ကို override လုပ်ရန်:
```bash
python -m src.main --novel wayfarer --chapter 1 --model qwen:7b
```

---

## 🖥️ CLI Usage (Command Line အသုံးပြုပုံ)

### Translation Commands

```bash
# Chapter တစ်ခုတည်း ဘာသာပြန်ရန်
python -m src.main --novel wayfarer --chapter 1

# Chapter အားလုံး ဘာသာပြန်ရန်
python -m src.main --novel reverend-insanity --all

# Chapter အပိုင်းအခြား ဘာသာပြန်ရန်
python -m src.main --novel wayfarer --chapter-range 21-35

# Chapter N မှစ၍ အကုန်ဘာသာပြန်ရန်
python -m src.main --novel reverend-insanity --all --start 10

# Workflow ကို explicitly သတ်မှတ်ရန်
python -m src.main --novel wayfarer --chapter 1 --workflow way1     # EN→MM
python -m src.main --novel novel --chapter 1 --lang zh              # CN→MM auto

# Config file သတ်မှတ်ရန် (way2 pivot)
python -m src.main --novel novel --chapter 1 --config config/settings.pivot.yaml

# Pipeline mode သတ်မှတ်ရန်
python -m src.main --novel novel --chapter 1 --mode single_stage    # 1-stage (recommended)
python -m src.main --novel novel --chapter 1 --mode lite            # 3-stage
python -m src.main --novel novel --chapter 1 --mode full            # 6-stage
python -m src.main --novel novel --chapter 1 --mode fast            # 2-stage
```

### Quality & Review Commands

```bash
# ဘာသာပြန်ပြီးသား .mm.md ဖိုင်ကို quality review လုပ်ရန်
python -m src.main --review data/output/wayfarer/wayfarer_chapter_001.mm.md

# ဘာသာပြန်ပြီးသားဖိုင်ကို terminal မှကြည့်ရန်
python -m src.main --view data/output/wayfarer/wayfarer_chapter_001.mm.md

# Chapter အလိုက် quality score trends ကြည့်ရန်
python -m src.main --stats --novel wayfarer

# Metadata ပြန်တည်ဆောက်ရန်
python -m src.main --novel wayfarer --rebuild-meta
```

### Glossary Commands

```bash
# Glossary generate လုပ်ရန်
python -m src.main --novel wayfarer --generate-glossary --chapter-range 1-5

# Initial glossary generate → human review အတွက် stop
python -m src.main --novel wayfarer --init-glossary

# Pending terms အားလုံးကို approve လုပ်ရန်
python -m src.main --novel wayfarer --approve-glossary

# High-confidence terms များကို auto-promote လုပ်ရန်
python -m src.main --novel wayfarer --auto-promote
```

### Fine-tuning & Training

```bash
# Rejected chunks များကို interactive ဖြင့် rate လုပ်ရန်
python -m src.main --rate-rejected --novel outside-of-time

# LoRA adapter ကို fine-tune လုပ်ရန်
python -m src.main --finetune --novel outside-of-time
```

### Model Comparison

```bash
# Chapter တစ်ခုတည်းကို model အားလုံးနှင့် ဘာသာပြန်ပြီး နှိုင်းယှဉ်ရန်
python -m src.main --novel sample --chapter 1 --compare-models
```

### Database Migration

```bash
# JSON → SQLite migration
python -m src.main --migrate-sql --novel wayfarer

# SQLite backend ကို explicitly သုံးရန်
python -m src.main --novel wayfarer --chapter 1 --use-sql
```

### Other Utilities

```bash
# Test run
python -m src.main --test

# Python cache ရှင်းလင်းရန်
python -m src.main --clean
# Or: ./clean_run.sh

# Version ကြည့်ရန်
python -m src.main --version
```

---

## 🌐 Web UI Usage

Flask-based Web UI ကိုအောက်ပါအတိုင်း launch လုပ်နိုင်သည်။

```bash
# Default port 5000
python -m src.main --ui

# Explicit port
python -m src.main --flask --port 8080
```

Web UI တွင် အောက်ပါ page များ ပါဝင်သည်။

| Page | Function |
|---|---|
| **Dashboard** | Translation history, quality stats, progress |
| **Translate** | Novel/chapter ရွေးချယ်၍ ဘာသာပြန်ခြင်း |
| **Editor** | ဘာသာပြန်ပြီးသား စာသားများကို ပြင်ဆင် / ပြန်လည်သုံးသပ်ခြင်း |
| **Reader** | ဘာသာပြန်ပြီးသား ဝတ္ထုကို chapter အလိုက်ဖတ်ရှုခြင်း |
| **Glossary** | Glossary terms များကို စီမံခန့်ခွဲခြင်း |
| **Settings** | Model, Config, Database settings များ |
| **Cleanup** | Cache နှင့် temporary files ရှင်းလင်းခြင်း |

---

## 📊 Pipeline Stages (ဘာသာပြန်လုပ်ငန်းစဉ်)

### way1: EN→MM Direct (အင်္ဂလိပ်→မြန်မာ တိုက်ရိုက်)

```
Input (.md) → [Preprocess] → [Translate] → [Refine] → [Quality] → Output (.mm.md)
```

| Stage | Agent | Description |
|---|---|---|
| 1. **Preprocess** | `preprocessor.py` | Markdown cleaning, paragraph chunking (smart_chunk), language detection |
| 2. **Translate** | `translator.py` | Glossary injection, rolling context, chunk-by-chunk translation via Ollama |
| 3. **Refine** (optional) | `refiner.py` | Literary quality editing, SVO→SOV conversion |
| 4. **Reflect** (optional) | `reflection_agent.py` | Self-correction, error detection and fixing |
| 5. **Quality** | `myanmar_quality_checker.py` | Myanmar ratio check, fluency scoring, linguistic validation |
| 6. **Consistency** | `checker.py` | Glossary consistency verification |
| 7. **FictionEditor** | `fiction_editor.py` | 6 tone presets (humanize, dramatic, casual, literary, action, romantic) |
| 8. **QA Review** | `qa_tester.py` | Final quality assurance, full validation |

### way2: CN→EN→MM Pivot (တရုတ်→အင်္ဂလိပ်→မြန်မာ)

| Stage | Model | Description |
|---|---|---|
| 1. **CN→EN Pivot** | `alibayram/hunyuan:7b` | Chinese → English intermediate translation |
| 2. **EN→MM** | `padauk-gemma:q8_0` | English → Myanmar final translation |
| 3-8 | Same as way1 | Remaining pipeline stages |

### Pipeline Modes

| Mode | Stages | Description |
|---|---|---|
| `single_stage` | Translate only | **RECOMMENDED** — padauk-gemma အတွက် အကောင်းဆုံး |
| `lite` | Translate → Refine → Quality | 3-stage balanced mode |
| `fast` | Translate → Quality | Fastest, skip refinement |
| `full` | All 6+ stages | Maximum quality (slower) |
| `two_stage` | Stage1 → Stage2 (pivot) | CN→EN→MM အတွက် |

### Chunking System

Paragraph အလိုက် smart chunking ကို `src/utils/chunker.py` မှ ဆောင်ရွက်သည်။

- **Overlap = 0** (paragraph duplication ကို လုံးဝရှောင်ရှားရန်)
- **Split only at `\n\n`** (paragraph boundaries)
- **Max tokens**: 1500 (default, configurable)

---

## 📚 Glossary System (ဝေါဟာရစနစ်)

### Architecture

```
MemoryManager (Single Gateway)
    ├── Tier 1: Per-novel Glossary
    ├── Tier 2: Chapter Context (FIFO sliding window)
    ├── Tier 3: Session Rules (Dynamic corrections)
    └── Optional: Universal Blueprint (READ-ONLY reference)
```

### Glossary Lifecycle

1. **Extraction**: `GlossaryGenerator` က chapter များမှ term များကို extract လုပ်သည်
2. **Pending**: Term အသစ်များသည် pending state တွင် ရောက်ရှိသည်
3. **Approval**: CLI (`--approve-glossary`) သို့ Web UI မှ approve လုပ်နိုင်သည်
4. **Injection**: Translator က MemoryManager မှ term များကို top 20 ထိ prompt တွင် inject လုပ်သည်
5. **Tracking**: `ContextUpdater` က term usage ကို chapter အလိုက်ခြေရာခံသည်

### MemoryManager Key Methods

```python
add_term(source, target, category, chapter)     # Add approved term
add_pending_term(source, target, category, ch)  # Add pending term
get_term(source)                                 # Lookup term → "【?source?】" if missing
get_top_n(n=20)                                  # Get top N terms for prompt injection
bulk_approve_all_pending()                       # Approve all pending terms
auto_approve_by_confidence(threshold=0.85)       # Auto-approve high confidence terms
```

### Data Categories

| Category | Example |
|---|---|
| `character` | 罗青 → လော်ချင်, 方源 → ဖန်ယွမ် |
| `place` | 小戎镇 → ရှောင်ရုံမြို့, 青竹山 → ချင်းကျူးတောင် |
| `level` | 筑基 → ကျူးကျီ, 金丹 → ကျင့်တန်း |
| `item` | 飞剑 → ပျံသန်းဓား, 丹药 → ဆေးလုံး |

---

## ✅ Quality System (အရည်အသွေးစနစ်)

### Quality Gates

```
Score ≥ 70  → PASS (auto-advance)
Score 50-69 → RETRY (max 2x, lower temperature + reinject rules)
Score ≤ 49  → STOP (alert user)
```

### Quality Checks

| Check | Description |
|---|---|
| Myanmar ratio ≥ 70% | မြန်မာစာလုံးအချိုး 70% ရှိရမည် |
| Chinese script leakage = 0 | တရုတ်စာလုံးများ မပါဝင်ရ |
| Bengali/Indic script = 0 | Indic script ၉ မျိုး လုံးဝမပါဝင်ရ |
| Thai/Khmer script = 0 | ထိုင်း/ခမာ စာလုံးများ မပါဝင်ရ |
| Placeholder guard | 【?term?】 tokens များကို မပြောင်းလဲရ |
| Paragraph duplication | Chunk နှစ်ခုကြား paragraph duplication မရှိရ |
| Markdown preservation | Headers, bold, italic, lists, quotes ပျက်မသွားရ |
| SVO→SOV conversion | အင်္ဂလိပ် SVO structure မကျန်ရစ်ရ |
| Archaic words check | သင်သည်/ဤ/ထို မပါဝင်ရ (မင်း/ဒီ/အဲဒီ သုံးရန်) |
| Particle repetition | တူညီသော particle တစ်ခုကို paragraph တွင် ≤ 2 ကြိမ်သာ |

### Fluency Scorer (7 Dimensions)

`src/utils/fluency_scorer.py` မှ reference-free fluency scoring ကို ဆောင်ရွက်သည်။

| Dimension | Description |
|---|---|
| F1: Lexical Diversity | Type-Token Ratio (TTR) |
| F2: Particle Diversity | မြန်မာဝါကျဖွဲ့ဆက်မှု ကွဲပြားမှု |
| F3: Sentence Flow | Sentence length variance + proper break punctuation |
| F4: Syllable Richness | Compound word density |
| F5: Paragraph Rhythm | Paragraph length variance |
| F6: Punctuation Health | Proper use of ။ and ၊ |
| F7: Repetition Penalty | Consecutive identical particle/word penalty |

---

## 🎯 Model Warnings (အရေးကြီးသော Model သတိပေးချက်များ)

### ✅ Proven Myanmar Output Models

| Model | Works? | Use Case | Temperature |
|---|---|---|---|
| `padauk-gemma:q8_0` | ✅ **PRIMARY** | EN→MM, CN→MM (direct) | ≤ 0.2 |
| `sailor2-20b:latest` | ✅ Alternative | EN→MM, CN→MM | ≤ 0.35 |

### ❌ Models That FAIL for Myanmar Output

| Model | Problem |
|---|---|
| `sailor2:8b` | **FAILED** — Myanmar ratio 11-55% (required 70%). Outputs English instead of Myanmar. |
| `qwen2.5:14b` | Outputs Chinese/Japanese, NOT Myanmar. Use for CN→EN pivot only. |
| `qwen:7b` | Outputs English, NOT Myanmar. Use for validation/checking only. |

### ⚠️ Pivot Models (CN→EN Only)

| Model | Use |
|---|---|
| `alibayram/hunyuan:7b` | CN→EN pivot Stage 1. Does NOT output Myanmar. |
| `qwen2.5:14b` | CN→EN only. Does NOT output Myanmar. |

### 🔴 Critical: Padauk-Gemma Temperature Rule

> **padauk-gemma:q8_0** ၏ temperature ကို **0.2 ထက်မကျော်ရပါ။**
> Temperature > 0.2 ဆိုပါက glossary-comparison garbage output များ ထွက်လာပြီး translation quality ပျက်စီးသွားပါမည်။

---

## 📁 Directory Structure (အဓိကဖိုင်များ)

```
novel_translation_project/
├── config/                      # Configuration files
├── data/
│   ├── input/{novel}/           # Source chapter files (*.md)
│   └── output/{novel}/          # Translated output
├── src/
│   ├── main.py                  # Entry point
│   ├── cli/                     # CLI modules
│   ├── agents/                  # Translation agents
│   ├── pipeline/                # Pipeline orchestrator
│   ├── memory/                  # MemoryManager, VersionManager
│   ├── utils/                   # Ollama, File I/O, Chunker, Postprocessor
│   ├── web/                     # Flask Web UI
│   └── training/                # Fine-tuning scaffold
├── tests/                       # 440+ tests
├── logs/                        # Translation logs, quality reports
├── requirements.txt
└── README.md
```

---

## 🐛 Troubleshooting (အဖြစ်များသော Error များ)

### 1. Ollama ကို Run မထားပါက

```
Error: Could not connect to Ollama at http://localhost:11434
```

**Solution:** `ollama serve` ဖြင့် Ollama ကို run ပါ။

### 2. Low Myanmar Ratio

```
Error: Myanmar ratio 45% is below threshold 70%
```

**Solutions:**
- `padauk-gemma:q8_0` model ကိုသာ သုံးပါ
- Temperature ကို 0.2 သို့လျှော့ပါ
- `--mode single_stage` ကိုသုံးပါ

### 3. Database Lock Error

```
Error: database is locked
```

**Solution:** အခြား process မှ database ကိုသုံးနေခြင်းမရှိစေရန် စစ်ဆေးပါ။ System က 30 စက္ကန့်အထိ auto-retry လုပ်ပေးသည်။

### 4. Ollama OOM

```
Error: Ollama process killed (OOM)
```

**Solutions:** Chunk size ကို 800 သို့လျှော့ပါ။ ပိုသေးသော model ကိုသုံးပါ။ `--unload-after-chapter` flag ကိုသုံးပါ။

---

## 🧪 Testing (စမ်းသပ်ခြင်း)

```bash
# Test အားလုံး run ရန် (440+ tests passing)
pytest tests/ -v --tb=short

# Specific test file
pytest tests/test_translator.py -v
pytest tests/test_postprocessor.py -v

# Coverage with report
pytest tests/ --cov=src --cov-report=term-missing
```

---

## 🔒 Stability Rules

1. **NO CRASHES**: Ollama call အားလုံးတွင် timeout + retry + exception handling ပါရှိရမည်
2. **NO HIDDEN STATE BUGS**: State အားလုံးသည် MemoryManager တစ်ခုတည်းမှသာ flow လုပ်ရမည်
3. **NO HANGING REQUESTS**: Retry loop အားလုံးတွင် hard maximum iteration count ရှိရမည်

---

> **Note:** CLI flags, file paths, model names များသည် project ၏ လက်ရှိ source code ပေါ်တွင် အခြေခံထားပါသည်။
