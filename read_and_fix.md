# AI Translation Pipeline for Novel (Chinese/English → Myanmar)

## Overview
Structured pipeline for high-quality Myanmar translation using context, prompts, and multi-step processing.

---

## 1. Context Injection (Character + Story)

### characters.md
# Characters
Name: Zhang San  
Myanmar: ဇန်းဆန်း  
Personality: Calm, intelligent  

Name: Li Si  
Myanmar: လီစီ  
Personality: Brave  

### story.md
# Story Summary
A cultivation story about growth and power.

---

## 2. Translation Prompt

You are a professional novel translator.

[Character Information]
{characters}

[Story Context]
{story}

Translate into natural Myanmar.
- Keep meaning
- Keep names consistent
- Keep markdown format

[Text]
{input}

---

## 3. Pipeline

Step 1: Translate  
Step 2: Rewrite  
Step 3: Refine  

---

## 4. Rewrite Prompt

Rewrite to natural Myanmar novel style.
Keep meaning and tone.

---

## 5. Refine Prompt

Fix grammar and improve flow.
Do not change meaning.

---

## 6. Glossary

{
 "cultivation": "ကျင့်ကြံခြင်း"
}

---

## 7. Flow

characters + story + chapter  
→ translate  
→ rewrite  
→ refine  
→ output
