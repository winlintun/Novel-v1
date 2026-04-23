"""
Refiner Agent
Polishes Myanmar translation for better flow, tone, and literary quality.
"""

import logging
from typing import List

from src.utils.ollama_client import OllamaClient
from src.agents.prompt_patch import EDITOR_SYSTEM_PROMPT
from src.utils.postprocessor import clean_output

logger = logging.getLogger(__name__)


class Refiner:
    """
    Refines translated text for better quality.
    Optional second-pass improvement.
    """
    
    def __init__(self, ollama_client: OllamaClient):
        self.ollama = ollama_client
    
    def refine_paragraph(self, text: str) -> str:
        """
        Refine a single paragraph.
        
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
        
        # Clean output: strip <think>, <answer>, tags, etc.
        refined = clean_output(raw)
        
        return refined
    
    def refine_chapter(self, paragraphs: List[str]) -> List[str]:
        """
        Refine multiple paragraphs.
        
        Args:
            paragraphs: List of translated paragraphs
            
        Returns:
            List of refined paragraphs
        """
        refined = []
        total = len(paragraphs)
        
        for i, para in enumerate(paragraphs, 1):
            logger.info(f"Refining paragraph {i}/{total}...")
            
            try:
                result = self.refine_paragraph(para)
                refined.append(result)
            except Exception as e:
                logger.warning(f"Refinement failed for paragraph {i}: {e}")
                refined.append(para)  # Keep original on failure
        
        return refined
    
    def refine_full_text(self, text: str) -> str:
        """
        Refine entire chapter text at once.
        
        Args:
            text: Full chapter translation
            
        Returns:
            Refined chapter
        """
        # Split into paragraphs
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        
        # Refine each
        refined_paragraphs = self.refine_chapter(paragraphs)
        
        # Join back
        return '\n\n'.join(refined_paragraphs)
