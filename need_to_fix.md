# How to Fix Poor Burmese Translation Quality When Using Ollama (gemma:12b) or NLLB-200

## The Problem

When you use **Ollama with gemma:12b** or **NLLB-200** to translate Chinese or English novels into Burmese, the output often looks like this:

- Sentences feel **stiff, robotic, and unnatural**
- Dialogue sounds like a **legal document**, not a conversation
- Emotions are **lost or mistranslated**
- Character names are **inconsistent** across paragraphs
- The text is **hard to read** and even harder to enjoy

This happens because these models were not specifically trained for **literary Burmese translation**. They do word-for-word or phrase-for-phrase mapping without understanding narrative tone, character voice, or cultural nuance.

---

## Root Causes

| Cause | What Goes Wrong |
|---|---|
| No style instruction | Model defaults to formal/academic Burmese |
| No context passed | Each sentence is translated in isolation |
| No character glossary | Names are rendered differently each time |
| No post-processing | Raw output is never cleaned or refined |
| Wrong model usage | NLLB-200 is a sentence-level model, not a novel translator |

---

## The Two-Stage Solution

Instead of asking one model to do everything, use a **two-stage pipeline**:

```
Stage 1: Raw Translation
  → Use NLLB-200 or gemma:12b to get a rough draft

Stage 2: Rewriting / Post-Processing
  → Use a capable LLM (Claude, GPT-4, or gemma with a strong prompt)
    to rewrite the rough draft into natural, fluent Burmese
```

This is exactly how professional human translators work:
a rough draft first, then a polished rewrite.

---

## How to Instruct the AI Correctly

### The Wrong Way (What Most People Do)

```
Prompt: "Translate this to Burmese: [novel text]"
```

This gives the AI zero guidance. It will produce technically correct
but emotionally flat, unreadable Burmese.

---

### The Right Way — Full Prompt Template

Use this prompt structure when sending text to your LLM for rewriting:

```
SYSTEM PROMPT:
You are an expert Burmese literary editor and translator.
Your job is NOT to re-translate from scratch.
Your job is to take an existing rough Burmese translation
and REWRITE it so that it reads like a native Burmese novel.

Follow these rules strictly:
1. Use natural, modern, conversational Burmese — not formal or archaic language.
2. Dialogue must sound like real people talking, not reading a textbook.
3. Emotions must be shown through physical reactions and short sentences,
   not described with long abstract words.
4. Never use overly long compound sentences. Break them up.
5. Keep character names exactly as provided in the glossary below.
6. If a phrase sounds unnatural in Burmese, find a culturally equivalent expression.
7. Do not add or remove story content — only improve the language quality.

CHARACTER GLOSSARY:
- Wei Wuxian → ဝေ့ဝူရှျန်
- Lan Wangji → လန်ဝမ်ကျိ
- [Add more characters here]

USER PROMPT:
Here is the rough Burmese translation. Please rewrite it
to sound natural and fluid:

[PASTE ROUGH TRANSLATION HERE]
```

---

## Specific Fixes for Common Problems

### Problem 1: Dialogue Sounds Unnatural

**Raw output (bad):**
> "သင်သည် ဤနေရာသို့ အဘယ်ကြောင့် ရောက်ရှိလာသနည်း" ဟု သူမသည် မေးမြန်းလေသည်။

**Rewritten (good):**
> "မင်း ဘာကြောင့် ဒီကို လာတာလဲ" လို့ သူမ မေးလိုက်တယ်။

**How to fix it in your prompt:**
```
Always rewrite dialogue using this format:
"[spoken words]" လို့ [character] [verb like ပြောတယ် / မေးတယ် / တိုးတိုးပြောတယ်]

Keep spoken words short, direct, and emotionally honest.
```

---

### Problem 2: Emotions Are Described, Not Felt

**Raw output (bad):**
> သူသည် အလွန်ဝမ်းနည်းပူဆွေးသောခံစားချက်ကို ခံစားနေသည်။

