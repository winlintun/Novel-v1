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

GLOSSARY_EXTRACTION_PROMPT = """You are a terminology extraction specialist for Wuxia/Xianxia novels, powered by padauk-gemma — a native Burmese language model.

## TASK
Scan the {source_lang} source text and extract ALL key terminology.
Output MUST exactly match the Universal Glossary Blueprint schema (v3.2.1).
Extracted terms will be merged directly into the project glossary pipeline without manual field mapping.

## EXTRACTION CATEGORIES (Priority Order)
1. character           : Named people, spirits, demons, gods, clones, alter-egos
2. location            : Places, sects, buildings, realms, dungeons, formations
3. organization        : Sects, clans, guilds, factions, armies, councils
4. item_artifact       : Named weapons, pills, treasures, talismans, cauldrons, Gu
5. technique           : Named skills, spells, sword arts, body techniques
6. power_level         : Cultivation ranks, realm names, grade tiers
7. cultivation_concept : Energy types, dao concepts, laws, paths
8. title_honorific     : Formal titles, kinship terms, epithets
9. event               : Named historical events, wars, ceremonies (explicit only)

## MYANMAR TRANSLITERATION & TRANSLATION RULES

### Phonetic Mapping (Chinese/English -> Burmese)
- F/ph       -> ဖ        (Fang -> ဖန်)
- X/Sh       -> ရှ/ချ    (Xian -> ရှန်)
- Q          -> ချ        (Qing -> ချင်း)
- Zh/Ch      -> ချ/ဂျ    (Zhang -> ဇန်, Chen -> ချန်)
- -ing/-eng  -> -င်း/-န် (Ming -> မင်း)
- -an/-en    -> -န်/-မ်  (Yuan -> ယွမ်, Chen -> ချန်)
- -ao        -> -ေါ       (Bao -> ဘေါ)
- -ou        -> -ိုး     (Zhou -> ဇိုး)

### Meaning-Based (Cultivation / Power Terms)
- Translate meaning — do NOT transliterate abstract concepts
- "Spirit Condensation Realm" -> "ဝိညာဉ်စုပေါင်းဘုံ"
- "Heavenly Dao"              -> "နတ်ကောင်းကင်တရားလမ်း"
- "Gu Master"                 -> "ကူးသခင်"

### Hybrid (Place Names)
- Phonetic base + Myanmar location suffix
- "Gu Yue Village"    -> "ကူယွဲ့ကျေးရွာ"
- "Azure Dragon Sect" -> "အေးရှားဒရဂွန်ဂိုဏ်း"

### Unicode Safety (STRICT)
- target_term: Myanmar Unicode ONLY (U+1000-U+109F)
- NEVER use Thai, Bengali, Korean, Chinese, or English letters in target_term
- Standard punctuation only: ? ! : , . (NOT fullwidth variants)
- Unknown / unresolvable term -> target_term: "【?term?】"

## OUTPUT SCHEMA (v3.2.1 COMPLIANT)
Return ONLY valid JSON. No markdown fences. No explanation. No preamble.

{{
  "extraction_meta": {{
    "schema_version": "3.2.1",
    "source_language": "{source_lang}",
    "total_terms_found": 0,
    "overall_confidence": "high|medium|low"
  }},
  "terms": [
    {{
      "id": "char_001",
      "source_term": "Exact term as it appears in source text",
      "target_term": "Myanmar transliteration or translation",
      "aliases_en": ["alternate English spelling"],
      "aliases_cn": ["中文变体"],
      "category": "character|location|organization|item_artifact|technique|power_level|cultivation_concept|title_honorific|event",
      "translation_rule": "transliterate|translate|hybrid|fixed|pattern_match",
      "priority": 1,
      "gender": "male|female|unknown|n/a",
      "affiliation": [],
      "status": "pending",
      "usage_frequency": "high|medium|low",
      "chapter_first_seen": 0,
      "description": "One sentence: role or context in the story for AI tone matching",
      "context_variants": {{
        "formal":   {{"self": "ကျွန်တော်", "target": "ခင်ဗျား", "honorific": "ဆရာ"}},
        "casual":   {{"self": "ငါ",        "target": "မင်း",     "honorific": ""}},
        "hostile":  {{"self": "ငါ",        "target": "နင်",      "honorific": "မိစ္ဆာကောင်"}},
        "pleading": {{"self": "ကျွန်တော်", "target": "အရှင်",   "honorific": "ကျေးဇူးပြု၍"}},
        "intimate": {{"self": "ငါ",        "target": "မင်း",     "honorific": "ချစ်သူ"}}
      }},
      "relationships": [],
      "usage_example": {{
        "source": "Short source sentence showing the term in context",
        "target": ""
      }},
      "confidence": 0.85,
      "notes": "Transliteration rationale, ambiguity, or usage tip"
    }}
  ]
}}

## FIELD RULES (ENFORCE STRICTLY)
1. id: Format {{category_prefix}}_{{3-digit}} (e.g., char_001, loc_002, org_003). Prefixes: char, loc, org, item, tech, lvl, cult, title, event.
2. status: ALWAYS "pending" for extracted terms. Human reviewer changes to "approved" later.
3. context_variants: Fill ONLY for category="character". For ALL other categories, set exactly: "context_variants": {{}}
4. relationships: Array of objects. Only fill if source text explicitly shows a relationship. Format: [{{"target_id": "char_XXX", "relation_type": "master|disciple|enemy|sibling", "attitude": "respectful|hostile|neutral", "default_address": "formal|casual", "override_conditions": []}}]
5. usage_frequency: high (5+ times or plot-critical), medium (2-4 times), low (1 time).
6. confidence: Float 0.0-1.0. >=0.95 = auto-merge eligible. <0.70 = flag for manual review.
7. translation_rule: character/location -> "transliterate" or "hybrid". cultivation/power -> "translate" or "fixed". technique -> "translate".
8. deduplication: Merge case variants ("Fang yuan" / "Fang Yuan") into one entry. Add variants to aliases_en or aliases_cn.

## FALLBACK
If no terms found, return EXACTLY:
{{"extraction_meta": {{"schema_version": "3.2.1", "source_language": "{source_lang}", "total_terms_found": 0, "overall_confidence": "high"}}, "terms": []}}

SOURCE LANGUAGE: {source_lang}

TEXT TO ANALYZE:
{text}

OUTPUT (RAW JSON ONLY, NO MARKDOWN):"""

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
        Extract terms from a block of text using the new v3.2.1 schema.
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
        Now compatible with v3.2.1 schema (source_term, target_term, etc.)
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
                    # v3.2.1 schema uses source_term instead of source
                    source = term.get("source_term") or term.get("source")
                    if source and source not in all_terms:
                        all_terms[source] = term

            except Exception as e:
                self.log_error(f"Error reading {path}: {e}")

        return list(all_terms.values())

    def save_to_pending(self, terms: List[Dict[str, Any]], chapter_num: int = 0):
        """
        Save extracted terms to glossary_pending.json with duplicate checking.
        Now compatible with v3.2.1 schema (source_term, target_term).
        Checks for duplicates against: approved glossary + existing pending terms.
        """
        # Load existing pending terms to check for duplicates
        existing_pending = self.memory.get_pending_terms()
        existing_sources = {t.get("source", "").lower() for t in existing_pending if t.get("source")}
        
        # Also get approved glossary terms
        approved_terms = self.memory.get_all_terms()
        approved_sources = {t.get("source", "").lower() for t in approved_terms if t.get("source")}
        
        saved_count = 0
        skipped_duplicates = 0
        
        for term in terms:
            # v3.2.1 schema: source_term, target_term, category
            source = term.get("source_term") or term.get("source", "")
            target = term.get("target_term") or term.get("target_proposal", "")
            category = term.get("category", "item")
            
            # Skip invalid terms (placeholders, empty)
            if not source or not target or "【?term?】" in target:
                continue
            
            source_lower = source.lower()
            
            # Check for duplicates
            if source_lower in approved_sources:
                skipped_duplicates += 1
                continue
            if source_lower in existing_sources:
                skipped_duplicates += 1
                continue
            
            # Add to pending
            self.memory.add_pending_term(
                source=source,
                target=target,
                category=category,
                chapter=chapter_num
            )
            existing_sources.add(source_lower)  # Track to avoid duplicates within this run
            saved_count += 1

        total_skipped = (len(terms) - saved_count - skipped_duplicates)
        self.log_info(f"Saved {saved_count} terms, skipped {skipped_duplicates} duplicates, {total_skipped} invalid/placeholder.")

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
