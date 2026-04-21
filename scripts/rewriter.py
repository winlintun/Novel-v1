#!/usr/bin/env python3
"""
Rewriter Module - Two-Stage Translation Pipeline (Stage 2)

This module implements the second stage of the two-stage translation pipeline
as described in need_to_fix.md. It takes a rough translation (from NLLB-200
or a basic LLM) and rewrites it into natural, fluent, emotionally resonant Burmese.

Usage:
    from scripts.rewriter import rewrite_burmese, get_rewrite_prompt
    
    # Two-stage translation
    rough_translation = translator.translate(text, raw_prompt)
    polished_translation = rewrite_burmese(rough_translation, glossary_manager)

Features:
    - Rewrites stiff/robotic Burmese into natural conversational Burmese
    - Fixes dialogue to sound like real people talking
    - Shows emotions through physical sensations instead of abstract labels
    - Breaks long complex sentences into short, rhythmic ones
    - Maintains strict character name consistency via glossary
"""

import os
import json
import logging
from typing import Optional, Iterator
from pathlib import Path

# Import the base translator classes
from scripts.translator import BaseTranslator, get_translator, managed_request

logger = logging.getLogger(__name__)


def get_rewrite_prompt(glossary_text: str = "", context: str = "") -> str:
    """
    Get the system prompt for rewriting rough Burmese translations.
    
    This prompt is designed to transform stiff, literal translations into
    natural, emotionally resonant Burmese prose as described in need_to_fix.md.
    
    Args:
        glossary_text: Character name glossary to inject
        context: Previous context for consistency (optional)
        
    Returns:
        System prompt string for the rewriter
    """
    context_section = f"""
PREVIOUS CONTEXT (for consistency):
{context}

---
""" if context else ""

    return f"""You are an expert Burmese literary editor and translator.
Your job is NOT to translate from Chinese/English. 
Your job is to take an existing rough Burmese translation and REWRITE it 
so that it reads like a native Burmese novel — natural, emotional, and engaging.

{context_section}
CRITICAL REWRITING RULES:

1. **NATURAL DIALOGUE**
   - Dialogue must sound like REAL people talking, not reading a textbook
   - Use: "မင်း ဘာလို့ ဒီလိုလုပ်တာလဲ" လို့ သူမ မေးလိုက်တယ်
   - NOT: "သင်သည် ဤသို့ပြုလုပ်ရခြင်း၏ အကြောင်းရင်းက အဘယ်ပါလိမ့်" ဟု သူမ မေးလေသည်
   - Keep spoken words SHORT, DIRECT, and EMOTIONALLY HONEST

2. **SHOW EMOTIONS, DON'T TELL**
   - ❌ BAD: "သူသည် အလွန်ဝမ်းနည်းပူဆွေးသောခံစားချက်ကို ခံစားနေသည်"
   - ✅ GOOD: "သူ့ရင်ထဲမှာ တစ်ခုခု နာကျင်နေသလိုပဲ။ မျက်ရည်တွေ မသိမသာ စီးကျလာတယ်"
   - Express feelings through PHYSICAL SENSATIONS and IMAGERY
   - Use short, fragmented sentences for emotional impact

3. **BREAK LONG SENTENCES**
   - ❌ BAD: One sentence with 50+ words describing everything
   - ✅ GOOD: Break into 2-3 short sentences, each with ONE idea
   - Example:
     ❌ "သူသည် တောင်ထိပ်သို့ တက်ရောက်ရောက်ချင်း အနောက်ဘက်တွင် နေဝင်ရောင်ခြည်များ ထိုးဖောက်ကာ တောအုပ်ကြီးများပေါ်သို့ ရောင်ခြည်ကျရောက်လျက် တည်ရှိသောမြင်ကွင်းကို မြင်တွေ့ခဲ့ရသည်"
     ✅ "တောင်ထိပ်ကို ရောက်တာနဲ့ သူ ရပ်မိသွားတယ်။ နေဝင်ရောင်က တောအုပ်ကြီးကို ရွှေရောင်ဆိုးထားသလို ဖုံးလွှမ်းနေတယ်။ လှပါတယ်။"
   - Short sentences create RHYTHM. Rhythm creates EMOTION.

4. **AVOID FORMAL/ARCHAIC LANGUAGE**
   - Use MODERN, CONVERSATIONAL Burmese
   - ❌ သင်သည်၊ ထိုသို့သော၊ အလွန်မူ၊ ရှိပါသည်
   - ✅ မင်း၊ အဲ့လိုမျိုး၊ သိပ်ကို၊ ရှိတယ်
   - Write the way a Burmese storyteller would tell it around a fire

5. **CULTURAL ADAPTATION**
   - If a phrase sounds foreign in Burmese, find a culturally equivalent expression
   - Keep the MEANING and EMOTION, not the literal words
   - Make it feel like it was originally written in Burmese

6. **STRICT NAME CONSISTENCY**
   - NEVER change character names from the glossary
   - If a name appears differently in the rough text, correct it to the glossary version

7. **PRESERVE CONTENT**
   - Do NOT add or remove story content
   - Do NOT summarize
   - Only improve the LANGUAGE QUALITY

8. **OUTPUT FORMAT**
   - Output ONLY the rewritten Burmese text
   - NO explanations, NO notes, NO "Here is the rewrite"
   - Keep paragraph breaks and dialogue formatting
{glossary_text}

REMEMBER: You are not fixing grammar. You are making the reader FEEL the story.
Write so naturally that the reader forgets they are reading a translation."""


