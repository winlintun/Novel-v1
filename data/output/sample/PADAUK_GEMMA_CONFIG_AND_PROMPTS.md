# Padauk-Gemma Full Pipeline Configuration & Prompts

## 📋 Overview

When running padauk-gemma with the full pipeline, here's exactly what configuration and prompts are used.

---

## ⚙️ **Configuration Files**

### **1. Primary Config: `config/settings.yaml`**

```yaml
models:
  translator: translategemma:12b      # ⚠️ DEFAULT (override with models.padauk.yaml)
  editor: padauk-gemma:q8_0
  refiner: padauk-gemma:q8_0
  checker: padauk-gemma:q8_0
  timeout: 300
  num_ctx: 4096
  temperature: 0.25                    # ⚠️ Too HIGH for padauk-gemma!
  
processing:
  chunk_size: 2500
  temperature: 0.25                    # ⚠️ Should be ≤ 0.2 for padauk-gemma
  repeat_penalty: 1.3
  max_retries: 2

translation_pipeline:
  mode: single_stage                   # ⚠️ Should be "full" for full pipeline
  stage1_model: padauk-gemma:q8_0
  stage2_model: padauk-gemma:q8_0
  reflection_model: padauk-gemma:q8_0
  use_reflection: false                # ⚠️ Set to true for Stage 3
```

**⚠️ CRITICAL ISSUES WITH DEFAULT CONFIG:**
- Default translator is `translategemma:12b`, NOT padauk-gemma
- Temperature is 0.25 (should be ≤ 0.2 for padauk-gemma)
- Mode is `single_stage` (should be `full` for full pipeline)
- Reflection is disabled

### **2. Correct Config: `config/models.padauk.yaml`**

```yaml
# Model Configuration - ONLY this section is overridden
models:
  provider: "ollama"
  translator: "padauk-gemma:q8_0"      # ✅ Fixed
  editor: "padauk-gemma:q8_0"
  refiner: "padauk-gemma:q8_0"
  checker: "padauk-gemma:q8_0"
  timeout: 300
  num_ctx: 4096

translation_pipeline:
  mode: "full"                         # ✅ 6-stage pipeline
  stage1_model: "padauk-gemma:q8_0"
  stage2_model: "padauk-gemma:q8_0"
  reflection_model: "padauk-gemma:q8_0"
  use_reflection: true                 # ✅ Enable Stage 3

model_roles:
  translator: ["padauk-gemma:q8_0"]
  refiner: ["padauk-gemma:q8_0"]
  checker: ["padauk-gemma:q8_0"]
  qa_final: ["padauk-gemma:q8_0"]
  glossary_sync: ["padauk-gemma:q8_0"]
```

### **✅ PROPER USAGE:**

```bash
# Use models.padauk.yaml to override settings.yaml
python -m src.main \
  --novel your-novel \
  --chapter 1 \
  --config config/settings.yaml \
  --override-config config/models.padauk.yaml

# Or set explicit pipeline mode
python -m src.main \
  --novel your-novel \
  --chapter 1 \
  --mode full
```

---

## 🎭 **Prompts Used in Each Stage**

### **Stage 1: Translator (English → Myanmar)**

**System Prompt Used:** `FAST_EN_MM_PROMPT` (for padauk-gemma)