**Rewritten (good):**
> သူ့ရင်ထဲမှာ တစ်ခုခု နာကျင်နေသလိုပဲ။ မျက်ရည်တွေ မသိမသာ စီးကျလာတယ်။

**How to fix it in your prompt:**
```
Never describe emotions with abstract labels like "ဝမ်းနည်းသည်" alone.
Instead, show the emotion through:
- Physical sensations (chest tightening, hands trembling)
- Short fragmented sentences
- Character actions or silence
```

---

### Problem 3: Sentences Are Too Long and Complex

**Raw output (bad):**
> သူသည် တောင်ထိပ်သို့ တက်ရောက်ရောက်ချင်း အနောက်ဘက်တွင် နေဝင်ရောင်ခြည်များ ထိုးဖောက်ကာ တောအုပ်ကြီးများပေါ်သို့ ရောင်ခြည်ကျရောက်လျက် တည်ရှိသောမြင်ကွင်းကို မြင်တွေ့ခဲ့ရသည်။

**Rewritten (good):**
> တောင်ထိပ်ကို ရောက်တာနဲ့ သူ ရပ်မိသွားတယ်။
> နေဝင်ရောင်က တောအုပ်ကြီးကို ရွှေရောင်ဆိုးထားသလို ဖုံးလွှမ်းနေတယ်။
> လှပါတယ်။ ဒါပေမဲ့ ရင်ထဲမှာ တစ်ဆုပ်ကြည်ကြည်လည်း ဖြစ်မိတယ်။

**How to fix it in your prompt:**
```
Break long sentences into 2–3 short sentences.
Each sentence should carry ONE idea or ONE image.
Short sentences create rhythm. Rhythm creates emotion.
```

---

### Problem 4: Character Names Are Inconsistent

**How to fix it:**
```python
# Always build and pass a glossary before translation

GLOSSARY = {
    "Wei Wuxian": "ဝေ့ဝူရှျန်",
    "Lan Wangji": "လန်ဝမ်ကျိ",
    "Jiang Cheng": "ကျန်ချင်",
}

def build_glossary_text(glossary: dict) -> str:
    lines = ["CHARACTER NAME GLOSSARY (never change these):"]
    for original, burmese in glossary.items():
        lines.append(f"  - {original} → {burmese}")
    return "\n".join(lines)
```

Include this glossary text in **every single API call**. Never skip it.

---

## Recommended Pipeline (Code Structure)

```python
def two_stage_translate(original_text: str, glossary: dict) -> str:

    # --- STAGE 1: Raw Translation ---
    # Use NLLB-200 or ollama gemma:12b to get rough Burmese
    rough_translation = nllb_or_ollama_translate(original_text)

    # --- STAGE 2: Rewrite for Quality ---
    # Use a strong LLM to polish the rough translation
    glossary_text = build_glossary_text(glossary)

    rewrite_prompt = f"""
You are a Burmese literary editor. Rewrite this rough translation
into natural, emotional, conversational Burmese.

{glossary_text}

RULES:
- Short sentences. Real dialogue. Show emotions physically.
- Never sound like a textbook.
- Keep all character names exactly as in the glossary.

ROUGH TRANSLATION TO REWRITE:
{rough_translation}
"""

    polished = call_llm_api(rewrite_prompt)
    return polished
```

---

## Model Comparison

| Model | Best Used For | Weakness |
|---|---|---|
| **NLLB-200** | Fast sentence-level translation | No literary style, no context |
| **gemma:12b (Ollama)** | Decent multilingual drafts | Needs strong prompting for Burmese |
| **Claude / GPT-4** | Rewriting and polishing | Costs more, but far better quality |
| **Two-stage pipeline** | Best overall quality | Slightly slower, worth it |

---

## Summary — Tell Your AI This

> "Do not translate word by word. Read the passage as a whole.
> Understand the mood, the character's voice, and the scene's atmosphere.
> Then write it in Burmese the way a Burmese novelist would write it —
> naturally, emotionally, and in a way that makes the reader forget
> they are reading a translation."

That single instruction, combined with a character glossary and
a two-stage pipeline, will transform your output from unreadable
to genuinely enjoyable Burmese fiction.