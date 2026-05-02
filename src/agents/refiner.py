"""
Refiner Agent
Polishes Myanmar translation for better flow, tone, and literary quality.
Uses batch processing for 5-10x speedup.
"""

import logging
from typing import List, Optional

from src.utils.ollama_client import OllamaClient
from src.agents.base_agent import BaseAgent
from src.agents.prompt_patch import EDITOR_SYSTEM_PROMPT
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

PARTICLE DIVERSITY RULE:
- Avoid CONSECUTIVE repetition of the same particle (e.g., "သည်...သည်...သည်").
- Normal single use of သည် per sentence is correct grammar — do NOT remove it.
- If you see 3+ consecutive sentences all ending with the same particle, vary 1-2 of them.
- Use ကို, မှာ, ၏, ၌, ဖြင့် as alternatives where appropriate.
"""

# Derived from EDITOR_SYSTEM_PROMPT for batch mode — adds separator output format
BATCH_REFINER_PROMPT = EDITOR_SYSTEM_PROMPT + GLOSSARY_ENFORCEMENT + """
BATCH MODE: Refine multiple paragraphs at once.
OUTPUT: Return paragraphs separated by "---PARA---"
DO NOT add explanations. DO NOT renumber paragraphs.
"""


class Refiner(BaseAgent):
    """
    Refines translated text for better quality.
    Uses batch processing for 5-10x speedup over paragraph-by-paragraph.
    """
    
    def __init__(self, ollama_client: OllamaClient = None, batch_size: int = 5,
                 config: dict = None, memory_manager: Optional[MemoryManager] = None):
        super().__init__(ollama_client, config=config, memory_manager=memory_manager)
        self.ollama = ollama_client
        self.batch_size = batch_size
    
    def _get_glossary_for_prompt(self) -> str:
        """Fetch top 20 glossary terms for injection into the refinement prompt."""
        if hasattr(self, 'memory') and self.memory:
            try:
                return self.memory.get_glossary_for_prompt(limit=20)
            except Exception:
                pass
        return ""
    
    def refine_paragraph(self, text: str) -> str:
        """
        Refine a single paragraph (legacy method).
        
        Args:
            text: Raw Myanmar translation
            
        Returns:
            Refined Myanmar text
        """
        glossary_block = self._get_glossary_for_prompt()
        glossary_prefix = ""
        if glossary_block:
            glossary_prefix = glossary_block + "\n\n"
        
        prompt = f"""{glossary_prefix}Refine this Myanmar text for better flow and literary quality:

{text}

REFINED TEXT:"""
        
        raw = self.ollama.chat(
            prompt=prompt,
            system_prompt=EDITOR_SYSTEM_PROMPT + GLOSSARY_ENFORCEMENT
        )
        
        return clean_output(raw)
    
    def refine_batch(self, paragraphs: List[str]) -> List[str]:
        """
        Refine multiple paragraphs in a single API call (FAST).
        
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
        
        glossary_block = self._get_glossary_for_prompt()
        glossary_prefix = ""
        if glossary_block:
            glossary_prefix = glossary_block + "\n\n"
        
        prompt = f"""{glossary_prefix}Refine these {len(paragraphs)} Myanmar paragraphs.
Separate output with: {separator}

{combined}

REFINED TEXT:"""
        
        try:
            raw = self.ollama.chat(
                prompt=prompt,
                system_prompt=BATCH_REFINER_PROMPT
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
