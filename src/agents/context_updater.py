"""
Context Updater Agent
Updates memory after chapter translation.
Extracts entities and updates glossary/context.
"""

import logging
import re
from typing import Dict, List, Any

from src.utils.ollama_client import OllamaClient
from src.memory.memory_manager import MemoryManager
from src.utils.json_extractor import safe_parse_terms
from src.agents.base_agent import BaseAgent
from src.agents.prompt_patch import EXTRACTOR_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class ContextUpdater(BaseAgent):
    """
    Updates memory after chapter translation:
    - Extracts new entities
    - Updates glossary
    - Updates chapter context
    """
    
    def __init__(
        self,
        ollama_client: OllamaClient,
        memory_manager: MemoryManager,
        config: Dict[str, Any] = None
    ):
        super().__init__(ollama_client, memory_manager, config)
    
    def extract_entities(self, text: str) -> Dict[str, List]:
        """
        Extract entities from text using LLM.
        Uses safe_parse_terms to handle malformed JSON gracefully.
        
        Args:
            text: Source text to analyze
            
        Returns:
            Dict with extracted entities by category
        """
        # Limit text length for extraction
        sample_text = text[:3000]  # First 3000 chars
        
        # Build prompt with glossary context using EXTRACTOR_SYSTEM_PROMPT
        glossary_str = ""
        if self.memory:
            try:
                glossary_str = self.memory.get_glossary_for_prompt(limit=30) or ""
                if not isinstance(glossary_str, str):
                    glossary_str = ""
            except Exception:
                pass
        prompt = EXTRACTOR_SYSTEM_PROMPT.replace("{glossary}", glossary_str).replace("{translated_text}", sample_text)
        
        try:
            raw_response = self.client.chat(prompt=prompt)
            
            # Use safe_parse_terms to handle malformed JSON
            data = safe_parse_terms(raw_response)
            
            # Convert new_terms format to legacy entity format for compatibility
            new_terms = data.get("new_terms", [])
            
            result = {
                'characters': [],
                'cultivation_realms': [],
                'sects_organizations': [],
                'items_artifacts': []
            }
            
            # Map category to result keys
            category_map = {
                'character': 'characters',
                'place': 'sects_organizations',
                'level': 'cultivation_realms',
                'item': 'items_artifacts'
            }
            
            for term in new_terms:
                category = term.get('category', '')
                target_key = category_map.get(category, 'items_artifacts')
                
                result[target_key].append({
                    'name': term.get('source', ''),
                    'description': term.get('target', ''),
                    'type': category
                })
            
            logger.info(f"Extracted {len(new_terms)} new entities")
            return result
            
        except Exception as e:
            logger.warning(f"Entity extraction failed: {e}")
            return {
                'characters': [],
                'cultivation_realms': [],
                'sects_organizations': [],
                'items_artifacts': []
            }
    
    def update_glossary(self, entities: Dict[str, List], chapter_num: int) -> int:
        """
        Add extracted entities to pending glossary for review.
        Uses the target translation provided by the extraction LLM.
        
        Args:
            entities: Extracted entities dict with 'name' and 'description' (translation)
            chapter_num: Current chapter number
            
        Returns:
            Number of new terms added to pending
        """
        added = 0
        
        for category_key, category_name in [
            ('characters', 'character'),
            ('items_artifacts', 'item'),
            ('sects_organizations', 'organization'),
            ('cultivation_realms', 'level'),
        ]:
            for entity in entities.get(category_key, []):
                name = entity.get('name', '').strip()
                translation = entity.get('description', '').strip()
                
                if not name or len(name) > 20:
                    continue
                    
                # Use the LLM-provided translation if it looks valid, else placeholder
                target = translation if translation and translation != f"[{name}]" else f"【?{name}?】"
                
                if self.memory.add_pending_term(
                    source=name,
                    target=target,
                    category=category_name,
                    chapter=chapter_num
                ):
                    added += 1
        
        logger.info(f"Added {added} new terms to pending glossary")
        return added
    
    def update_chapter_context(self, chapter_num: int, translated_text: str):
        """
        Update context memory after chapter translation.
        
        Args:
            chapter_num: Current chapter number
            translated_text: Translated chapter text
        """
        # Update chapter tracking
        self.memory.update_chapter_context(chapter_num)
        
        # Save to disk
        self.memory.save_memory()
        
        logger.info(f"Context updated for Chapter {chapter_num}")
    
    def process_chapter(
        self,
        original_text: str,
        translated_text: str,
        chapter_num: int
    ) -> Dict[str, Any]:
        """
        Process chapter after translation:
        - Extract entities
        - Update glossary
        - Update context
        
        Args:
            original_text: Original Chinese text
            translated_text: Myanmar translation
            chapter_num: Chapter number
            
        Returns:
            Processing results
        """
        logger.info(f"Processing Chapter {chapter_num} for context updates...")
        
        # Extract entities from original
        entities = self.extract_entities(original_text)
        
        # Update glossary with new entities
        new_terms = self.update_glossary(entities, chapter_num)
        
        # Update chapter context
        self.update_chapter_context(chapter_num, translated_text)
        
        return {
            'chapter': chapter_num,
            'entities_found': sum(len(v) for v in entities.values()),
            'new_terms_added': new_terms,
            'characters': len(entities.get('characters', [])),
            'realms': len(entities.get('cultivation_realms', [])),
            'sects': len(entities.get('sects_organizations', [])),
            'items': len(entities.get('items_artifacts', []))
        }
