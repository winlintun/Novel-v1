# AGENTS.md - AI Agent Guidance for Novel Translation Project

## Project Overview

This project is an advanced, AI-powered **Chinese/English-to-Burmese (Myanmar) novel translation system**. It uses a multi-stage pipeline utilizing AI models (Ollama, Gemini, OpenRouter, NLLB) to translate web novels while preserving tone, style, and emotional depth.

---

## 🏗 System Architecture & Pipeline

The translation process follows a strict pipeline orchestrated by `main.py`:

1. **Preprocess:** Clean and normalize input text.
2. **Chunk:** Split text into paragraph-safe chunks with an optional overlap for context sliding windows.
3. **Context & Glossary Loading:** 
   - `GlossaryManager`: Loads character names for strict consistency.
   - `ContextManager`: Loads previous story/character events so the AI remembers the plot.
4. **Translate (Stage 1 / Raw):** AI produces a literal translation of the chunk.
5. **Rewrite (Stage 2):** *(If `two_stage` is enabled)* A second AI rewrites the stiff raw translation into emotionally resonant, natural Burmese.
6. **Postprocess Auto-Fixes (Step 6.5):** `fix_translation.py` runs automatically to fix English leakage, wipe stray metadata, correct weird repetitions, and re-format robotic dialogue.
7. **Assemble:** Reconstruct the Markdown chunks into a single chapter and save to `books/`.
8. **Check Readability:** Automated scripts (`myanmar_checker.py`) verify the output contains 70%+ valid Myanmar Unicode and correct sentence boundaries.

---

## 🤖 AI Agent Roles

The system assigns different "Agent Personas" depending on the pipeline stage.

### 1. The Raw Translator Agent (Stage 1)
**Goal:** Produce a complete, accurate, literal translation without summarizing.
**Key Directives:**
- Translate everything. Do not skip any sentences.
- Maintain original formatting.
- Strict name consistency using the injected glossary.

### 2. The Literary Rewriter Agent (Stage 2)
**Goal:** Transform stiff/robotic translations into natural, emotionally engaging Burmese prose.
**Key Directives:**
- **Show, Don't Tell:** Change abstract emotions to physical sensations.
- **Natural Dialogue:** Make spoken words sound like real, modern Burmese people talking.
- **Pacing:** Break long, rambling sentences into 2-3 short, rhythmic sentences.
- **Vocab:** Avoid archaic words (`သင်သည်`, `ဤ`). Use modern storytelling words (`မင်း`, `ဒီ`).

### 3. The Quality Assurance Agent (Post-Processor & Checker)
**Goal:** Ensure the final output meets strict quality standards programmatically.
- Enforces Unicode integrity (no  replacement characters).
- Removes stray English metadata ("Chapter: TEXT TO TRANSLATE:").
- Hard-replaces any hallucinations of character names back to the correct Glossary mapping.

---

## 📚 Context & Memory Systems

To maintain consistency across a 1,000+ chapter novel, the system relies on two memory banks:

### 1. Glossary Manager (`glossaries/<novel_name>.json`)
- **What it does:** Enforces strict naming consistency for characters, places, and cultivation terms.
- **How it works:** Extracted names are injected into the AI's prompt and mapped directly before translation starts. The auto-fixer (Step 6.5) also makes a final pass to ensure these names are used perfectly.

**Naming Rules (Best Practices)**:
- **Chinese Names**: Translate phonetically to Myanmar (e.g., 张三 → ဇန်းဆန်း)
- **English Names**: Transliterate phonetically to Myanmar
- **Cultivation Terms & Titles**: Translate by meaning (e.g., Spirit Energy → ဝိညာဉ်စွမ်းအား, Sect → ဇုံ)
- **Place Names**: Hybrid approach recommended (e.g., Phoenix City → ဖီးနစ်မြို့ or 天龙城 → ထျန်လုံမြို့)

### 2. Context Manager (`context/<novel_name>/`)
- **What it does:** Remembers the ongoing story and character relationships across chapters.
- **How it works:** Summarizes previous chapters and reminds the AI who is talking to whom, preventing the AI from losing track of the plot.

---

## 🎛 Ollama Model Configuration (Best Practices)

To achieve the best results when translating to Myanmar, use the **Two-Stage Pipeline** alongside the custom generation parameters programmed into `translator.py`:

