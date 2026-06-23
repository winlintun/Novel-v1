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
  ],
  "relationships": [
    {{
      "src": "Exact source string of a term from the terms array above",
      "dst": "Exact source string of another term from the terms array above",
      "relation_type": "one of the RELATION TYPES listed below",
      "confidence": 0.9
    }}
  ]
}}

## RELATIONSHIPS (worldbuilding edges between extracted terms)
Only emit a relationship when BOTH endpoints appear in the `terms` array above
(use their exact `source` strings). relation_type MUST be one of these values:
- located_in     : place located_in larger place; character located_in place
- part_of        : generic containment (region part_of country)
- ruled_by       : kingdom ruled_by king
- rules          : king rules kingdom (inverse of ruled_by)
- capital_of     : city capital_of kingdom
- member_of      : character member_of sect/clan
- heads          : patriarch heads clan; sect_master heads sect
- subordinate_to : peak_master subordinate_to sect_master
- master_of      : character master_of disciple
- disciple_of    : character disciple_of master
- parent_of      : character parent_of character
- child_of       : character child_of character
- sibling_of     : character sibling_of character
- spouse_of      : character spouse_of character
- ally_of        : character ally_of character
- enemy_of       : character enemy_of character
- owns           : character owns item
- wields         : character wields weapon/technique
- located_at     : character located_at place
If no relationships are evident, emit an empty array: "relationships": []

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
{{"extraction_meta": {{"schema_version": "3.2.1", "source_language": "{source_lang}", "total_terms_found": 0}}, "terms": [], "relationships": []}}

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
  ],
  "relationships": [
    {{
      "src": "Exact English source string of a term from the terms array above",
      "dst": "Exact English source string of another term from the terms array above",
      "relation_type": "located_in|part_of|ruled_by|rules|capital_of|member_of|heads|subordinate_to|master_of|disciple_of|parent_of|child_of|sibling_of|spouse_of|ally_of|enemy_of|owns|wields|located_at",
      "confidence": 0.9
    }}
  ]
}}

## RELATIONSHIPS
Only emit a relationship when BOTH endpoints appear in the `terms` array above
(use their exact English `source` strings). If no relationships are evident,
emit an empty array: "relationships": []