def get_raw_translation_prompt(source_lang: str = "Chinese") -> str:
    """
    Get a minimal prompt for raw translation (Stage 1).
    
    This is used for the first pass when doing two-stage translation.
    The goal is a literal but complete translation that the rewriter will polish.
    
    Args:
        source_lang: Source language name
        
    Returns:
        System prompt for raw translation
    """
    return f"""You are a translator converting {source_lang} to Burmese.

Your goal: Produce a COMPLETE, LITERAL translation of the input text into Burmese.

RULES:
1. Translate EVERYTHING — do not skip any sentences
2. Be LITERAL — word-for-word is okay for this stage
3. Keep all character names as close to original pronunciation as possible
4. Keep all dialogue and descriptions
5. Output ONLY the Burmese translation, nothing else

NOTE: This is a rough draft that will be polished later. Focus on accuracy and completeness, not style."""


class BurmeseRewriter:
    """
    Rewrites rough Burmese translations into natural, literary Burmese.
    
    This implements Stage 2 of the two-stage pipeline from need_to_fix.md.
    """
    
    def __init__(self, model_name: str = None, glossary_manager=None):
        """
        Initialize the rewriter.
        
        Args:
            model_name: Model to use for rewriting (defaults to AI_MODEL env var)
            glossary_manager: Optional GlossaryManager for name consistency
        """
        self.model_name = model_name or os.getenv("AI_MODEL", "ollama")
        self.translator = None
        self.glossary_manager = glossary_manager
        
    def _get_translator(self) -> BaseTranslator:
        """Lazy load the translator."""
        if self.translator is None:
            self.translator = get_translator(self.model_name)
        return self.translator
    
    def rewrite(self, rough_text: str, context: str = "") -> str:
        """
        Rewrite rough Burmese translation into natural Burmese.
        
        Args:
            rough_text: The rough/stiff translation to rewrite
            context: Previous context for consistency (optional)
            
        Returns:
            Polished, natural Burmese text
        """
        if not rough_text or not rough_text.strip():
            return ""
        
        # Build glossary text
        glossary_text = ""
        if self.glossary_manager is not None:
            try:
                glossary_text = self.glossary_manager.get_glossary_text()
            except Exception as e:
                logger.warning(f"Failed to get glossary: {e}")
        
        # Get the rewrite prompt
        system_prompt = get_rewrite_prompt(glossary_text, context)
        
        # Prepare the user prompt
        user_prompt = f"""ROUGH BURMESE TRANSLATION TO REWRITE:

{rough_text}

---

Rewrite the above text into natural, emotionally resonant Burmese following ALL the rules in your instructions.
Remember: Short sentences, real dialogue, show emotions through physical sensations, modern conversational language."""
        
        # Get translator and rewrite
        translator = self._get_translator()
        
        logger.info(f"Rewriting {len(rough_text)} chars of rough translation")
        
        try:
            result = translator.translate(user_prompt, system_prompt)
            logger.info(f"Rewrote into {len(result)} chars of polished Burmese")
            return result
        except Exception as e:
            logger.error(f"Rewriting failed: {e}")
            # Return original if rewriting fails
            return rough_text
    
    def rewrite_stream(self, rough_text: str, context: str = "") -> Iterator[str]:
        """
        Rewrite with streaming output.
        
        Args:
            rough_text: The rough translation to rewrite
            context: Previous context (optional)
            
        Yields:
            Chunks of rewritten text as they arrive
        """
        if not rough_text or not rough_text.strip():
            return
        
        # Build glossary text
        glossary_text = ""
        if self.glossary_manager is not None:
            try:
                glossary_text = self.glossary_manager.get_glossary_text()
            except Exception as e:
                logger.warning(f"Failed to get glossary: {e}")
        
        # Get the rewrite prompt
        system_prompt = get_rewrite_prompt(glossary_text, context)
        
        # Prepare the user prompt
        user_prompt = f"""ROUGH BURMESE TRANSLATION TO REWRITE:

{rough_text}

---

Rewrite the above text into natural, emotionally resonant Burmese following ALL the rules in your instructions."""
        
        # Get translator and rewrite with streaming
        translator = self._get_translator()
        
        logger.info(f"Rewriting {len(rough_text)} chars (streaming)")
        
        try:
            yield from translator.translate_stream(user_prompt, system_prompt)
        except Exception as e:
            logger.error(f"Streaming rewrite failed: {e}")
            # Fall back to non-streaming
            result = self.rewrite(rough_text, context)
            yield result