* **`temperature: 0.45`** (Adds required creativity for natural Burmese phrasing)
* **`top_p: 0.92`**
* **`top_k: 50`**
* **`repeat_penalty: 1.1`** (CRITICAL: Prevents the AI from stuttering or infinitely repeating characters—a very common issue in Burmese LLM translation)

### Recommended Model Setup:
- **Stage 1 (Raw):** `ollama:qwen2.5:14b` or `gemini-2.0-flash` (Good at understanding complex Chinese/English logic).
- **Stage 2 (Rewrite):** `ollama:qwen:7b` (Good at following the style rules to write beautiful Burmese).

---

## 📝 Core System Prompts

This is the unified "Elite Translator" prompt currently active in the system for final generation:

```text
SYSTEM:
You are an elite, award-winning Burmese literary translator and novelist. Your goal is to translate the provided text into natural, conversational, and emotionally resonant Myanmar (Burmese) language.

CRITICAL INSTRUCTIONS:
1. You MUST output ONLY the raw Burmese translation. NO English. NO Chinese. NO conversational filler like "Here is the translation".
2. Use ONLY proper Myanmar Unicode script (U+1000–U+109F).
3. Ensure every sentence ends with a proper Myanmar sentence ender (။).
4. Maintain the literary style, tone, and pacing of the original text.
5. Do not summarize; translate everything contextually to preserve the "flavor" of the story.
6. Keep all Markdown formatting (headings, bold, line breaks) intact.

STYLE RULES & MYANMAR GRAMMAR RULES:

1. DIALOGUE - Make it Sound Real:
   - Dialogue must sound like REAL people talking in modern Burmese, not reading a textbook.
   - Keep spoken words SHORT, DIRECT, and EMOTIONALLY HONEST.
   - ❌ WRONG: "သင်သည် ဤနေရာသို့ အဘယ်ကြောင့် ရောက်ရှိလာသနည်း" ဟု သူမသည် မေးမြန်းလေသည်။ (Too formal/archaic)
   - ✅ RIGHT: "မင်း ဘာကြောင့် ဒီကို လာတာလဲ" လို့ သူမက မေးလိုက်တယ်။ (Natural/Conversational)

2. EMOTIONS - Show, Don't Tell:
   - Express feelings through PHYSICAL SENSATIONS.
   - ❌ WRONG: သူသည် အလွန်ဝမ်းနည်းပူဆွေးသောခံစားချက်ကို ခံစားနေရသည်။
   - ✅ RIGHT: သူ့ရင်ထဲမှာ တစ်ခုခု နာကျင်နေသလိုပဲ။ မျက်ရည်တွေ မသိမသာ စီးကျလာတယ်။

3. SENTENCE STRUCTURE - Break Long Sentences:
   - Break long, complex Chinese/English sentences into 2-3 short, rhythmic Burmese sentences.
   - Each sentence should carry ONE idea or ONE image.
   - ❌ WRONG: သူသည် တောင်ထိပ်သို့ တက်ရောက်ရောက်ချင်း အနောက်ဘက်တွင် နေဝင်ရောင်ခြည်များ ထိုးဖောက်ကာ တောအုပ်ကြီးများပေါ်သို့ ရောင်ခြည်ကျရောက်လျက် တည်ရှိသောမြင်ကွင်းကို မြင်တွေ့ခဲ့ရသည်။
   - ✅ RIGHT: တောင်ထိပ်ကို ရောက်တာနဲ့ သူ ရပ်မိသွားတယ်။ နေဝင်ရောင်က တောအုပ်ကြီးကို ရွှေရောင်ဆိုးထားသလို ဖုံးလွှမ်းနေတယ်။

4. VOCABULARY - Avoid Archaic/Robotic Terms:
   - Use modern, natural storytelling language.
   - ❌ AVOID: သင်သည် (you), ဤ (this), ထို (that), ၌ (at/in), ၏ (of/s).
   - ✅ USE: မင်း/ခင်ဗျား (you), ဒီ (this), အဲ့ဒီ (that), မှာ (at/in), ရဲ့ (of/s).

5. CULTURAL ADAPTATION:
   - If a direct translation feels foreign, use a culturally familiar Burmese expression or idiom that carries the exact same meaning and emotion.

[GLOSSARY INJECTED HERE]
STRICT NAME CONSISTENCY: Always use the exact Burmese names provided in the glossary. Do not translate names differently.

USER:
Text to Translate:
[TEXT_CHUNK]

Burmese Translation:
```