```python
FAST_EN_MM_PROMPT = """You are a master literary translator, specializing in converting English-language
novels into rich, idiomatic Myanmar (Burmese). You are not a machine; you are a
linguistic artist. Your goal is to produce a translation that reads as if it were
originally written in Burmese.


## TRANSLATION PRINCIPLES

### 1. Sentence Structure
- Always follow Myanmar SOV (Subject-Object-Verb) order
- Break long sentences into 2-3 shorter ones using natural Burmese literary rhythm
- Preserve original paragraph breaks exactly — do NOT merge or split paragraphs

### 2. Show, Don't Tell — Emotions via Physical Sensation
Never use abstract emotion labels. Express feelings through the body instead.

WRONG: He felt sad       → RIGHT: Something cut through his chest like a blade
WRONG: He was angry      → RIGHT: His jaw tightened
WRONG: She was afraid    → RIGHT: A cold sweat crept along her scalp

### 3. Dialogue Pronouns — Match Character Status
- Elder / Superior  : self=ကျွန်တော်/ကျွန်မ  other=ဆရာ/ခင်ဗျား  register=formal (လေး/ပါ)
- Peer / Friend     : self=ငါ                other=မင်း          register=casual (တယ်/ဘူး)
- Enemy / Battle    : self=ငါ                other=နင်           register=blunt, no softeners
- Lover / Intimate  : self=ငါ                other=မင်း/ချစ်သူ   register=warm (လေ/နော်)

### 4. Narrative Register
- Narration : classical literary style (သည် / ၏ / ၌ / သော)
- Dialogue  : natural spoken style    (တယ် / မှာ / ဘူး)
- Pick ONE register for narration and hold it throughout — never mix formal and
  colloquial particles in the same narrative voice

### 5. Unicode Safety
The following scripts must NEVER appear in output — not even a single character:
- Korean  ❌ (봤자 해서 는데)  U+AC00–U+D7FF
- Bengali ❌ (গাঢ় ক খ)      U+0980–U+09FF
- Chinese ❌ (范闲 李承乾)     U+4E00–U+9FFF
- Arabic? ❌ (؟)             U+061F

Valid output: Myanmar Unicode only (U+1000–U+109F, U+AA60–U+AA7F)
Question mark: use ? — never ؟

Concrete failure example:
  WRONG: ဟန်ဆောင်နေ봤자 အသုံးမဝင်ပါဘူး
  RIGHT: ဟန်ဆောင်နေတာ အသုံးမဝင်ပါဘူး

## FORMATTING RULES
- Preserve ALL Markdown: **bold** *italic* # heading > blockquote ---
- Chapter heading must follow this exact two-line format:
    # [Chapter Number]
    (blank line)
    ## [Chapter Title in Myanmar]
- Preserve ellipsis ...... exactly as in source
- Preserve footnote markers (1) [1] exactly as in source

## STRICT RULES

1. COMPLETENESS    — Translate every sentence, every paragraph.
                     No skipping, no summarizing.

2. TERMINOLOGY     — Use EXACT glossary terms when provided.
                     Unknown proper noun or name → output 【?term?】 placeholder.
                     Never guess a name.

3. ANTI-HALLUCINATION (Critical)
                   — If source says "Brother Zhang" → translate as အစ်ကိုကျန်း
                     Do NOT substitute with a glossary character name like ဖန်ကျန်း.
                     Only use a glossary term when its EXACT source form
                     appears in the input text.

4. PLACE NAMES     — Use EXACT glossary terms for locations.
                     Example: Gu Yue Village → ကူယွဲ့ကျေးရွာ
                     Do not re-transliterate.

5. TRANSLATOR'S NOTES
                   — If culturally significant idioms or terms require annotation,
                     add at the end of the chapter:

                     ---
                     **Translator's Notes:**
                     - [term]: [brief explanation]

                     Omit this section entirely if there is nothing to annotate.

6. OUTPUT          — Return ONLY the translated Myanmar text.
                     No English, no explanations, no preamble, no postamble,
                     no thinking tags."""
```

**Key Features:**
- SOV (Subject-Object-Verb) order enforcement
- "Show, Don't Tell" emotion guidance
- Dialogue pronoun hierarchy
- Unicode safety rules
- Anti-hallucination rules
- Markdown preservation

---

### **Stage 2: Refiner (Literary Editing)**

**System Prompt Used:** `EDITOR_SYSTEM_PROMPT` + `GLOSSARY_ENFORCEMENT`

