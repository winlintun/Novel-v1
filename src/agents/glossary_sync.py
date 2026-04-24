"""
Glossary Synchronization Agent
- Uses aya-expanse:8b for multilingual terminology mapping
- Detects inconsistent translations across chapters
- Proposes merges for duplicate terms
"""
import logging
from typing import Optional, List, Dict, Any

from src.memory.memory_manager import MemoryManager
from src.utils.ollama_client import OllamaClient
from src.utils.file_handler import FileHandler
from src.utils.json_extractor import extract_json_from_response

logger = logging.getLogger(__name__)

class GlossarySyncAgent:
    """Sync terminology consistency using multilingual LLM."""
    
    def __init__(
        self,
        memory_manager: MemoryManager,
        ollama_client: OllamaClient,
        model: str = "aya-expanse:8b"
    ):
        self.mm = memory_manager
        self.client = ollama_client
        self.model = model
    
    def check_consistency(self, chapter_text: str, chapter_num: int) -> List[Dict[str, Any]]:
        """
        Scan chapter for terms that may have inconsistent translations.
        Returns list of potential issues for human review.
        """
        glossary = self.mm.get_all_terms()
        
        prompt = f"""
You are a terminology consistency specialist for Chinese-Myanmar translation.

TASK: Scan the Myanmar text below and identify any terms that:
1. Appear to be translations of glossary terms but don't match exactly
2. Could be variants of existing terms (synonyms, spelling variants)
3. Should be added to glossary but aren't

GLOSSARY (approved terms):
{glossary}

MYANMAR TEXT (Chapter {chapter_num}):
{chapter_text}

OUTPUT FORMAT (JSON only):
{{
  "inconsistencies": [
    {{"term_in_text": "found_variant", "glossary_term": "approved_term", "suggestion": "replace_with_approved"}}
  ],
  "new_candidates": [
    {{"source_cn": "新词", "proposed_mm": "ကမ်းလှမ်းချက်", "category": "item", "confidence": 0.85}}
  ]
}}

Return ONLY valid JSON. No explanations.
"""
        
        response = self.client.chat(
            prompt=prompt,
            temperature=0.1
        )
        
        # Parse and validate response
        try:
            result = extract_json_from_response(response)
            inconsistencies = result.get("inconsistencies", [])
            candidates = result.get("new_candidates", [])
            # Make sure it's lists
            if not isinstance(inconsistencies, list):
                inconsistencies = []
            if not isinstance(candidates, list):
                candidates = []
            return inconsistencies + candidates
        except Exception as e:
            # Fallback: return empty, log warning
            logger.warning(f"Failed to parse consistency check response: {e}")
            return []
    
    def propose_merges(self) -> List[Dict[str, Any]]:
        """
        Analyze glossary_pending.json for terms that might duplicate existing entries.
        Returns merge suggestions for human approval.
        """
        pending = []
        pending_data = FileHandler.read_json("data/glossary_pending.json")
        if pending_data:
            pending = pending_data.get("pending_terms", [])

        approved = self.mm.get_all_terms()
        
        prompt = f"""
You are a terminology deduplication specialist.

TASK: Compare pending terms against approved glossary.
Identify pending terms that are likely:
1. Duplicate of existing term (different spelling/transliteration)
2. Sub-category of existing term
3. Completely new (no conflict)

PENDING TERMS:
{pending}

APPROVED GLOSSARY:
{approved}

OUTPUT FORMAT (JSON only):
{{
  "merge_suggestions": [
    {{"pending_id": "pending_001", "approved_id": "term_042", "reason": "Same character, variant transliteration"}}
  ],
  "keep_separate": ["pending_003", "pending_007"]
}}

Return ONLY valid JSON.
"""
        response = self.client.chat(
            prompt=prompt,
            temperature=0.1
        )

        try:
            result = extract_json_from_response(response)
            return result.get("merge_suggestions", [])
        except Exception as e:
            logger.warning(f"Failed to parse merge proposals response: {e}")
            return []
