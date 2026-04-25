# Novel Translation Pipeline — Complete Guide

> **Project:** [Novel-v1](https://github.com/winlintun/Novel-v1)
> **Hardware:** Ryzen 7 5700X · 16GB RAM · AMD RX 580 (CPU-only, ROCm unsupported)
> **Target:** Chinese/English → Myanmar (Burmese) Wuxia/Xianxia novel translation

---

## 1. System Overview

Novel-v1 သည် Chinese သို့မဟုတ် English Wuxia/Xianxia ဝတ္ထုများကို Myanmar ဘာသာသို့ ဘာသာပြန်ပေးသော AI-powered pipeline တစ်ခုဖြစ်သည်။ Local Ollama models များကို အသုံးပြု၍ **chapter တစ်ခုချင်းစီ** ဘာသာပြန်သည်။ တစ်ကြိမ်တည်း chapters အားလုံး batch လုပ်မဘာသာပြန်ပါ။

### Hardware မှတ်ချက်

| Item | Spec | Impact |
|------|------|--------|
| CPU | Ryzen 7 5700X (16 threads) | `num_thread: 14` သတ်မှတ် |
| RAM | 16GB | 7B models သာ အသင့်တော်ဆုံး |
| GPU | RX 580 (GCN4/Polaris) | ROCm မ support — CPU-only run |

> ⚠️ **14B model (qwen2.5:14b) ကို CPU-only 16GB RAM တွင် run မဖြစ်နိုင်** — disk swap ဖြစ်ပြီး chapter တစ်ခုကို 5+ နာရီ ကြာနိုင်သည်။ 7B models သာ သုံးပါ။

---

## 2. ဘာသာပြန်ပုံ — Pipeline Architecture

### 2.1 Memory System (3-Tier)

Pipeline စတင်သောအခါ `src/main.py` သည် memory system ၃ ထပ်ကို load လုပ်သည်။

```
Tier 1 — Glossary       : data/glossary.json          (အတည်ပြုပြီး term database)
Tier 2 — Context        : data/context_memory.json     (chapter progress tracking)
Tier 3 — Session Rules  : Runtime only                 (ယခု session အတွက်သာ)
```

**Rules:**
- Agent တိုင်း data ကို `MemoryManager` မှတစ်ဆင့်သာ ဖတ်ရမည်
- `glossary.json` ကို direct access မလုပ်ရ
- Unknown term → `【?term?】` placeholder — guess မလုပ်ရ

### 2.2 Preprocessor

Chinese/English text ကို clean လုပ်ပြီး chunks ဖြတ်သည်။

```yaml
chunk_size:   1200   # 7B model safe range (3000 → repetition loop ဖြစ်တယ်)
overlap_size: 100    # Context continuity အတွက် sliding window
```

---

## 3. 4-Stage Agent Pipeline

```
Input Chapter
     │
     ▼
┌─────────────────────────────────┐
│  Stage 1 — Translator           │
│  Chinese/English → Myanmar      │
│  (Literal, accurate)            │
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│  Stage 2 — Editor (Refiner)     │
│  Literary rewrite               │
│  (Natural flow, tone, SOV)      │
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│  Stage 3 — Consistency Checker  │
│  Glossary cross-check           │
│  (Name/place/term verification) │
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│  Stage 4 — QA / Final Reviewer  │
│  Logical flow + tone check      │
│  APPROVED / NEEDS_REVISION      │
└────────────────┬────────────────┘
                 │
                 ▼
         Output Chapter
    data/output/<novel>/<chapter>_mm.md
```

### Stage 1 — Translator Agent

**Goal:** Accurate, literal translation. SVO → SOV structure conversion.

**Rules:**
- Glossary terms ကို exact အတိုင်း သုံးရမည်
- Previous context ဖတ်ပြီး pronoun resolve လုပ်ရမည်
- Unknown term → `【?term?】`
- `<think>`, `<answer>` tags — output မထွက်ရ

### Stage 2 — Editor (Refiner) Agent

**Goal:** Natural Myanmar literary prose ဖြစ်အောင် rewrite လုပ်ခြင်း။

**Rules:**
- SOV structure + particles (သည်/ကို/မှာ/အတွက်) မှန်ကန်ရမည်
- Dialogue: `မင်း`, `ဒီ`, `တဲ့` — natural spoken Myanmar
- Emotions: abstract မဟုတ်ဘဲ physical sensation ဖြင့် ဖော်ပြ
- Long sentences → 2-3 short rhythmic sentences ဖြတ်ပါ

**ဥပမာ:**

| မှားသော နည်း ❌ | မှန်သော နည်း ✅ |
|---------------|---------------|
| သူသည် အလွန်ဝမ်းနည်းသည်ကို ခံစားနေသည် | သူ့ရင်ထဲ တစ်ခုခု နာကျင်နေသလိုပဲ။ မျက်ရည်တွေ စီးကျလာတယ်။ |
| "သင်သည် ဘာကြောင့် ဒီသို့ ရောက်ရှိလာသနည်း" | "မင်း ဘာကြောင့် ဒီကို လာတာလဲ" |

### Stage 3 — Consistency Checker Agent

**Goal:** Glossary နှင့် term consistency စစ်ဆေးခြင်း။

**Output format:**
```
CORRECTIONS: [mismatch list or "None"]
FINAL TEXT:  [corrected Myanmar text]
```

### Stage 4 — QA / Final Reviewer Agent

**Goal:** Final quality gate — logic, tone, completeness စစ်ဆေးခြင်း။

**Output format:**
```
STATUS:     [APPROVED / NEEDS_REVISION]
ISSUES:     [list or "None"]
FINAL TEXT: [Myanmar text]
```

---

## 4. Post-Processing & Term Extraction

Chapter ဘာသာပြန်ပြီးသောအခါ —

1. **Postprocessor** (`src/utils/postprocessor.py`) run သည်:
   - `<think>`, `<answer>`, HTML comments strip လုပ်သည်
   - Thai/Chinese character leakage detect လုပ်သည်
   - Myanmar ratio ≥ 70% ဖြစ်မဖြစ် validate လုပ်သည်

2. **Term Extractor** (`src/agents/context_updater.py`) run သည်:
   - Translation ထဲမှ new proper nouns scan လုပ်သည်
   - `data/glossary_pending.json` သို့ routing လုပ်သည် (glossary.json ထဲ တိုက်ရိုက် မသွင်း)
   - Human review ကျပ်မှသာ main glossary merge လုပ်သည်

---

## 5. ဘာကြောင့် Direct Translation ဆိုးတာလဲ — Pivot Language Solution

### ပြဿနာ (qwen2.5:14b direct CN→MM)

| Test | Myanmar % | ပြဿနာ |
|------|-----------|-------|
| ပထမကြိုးစားမှု | 22% | 69% Chinese ကျန်ခဲ့သည် |
| Fix လုပ်ပြီး | 55.8% | English words ယိုထွက်, repetition loop |

**Root cause:** Local 7B/14B models တွင် Chinese→Myanmar direct training data မရှိ — model က Chinese ကို Myanmar သို့ ဘာသာပြန်နည်းကို မသိ။

### Solution — Pivot Language (English as Bridge)

```
Chinese Input
     │
     ▼
[Stage 1: hunyuan:7b]         Chinese → English
     │                        (Tencent Chinese-native model)
     ▼
English (Pivot)
     │
     ▼
[Stage 2: seallms-v3-7b]      English → Myanmar
     │                        (SEA language specialist)
     ▼
Myanmar Output ✅
```

**ဘာကြောင့် ဒီနည်းလမ်း ကောင်းတာလဲ:**

| Model | Strength | Role |
|-------|----------|------|
| `alibayram/hunyuan:7b` | Tencent Chinese-native, CN→EN ~95% accuracy | Stage 1 |
| `yxchia/seallms-v3-7b:Q4_K_M` | SEA 8 languages trained, Myanmar specialist | Stage 2 |
| `qwen:7b` | Fast, rule-following, structured output | Stage 3 + 4 |

---

## 6. Chinese → Myanmar Translation Setup

### `config/settings.fast.yaml`

```yaml
translation_pipeline:
  mode: "two_stage"

  # Stage 1: Chinese → English (pivot)
  stage1_model: "ollama:alibayram/hunyuan:7b"
  stage1_source_lang: "chinese"
  stage1_target_lang: "english"

  # Stage 2: English → Myanmar
  stage2_model: "ollama:yxchia/seallms-v3-7b:Q4_K_M"
  stage2_source_lang: "english"
  stage2_target_lang: "myanmar"

models:
  translator: "alibayram/hunyuan:7b"
  editor:     "yxchia/seallms-v3-7b:Q4_K_M"
  checker:    "qwen:7b"
  ollama_base_url: "http://localhost:11434"

processing:
  chunk_size:     1200
  overlap_size:   100
  temperature:    0.45
  repeat_penalty: 1.3     # prevents repetition loops — critical
  top_p:          0.92
  top_k:          50
  num_thread:     14      # Ryzen 7 5700X (16 threads, leave 2 for OS)
  num_ctx:        4096
```

### Stage 1 — Translator Prompt (Chinese → English)

```
You are an expert Chinese-to-English translator for Wuxia/Xianxia novels.

RULES:
1. Translate Chinese text to natural English prose.
2. Keep character names as Chinese Pinyin (e.g. 罗青 → Luo Qing).
3. Preserve all Markdown formatting.
4. Do NOT output <think>, <answer>, or any tags.
5. OUTPUT: English text only. Zero explanations.

INPUT (Chinese):
{input_text}
```

### Stage 2 — Editor Prompt (English → Myanmar)

```
CRITICAL LANGUAGE RULE:
- Output: Myanmar Unicode ONLY (U+1000–U+109F)
- FORBIDDEN: Thai, Chinese, English in output
- Do NOT output <think>, <answer> tags
- Unknown terms → 【?term?】

You are a Myanmar literary translator for Wuxia/Xianxia novels.

RULES:
1. Convert English SVO → Myanmar SOV structure naturally.
2. Use EXACT glossary terms for all names, places, cultivation terms.
3. Preserve ALL Markdown formatting.
4. Formal Myanmar for narrative. Natural spoken Myanmar for dialogue.
5. Particles: သည်/ကို/မှာ/အတွက်/ကဲ့သို့ — correct usage required.
6. OUTPUT: Myanmar text only. Zero explanations.

GLOSSARY:
{glossary}

PREVIOUS CONTEXT:
{context}

INPUT (English):
{english_text}
```

### CLI Command (Chinese Novel)

```bash
# Chapter တစ်ခုချင်းစီ ဘာသာပြန်
python -m src.main_fast --novel 古道仙鸿 --chapter 1
python -m src.main_fast --novel 古道仙鸿 --chapter 2

# Chapter 10 မှ ဆက်ဘာသာပြန်
python -m src.main_fast --novel 古道仙鸿 --all --start 10

# Memory cleanup ပါ run
python -m src.main_fast --novel 古道仙鸿 --all --unload-after-chapter
```

---

## 7. English → Myanmar Translation Setup

English novel ဆိုရင် **Stage 1 (pivot) မလိုတော့** — `seallms-v3-7b` တစ်ကောင်တည်း EN→MM direct ဘာသာပြန်နိုင်သည်။ Pipeline ပိုမြန်ပြီး quality ပိုကောင်းသည်။

### `config/settings.english.yaml`

```yaml
translation_pipeline:
  mode: "single_stage"     # English → Myanmar တစ်ဆင့်တည်းဘဲ လုံလောက်သည်

  stage1_model:       "ollama:yxchia/seallms-v3-7b:Q4_K_M"
  stage1_source_lang: "english"
  stage1_target_lang: "myanmar"

models:
  translator: "yxchia/seallms-v3-7b:Q4_K_M"
  editor:     "yxchia/seallms-v3-7b:Q4_K_M"
  checker:    "qwen:7b"
  ollama_base_url: "http://localhost:11434"

processing:
  chunk_size:     1500    # EN text ပိုတိုသောကြောင့် chunk ပိုကြီးနိုင်
  overlap_size:   100
  temperature:    0.45
  repeat_penalty: 1.3
  top_p:          0.92
  top_k:          50
  num_thread:     14
  num_ctx:        4096
```

### Stage 1 — Translator Prompt (English → Myanmar, Single Stage)

```
CRITICAL LANGUAGE RULE:
- Output: Myanmar Unicode ONLY (U+1000–U+109F)
- FORBIDDEN: Thai, Chinese, English in output
- Do NOT output <think>, <answer> tags
- Unknown terms → 【?term?】

You are an expert English-to-Myanmar literary translator for Wuxia/Xianxia novels.

RULES:
1. Convert English SVO → Myanmar SOV naturally. Do NOT translate word-by-word.
2. Use EXACT glossary terms for all names, places, cultivation terms.
3. Preserve ALL Markdown formatting (#, **, *, lists, quotes).
4. TONE:
   - Narrative: formal literary Myanmar (သည်, ၏, သော)
   - Dialogue: natural spoken Myanmar (မင်း, ဒီ, တဲ့, လဲ)
   - Adjust honorifics based on character status hierarchy.
5. Show emotions through physical sensation — not abstract labels.
6. Break long sentences into 2-3 short rhythmic Myanmar sentences.
7. OUTPUT: Myanmar text only. Zero explanations. Zero preamble.

GLOSSARY:
{glossary}

PREVIOUS CONTEXT (last 2 paragraphs):
{context}

INPUT (English):
{input_text}
```

### CLI Command (English Novel)

```bash
# Config file ကို english version သုံးဘာသာပြန်
python -m src.main_fast --novel my_english_novel --chapter 1 --config config/settings.english.yaml

# single_stage mode သတ်မှတ်ပြီး run
python -m src.main_fast --novel my_english_novel --chapter 1 --single-stage
```

---

## 8. Model Assignment Summary

| Stage | Chinese Novel | English Novel | Role |
|-------|---------------|---------------|------|
| Stage 1 | `hunyuan:7b` | `seallms-v3-7b` | Translation |
| Stage 2 | `seallms-v3-7b` | *(မလို)* | Literary edit |
| Stage 3 | `qwen:7b` | `qwen:7b` | Consistency check |
| Stage 4 | `qwen:7b` | `qwen:7b` | QA review |

---

## 9. Glossary System

### `data/glossary.json` — Schema (v3.0)

```json
{
  "glossary_version": "3.0",
  "novel_name": "古道仙鸿",
  "terms": [
    {
      "id": "term_001",
      "source_term": "罗青",
      "target_term": "လူချင်း",
      "aliases_cn": ["小孩童", "放牛娃"],
      "aliases_mm": ["လူချင်း"],
      "category": "person_character",
      "translation_rule": "transliterate",
      "do_not_translate": true,
      "verified": true,
      "source": "罗青",
      "target": "လူချင်း"
    }
  ]
}
```

### Chapter 001 — အတည်ပြုထားသော Characters

| Chinese | Myanmar | Category |
|---------|---------|----------|
| 罗青 | လူချင်း | Protagonist |
| 黄牛 / 牛哥 | နွားဖော်ကြီး / နွားကြီးဆေး | Animal companion |
| 方宗主 | ဖန်ဇုံပိုင် | Villain sect leader |
| 古堂主 | ဂူတန်မင်း | Villain hall master |
| 尊儿 | ဇွန်ရဲ | Child character |
| 小戎镇 / 小戎山 | ရှောင်ရုံးမြို့ / ရှောင်ရုံးတောင် | Setting |
| 魔教 / 圣教 | မာရ်ဂိုဏ်း | Demon faction |
| 道士 / 道长 | တာအိုဆရာတော် | Taoist cultivators |

### Naming Rules

| Type | Rule | Example |
|------|------|---------|
| Chinese names | Phonetic transliteration | 罗青 → လူချင်း |
| English names | Phonetic to Myanmar | "Lin Yuan" → လင်ယွန်း |
| Cultivation terms | Translate by meaning | 仙人 → နတ်သမား |
| Sect/Clan | Hybrid approach | 魔教 → မာရ်ဂိုဏ်း |
| Place names | Hybrid | 小戎镇 → ရှောင်ရုံးမြို့ |
| Unknown | Placeholder only | → 【?term?】 |

### Pending Terms Workflow

```
Term Extractor detects new term
         │
         ▼
  glossary_pending.json   ← auto-saved here
         │
    Human reviews
         │
    status: "approved"
         │
         ▼
    glossary.json         ← merged here (never auto-merge)
```

---

## 10. Output Quality Targets

| Metric | Target | Fix ပြုလုပ်ရမည်ဆိုလျှင် |
|--------|--------|----------------------|
| Myanmar char ratio | ≥ 70% | Stage 2 rewriter ထပ် run |
| Thai char leak | 0 | Language guard prompt စစ်ဆေး |
| Chinese in body text | 0 | Stage 1 prompt စစ်ဆေး |
| `<think>` tags | 0 | `clean_output()` run |
| `【?term?】` placeholders | ≤ 5 per chapter | Glossary ထဲ term ထပ်ထည့် |
| Repetition loops | 0 | `repeat_penalty: 1.3` သတ်မှတ် |

---

## 11. Common Errors & Fixes

| Error | Root Cause | Fix |
|-------|-----------|-----|
| Thai output (ศตวรรษ...) | Language guard missing | CRITICAL LANGUAGE RULE prompt ထိပ်ဆုံး ထည့် |
| `</think>` `</answer>` ယိုထွက် | Reasoning model tags | `clean_output()` postprocessor run |
| Entity extraction JSON error | Model returned non-JSON | `safe_parse_terms()` with 3-attempt fallback သုံး |
| 22%→55% Myanmar only | Direct CN→MM no training | Pivot language (EN bridge) သုံး |
| Repetition loop (တစ်ကြောင်းထပ်) | `repeat_penalty` မပါ | `repeat_penalty: 1.3` settings.yaml ထည့် |
| OOM / slow 14B model | 16GB RAM မလောက် | 7B models (`hunyuan:7b`, `seallms-v3-7b`) သာ သုံး |
| Chapter 1 takes 9+ min/chunk | chunk_size ကြီးလွန်း | `chunk_size: 1200` ပြောင်း |
| Glossary wrong characters | Test data ကျန်ခဲ့ | `glossary.json` ကို novel-specific data ဖြင့် replace |

---

## 12. Code Review Workflow (Auto-run After Every Task)

```
STEP 1 — OpenCode implements feature / fix / refactor

STEP 2 — Gemini sub-agents (parallel):
  gemini run "Review diff for bugs and code quality. List issues or READY_TO_COMMIT"
  gemini run "Review diff for security issues. List issues or READY_TO_COMMIT"

STEP 3 — OpenCode fixes ALL issues from both agents

STEP 4 — Repeat STEP 2 until both say READY_TO_COMMIT

STEP 5 — Commit ✅
```

---

## 13. Code Drift Prevention

```
[ ] No cross-agent imports (MemoryManager ကိုသာ ဖြတ်)
[ ] No direct glossary.json / context_memory.json access (FileHandler သာ သုံး)
[ ] All functions have type hints
[ ] New function has test in tests/
[ ] pytest tests/ -v passes
[ ] Unknown terms → 【?term?】 (never free-form guess)
[ ] JSON writes via FileHandler.write_json() only
[ ] repeat_penalty: 1.3 in all Ollama calls
```

---

## 14. Quick Reference Commands

```bash
# ─── Chinese Novel ───────────────────────────────────────────
# Chapter တစ်ခု (fast mode, 7B model)
python -m src.main_fast --novel 古道仙鸿 --chapter 1

# Chapter တစ်ခု (standard mode, better quality)
python -m src.main --novel 古道仙鸿 --chapter 1

# Chapter 5 မှ ဆက်ဘာသာပြန်
python -m src.main_fast --novel 古道仙鸿 --all --start 5

# ─── English Novel ───────────────────────────────────────────
# Chapter တစ်ခု (single-stage, seallms only)
python -m src.main_fast --novel my_novel --chapter 1 --single-stage

# ─── Memory Management ───────────────────────────────────────
# Model unload (RAM ထုတ်)
python -m tools.cleanup --stop-all

# Status ကြည့်
python -m tools.cleanup --status

# ─── Glossary ────────────────────────────────────────────────
# Pending terms ကြည့်
python -m src.tools.approve_terms --novel 古道仙鸿 --list-pending

# Term တစ်ခု approve
python -m src.tools.approve_terms --novel 古道仙鸿 --approve term_id

# ─── Tests ───────────────────────────────────────────────────
pytest tests/ -v --tb=short
```

---


Here are suggested additions to make it even more robust for your CPU-only, 16GB RAM setup:
### 🔧 Suggested Additions
#### 15. Troubleshooting Flowchart (Quick Debug)
graph TD
    A[Output Quality Poor?] --> B{Myanmar % < 70%?}
    B -->|Yes| C[Check Stage 2 prompt: CRITICAL LANGUAGE RULE]
    B -->|No| D{【?term?】 too many?}
    D -->|Yes| E[Update glossary_pending.json → approve terms]
    D -->|No| F{Repetition loop?}
    F -->|Yes| G[Set repeat_penalty: 1.3 + reduce chunk_size]
    F -->|No| H[Check Ollama logs + RAM usage]


#### 16. Performance Benchmarks (Ryzen 7 5700X / 16GB RAM)
| Model           | Mode      | Avg Time/Chunk | Chunks/Chapter | Est. Time/Chapter  |
|-----------------|-----------|----------------|----------------|--------------------|
| hunyuan:7b      | CN→EN     | ~45 sec        | 8-12           | ~6-9 min           |
| seallms-v3-7b   | EN→MM     | ~60 sec        | 8-12           | ~8-12 min          |
| qwen:7b         | Check+QA  | ~30 sec        | 8-12           | ~4-6 min           |
| Total (Chinese) | Two-stage | —              | —              | ~18-27 min/chapter |

> 💡 Tip: `Run --unload-after-chapter` to free RAM between chapters for stability.

#### 17. Memory File Backup & Recovery
``` bash
# Auto-backup before each chapter (add to main.py init)
def backup_novel_memory(novel_name: str):
    for scope in ["glossary", "context", "pending"]:
        src = Path(f"data/{scope}/{novel_name}.json")
        if src.exists():
            dst = src.with_suffix(f".backup_{datetime.now():%Y%m%d_%H%M}")
            shutil.copy2(src, dst)

# Recovery command
python -m src.tools.recover --novel 古道仙鸿 --from-backup 20260425_1430
```

####  Prompt Versioning Strategy
```yaml
# config/prompts.yaml
prompts:
  translator_v2.1: "prompts/translator_v2.1.txt"
  refiner_v1.3: "prompts/refiner_v1.3.txt"
  
# Log which prompt version produced each output
# Enables A/B testing and rollback if quality drops
```