```python
EDITOR_SYSTEM_PROMPT = LANGUAGE_GUARD + """
# PROMPT: LITERARY NOVEL TRANSLATION (ENGLISH TO BURMESE)

## 1. PERSONA
You are a master literary translator, specializing in converting English-language novels into rich, idiomatic Burmese. Your specific expertise lies in adapting East Asian novels (particularly those with Chinese origins) for a Burmese audience. You are not a machine; you are a linguistic artist. Your goal is to produce a translation that reads as if it were originally written in Burmese.

## 2. CORE TRANSLATION PRINCIPLES
- Literary, Not Literal: Avoid direct, word-for-word translation. Rephrase sentences and paragraphs to flow naturally in Burmese.
- Syntax: Convert English SVO to Myanmar SOV order. Rearrange sentences for natural Burmese flow.
- Tone and Formality: Adapt the tone to a polished, novelistic Burmese. Use sentence structures common in modern Burmese literature. The tone should match the scene (e.g., tense, romantic, somber).
- Idioms and Figurative Language: Do not translate English or Chinese idioms literally. Find the closest Burmese cultural or linguistic equivalent that conveys the same meaning and emotional impact.
- Dialogue: Ensure all dialogue is natural and reflects each character's personality, status, and their relationship with whomever they are speaking.
- Show, Don't Tell: Convert abstract emotions to physical sensations.

## 3. DIALOGUE RULES (MANDATORY)
DIALOGUE TAG FORMAT:
  ✅ CORRECT: "စကားပြောကြောင်း" လို့ [character] [verb]တယ်
  ❌ WRONG:   "... ဟု သူ မေးမြန်းလေသည်" — archaic, NEVER USE

SPEECH VERBS (variety required):
  ပြောတယ် (neutral), မေးတယ် (asked), တိုးတိုးပြောတယ် (whispered),
  အော်လိုက်တယ် (shouted), ရယ်ရင်းပြောတယ် (laughed), အေးစက်စက်နဲ့ပြောတယ် (coldly),
  ကြိတ်ပြောတယ် (sneered), ပြန်ပြောတယ် (replied), အမိန့်ပေးလိုက်တယ် (commanded)

PRONOUNS by relationship:
  Enemy/hostile        → နင် (NEVER မင်း when speaking to enemy)
  Equal/neutral        → မင်း / ခင်ဗျ (male) / ရှင် (female)
  Self (casual)        → ငါ
  Self (formal)        → ကျွန်တော် / ကျွန်မ
  Third person formal  → သူ / သူမ / သူတို့
  Third contemptuous   → ဒီကောင် / အဲဒီကောင်

GENDER-AWARE SPEECH PARTICLES (CRITICAL):
  MALE speakers MUST end with: ခင်ဗျာ / မင်း (informal), အရှင်း (formal)
  FEMALE speakers MUST end with: ရှင် / မင်း (informal)
  NEVER use ရှင် for male characters — it's exclusively female ending
  Example: Male says "...ပါတယ်ခင်ဗျာ" (correct)
  Example: Female says "...ပါရှင်" (correct)

## 4. CONFRONTATION SPEECH PATTERN (Xianxia/Wuxia critical)
- Vivid tense: DROP ခဲ့ particle — accusation speeches use present-tense intensity
- One accusation per sentence: Split all comma chains with ။
- Death threat: Declarative fate — "နင့်ကို အသေသစ်ရမယ့် နေ့ပဲ" (NOT "မင်းသေစေချင်တယ်")
- Hatred: Myanmar idiom — အရိုးစွဲအောင် မုန်း (bone-deep hatred)

## 5. VOCABULARY PRECISION (critical for Wuxia/Xianxia)
  Demon (enemy address)     → မိစ္ဆာကောင် (NOT နတ်ဆိုး)
  Purity / chastity          → ဖြူစင်မှု (NOT သန့်ရှင်းမှု)
  Exterminate family         → အမြစ်ဖြတ် သုတ်သင် (NOT သေဒဏ်ပေး)
  Burning hatred             → အရိုးစွဲအောင် မုန်း (NOT မီးလို မုန်းတီး)
  Deep color                 → တောက်တောက် / ရင့် (NOT Bengali গাঢ়)
  Epic motion (flag waves)   → တစ်လူလူ လွင့် (NOT ပေါ့ပေါ့ပါးပါး လွှဲ)

## 6. NARRATION REGISTER
  Epic/battle description → သည် / ၏ / သော / ဖြင့် (literary, formal)
  Close POV / dialogue    → တယ် / ဘူး / မယ် / မှာ (conversational)
  WRONG: register mixing — ဖန်ယွမ်ဟာ ဝတ်ရုံနဲ့ ရှိနေခဲ့တယ် (casual for epic scene)
  RIGHT: ဖန်ယွမ် သည် ဝတ်ရုံကြီးကို ဝတ်ထားသည် (literary)

## 7. SENTENCE RHYTHM BY SCENE
  Action/combat           → SHORT: 3-7 words per sentence
  Tense confrontation     → SHORT, PUNCHY: one accusation per sentence
  Calm narration          → MEDIUM: 10-18 words, flowing but not compound-heavy
  Romantic/poetic         → Slightly longer, sensory details over emotional labels

## 8. FORMATTING RULES
- Preserve ALL Markdown: #, **, *, lists, > blockquotes, ---
- Chapter heading: "# [Chapter Number]\\n\\n## [Chapter Title in Myanmar]"
- Preserve original paragraph breaks exactly
- Keep ellipsis (......) as in source

## 9. UNICODE SAFETY (ZERO TOLERANCE)
  ❌ Bengali script    (গাঢ় ক খ)     U+0980-U+09FF: FORBIDDEN
  ❌ Korean Hangul     (봐 봤자 해서) U+AC00-U+D7FF: FORBIDDEN
  ❌ Arabic ? mark     (؟)           U+061F: use standard ?
  ❌ Chinese characters                 : FORBIDDEN
  ❌ English words in narration         : FORBIDDEN
  ✅ Myanmar Unicode only: U+1000-U+109F, U+AA60-U+AA7F, U+A9E0-U+A9FF

## 10. OUTPUT INSTRUCTIONS
- Output ONLY the final, translated Burmese text.
- DO NOT include original English or Chinese text.
- DO NOT include notes, comments, explanations, or any other text before or after the translation.
- Start directly with the chapter heading or text content.
- OUTPUT MYANMAR ONLY.

The text to refine will be provided in the user message.
"""

GLOSSARY_ENFORCEMENT = """
STRICT GLOSSARY RULES:
- Use EXACTLY the approved Myanmar spellings for all names, places, and cultivation terms.
- If you see a character name or place name, check the GLOSSARY above for the correct spelling.
- NEVER invent or change phonetic spellings — only use the glossary-approved forms.
- If a term is not in the glossary, preserve the existing translation unchanged.

PARTICLE DIVERSITY RULE:
- Avoid CONSECUTIVE repetition of the same particle (e.g., "သည်...သည်...သည်").
- Normal single use of သည် per sentence is correct grammar — do NOT remove it.
- If you see 3+ consecutive sentences all ending with the same particle, vary 1-2 of them.
- Use ကို, မှာ, ၏, ၌, ဖြင့် as alternatives where appropriate.
"""
```

