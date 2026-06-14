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
- target: Myanmar Unicode ONLY (U+1000-U+109F)
- NEVER use Thai, Bengali, Korean, Chinese, or English letters in target
- Standard punctuation only: ? ! : , . (NOT fullwidth variants)
- Unknown / unresolvable term -> target: "【?term?】"

## OUTPUT SCHEMA
Return ONLY valid JSON. No markdown fences. No explanation. No preamble.

{{
  "extraction_meta": {{
    "schema_version": "3.2.1",
    "source_language": "{source_lang}",
    "total_terms_found": 0
  }},
  "terms": [
    {{
      "source": "Exact term as it appears in source text",
      "target": "Myanmar transliteration or translation",
      "category": "character|creature|place|organization|title|cultivation|technique|item|food|currency|concept",
      "subtype": "specific kind, see SUBTYPE list below (or omit if unsure)",
      "confidence": 0.85
    }}
  ]
}}

## SUBTYPE (fine-grained kind under the coarse category)
- place    : empire, dynasty, kingdom, country, region, province, prefecture, district,
             township, city, town, village, hamlet, ward, street, marketplace, mountain,
             peak, range, river, lake, sea, valley, gorge, forest, plains, desert,
             wilderness, secret_realm, dungeon, cave_abode, sealed_land, spiritual_vein,
             hall, pavilion, tower, terrace, gate, courtyard, manor, estate, temple,
             shrine, monastery, tomb, ancestral_hall
- organization : sect, clan, family, guild, alliance
- title    : king, prince, princess, noble, lord, official_rank, minister, general,
             sect_master, peak_master, elder, steward, disciple, family_head,
             patriarch, matriarch
- cultivation  : realm, rank, stage, spiritual_root, concept
- technique : sword_art, body_technique, spell, skill, formation
- item     : weapon, artifact, pill, treasure, material, talisman
- creature : beast, spirit_beast, demon_beast, monster, mount
- concept  : term, law, dao, direction, event

## FIELD RULES
1. confidence: Float 0.0-1.0. >=0.95 = auto-merge eligible. <0.70 = flag for manual review.
2. deduplication: Merge case variants into one entry. Use the most common spelling.
3. subtype: choose the most specific kind from the SUBTYPE list. If none fits, omit the field.

## FALLBACK
If no terms found, return EXACTLY:
{{"extraction_meta": {{"schema_version": "3.2.1", "source_language": "{source_lang}", "total_terms_found": 0}}, "terms": []}}

SOURCE LANGUAGE: {source_lang}

TEXT TO ANALYZE:
{text}

OUTPUT (RAW JSON ONLY, NO MARKDOWN):"""

CROSS_LINGUAL_GLOSSARY_PROMPT = """You are a bilingual terminology extraction specialist for Wuxia/Xianxia novels.

## TASK
You are given the SAME chapter in TWO languages: English (source) and Myanmar (translation).
For each named entity in the English text (characters, places, techniques, items, etc.),
find its corresponding translation in the Myanmar text and output a glossary entry.

## EXTRACTION CATEGORIES
1. character           : Named people, spirits, demons, gods
2. location            : Places, sects, realms, buildings
3. organization        : Sects, clans, guilds, factions
4. item_artifact       : Named weapons, pills, treasures, cauldrons
5. technique           : Named skills, spells, sword arts, techniques
6. power_level         : Cultivation ranks, realm names, grade tiers
7. cultivation_concept : Energy types, dao concepts, laws, paths
8. title_honorific     : Formal titles, kinship terms, epithets

