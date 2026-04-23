"""
Refiner Agent
Polishes Myanmar translation for better flow, tone, and literary quality.
"""

import logging
from typing import List

from src.utils.ollama_client import OllamaClient

logger = logging.getLogger(__name__)


REFINER_SYSTEM_PROMPT = """You are a professional Myanmar language editor specializing in literary texts.

Your task is to improve the provided Myanmar translation while preserving meaning and structure.

REFINEMENT GOALS:
1. Flow: Ensure sentences connect smoothly, natural transitions
2. Tone Consistency: Maintain appropriate tone (formal for narrative, natural for dialogue)
3. Word Choice: Use evocative, literary vocabulary where appropriate
4. Rhythm: Break overly long sentences; vary sentence length for readability
5. Cultural Fit: Ensure expressions feel natural to Myanmar readers

WHAT NOT TO CHANGE:
- Do NOT alter names (use glossary terms exactly)
- Do NOT change plot or meaning
- Do NOT remove markdown formatting
- Do NOT add explanations or notes

OUTPUT ONLY the refined Myanmar text."""


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
        
        refined = self.ollama.chat(
            prompt=prompt,
            system_prompt=REFINER_SYSTEM_PROMPT
        )
        
        return refined.strip()
    
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
