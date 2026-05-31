"""
Refiner Agent
Polishes Myanmar translation for better flow, tone, and literary quality.
Uses batch processing for 5-10x speedup.
"""

import re
import logging
from typing import List, Optional

from src.utils.ollama_client import OllamaClient
from src.agents.base_agent import BaseAgent
from src.agents.prompts import EDITOR_SYSTEM_PROMPT
from src.agents.prompts.cn_mm_rules import build_rewriter_prompt as build_cn_rewriter
from src.agents.prompts.en_mm_rules import build_rewriter_prompt as build_en_rewriter
from src.utils.postprocessor import clean_output
from src.memory.memory_manager import MemoryManager

logger = logging.getLogger(__name__)

# Glossary enforcement section appended to the editor prompt
GLOSSARY_ENFORCEMENT = """

STRICT GLOSSARY RULES:
- Use EXACTLY the approved Myanmar spellings for all names, places, and cultivation terms.
- If you see a character name or place name, check the GLOSSARY above for the correct spelling.
- NEVER invent or change phonetic spellings — only use the glossary-approved forms.
- If a term is not in the glossary, preserve the existing translation unchanged.
- NEVER translate Chinese character names as Myanmar color/meaning words.
  Example: 紫 in a name → use glossary transliteration, NOT ခရမ်း (color word).

PARTICLE DIVERSITY RULE:
- Avoid CONSECUTIVE repetition of the same particle (e.g., "သည်...သည်...သည်").
- Normal single use of သည် per sentence is correct grammar — do NOT remove it.
- If you see 3+ consecutive sentences all ending with the same particle, vary 1-2 of them.
- Use ကို, မှာ, ၏, ၌, ဖြင့် as alternatives where appropriate.

DIALOGUE REGISTER CHECK (CRITICAL):
- Confrontation scenes: characters use ငါ/နင် (casual/aggressive), NOT ကျွန်ုပ်/သင်
- Respectful dialogue: use ခင်ဗျား/ကျုပ်, NOT ကျွန်ုပ်၏/သင်၏
- NEVER use ရှိပါတယ်/မတရားပါသလား in dramatic/life-and-death scenes
- Use natural endings: ဖြစ်တယ်, မသင့်ဘူးလား, ငါ့ဟာ

LITERARY IDIOM INJECTION:
- Replace literal translations with Myanmar literary equivalents:
  "echoed everywhere" → အရပ်ရှစ်မျက်နှာသို့ ပဲ့တင်ထပ် (eight directions idiom)
  "bewildered" → မိန်းမောတွေဝေ (classic literary expression)
  "like lightning" → မိုးကြိုးပစ်ချလိုက်သည့်ပမာ (dramatic)
  "wind blowing" → လေတဟူးဟူး တိုက်ခတ် (reduplication for sound)
- Use Myanmar reduplication (ထပ်ကိန်း) for vivid description:
  Movement: လှုပ်လှုပ်ရှားရှား, တုန်တုန်ယင်ယင်
  Sound: ဝှီးခနဲ, ဟိန်းခနဲ, တဖျပ်ဖျပ်
  Extent: ကျယ်ကျယ်ပြန့်ပြန့်, နက်နက်ရှိုင်းရှိုင်း

CONTENT COMPLETENESS CHECK:
- Verify ALL source paragraphs are translated — no skipping or compressing.
- ALL dialogue lines must be present — no missing exchanges.
- If source has N paragraphs, output must have N paragraphs.
"""