## RULES
- Extract the EXACT English term from the English text
- Find its EXACT Myanmar equivalent in the Myanmar text — use the term AS IT APPEARS in the translation, do NOT re-translate or guess
- If a term appears in English but NOT in the Myanmar text, skip it (it wasn't translated)
- If a term appears in Myanmar but NOT in the English text, skip it (it was inserted by the translator)
- Use Myanmar Unicode ONLY (U+1000-U+109F) for target
- Unknown / no match -> target: "【?term?】"

## OUTPUT
Return ONLY valid JSON. No markdown. No explanation.

{{
  "extraction_meta": {{
    "schema_version": "3.2.1",
    "source_language": "English",
    "total_terms_found": 0
  }},
  "terms": [
    {{
      "source": "Exact English term from source text",
      "target": "Exact Myanmar term from translation text",
      "category": "character|location|organization|item_artifact|technique|power_level|cultivation_concept|title_honorific",
      "confidence": 0.85
    }}
  ]
}}

## FALLBACK
If no terms found: {{"extraction_meta": {{"schema_version": "3.2.1", "source_language": "English", "total_terms_found": 0}}, "terms": []}}

ENGLISH TEXT:
{en_text}

MYANMAR TEXT:
{mm_text}

OUTPUT (RAW JSON ONLY, NO MARKDOWN):"""

class GlossaryGenerator(BaseAgent):
    """
    Agent responsible for automatic glossary generation from source text.
    """

    # Sliding-window extraction parameters. Each window is one bounded Ollama
    # call (chat() enforces its own timeout + retry cap). MAX_WINDOWS_PER_FILE
    # is a hard ceiling so an unexpectedly huge file can never spawn an
    # unbounded number of requests (NO HANGING REQUESTS rule).
    WINDOW_SIZE = 4000
    WINDOW_STEP = 2000
    MAX_WINDOWS_PER_FILE = 20

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

    def _iter_windows(self, content: str) -> List[str]:
        """Split content into overlapping windows for full-coverage extraction.

        Short chapters (<= WINDOW_SIZE) yield a single window. Longer chapters
        are scanned with a sliding window (WINDOW_SIZE chars, WINDOW_STEP step)
        so terms in the second half are not missed. The number of windows is
        hard-capped at MAX_WINDOWS_PER_FILE to bound the number of Ollama calls.
        """
        if len(content) <= self.WINDOW_SIZE:
            return [content] if content else []

        windows: List[str] = []
        start = 0
        while start < len(content) and len(windows) < self.MAX_WINDOWS_PER_FILE:
            windows.append(content[start:start + self.WINDOW_SIZE])
            start += self.WINDOW_STEP
        return windows

    def process_files(self, file_paths: List[str], source_lang: str = "Chinese") -> List[Dict[str, Any]]:
        """
        Process multiple files to generate a comprehensive glossary.
        Each file is scanned with an overlapping sliding window so terms in the
        second half of long chapters are not missed. Duplicate terms (within a
        file and across files) are deduplicated by source term.
        Expects fields: source, target, category, confidence.
        """
        all_terms = {} # Use dict to deduplicate by source term

        for path in file_paths:
            self.log_info(f"Extracting terms from {path}...")
            try:
                with open(path, 'r', encoding='utf-8-sig') as f:
                    content = f.read()

                # Sliding-window extraction: full coverage instead of only the
                # first WINDOW_SIZE chars. extract_terms() already truncates to
                # 4000 chars and handles its own errors per call.
                for window in self._iter_windows(content):
                    terms = self.extract_terms(window, source_lang)
                    for term in terms:
                        source = term.get("source") or term.get("source_term")
                        if source and source not in all_terms:
                            all_terms[source] = term

            except Exception as e:
                self.log_error(f"Error reading {path}: {e}")

        return list(all_terms.values())

    def save_to_pending(self, terms: List[Dict[str, Any]], chapter_num: int = 0):
        """
        Save extracted terms to the database as pending glossary entries.
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
        
        placeholder_count = 0
        for term in terms:
            source = term.get("source") or term.get("source_term", "")
            target = term.get("target") or term.get("target_term", "")
            category = term.get("category", "item")
            subtype = term.get("subtype") or None
            confidence = float(term.get("confidence", 0.0))
            
            # Skip invalid terms (empty)
            if not source or not target:
                continue
            if "【?term?】" in target:
                placeholder_count += 1
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
                chapter=chapter_num,
                confidence=confidence,
                subtype=subtype,
            )
            existing_sources.add(source_lower)  # Track to avoid duplicates within this run
            saved_count += 1

        self.log_info(
            f"Saved {saved_count} terms, skipped {skipped_duplicates} duplicates, "
            f"{placeholder_count} placeholders."
        )

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
            preprocessor = Preprocessor(memory_manager=self.memory)
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

    def generate_from_pair(self, en_file: str, mm_file: str, chapter_num: int = 0) -> int:
        """
        Generate glossary terms by pairing English source with Myanmar translation.
        Reads both files and asks the model to identify named entities in the
        English text and find their corresponding Myanmar equivalents.

        Args:
            en_file: Path to the English source chapter
            mm_file: Path to the Myanmar translation chapter
            chapter_num: Chapter number for logging

        Returns:
            Number of terms extracted
        """
        # Uses module-level constant: CROSS_LINGUAL_GLOSSARY_PROMPT

        try:
            logger.info(f"Reading chapter {chapter_num}: EN={en_file} MM={mm_file}")

            with open(en_file, 'r', encoding='utf-8-sig') as f:
                en_content = f.read()
            with open(mm_file, 'r', encoding='utf-8-sig') as f:
                mm_content = f.read()

            if not en_content.strip() or not mm_content.strip():
                logger.warning(f"Chapter {chapter_num}: one of the files is empty")
                return 0

            prompt = CROSS_LINGUAL_GLOSSARY_PROMPT.format(
                en_text=en_content[:2500],
                mm_text=mm_content[:2500],
            )

            try:
                response = self.client.chat(prompt=prompt)
                data = extract_json_from_response(response)
                terms = data.get("terms", [])
            except Exception as e:
                logger.error(f"Term extraction failed for chapter {chapter_num}: {e}")
                terms = []

            if terms:
                self.save_to_pending(terms, chapter_num)
                logger.info(f"✅ Chapter {chapter_num}: Extracted {len(terms)} terms from EN↔MM pair")
            else:
                logger.info(f"⚠️ Chapter {chapter_num}: No terms found")

            return len(terms)

        except Exception as e:
            logger.error(f"❌ Failed to process chapter {chapter_num}: {e}")
            return 0