def rewrite_burmese(rough_text: str, 
                   model_name: str = None,
                   glossary_manager=None,
                   context: str = "") -> str:
    """
    Convenience function to rewrite rough Burmese translation.
    
    Args:
        rough_text: The rough translation to polish
        model_name: Model to use for rewriting
        glossary_manager: Optional glossary for name consistency
        context: Previous context (optional)
        
    Returns:
        Polished Burmese text
    """
    rewriter = BurmeseRewriter(model_name, glossary_manager)
    return rewriter.rewrite(rough_text, context)


def two_stage_translate(text: str,
                       raw_translator: BaseTranslator,
                       rewriter_model: str = None,
                       glossary_manager=None,
                       source_lang: str = "Chinese") -> str:
    """
    Perform two-stage translation: raw translation + rewrite.
    
    This implements the full pipeline from need_to_fix.md:
    Stage 1: Raw literal translation
    Stage 2: Rewrite into natural Burmese
    
    Args:
        text: Original text to translate
        raw_translator: Translator for stage 1 (can be NLLB or basic LLM)
        rewriter_model: Model name for stage 2 (defaults to AI_MODEL env var)
        glossary_manager: Optional glossary for name consistency
        source_lang: Source language
        
    Returns:
        Polished Burmese translation
    """
    logger.info("=== STAGE 1: Raw Translation ===")
    
    # Stage 1: Raw translation
    raw_prompt = get_raw_translation_prompt(source_lang)
    rough_translation = raw_translator.translate(text, raw_prompt)
    
    logger.info(f"Stage 1 complete: {len(rough_translation)} chars")
    logger.info("=== STAGE 2: Rewriting ===")
    
    # Stage 2: Rewrite
    rewriter = BurmeseRewriter(rewriter_model, glossary_manager)
    polished_translation = rewriter.rewrite(rough_translation)
    
    logger.info(f"Stage 2 complete: {len(polished_translation)} chars")
    
    return polished_translation


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python rewriter.py <rough_translation_file> [model_name]")
        print("Example: python rewriter.py rough_output.txt ollama")
        sys.exit(1)
    
    input_file = sys.argv[1]
    model = sys.argv[2] if len(sys.argv) > 2 else None
    
    # Read rough translation
    with open(input_file, 'r', encoding='utf-8') as f:
        rough_text = f.read()
    
    print(f"Rewriting {len(rough_text)} characters...")
    print("=" * 60)
    
    # Rewrite
    rewriter = BurmeseRewriter(model)
    polished = rewriter.rewrite(rough_text)
    
    # Save output
    output_file = input_file.replace('.txt', '_polished.txt')
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(polished)
    
    print("=" * 60)
    print(f"✓ Rewrote to: {output_file}")
    print(f"  Original: {len(rough_text)} chars")
    print(f"  Polished: {len(polished)} chars")
