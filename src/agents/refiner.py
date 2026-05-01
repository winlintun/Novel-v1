"""
Refiner Agent
Polishes Myanmar translation for better flow, tone, and literary quality.
Uses batch processing for 5-10x speedup.
"""

import logging
from typing import List

from src.utils.ollama_client import OllamaClient
from src.agents.base_agent import BaseAgent
from src.agents.prompt_patch import EDITOR_SYSTEM_PROMPT
from src.utils.postprocessor import clean_output

logger = logging.getLogger(__name__)

# Derived from EDITOR_SYSTEM_PROMPT for batch mode — adds separator output format
BATCH_REFINER_PROMPT = EDITOR_SYSTEM_PROMPT + """
BATCH MODE: Refine multiple paragraphs at once.
OUTPUT: Return paragraphs separated by "---PARA---"
DO NOT add explanations. DO NOT renumber paragraphs.
"""


class Refiner(BaseAgent):
    """
    Refines translated text for better quality.
    Uses batch processing for 5-10x speedup over paragraph-by-paragraph.
    """
    
    def __init__(self, ollama_client: OllamaClient = None, batch_size: int = 5, config: dict = None):
        super().__init__(ollama_client, config=config)
        self.ollama = ollama_client
        self.batch_size = batch_size
    
    def refine_paragraph(self, text: str) -> str:
        """
        Refine a single paragraph (legacy method).
        
        Args:
            text: Raw Myanmar translation
            
        Returns:
            Refined Myanmar text
        """
        prompt = f"""Refine this Myanmar text for better flow and literary quality:

{text}

REFINED TEXT:"""
        
        raw = self.ollama.chat(
            prompt=prompt,
            system_prompt=EDITOR_SYSTEM_PROMPT
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
        
        prompt = f"""Refine these {len(paragraphs)} Myanmar paragraphs.
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
