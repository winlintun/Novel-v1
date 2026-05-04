#!/usr/bin/env python3
"""
Glossary Generator Agent
Extracts terminology from source text to build an initial glossary.
Supports both Chinese and English source text.
"""

import logging
from typing import Dict, List, Optional, Any

from src.utils.ollama_client import OllamaClient
from src.memory.memory_manager import MemoryManager
from src.utils.json_extractor import extract_json_from_response
from src.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

GLOSSARY_EXTRACTION_PROMPT = """You are a terminology extraction specialist for Wuxia/Xianxia novels.

TASK: Scan the {source_lang} text and identify all key terminology that should be included in a translation glossary.
Focus on:
1. Character Names (Proper nouns for people)
2. Locations (Places, Sects, Buildings)
3. Items/Artifacts (Weapons, Pills, Treasures)
4. Cultivation Terms (Levels, Techniques, Energy types)

RULES:
1. Output ONLY valid JSON.
2. Format: {{"terms": [{{"source": "Original Term", "target_proposal": "Myanmar/Burmese phonetics", "category": "character|place|level|item", "description": "Brief context"}}]}}
3. Use consistent Myanmar transliteration for names.
4. If no terms found, return {{"terms": []}}

SOURCE LANGUAGE: {source_lang}
TEXT TO ANALYZE:
{text}

OUTPUT (JSON ONLY):"""

class GlossaryGenerator(BaseAgent):
    """
    Agent responsible for automatic glossary generation from source text.
    """

    def __init__(
        self,
        ollama_client: Optional[OllamaClient] = None,
        memory_manager: Optional[MemoryManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        super().__init__(ollama_client, memory_manager, config)

    def extract_terms(self, text: str, source_lang: str = "Chinese") -> List[Dict[str, Any]]:
        """
        Extract terms from a block of text.
        """
        prompt = GLOSSARY_EXTRACTION_PROMPT.format(
            source_lang=source_lang,
            text=text[:4000] # Limit to 4000 chars for context window
        )

        try:
            response = self.client.chat(prompt=prompt)
            data = extract_json_from_response(response)
            return data.get("terms", [])
        except Exception as e:
            self.log_error(f"Term extraction failed: {e}")
            return []

    def process_files(self, file_paths: List[str], source_lang: str = "Chinese") -> List[Dict[str, Any]]:
        """
        Process multiple files to generate a comprehensive glossary.
        Uses single sample per file for speed - duplicate terms across files are deduped.
        """
        all_terms = {} # Use dict to deduplicate by source term

        for path in file_paths:
            self.log_info(f"Extracting terms from {path}...")
            try:
                with open(path, 'r', encoding='utf-8-sig') as f:
                    content = f.read()

                # Single sample from the first 4000 chars - fast extraction
                # Duplicate detection across multiple files provides coverage
                sample = content[:4000]
                terms = self.extract_terms(sample, source_lang)
                for term in terms:
                    source = term.get("source")
                    if source and source not in all_terms:
                        all_terms[source] = term

            except Exception as e:
                self.log_error(f"Error reading {path}: {e}")

        return list(all_terms.values())

    def save_to_pending(self, terms: List[Dict[str, Any]], chapter_num: int = 0):
        """
        Save extracted terms to glossary_pending.json.
        """
        for term in terms:
            self.memory.add_pending_term(
                source=term.get("source"),
                target=term.get("target_proposal", ""),
                category=term.get("category", "item"),
                chapter=chapter_num
            )

        self.log_info(f"Saved {len(terms)} terms to pending glossary.")

    def generate_from_chapter(self, chapter_file: str, chapter_num: int = 0) -> int:
        """
        Generate glossary terms from a single chapter file.
        
        Args:
            chapter_file: Path to the chapter file
            chapter_num: Chapter number for logging
            
        Returns:
            Number of terms extracted
        """
        try:
            logger.info(f"Reading chapter {chapter_num}: {chapter_file}")

            # Read the chapter file
            with open(chapter_file, 'r', encoding='utf-8-sig') as f:
                content = f.read()

            if not content.strip():
                logger.warning(f"Chapter {chapter_num} is empty")
                return 0

            # Detect source language
            from src.agents.preprocessor import Preprocessor
            preprocessor = Preprocessor()
            detected_lang = preprocessor.detect_language(content)
            source_lang = "Chinese" if detected_lang == "chinese" else "English"

            logger.info(f"Processing chapter {chapter_num} ({source_lang}, {len(content)} chars)...")

            # Process this file
            terms = self.process_files([chapter_file], source_lang)

            # Save to pending
            if terms:
                self.save_to_pending(terms, chapter_num)
                logger.info(f"✅ Chapter {chapter_num}: Extracted {len(terms)} terms")
            else:
                logger.info(f"⚠️ Chapter {chapter_num}: No terms found")

            return len(terms)

        except Exception as e:
            logger.error(f"❌ Failed to process chapter {chapter_num}: {e}")
            return 0
