"""
Fast Refiner Agent with Batch Processing
Processes multiple paragraphs in a single API call for 5-10x speedup.
"""

import logging
from typing import List

from src.utils.ollama_client import OllamaClient
from src.agents.prompt_patch import EDITOR_SYSTEM_PROMPT
from src.utils.postprocessor import clean_output

logger = logging.getLogger(__name__)


BATCH_REFINER_SYSTEM_PROMPT = """You are a senior Myanmar literary editor. 
Refine multiple Myanmar text paragraphs for natural flow and literary quality.

RULES:
1. Fix awkward phrasing from direct translation
2. Ensure correct SOV structure and proper particle usage
3. Use modern storytelling words (မင်း, ဒီ) not archaic (သင်သည်, ဤ)
4. Keep all Wuxia/Xianxia terms intact
5. Preserve Markdown formatting

OUTPUT FORMAT:
Return paragraphs separated by "\n\n---PARAGRAPH_BREAK---\n\n"
DO NOT add explanations, only the refined text."""


class FastRefiner:
    """
    Fast batch refiner that processes multiple paragraphs at once.
    5-10x faster than paragraph-by-paragraph refinement.
    """
    
    def __init__(
        self,
        ollama_client: OllamaClient,
        batch_size: int = 5,
        max_batch_chars: int = 2000
    ):
        self.ollama = ollama_client
        self.batch_size = batch_size
        self.max_batch_chars = max_batch_chars
    
    def create_batches(self, paragraphs: List[str]) -> List[List[str]]:
        """
        Create batches of paragraphs for efficient processing.
        
        Args:
            paragraphs: List of all paragraphs
            
        Returns:
            List of batches (each batch is a list of paragraphs)
        """
        batches = []
        current_batch = []
        current_chars = 0
        
        for para in paragraphs:
            para_chars = len(para)
            
            # Check if adding this paragraph would exceed limits
            if (len(current_batch) >= self.batch_size or 
                current_chars + para_chars > self.max_batch_chars):
                if current_batch:
                    batches.append(current_batch)
                current_batch = [para]
                current_chars = para_chars
            else:
                current_batch.append(para)
                current_chars += para_chars
        
        # Add remaining paragraphs
        if current_batch:
            batches.append(current_batch)
        
        return batches
    
    def refine_batch(self, batch: List[str]) -> List[str]:
        """
        Refine a batch of paragraphs in a single API call.
        
        Args:
            batch: List of paragraphs to refine
            
        Returns:
            List of refined paragraphs
        """
        if not batch:
            return []
        
        # Join paragraphs with separator
        separator = "\n\n---PARAGRAPH_BREAK---\n\n"
        combined_text = separator.join(batch)
        
        prompt = f"""Refine these {len(batch)} Myanmar text paragraphs.
Maintain the same number of paragraphs. Separate output with:
{separator}

TEXT TO REFINE:
{combined_text}

REFINED TEXT:"""
        
        try:
            raw_response = self.ollama.chat(
                prompt=prompt,
                system_prompt=BATCH_REFINER_SYSTEM_PROMPT,
                stream=False
            )
            
            # Clean the output
            cleaned = clean_output(raw_response)
            
            # Split back into paragraphs
            refined_paragraphs = cleaned.split(separator)
            
            # Clean up each paragraph
            refined_paragraphs = [p.strip() for p in refined_paragraphs if p.strip()]
            
            # If we got fewer paragraphs than expected, log warning
            if len(refined_paragraphs) != len(batch):
                logger.warning(
                    f"Batch refinement: expected {len(batch)} paragraphs, "
                    f"got {len(refined_paragraphs)}"
                )
                
                # Pad with originals if needed
                while len(refined_paragraphs) < len(batch):
                    idx = len(refined_paragraphs)
                    if idx < len(batch):
                        refined_paragraphs.append(batch[idx])
            
            return refined_paragraphs
            
        except Exception as e:
            logger.error(f"Batch refinement failed: {e}")
            # Return original paragraphs on failure
            return batch
    
    def refine_chapter(self, paragraphs: List[str]) -> List[str]:
        """
        Refine all paragraphs using batch processing.
        
        Args:
            paragraphs: List of translated paragraphs
            
        Returns:
            List of refined paragraphs
        """
        if not paragraphs:
            return []
        
        # Create batches
        batches = self.create_batches(paragraphs)
        logger.info(f"Created {len(batches)} batches from {len(paragraphs)} paragraphs")
        
        refined = []
        total_batches = len(batches)
        
        for i, batch in enumerate(batches, 1):
            logger.info(f"Refining batch {i}/{total_batches} ({len(batch)} paragraphs)...")
            
            batch_result = self.refine_batch(batch)
            refined.extend(batch_result)
        
        return refined
    
    def refine_full_text(self, text: str) -> str:
        """
        Refine entire chapter text using batch processing.
        
        Args:
            text: Full chapter translation
            
        Returns:
            Refined chapter text
        """
        # Split into paragraphs
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        
        if not paragraphs:
            return text
        
        # Refine in batches
        refined_paragraphs = self.refine_chapter(paragraphs)
        
        # Join back
        return '\n\n'.join(refined_paragraphs)


# Backwards compatibility alias
Refiner = FastRefiner