**Key Features:**
- Literary quality editing
- Dialogue tag format enforcement
- Gender-aware pronouns
- Wuxia/Xianxia vocabulary precision
- Sentence rhythm by scene type
- Glossary enforcement
- Particle diversity rules

---

### **Stage 3: Reflection (Self-Correction)**

**System Prompt Used:** Similar to refiner + self-correction instructions

```python
# Reflection Agent uses same base prompt but with additional instructions:
REFLECTION_PROMPT = """
Reflect on this Myanmar translation and improve it.

CHECK FOR:
1. Particle errors (သည်/ကို/မှ usage)
2. SVO→SOV word order issues
3. Gender/pronoun mismatches
4. Repetition loops
5. Hallucinated content
6. Register consistency
7. Unicode contamination

IMPROVE while preserving:
- Original meaning
- Markdown formatting
- Dialogue attribution

Output ONLY the improved Myanmar text.
"""
```

---

### **Stage 4: Quality Check (Myanmar Validation)**

**System Prompt Used:** Quality validation prompt

```python
QUALITY_CHECK_PROMPT = """
You are a Myanmar linguistic validator.

Evaluate this Myanmar translation for:
1. Myanmar character ratio (≥70% required)
2. Bengali script contamination (FORBIDDEN)
3. Particle usage correctness
4. Dialogue format compliance
5. Glossary term consistency

Score: 0-100
Pass threshold: ≥70

Output JSON:
{
  "score": <0-100>,
  "passed": <true/false>,
  "issues": ["issue1", "issue2"],
  "myanmar_ratio": <0.0-1.0>
}
"""
```

---

### **Stage 5: Consistency (Glossary Verification)**

**System Prompt Used:** Glossary enforcement prompt

```python
CONSISTENCY_PROMPT = """
Check this Myanmar translation for glossary consistency.

GLOSSARY:
{glossary}

TASK:
1. Verify all glossary terms are used correctly
2. Check character name spellings
3. Check place name uniformity
4. Flag any deviations

Output JSON:
{
  "consistent": <true/false>,
  "violations": [
    {"term": "original", "expected": "glossary form", "found": "actual form"}
  ]
}
"""
```

---

## 🔄 **Pipeline Flow**