class Refiner(BaseAgent):
    """
    Refines translated text for better quality.
    Uses batch processing for 5-10x speedup over paragraph-by-paragraph.
    Uses build_rewriter_prompt() from linguistic rules for scene-aware prompts.
    """

    def __init__(self, ollama_client: OllamaClient = None, batch_size: int = 5,
                 config: dict = None, memory_manager: Optional[MemoryManager] = None):
        super().__init__(ollama_client, config=config, memory_manager=memory_manager)
        self.ollama = ollama_client
        self.batch_size = batch_size

    def _detect_scene_type(self, text: str) -> str:
        """Detect scene type from Myanmar text for dynamic rule injection."""
        confrontation_kw = ['နင်', 'သေ', 'သတ်', 'မုန်း', 'လက်စား', 'ဒီကောင်', 'မိစ္ဆာ']
        action_kw = ['ထိုး', 'တိုက်', 'ခုတ်', 'ပစ်', 'ရိုက်', 'ကန်', 'ဓား', 'လက်သီး']
        lines = [l for l in text.split('\n') if l.strip()]
        total_lines = len(lines) if lines else 1
        dialogue_lines = sum(1 for l in lines if any(q in l for q in '""「」'))
        exclamation_count = text.count('!')
        confrontation_count = sum(1 for kw in confrontation_kw if kw in text)
        action_count = sum(1 for kw in action_kw if kw in text)
        dialogue_ratio = dialogue_lines / total_lines

        if confrontation_count >= 2 or (exclamation_count >= 2 and dialogue_ratio > 0.3):
            return "confrontation"
        if dialogue_ratio > 0.5:
            return "dialogue"
        if action_count >= 3:
            return "action"
        return "narration"

    def _get_glossary_for_prompt(self) -> str:
        """Fetch top 20 glossary terms for injection into the refinement prompt."""
        if hasattr(self, 'memory') and self.memory:
            try:
                return self.memory.get_glossary_for_prompt(limit=20)
            except Exception:
                pass
        return ""

    def _build_prompt(self, text: str, scene_type: str = "narration",
                      batch_mode: bool = False, batch_count: int = 1,
                      source_lang: str = "chinese") -> tuple:
        """Build system prompt + user prompt using live build_rewriter_prompt().

        Falls back to EDITOR_SYSTEM_PROMPT + GLOSSARY_ENFORCEMENT if
        the dynamic builder fails.
        """
        glossary_block = self._get_glossary_for_prompt()
        glossary_prefix = ""
        if glossary_block:
            glossary_prefix = glossary_block + "\n\n"

        try:
            if source_lang.startswith("en"):
                system_prompt = build_en_rewriter(
                    glossary_text=glossary_block,
                    context="",
                ) + "\n\n" + GLOSSARY_ENFORCEMENT
            else:
                system_prompt = build_cn_rewriter(
                    glossary_text=glossary_block,
                    context="",
                    scene_type=scene_type,
                ) + "\n\n" + GLOSSARY_ENFORCEMENT
        except Exception as e:
            logger.warning(f"build_rewriter_prompt failed ({e}), falling back to EDITOR_SYSTEM_PROMPT")
            system_prompt = EDITOR_SYSTEM_PROMPT + GLOSSARY_ENFORCEMENT

        if batch_mode:
            separator = "\n---PARA---\n"
            user_prompt = f"""{glossary_prefix}Refine these {batch_count} Myanmar paragraphs into better Myanmar translation.
⚠️ CRITICAL: Your output MUST be in Myanmar Unicode script (U+1000-U+109F). DO NOT output English.
DO NOT re-translate the original English content - only refine the existing Myanmar translation.
Separate output with: {separator}

{text}

REFINED MYANMAR TEXT:"""
        else:
            user_prompt = f"""{glossary_prefix}Refine this Myanmar text for better flow and literary quality.
⚠️ CRITICAL: Output MUST be Myanmar Unicode script. DO NOT output English.

{text}

REFINED MYANMAR TEXT:"""

        return system_prompt, user_prompt

    def refine_paragraph(self, text: str) -> str:
        """
        Refine a single paragraph (legacy method).

        Auto-detects scene type for dynamic cultural rule injection.

        Args:
            text: Raw Myanmar translation

        Returns:
            Refined Myanmar text
        """
        scene_type = self._detect_scene_type(text)
        system_prompt, user_prompt = self._build_prompt(text, scene_type)

        raw = self.ollama.chat(
            prompt=user_prompt,
            system_prompt=system_prompt,
        )

        return clean_output(raw)

    def refine_batch(self, paragraphs: List[str]) -> List[str]:
        """
        Refine multiple paragraphs in a single API call (FAST).
        
        Auto-detects scene type from combined text.

        Args:
            paragraphs: List of paragraphs to refine
            
        Returns:
            List of refined paragraphs
        """
        if not paragraphs:
            return []

        if len(paragraphs) == 1:
            return [self.refine_paragraph(paragraphs[0])]

        separator = "\n---PARA---\n"
        combined = separator.join(paragraphs)

        # Detect scene type from combined text for dynamic rule injection
        scene_type = self._detect_scene_type(combined)
        system_prompt, user_prompt = self._build_prompt(
            combined, scene_type=scene_type,
            batch_mode=True, batch_count=len(paragraphs),
        )

        try:
            raw = self.ollama.chat(
                prompt=user_prompt,
                system_prompt=system_prompt,
            )

            cleaned = clean_output(raw)
            refined = cleaned.split(separator)
            refined = [p.strip() for p in refined if p.strip()]

            # Pad with originals if needed
            while len(refined) < len(paragraphs):
                idx = len(refined)
                refined.append(paragraphs[idx] if idx < len(paragraphs) else "")

            return refined[:len(paragraphs)]

        except Exception as e:
            logger.error(f"Batch refinement failed: {e}, falling back to individual")
            # Fallback to individual processing
            return [self.refine_paragraph(p) for p in paragraphs]

    def refine_chapter(self, paragraphs: List[str]) -> List[str]:
        """
        Refine multiple paragraphs using batch processing.
        
        Args:
            paragraphs: List of translated paragraphs
            
        Returns:
            List of refined paragraphs
        """
        refined = []
        total = len(paragraphs)

        # Process in batches
        for i in range(0, total, self.batch_size):
            batch = paragraphs[i:i + self.batch_size]
            batch_num = i // self.batch_size + 1
            total_batches = (total + self.batch_size - 1) // self.batch_size

            logger.info(f"Refining batch {batch_num}/{total_batches} ({len(batch)} paragraphs)...")

            batch_result = self.refine_batch(batch)
            refined.extend(batch_result)

        return refined

    def refine_full_text(self, text: str) -> str:
        """
        Refine entire chapter text using batch processing.
        
        Args:
            text: Full chapter translation
            
        Returns:
            Refined chapter
        """
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]

        if not paragraphs:
            return text

        refined_paragraphs = self.refine_chapter(paragraphs)
        return '\n\n'.join(refined_paragraphs)