## FALLBACK
If no terms found: {{"extraction_meta": {{"schema_version": "3.2.1", "source_language": "English", "total_terms_found": 0}}, "terms": [], "relationships": []}}

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
        config: Optional[Dict[str, Any]] = None,
        auto_approve_threshold: float = 0.0,
    ):
        super().__init__(ollama_client, memory_manager, config)
        # Terms with confidence >= this are saved as 'approved' (immediately
        # injectable by the translator) instead of 'pending'. 0.0 = off (all
        # pending, human must review). Recommended: 0.85 for --from-mm (targets
        # pulled verbatim from existing translation), 0.9+ for monolingual EN.
        self.auto_approve_threshold = auto_approve_threshold

    def _extract_from_window(
        self, text: str, source_lang: str = "Chinese"
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Extract terms AND relationships from one text window.

        Returns (terms, relationships). Both are empty lists on any failure
        (the caller proceeds safely — NO CRASHES rule).
        """
        prompt = GLOSSARY_EXTRACTION_PROMPT.format(
            source_lang=source_lang,
            text=text[:4000],  # Limit to 4000 chars for context window
        )
        try:
            response = self.client.chat(prompt=prompt, format="json")
            data = extract_json_from_response(response)
            terms = data.get("terms", []) or []
            relationships = data.get("relationships", []) or []
            return terms, relationships
        except Exception as e:
            self.log_error(f"Term extraction failed: {e}")
            return [], []

    def extract_terms(self, text: str, source_lang: str = "Chinese") -> List[Dict[str, Any]]:
        """Extract terms from a block of text (v3.2.1 schema).

        Backward-compatible wrapper around _extract_from_window that returns
        only the terms list (relationships are ignored here — use
        _extract_from_file / generate_from_chapter for relationship-aware
        extraction).
        """
        terms, _ = self._extract_from_window(text, source_lang)
        return terms

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
                    terms, _rels = self._extract_from_window(window, source_lang)
                    for term in terms:
                        source = term.get("source") or term.get("source_term")
                        if source and source not in all_terms:
                            all_terms[source] = term

            except Exception as e:
                self.log_error(f"Error reading {path}: {e}")

        return list(all_terms.values())

    def _extract_from_file(
        self, file_path: str, source_lang: str = "Chinese"
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Extract deduplicated terms + relationships from one file.

        Sliding-window scan with per-source dedup on terms and per-(src,dst,
        relation) dedup on relationships. Returns (terms, relationships).
        """
        all_terms: Dict[str, Dict[str, Any]] = {}
        all_rels: Dict[tuple, Dict[str, Any]] = {}
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                content = f.read()
        except Exception as e:
            self.log_error(f"Error reading {file_path}: {e}")
            return [], []

        for window in self._iter_windows(content):
            terms, rels = self._extract_from_window(window, source_lang)
            for term in terms:
                src = term.get("source") or term.get("source_term")
                if src and src not in all_terms:
                    all_terms[src] = term
            for rel in rels:
                src = rel.get("src", "")
                dst = rel.get("dst", "")
                rtype = rel.get("relation_type", "")
                if src and dst and rtype:
                    key = (src.lower(), dst.lower(), rtype)
                    if key not in all_rels:
                        all_rels[key] = rel
        return list(all_terms.values()), list(all_rels.values())

    def save_to_pending(self, terms: List[Dict[str, Any]], chapter_num: int = 0) -> int:
        """Save extracted terms to the database.

        Dedup-on-rerun: a term that already exists in the approved glossary OR
        in pending is SKIPPED (not updated) — only terms that do NOT yet exist
        are saved. This makes ``--generate-glossary`` re-runs idempotent.

        Auto-approve: when self.auto_approve_threshold > 0 and a term's
        confidence >= threshold (and target is valid Myanmar, not a
        placeholder), the term is saved with status='approved' so it is
        immediately injectable by the translator. Lower-confidence terms stay
        'pending' for human review.

        Returns the number of terms actually saved (new only).
        """
        # Load existing pending + approved terms to skip duplicates up-front
        # (fast path — avoids a DB round-trip per term).
        existing_pending = self.memory.get_pending_terms()
        existing_sources = {t.get("source", "").lower() for t in existing_pending if t.get("source")}

        approved_terms = self.memory.get_all_terms()
        approved_sources = {t.get("source", "").lower() for t in approved_terms if t.get("source")}

        saved_count = 0
        skipped_duplicates = 0
        placeholder_count = 0
        auto_approved_count = 0

        for term in terms:
            source = term.get("source") or term.get("source_term", "")
            target = term.get("target") or term.get("target_term", "")
            category = term.get("category", "item")
            subtype = term.get("subtype") or None
            confidence = float(term.get("confidence", 0.0))

            # Skip invalid terms (empty source/target)
            if not source or not target:
                continue
            if "【?term?】" in target:
                placeholder_count += 1
                continue

            source_lower = source.lower()

            # Dedup-on-rerun: skip if already approved OR already pending
            if source_lower in approved_sources:
                skipped_duplicates += 1
                continue
            if source_lower in existing_sources:
                skipped_duplicates += 1
                continue

            # Auto-approve high-confidence terms so they're immediately usable
            # by the translator. Placeholder targets are never auto-approved.
            do_auto_approve = (
                self.auto_approve_threshold > 0.0
                and confidence >= self.auto_approve_threshold
            )

            ok = self.memory.add_pending_term(
                source=source,
                target=target,
                category=category,
                chapter=chapter_num,
                confidence=confidence,
                subtype=subtype,
                approved=do_auto_approve,
            )
            if ok:
                existing_sources.add(source_lower)  # avoid intra-run dups
                saved_count += 1
                if do_auto_approve:
                    auto_approved_count += 1
            # If add_pending_term returned False (e.g. failed Myanmar validation),
            # it was rejected — not a duplicate, just filtered.

        self.log_info(
            f"Saved {saved_count} new terms ({auto_approved_count} auto-approved, "
            f"{saved_count - auto_approved_count} pending), "
            f"skipped {skipped_duplicates} duplicates, {placeholder_count} placeholders."
        )
        return saved_count

    def save_relationships(
        self, relationships: List[Dict[str, Any]], chapter_num: int = 0
    ) -> int:
        """Create term_relationships edges for extracted relationships.

        Routes through MemoryManager.add_relationship (the data-layer gateway)
        so the generator never touches the glossary repo directly — Modular
        Boundaries rule. Edges whose endpoints cannot be resolved (the term
        was filtered as placeholder/duplicate/non-Myanmar) are skipped. Unknown
        relation_types are rejected inside add_relationship.

        Returns the number of edges created.
        """
        if not relationships:
            return 0

        created = 0
        skipped = 0
        for rel in relationships:
            src = rel.get("src", "")
            dst = rel.get("dst", "")
            rtype = rel.get("relation_type", "")
            confidence = float(rel.get("confidence", 1.0))
            if not src or not dst or not rtype:
                skipped += 1
                continue

            ok = self.memory.add_relationship(
                src_source=src,
                dst_source=dst,
                relation_type=rtype,
                confidence=confidence,
                add_inverse=True,
            )
            if ok:
                created += 1
            else:
                skipped += 1  # endpoint missing / invalid relation / duplicate

        self.log_info(
            f"Relationships: created {created} edges, skipped {skipped} "
            f"(endpoint missing / invalid relation / duplicate)."
        )
        return created

    def generate_from_chapter(self, chapter_file: str, chapter_num: int = 0) -> int:
        """Generate glossary terms + relationships from a single chapter file.
        
        Args:
            chapter_file: Path to the chapter file
            chapter_num: Chapter number for logging + chapter_first_seen
            
        Returns:
            Number of NEW terms saved (dedup-skipped terms are not counted)
        """
        try:
            logger.info(f"Reading chapter {chapter_num}: {chapter_file}")

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

            # Relationship-aware extraction (sliding window + dedup)
            terms, relationships = self._extract_from_file(chapter_file, source_lang)

            saved = 0
            if terms:
                saved = self.save_to_pending(terms, chapter_num)
            if relationships:
                self.save_relationships(relationships, chapter_num)

            logger.info(
                f"✅ Chapter {chapter_num}: {saved} new terms saved, "
                f"{len(relationships)} relationships found"
            )
            return saved

        except Exception as e:
            logger.error(f"❌ Failed to process chapter {chapter_num}: {e}")
            return 0

    def generate_from_pair(self, en_file: str, mm_file: str, chapter_num: int = 0) -> int:
        """Generate glossary terms + relationships from an EN↔MM chapter pair.

        Reads both files and asks the model to identify named entities in the
        English text, find their Myanmar equivalents in the translation, and
        extract worldbuilding relationships between them.

        Args:
            en_file: Path to the English source chapter
            mm_file: Path to the Myanmar translation chapter
            chapter_num: Chapter number for logging + chapter_first_seen

        Returns:
            Number of NEW terms saved (dedup-skipped terms are not counted)
        """
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

            terms: List[Dict[str, Any]] = []
            relationships: List[Dict[str, Any]] = []
            try:
                response = self.client.chat(prompt=prompt, format="json")
                data = extract_json_from_response(response)
                terms = data.get("terms", []) or []
                relationships = data.get("relationships", []) or []
            except Exception as e:
                logger.error(f"Term extraction failed for chapter {chapter_num}: {e}")

            saved = 0
            if terms:
                saved = self.save_to_pending(terms, chapter_num)
            if relationships:
                self.save_relationships(relationships, chapter_num)

            logger.info(
                f"✅ Chapter {chapter_num}: {saved} new terms saved, "
                f"{len(relationships)} relationships found (EN↔MM pair)"
            )
            return saved

        except Exception as e:
            logger.error(f"❌ Failed to process chapter {chapter_num}: {e}")
            return 0