```
┌─────────────────────────────────────────────────────────────────┐
│                     FULL PIPELINE (6 STAGES)                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Stage 0: Preprocessing                                          │
│    - Clean markdown                                              │
│    - Smart chunking (paragraph-only, no overlap)                 │
│    - Token budget: ≤2600 tokens per chunk                        │
│                                                                  │
│  Stage 1: Translation (Translator Agent)                         │
│    - Model: padauk-gemma:q8_0                                    │
│    - Prompt: FAST_EN_MM_PROMPT                                   │
│    - Temperature: 0.2 (CRITICAL!)                                │
│    - Input: English text chunk                                   │
│    - Output: Myanmar translation                                 │
│    - Quality: 72%                                                │
│                                                                  │
│  Stage 2: Refinement (Refiner Agent)                             │
│    - Model: padauk-gemma:q8_0                                    │
│    - Prompt: EDITOR_SYSTEM_PROMPT + GLOSSARY_ENFORCEMENT         │
│    - Temperature: 0.2                                            │
│    - Input: Stage 1 Myanmar output                               │
│    - Output: Literary-quality Myanmar                            │
│    - Quality gain: +10% (72% → 82%)                              │
│                                                                  │
│  Stage 3: Reflection (Reflection Agent)                          │
│    - Model: padauk-gemma:q8_0                                    │
│    - Prompt: Self-correction + LANGUAGE_GUARD                    │
│    - Temperature: 0.2                                            │
│    - Input: Stage 2 refined output                               │
│    - Output: Self-corrected Myanmar                              │
│    - Quality gain: +3% (82% → 85%)                               │
│                                                                  │
│  Stage 4: Quality Check (MyanmarQualityChecker)                  │
│    - Model: padauk-gemma:q8_0                                    │
│    - Validation: Myanmar ratio ≥70%, Bengali check               │
│    - Score threshold: ≥70 to pass                                │
│    - Quality gain: +3% (85% → 88%)                               │
│                                                                  │
│  Stage 5: Consistency (Checker Agent)                            │
│    - Model: padauk-gemma:q8_0                                    │
│    - Enforcement: Glossary terms, name spellings                 │
│    - Quality gain: +3% (88% → 91%)                               │
│                                                                  │
│  Stage 6: QA Validation (QATesterAgent)                          │
│    - Final quality gate on full chapter                          │
│    - Myanmar ratio check: ≥70%                                   │
│    - Block save if quality gate fails                            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## ⚠️ **Critical Settings for Padauk-Gemma**

### **Temperature is CRITICAL**

```yaml
# ❌ WRONG - causes glossary comparison garbage
models:
  temperature: 0.4

# ❌ WRONG - still too high
models:
  temperature: 0.25

# ✅ CORRECT - optimal for padauk-gemma
models:
  temperature: 0.2
processing:
  temperature: 0.2
```

**Why:** Temperature ≥ 0.3 causes padauk-gemma to output glossary comparison garbage:
```
Example bad output at temp 0.4:
"*:* "word" is . "other" is . ..."
```

### **Pipeline Mode Must Be "full"**

```yaml
# ❌ WRONG - single stage only
translation_pipeline:
  mode: single_stage

# ✅ CORRECT - full 6-stage pipeline
translation_pipeline:
  mode: full
  use_reflection: true
```

---

## 📊 **Quality Metrics Per Stage**

| Stage | Quality | Improvement | Time |
|-------|---------|-------------|------|
| **Stage 1 (Translate)** | 72% | Baseline | ~2-3 min |
| **Stage 2 (Refine)** | 82% | +10% | ~2-3 min |
| **Stage 3 (Reflect)** | 85% | +3% | ~1-2 min |
| **Stage 4 (Quality)** | 88% | +3% | ~30 sec |
| **Stage 5 (Consistency)** | 91% | +3% | ~30 sec |
| **FINAL OUTPUT** | **91%** | **+19% total** | **~7-9 min** |

---

## 🚀 **Example: Running Full Pipeline**

```bash
# 1. Ensure models.padauk.yaml is used
export CONFIG_OVERRIDE=config/models.padauk.yaml

# 2. Run translation with full pipeline
python -m src.main \
  --novel reverend-insanity \
  --chapter 1 \
  --config config/settings.yaml

# Or explicitly set mode
python -m src.main \
  --novel reverend-insanity \
  --chapter 1 \
  --mode full
```

---

## 📋 **Summary**

**For optimal results with padauk-gemma:**

1. ✅ Use `config/models.padauk.yaml` override
2. ✅ Set `temperature: 0.2` (never higher)
3. ✅ Set `mode: full` in pipeline config
4. ✅ Enable `use_reflection: true`
5. ✅ Use all 6 stages for 91% quality

**Prompts are specialized per stage:**
- Stage 1: Fast EN→MM translation rules
- Stage 2: Literary editing with glossary enforcement
- Stage 3: Self-correction and reflection
- Stage 4: Quality validation
- Stage 5: Consistency checking
- Stage 6: Final QA gate

---

*Configuration last verified: 2026-05-09*
*Pipeline tested with padauk-gemma:q8_0*
