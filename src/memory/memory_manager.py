"""
Memory Manager Module
Handles 3-tier memory system: Glossary and Context Memory.
Supports per-novel glossary (primary) + optional universal reference (read-only).
Supports JSON backend (default) and SQLite backend (optional).

NOTE: Universal blueprint files are READ-ONLY reference templates.
They are NOT written to - only used as optional read-only fallback.
"""

import logging
import os
import re
import json as _json
from typing import Dict, List, Any, Optional
from datetime import datetime
from collections import deque
from src.utils.file_handler import FileHandler

logger = logging.getLogger(__name__)

# Universal blueprint files (READ-ONLY reference templates - NOT written to)
UNIVERSAL_GLOSSARY_REF = "data/universal_glossary_blueprint.json"
UNIVERSAL_PENDING_REF = "data/universal_glossary_pending_blueprint.json"
UNIVERSAL_CONTEXT_REF = "data/universal_context_memory_blueprint.json"


def _resolve_universal_ref_paths() -> tuple[str, str, str]:
    """Resolve universal (shared) reference paths.
    
    These are READ-ONLY reference templates - NOT written to.
    Only used as optional read-only fallback for lookup.
    """
    return (
        UNIVERSAL_GLOSSARY_REF,
        UNIVERSAL_PENDING_REF,
        UNIVERSAL_CONTEXT_REF,
    )


def _resolve_glossary_path(novel_name: Optional[str] = None) -> tuple[str, str, str]:
    """Resolve glossary, context, and pending file paths for a given novel.
    
    Dual-layer system:
    - Universal: data/universal_glossary_blueprint.json (shared across all novels)
    - Per-novel: data/output/{novel_name}/glossary/glossary.json (novel-specific)
    
    Per-novel mode (novel_name provided):
      data/output/{novel_name}/glossary/glossary.json
      data/output/{novel_name}/glossary/context_memory.json
      data/output/{novel_name}/glossary/glossary_pending.json
    
    Shared fallback (novel_name is None):
      data/output/default/glossary/glossary.json
      data/output/default/glossary/context_memory.json
      data/output/default/glossary/glossary_pending.json
    """
    if novel_name:
        safe_name = novel_name.replace('/', '_').replace('\\', '_').replace(' ', '_')
        base_dir = f"data/output/{safe_name}/glossary"
        os.makedirs(base_dir, exist_ok=True)
        return (
            f"{base_dir}/glossary.json",
            f"{base_dir}/context_memory.json",
            f"{base_dir}/glossary_pending.json",
        )
    base_dir = "data/output/default/glossary"
    os.makedirs(base_dir, exist_ok=True)
    return (f"{base_dir}/glossary.json", f"{base_dir}/context_memory.json", f"{base_dir}/glossary_pending.json")


class MemoryManager:
    """
    3-Tier Memory Management System:
    - Tier 1: Per-novel Glossary (novel-specific, PRIMARY - all writes go here)
    - Tier 2: Chapter Context (FIFO sliding window)
    - Tier 3: Session Rules (Dynamic corrections)
    
    OPTIONAL: Universal blueprint files can be used as READ-ONLY reference.
    Set use_universal=True to enable read-only lookup from blueprint files.
    """

    def __init__(
        self,
        glossary_path: str = "data/output/default/glossary/glossary.json",
        context_path: str = "data/output/default/glossary/context_memory.json",
        novel_name: Optional[str] = None,
        use_universal: bool = False,  # Default: disabled (per-novel only)
        use_sql: bool = True,         # Default: SQLite backend (NEW)
        db_path: str = "data/novel_translation.db",
    ):
        self.use_sql = use_sql
        self.novel_name = novel_name

        if use_sql:
            from src.db.connection import DatabaseConnection
            from src.db.schema import SchemaManager
            from src.db.repositories.glossary_repo import GlossaryRepository
            from src.db.repositories.chapter_repo import ChapterRepository
            from src.db.repositories.context_repo import ContextRepository
            from src.db.repositories.novel_repo import NovelRepository

            self.db = DatabaseConnection(db_path)
            self.schema = SchemaManager(self.db)
            self.schema.create_all()
            self.novel_repo = NovelRepository(self.db)
            self.glossary_repo = GlossaryRepository(self.db)
            self.chapter_repo = ChapterRepository(self.db)
            self.context_repo = ContextRepository(self.db)

            from src.db.sync_external import make_novel_id, sync_external_glossary

            self.novel_id = make_novel_id(novel_name) if novel_name else "novel_default"
            if not self.novel_repo.exists(self.novel_id):
                self.novel_repo.create(self.novel_id, novel_name or "default", "chinese")

            # Sync terms from external Glossary System DB on startup
            # force=True ensures local glossary always matches the authoritative external DB
            if novel_name:
                conn = self.db.connect()
                sync_result = sync_external_glossary(conn, novel_name, force=True)
                if sync_result["errors"]:
                    logger.warning(f"External glossary sync errors: {sync_result['errors']}")
                else:
                    total = sync_result["synced"] + sync_result["global_synced"]
                    if total > 0:
                        logger.info(
                            f"Synced {total} terms from external glossary "
                            f"({sync_result['synced']} novel + {sync_result['global_synced']} global)"
                        )

            self.glossary_path = ""
            self.context_path = ""
            self.pending_path = ""
            self.glossary: Dict[str, Any] = {"terms": [], "total_terms": 0}
            self.context_memory: Dict[str, Any] = {
                "current_chapter": 0, "last_translated_chapter": 0,
                "summary": "", "active_characters": {}, "recent_events": [],
                "paragraph_buffer": [],
            }
            self.paragraph_buffer: deque = deque(maxlen=10)
            self.session_rules: Dict[str, str] = {}
            self.universal_glossary: Dict[str, Any] = {}
            self.universal_pending: Dict[str, Any] = {}
            self.universal_context: Dict[str, Any] = {}
            self.use_universal = use_universal

            # Restore context from SQLite snapshots (summary, characters, events, voices)
            self._load_context_from_sql()

            # Bridge: convert glossary context_variants into character voice profiles
            self._populate_context_variants_from_glossary()

            # Load universal glossary if enabled (SQL path fix per report.md §2)
            if self.use_universal:
                self._load_universal_glossary()
            logger.info(f"MemoryManager initialized with SQL backend (novel={novel_name}, use_universal={self.use_universal})")
            return

        # Resolve novel-specific paths when novel_name is provided
        if novel_name:
            glossary_path, context_path, self.pending_path = _resolve_glossary_path(novel_name)
        else:
            self.pending_path = "data/output/default/glossary/glossary_pending.json"

        self.glossary_path = glossary_path
        self.context_path = context_path
        self.use_universal = use_universal

        # Dual-layer glossary support
        self.universal_glossary: Dict[str, Any] = {}
        self.universal_pending: Dict[str, Any] = {}
        self.universal_context: Dict[str, Any] = {}
        
        # Tier 1: Per-novel Glossary
        self.glossary: Dict[str, Any] = {}

        # Tier 2: Context Memory
        self.context_memory: Dict[str, Any] = {}
        self.paragraph_buffer: deque = deque(maxlen=10)

        # Tier 3: Session Rules
        self.session_rules: Dict[str, str] = {}

        # Load all memory (_load_memory handles universal glossary if use_universal=True)
        self._load_memory()

    def _load_universal_glossary(self) -> None:
        """Load universal (shared) glossary reference data for both SQL and JSON paths."""
        self.universal_glossary = FileHandler.read_json(UNIVERSAL_GLOSSARY_REF)
        if not self.universal_glossary:
            self.universal_glossary = {
                "metadata": {"schema_version": "3.2.1"},
                "terms": []
            }
        else:
            raw = self.universal_glossary.get("terms", [])
            self.universal_glossary["terms"] = [
                t for t in raw
                if not (
                    (t.get("source_term") or t.get("source", "")).startswith("<")
                    and (t.get("source_term") or t.get("source", "")).endswith(">")
                )
            ]
            logger.info(f"Loaded universal glossary: {len(self.universal_glossary.get('terms', []))} terms")

        self.universal_pending = FileHandler.read_json(UNIVERSAL_PENDING_REF)
        if not self.universal_pending:
            self.universal_pending = {
                "metadata": {"schema_version": "3.2.1-pending"},
                "pending_terms": []
            }

        self.universal_context = FileHandler.read_json(UNIVERSAL_CONTEXT_REF)
        if not self.universal_context:
            self.universal_context = {
                "metadata": {"schema_version": "3.2.1"},
                "dynamic_character_states": [],
                "translation_flow_buffer": []
            }

    def _load_memory(self) -> None:
        """Load all memory files including universal (shared) glossary."""
        
        # Load Universal (shared) glossary first if enabled
        if self.use_universal:
            self._load_universal_glossary()
        
        # Load per-novel glossary
        self.glossary = FileHandler.read_json(self.glossary_path)
        if not self.glossary:
            self.glossary = {
                "version": "1.0",
                "terms": [],
                "total_terms": 0
            }
        else:
            # Normalize glossary terms to handle both 'source'/'target' and 'source_term'/'target_term' formats
            terms = self.glossary.get("terms", [])
            normalized_count = 0
            for term in terms:
                if "source_term" in term and "source" not in term:
                    term["source"] = term["source_term"]
                    normalized_count += 1
                if "target_term" in term and "target" not in term:
                    term["target"] = term["target_term"]
            self.glossary["terms"] = terms
            if normalized_count > 0:
                logger.debug(f"Normalized {normalized_count} glossary terms from old format")

        # Load context memory
        self.context_memory = FileHandler.read_json(self.context_path)
        if not self.context_memory:
            self.context_memory = {
                "current_chapter": 0,
                "last_translated_chapter": 0,
                "summary": "",
                "active_characters": {},
                "character_voices": {},
                "recent_events": [],
                "paragraph_buffer": []
            }
        else:
            # Restore paragraph buffer
            buffer_data = self.context_memory.get("paragraph_buffer", [])
            self.paragraph_buffer = deque(buffer_data, maxlen=10)

        logger.info(f"Memory loaded: {self.glossary.get('total_terms', 0)} glossary terms")

    @staticmethod
    def _is_valid_myanmar_text(text: str, min_ratio: float = 0.5) -> bool:
        """Check if text contains sufficient Myanmar Unicode characters.
        
        Prevents Bengali, Latin, Chinese, or other non-Myanmar scripts
        from being stored as glossary target values.
        
        Args:
            text: Target translation text
            min_ratio: Minimum ratio of Myanmar chars (0.0-1.0)
            
        Returns:
            True if text passes Myanmar character ratio threshold
        """
        if not text or not text.strip():
            return False
        
        # Forcin placeholders — these are legitimate temp values
        if text.startswith("【?") and text.endswith("?】"):
            return True
        
        MYANMAR_RANGES = [(0x1000, 0x109F), (0xAA60, 0xAA7F), (0xA9E0, 0xA9FF)]
        
        mm_count = 0
        total = 0
        for ch in text:
            code = ord(ch)
            if ch.isspace() or ch in '။၊()[]':
                continue
            total += 1
            if any(lo <= code <= hi for lo, hi in MYANMAR_RANGES):
                mm_count += 1
        
        if total == 0:
            return False
        
        return (mm_count / total) >= min_ratio

    @staticmethod
    def _edit_distance(s1: str, s2: str) -> int:
        """Levenshtein distance between two strings."""
        if len(s1) < len(s2):
            return MemoryManager._edit_distance(s2, s1)
        if len(s2) == 0:
            return len(s1)
        prev = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            curr = [i + 1]
            for j, c2 in enumerate(s2):
                curr.append(min(
                    prev[j + 1] + 1,      # insertion
                    curr[j] + 1,           # deletion
                    prev[j] + (0 if c1 == c2 else 1)  # substitution
                ))
            prev = curr
        return prev[-1]

    def _check_target_similarity(self, new_source: str, new_target: str,
                                  max_distance: int = 3) -> Optional[str]:
        """Check if new_target is too similar to any existing approved target.

        Returns the source of the conflicting term, or None.
        """
        terms = self.glossary.get("terms", [])
        for term in terms:
            existing_target = term.get("target") or term.get("target_term", "")
            existing_source = term.get("source") or term.get("source_term", "")
            if not existing_target or existing_source == new_source:
                continue
            if abs(len(new_target) - len(existing_target)) > max_distance:
                continue
            dist = self._edit_distance(new_target, existing_target)
            if dist < max_distance:
                return existing_source
        return None

    # -------------------------------------------------------------------------
    # Tier 1: Glossary Operations
    # -------------------------------------------------------------------------

    def update_term(self, source: str, new_target: str, chapter: int = 0) -> bool:
        """Update an existing term with Myanmar validation."""
        if not self._is_valid_myanmar_text(new_target):
            logger.warning(f"Rejected non-Myanmar update for '{source}': '{new_target}'")
            return False

        # Check semantic deduplication
        similar_source = self._check_target_similarity(source, new_target)
        if similar_source:
            logger.warning(
                f"Near-duplicate target update for '{source}': '{new_target}' "
                f"is too similar to existing term '{similar_source}'"
            )

        terms = self.glossary.get("terms", [])

        for term in terms:
            term_source = term.get("source") or term.get("source_term", "")
            if term_source == source:
                # Always update both keys to ensure consistency
                term["target"] = new_target
                term["target_term"] = new_target
                term["chapter_last_seen"] = chapter
                term["updated_at"] = datetime.now().isoformat()

                self.save_memory()
                logger.info(f"Updated term: {source} -> {new_target}")
                return True

        return False

    def _sanitize_for_prompt(self, text: str) -> str:
        """Sanitize text for safe use in LLM prompts."""
        if not isinstance(text, str):
            text = str(text)
        # Remove newlines to prevent prompt structure breaking
        text = text.replace('\n', ' ').replace('\r', '')
        # Remove potentially dangerous sequences
        text = text.replace('```', '').replace('"""', '').replace("'''", '')
        # Limit length
        return text[:100]

    # -------------------------------------------------------------------------
    # Tier 2: Context Memory Operations
    # -------------------------------------------------------------------------

    def _generate_summary_from_text(self, text: str, max_length: int = 500) -> str:
        """Generate a brief summary from translated text."""
        sentences = text.replace('\n', ' ').split('။')
        if sentences:
            summary = '။'.join(sentences[:3])
            if len(summary) > max_length:
                summary = summary[:max_length] + "..."
            return summary
        return text[:max_length] if len(text) > max_length else text

    def _update_active_characters(self, text: str):
        """Extract and update active characters from translated text."""
        glossary_terms = self.get_all_terms()
        characters = {}
        
        for term in glossary_terms:
            if term.get('category') == 'character':
                target = term.get('target', '')
                if target and target in text:
                    source = term.get('source', '')
                    if source not in characters:
                        characters[source] = {
                            'target': target,
                            'chapters_active': []
                        }
                    if self.context_memory.get('current_chapter'):
                        characters[source]['chapters_active'].append(
                            self.context_memory['current_chapter']
                        )
        
        self.context_memory["active_characters"] = characters

    def _update_recent_events(self, text: str, chapter_num: int):
        """Extract recent events from translated text.
        
        Events are key plot points, dialogue highlights, or important actions.
        """
        events = self.context_memory.get("recent_events", [])
        
        event_indicators = ['သည်', 'ဖြစ်သည်', 'ဖြစ်ပွား', 'ဖြစ်ခဲ့', 'သွားသည်', 'လာသည်', 'ပြောလိုက်', 'ပါတယ်']
        
        sentences = text.replace('\n', ' ').split('။')
        key_events = []
        
        for sent in sentences[-5:]:
            sent = sent.strip()
            if len(sent) > 30 and any(indicator in sent for indicator in event_indicators):
                key_events.append(sent[:100])
        
        new_event = {
            'chapter': chapter_num,
            'description': '; '.join(key_events[:2]) if key_events else f"Chapter {chapter_num} translated"
        }
        
        events.append(new_event)
        events = events[-10:]
        
        self.context_memory["recent_events"] = events

    def push_to_buffer(self, translated_text: str):
        """Add translated paragraph to FIFO buffer."""
        self.paragraph_buffer.append(translated_text)

    def get_context_buffer(self, count: int = 3) -> str:
        """Get recent translations for context."""
        if not self.paragraph_buffer:
            summary = self.context_memory.get("summary", "")
            if summary:
                return "PREVIOUS CONTEXT (from summary):\n" + self._sanitize_for_prompt(summary)
            return "No previous context."

        recent = [self._sanitize_for_prompt(text) for text in list(self.paragraph_buffer)[-count:]]
        return "PREVIOUS CONTEXT:\n" + "\n".join(recent)

    def clear_buffer(self):
        """Clear paragraph buffer (e.g., at chapter end)."""
        self.paragraph_buffer.clear()
        logger.debug("Context buffer cleared")

    def get_summary(self) -> str:
        """Get summary of previous chapters."""
        summary = self.context_memory.get("summary", "")
        return self._sanitize_for_prompt(summary)

    # -------------------------------------------------------------------------
    # Character Voice Registry
    # -------------------------------------------------------------------------

    def set_character_voice(
        self,
        name: str,
        target: str,
        pronoun_self: str = "",
        pronoun_other: str = "",
        register: str = "neutral",
        speech_style: str = "",
        chapter: int = 0,
        scene_variants: Optional[Dict[str, Dict[str, str]]] = None,
    ) -> None:
        """Register or update a character's voice profile.

        Supports scene-tone-aware pronoun variants from the universal glossary
        blueprint (context_variants). When scene_variants is provided, the
        character voice includes all 5 scene tones (formal/casual/hostile/
        pleading/intimate) for dynamic selection during translation.

        Args:
            name: Source name (e.g., "Fang Yuan")
            target: Myanmar translation (e.g., "ဖန်ယွမ်")
            pronoun_self: Self-reference pronoun (e.g., "ငါ", "ကျွန်တော်")
            pronoun_other: Other-reference pronoun (e.g., "နင်", "မင်း")
            register: Speech register ("formal", "casual", "blunt_casual", "respectful", "neutral")
            speech_style: Description of speech patterns (e.g., "cold and direct")
            chapter: Current chapter number
            scene_variants: Dict mapping scene_tone keys to pronoun dicts:
                {"formal": {"self": "ကျွန်တော်", "other": "ခင်ဗျား", "honorific": "ဆရာ"},
                 "casual": {"self": "ငါ", "other": "မင်း"},
                 "hostile": {"self": "ငါ", "other": "နင်", "honorific": "မိစ္ဆာကောင်"},
                 ...}
        """
        voices = self.context_memory.setdefault("character_voices", {})
        if name in voices:
            existing = voices[name]
            existing["pronoun_self"] = pronoun_self or existing.get("pronoun_self", "")
            existing["pronoun_other"] = pronoun_other or existing.get("pronoun_other", "")
            existing["register"] = register or existing.get("register", "neutral")
            existing["speech_style"] = speech_style or existing.get("speech_style", "")
            if chapter and chapter not in existing.get("chapters_active", []):
                existing.setdefault("chapters_active", []).append(chapter)
            if scene_variants:
                existing.setdefault("scene_variants", {}).update(scene_variants)
        else:
            profile = {
                "target": target,
                "pronoun_self": pronoun_self,
                "pronoun_other": pronoun_other,
                "register": register,
                "speech_style": speech_style,
                "chapters_active": [chapter] if chapter else [],
            }
            if scene_variants:
                profile["scene_variants"] = scene_variants
            voices[name] = profile
        logger.debug(f"Character voice registered: {name} ({register})")

    def _populate_context_variants_from_glossary(self) -> None:
        """Bridge: convert glossary terms' context_variants into character voice profiles.

        Reads all glossary terms with category='character' that have
        non-empty context_variants (scene-tone pronoun sets). For each,
        calls set_character_voice() with all 5 variants so the translator
        can inject scene-appropriate pronouns.

        Called after glossary sync at MemoryManager startup.
        """
        try:
            terms = self.get_all_terms()
            populated = 0
            default_variants = {
                "formal": {"self": "ကျွန်တော်", "other": "ခင်ဗျား", "honorific": ""},
                "casual": {"self": "ငါ", "other": "မင်း", "honorific": ""},
                "hostile": {"self": "ငါ", "other": "နင်", "honorific": ""},
                "pleading": {"self": "ကျွန်တော်", "other": "အရှင်", "honorific": "ကျေးဇူးပြု၍"},
                "intimate": {"self": "ငါ", "other": "မင်း", "honorific": ""},
            }

            for term in terms:
                source = term.get("source") or term.get("source_term", "")
                target = term.get("target") or term.get("target_term", "")
                category = term.get("category", "")
                if category != "character" or not source or not target:
                    continue

                # Try to get context_variants from the term's data
                raw_variants = term.get("context_variants")
                if raw_variants and isinstance(raw_variants, dict):
                    # Rich variants from glossary blueprint — use as-is
                    self.set_character_voice(
                        name=source,
                        target=target,
                        register="neutral",
                        scene_variants=raw_variants,
                        chapter=term.get("chapter_first_seen", 1),
                    )
                    populated += 1
                    continue

                # If term has separate pronoun_self/pronoun_other but no variants,
                # create a basic variant set from them
                pronoun_self = term.get("pronoun_self", "")
                pronoun_other = term.get("pronoun_other", "")
                register = term.get("register", "neutral")
                speech_style = term.get("speech_style", "")

                if pronoun_self or pronoun_other:
                    self.set_character_voice(
                        name=source,
                        target=target,
                        pronoun_self=pronoun_self,
                        pronoun_other=pronoun_other,
                        register=register,
                        speech_style=speech_style,
                        chapter=term.get("chapter_first_seen", 1),
                        scene_variants=default_variants,
                    )
                    populated += 1

            if populated > 0:
                logger.info(f"Populated {populated} character voice profiles from glossary context_variants")
            else:
                logger.debug("No glossary context_variants found for any character terms")
        except Exception as e:
            logger.warning(f"Failed to populate context_variants: {e}")

    def _load_context_from_sql(self) -> None:
        """Load context memory from SQLite snapshots on startup (SQL path).

        Restores summary, current_chapter, active_characters, recent_events,
        and character_voices from the most recent context_snapshots stored in
        the database. Called during __init__ when use_sql=True.

        The paragraph_buffer cannot be restored from SQL (individual paragraph
        text is not stored in snapshots) — it starts empty per-session.
        """
        if not self.use_sql or not hasattr(self, 'context_repo') or not hasattr(self, 'chapter_repo'):
            return
        try:
            chapters = self.chapter_repo.get_chapters_by_novel(self.novel_id)
            chapter_ids = [c["id"] for c in chapters if c.get("id")]
            if not chapter_ids:
                return

            snapshots = self.context_repo.get_rolling_context(chapter_ids, limit=5)
            if not snapshots:
                return

            # Parse the latest snapshot for current context state
            latest = snapshots[0]
            raw = latest.get("summary_json", "{}")
            try:
                data = _json.loads(raw) if isinstance(raw, str) else raw
            except (ValueError, TypeError):
                logger.warning("Failed to parse latest context snapshot JSON")
                return

            if not isinstance(data, dict):
                return

            # Restore summary
            self.context_memory["summary"] = data.get("summary", "")

            # Restore current_chapter from the latest snapshot's chapter record
            latest_chapter_id = latest.get("chapter_id", "")
            for c in chapters:
                if c["id"] == latest_chapter_id and "chapter_num" in c:
                    self.context_memory["current_chapter"] = c["chapter_num"]
                    self.context_memory["last_translated_chapter"] = c["chapter_num"]
                    break

            # Restore active characters (stored as list of names → convert to dict)
            active_chars = data.get("active_chars", [])
            if isinstance(active_chars, list):
                self.context_memory["active_characters"] = {
                    name: {"target": "", "chapters_active": []}
                    for name in active_chars
                }

            # Restore recent events
            events = data.get("events", [])
            if isinstance(events, list):
                self.context_memory["recent_events"] = events

            # Merge character voices from ALL snapshots
            merged_voices: Dict[str, Any] = {}
            for snap in snapshots:
                snap_raw = snap.get("summary_json", "{}")
                try:
                    snap_data = _json.loads(snap_raw) if isinstance(snap_raw, str) else snap_raw
                except (ValueError, TypeError):
                    continue
                snap_voices = snap_data.get("character_voices", {}) if isinstance(snap_data, dict) else {}
                for name, profile in snap_voices.items():
                    if name not in merged_voices:
                        merged_voices[name] = profile
                    else:
                        existing_active = merged_voices[name].get("chapters_active", [])
                        new_active = profile.get("chapters_active", [])
                        merged_voices[name]["chapters_active"] = list(set(existing_active + new_active))

            if merged_voices:
                self.context_memory["character_voices"] = merged_voices

            logger.info(
                f"Restored context from {len(snapshots)} snapshot(s): "
                f"chapter={self.context_memory.get('current_chapter')}, "
                f"summary_len={len(self.context_memory.get('summary', ''))}, "
                f"active_chars={len(self.context_memory.get('active_characters', {}))}, "
                f"voices={len(merged_voices)}"
            )
        except Exception as e:
            logger.debug(f"Could not load context from SQL: {e}")

    def _load_voices_from_sql(self) -> Dict[str, Any]:
        """Load character voices from the latest context snapshot (SQL path)."""
        if not self.use_sql or not hasattr(self, 'context_repo') or not hasattr(self, 'chapter_repo'):
            return {}
        try:
            chapters = self.chapter_repo.get_chapters_by_novel(self.novel_id)
            chapter_ids = [c["id"] for c in chapters if c.get("id")]
            if not chapter_ids:
                return {}
            snapshots = self.context_repo.get_rolling_context(chapter_ids, limit=5)
            merged: Dict[str, Any] = {}
            for snap in snapshots:
                raw = snap.get("summary_json", "{}")
                try:
                    data = _json.loads(raw) if isinstance(raw, str) else raw
                except (ValueError, TypeError):
                    continue
                snap_voices = data.get("character_voices", {}) if isinstance(data, dict) else {}
                for name, profile in snap_voices.items():
                    if name not in merged:
                        merged[name] = profile
                    else:
                        # Merge chapters_active
                        existing_active = merged[name].get("chapters_active", [])
                        new_active = profile.get("chapters_active", [])
                        merged[name]["chapters_active"] = list(set(existing_active + new_active))
            return merged
        except Exception as e:
            logger.debug(f"Could not load voices from SQL: {e}")
            return {}

    def get_character_voices(self, active_only: bool = True, current_chapter: int = 0) -> str:
        """Get formatted character voice profiles for prompt injection.

        If the character has scene_variants (context_variants from the universal
        glossary blueprint), ALL variants are emitted with their scene-tone labels.
        The Translator's scene-tone classifier selects the right variant at runtime.

        Args:
            active_only: If True, only include characters active in current chapter.
            current_chapter: Current chapter number for active filtering.

        Returns:
            Formatted string for prompt injection, or empty string if no voices.
        """
        # SQL path: load voices from context snapshots
        if self.use_sql:
            voices = self._load_voices_from_sql()
        else:
            voices = self.context_memory.get("character_voices", {})

        if not voices:
            return ""

        lines = ["CHARACTER VOICE PROFILES:"]
        for name, profile in voices.items():
            if active_only and current_chapter > 0:
                if current_chapter not in profile.get("chapters_active", []):
                    continue
            target = profile.get("target", "")
            speech_style = profile.get("speech_style", "")

            scene_variants = profile.get("scene_variants")
            if scene_variants and isinstance(scene_variants, dict):
                # Rich mode: emit all 5 scene-tone variants
                parts = [f"  {name} ({target})"]
                if speech_style:
                    parts.append(f"style={speech_style}")
                for tone_key, variant in scene_variants.items():
                    v_parts = []
                    self_p = variant.get("self", "")
                    other_p = variant.get("other", variant.get("target", ""))
                    honorific = variant.get("honorific", "")
                    if self_p:
                        v_parts.append(f"self={self_p}")
                    if other_p:
                        v_parts.append(f"other={other_p}")
                    if honorific:
                        v_parts.append(f"honor={honorific}")
                    parts.append(f"  [{tone_key}] {' '.join(v_parts)}")
                lines.append("\n".join(parts))
            else:
                # Simple mode: single register
                parts = [f"  {name} ({target})"]
                if profile.get("pronoun_self"):
                    parts.append(f"self={profile['pronoun_self']}")
                if profile.get("pronoun_other"):
                    parts.append(f"other={profile['pronoun_other']}")
                if profile.get("register"):
                    parts.append(f"register={profile['register']}")
                if speech_style:
                    parts.append(f"style={speech_style}")
                lines.append(" | ".join(parts))

        return "\n".join(lines) if len(lines) > 1 else ""

    def get_character_voices_for_scene(self, scene_tone: str = "casual",
                                        active_only: bool = True,
                                        current_chapter: int = 0) -> str:
        """Get character voice profiles filtered to a specific scene tone.

        Instead of emitting all 5 variants, selects the matching variant
        for each character based on the detected scene tone. Saves token
        budget by injecting only the relevant variant.

        Args:
            scene_tone: One of "formal", "casual", "hostile", "pleading", "intimate"
            active_only: If True, only include characters active in current chapter.
            current_chapter: Current chapter number for active filtering.

        Returns:
            Formatted string with scene-specific voices, or empty string.
        """
        if self.use_sql:
            voices = self._load_voices_from_sql()
        else:
            voices = self.context_memory.get("character_voices", {})

        if not voices:
            return ""

        lines = ["CHARACTER VOICE PROFILES:"]
        for name, profile in voices.items():
            if active_only and current_chapter > 0:
                if current_chapter not in profile.get("chapters_active", []):
                    continue
            target = profile.get("target", "")
            scene_variants = profile.get("scene_variants", {})

            if scene_variants and isinstance(scene_variants, dict):
                variant = scene_variants.get(scene_tone, scene_variants.get("casual", {}))
                self_p = variant.get("self", profile.get("pronoun_self", ""))
                other_p = variant.get("other", variant.get("target", profile.get("pronoun_other", "")))
                honorific = variant.get("honorific", "")
                parts = [f"  {name} ({target})"]
                parts.append(f"[{scene_tone}] self={self_p} other={other_p}")
                if honorific:
                    parts[-1] += f" honor={honorific}"
                if profile.get("speech_style"):
                    parts.append(f"style={profile['speech_style']}")
                lines.append("\n".join(parts))
            else:
                parts = [f"  {name} ({target})"]
                if profile.get("pronoun_self"):
                    parts.append(f"self={profile['pronoun_self']}")
                if profile.get("pronoun_other"):
                    parts.append(f"other={profile['pronoun_other']}")
                lines.append(" | ".join(parts))

        return "\n".join(lines) if len(lines) > 1 else ""

    def extract_character_voices_from_text(
        self,
        source_text: str,
        translated_text: str,
        chapter: int = 0,
    ) -> None:
        """Extract character voice profiles from translated dialogue.

        Scans translated text for dialogue patterns and infers
        character voice attributes (pronouns, register) from how
        characters speak.

        Args:
            source_text: Original chapter text (for character name lookup)
            translated_text: Translated Myanmar text
            chapter: Current chapter number
        """
        voices = self.context_memory.setdefault("character_voices", {})
        active_chars = self.context_memory.get("active_characters", {})
        if not active_chars:
            return

        # For each active character, scan translated text for their dialogue
        for src_name, info in active_chars.items():
            target_name = info.get("target", "")
            if not target_name or target_name not in translated_text:
                continue

            if src_name not in voices:
                register = "neutral"
                pronoun_self = ""
                pronoun_other = ""

                # Infer register from how the character speaks in translation
                # Look for patterns near the character's name
                lines = translated_text.split("\n")
                for line in lines:
                    if target_name not in line:
                        continue
                    # Check for casual markers
                    if re.search(r'(?<!\S)(တယ်|ဘူး|ပါ့|လား|နော်)(?!\S)', line):
                        register = "casual"
                        pronoun_self = "ငါ"
                        pronoun_other = "နင်"
                    # Check for respectful markers
                    elif re.search(r'(?<!\S)(ပါသည်|ပါတယ်|ရှင်)(?!\S)', line):
                        if register == "neutral":
                            register = "respectful"
                            pronoun_self = "ကျွန်တော်"
                            pronoun_other = "ရှင်"
                    # Check for formal narration markers
                    elif re.search(r'(?<!\S)သည်(?!\S)', line) and "တယ်" not in line:
                        if register == "neutral":
                            register = "formal"
                            pronoun_self = "ငါ"
                            pronoun_other = "မင်း"

                self.set_character_voice(
                    name=src_name,
                    target=target_name,
                    pronoun_self=pronoun_self,
                    pronoun_other=pronoun_other,
                    register=register,
                    chapter=chapter,
                )

    # -------------------------------------------------------------------------
    # Tier 3: Session Rules
    # -------------------------------------------------------------------------

    def add_session_rule(self, incorrect: str, correct: str):
        """Add a temporary correction rule."""
        self.session_rules[incorrect] = correct
        logger.info(f"Session rule added: {incorrect} -> {correct}")

    def get_session_rules(self) -> str:
        """Get formatted session rules."""
        if not self.session_rules:
            return "No session rules."

        lines = ["CORRECTION RULES:"]
        for incorrect, correct in self.session_rules.items():
            lines.append(f"  {self._sanitize_for_prompt(incorrect)} -> {self._sanitize_for_prompt(correct)}")

        return "\n".join(lines)

    def clear_session_rules(self) -> None:
        """Clear all session rules (called at chapter start)."""
        self.session_rules.clear()
        logger.debug("Session rules cleared for new chapter")

    def promote_rule_to_glossary(self, incorrect: str, correct: str, chapter: int = 0):
        """Promote a session rule to permanent glossary entry."""
        # Add to glossary
        self.add_term(incorrect, correct, "user_correction", chapter)

        # Remove from session rules
        if incorrect in self.session_rules:
            del self.session_rules[incorrect]

        logger.info(f"Promoted to glossary: {incorrect} -> {correct}")

    def add_pending_term(
        self,
        source: str,
        target: str,
        category: str = "general",
        chapter: int = 0
    ) -> bool:
        """Add a term to the novel-specific pending glossary for review.

        If the term already exists in pending, increments its chapter
        appearance count and updates the last-seen chapter.
        
        Validates that the target contains Myanmar text before accepting
        (skips validation for placeholder targets like 【?term?】).
        """
        # SQL backend: use database directly
        if self.use_sql:
            # Check for duplicates in approved glossary
            if self.get_term(source):
                return False
            
            # Check if already in pending
            existing = self.glossary_repo.get_term_by_source(self.novel_id, source)
            if existing:
                # Update chapter tracking
                usage_count = existing.get('usage_count', 0) + 1
                self.glossary_repo.update_term(
                    existing['id'],
                    usage_count=usage_count,
                    updated_at=datetime.now().isoformat()
                )
                logger.debug(f"Updated pending term chapter count: {source} (usage_count={usage_count})")
                return True
            
            # Validate target: reject pure non-Myanmar unless it's a placeholder
            if target and not target.startswith("【?") and not target.startswith("["):
                if not self._is_valid_myanmar_text(target):
                    logger.warning(f"Rejected non-Myanmar pending target for '{source}': '{target}'")
                    return False
            
            # Add new pending term (usage_count defaults to 0 in INSERT)
            self.glossary_repo.add_term(
                novel_id=self.novel_id,
                source_term=source,
                target_term=target,
                category=category,
                status='pending',
                enforcement_level='soft',
            )
            logger.info(f"Added pending glossary term (SQL): {source} -> {target}")
            return True
        
        # JSON backend: use file-based storage
        # Load existing pending terms
        pending_data = FileHandler.read_json(self.pending_path)
        if not pending_data:
            pending_data = {"pending_terms": []}

        pending_terms = pending_data.get("pending_terms", [])

        # Check for duplicates in approved glossary
        if self.get_term(source):
            return False

        # Validate target: reject pure non-Myanmar unless it's a placeholder
        if target and not target.startswith("【?") and not target.startswith("["):
            if not self._is_valid_myanmar_text(target):
                logger.warning(f"Rejected non-Myanmar pending target for '{source}': '{target}'")
                return False

        # Check for duplicate in pending list — update chapter count
        for t in pending_terms:
            if t.get("source") == source:
                # Update chapter tracking
                chapters_seen = t.get("chapters_seen", [])
                if chapter not in chapters_seen and chapter > 0:
                    chapters_seen.append(chapter)
                t["chapters_seen"] = chapters_seen
                t["extracted_from_chapter"] = chapter  # last seen
                t["chapter_count"] = len(chapters_seen)
                t["updated_at"] = datetime.now().isoformat()
                # Update target if the new one is more specific (non-placeholder)
                if target and not target.startswith("【?") and not target.startswith("["):
                    if self._is_valid_myanmar_text(target):
                        t["target"] = target
                FileHandler.write_json(self.pending_path, pending_data)
                logger.debug(f"Updated pending term chapter count: {source} (seen in {len(chapters_seen)} chapters)")
                return True

        new_pending = {
            "source": source,
            "target": target,
            "category": category,
            "extracted_from_chapter": chapter,
            "chapters_seen": [chapter] if chapter > 0 else [],
            "chapter_count": 1 if chapter > 0 else 0,
            "status": "pending",
            "added_at": datetime.now().isoformat()
        }

        pending_terms.append(new_pending)
        pending_data["pending_terms"] = pending_terms

        FileHandler.write_json(self.pending_path, pending_data)
        logger.info(f"Added pending glossary term: {source} -> {target}")
        return True

    def get_pending_terms(self) -> List[Dict[str, Any]]:
        """Get all pending terms for review."""
        if self.use_sql:
            # SQL backend: query from database
            terms = self.glossary_repo.get_terms_by_novel(self.novel_id, status='pending')
            # Convert to legacy format for compatibility
            return [
                {
                    "source": t['source_term'],
                    "target": t['target_term'],
                    "category": t['category'],
                    "chapter_first_seen": 0,
                    "status": "pending",
                    "confidence": t.get('confidence', 0.7)
                }
                for t in terms
            ]
        # JSON backend: read from file
        pending_data = FileHandler.read_json(self.pending_path)
        if not pending_data:
            return []
        return pending_data.get("pending_terms", [])

    def promote_pending_to_glossary(
        self,
        source: str,
        chapter: int = 0,
        verified: bool = True
    ) -> bool:
        """Promote a pending term to the approved glossary.

        Args:
            source: The source term to promote
            chapter: Current chapter number
            verified: Mark term as verified

        Returns:
            True if promoted successfully, False if not found
        """
        if self.use_sql:
            # SQL backend
            term = self.glossary_repo.get_term_by_source(self.novel_id, source)
            if not term or term.get('status') != 'pending':
                return False
            
            target = term.get('target_term', '')
            
            # Update status to approved
            self.glossary_repo.update_term(
                term['id'],
                status='approved',
                reviewed_at=datetime.now().isoformat()
            )
            
            logger.info(f"Promoted pending term to glossary: {source} -> {target}")
            return True
        
        # JSON backend
        pending_data = FileHandler.read_json(self.pending_path)
        if not pending_data:
            return False

        pending_terms = pending_data.get("pending_terms", [])
        target = None
        category = "general"

        # Find the term
        for t in pending_terms:
            if t.get("source") == source:
                target = t.get("target", "")
                category = t.get("category", "general")
                break

        if not target:
            return False

        # Add to approved glossary
        terms = self.glossary.get("terms", [])
        existing = {t.get("source") or t.get("source_term", "") for t in terms}
        if source in existing:
            # Already exists — update it (keep in pending if update fails validation)
            self.update_term(source, target, chapter)
        else:
            if not self.add_term(source, target, category, chapter):
                logger.warning(f"Failed to add term '{source}' — target '{target}' rejected by validation. Keeping in pending.")
                return False

        # Remove from pending
        pending_data["pending_terms"] = [t for t in pending_terms if t.get("source") != source]
        FileHandler.write_json(self.pending_path, pending_data)

        # Mark as verified in glossary
        for t in self.glossary.get("terms", []):
            if (t.get("source") or t.get("source_term", "")) == source:
                t["verified"] = verified
                break

        self.save_memory()
        logger.info(f"Promoted pending term to glossary: {source} -> {target}")
        return True

    def reject_pending_term(self, source: str) -> bool:
        """Remove a pending term without promoting to glossary.

        Args:
            source: The source term to reject

        Returns:
            True if rejected successfully, False if not found
        """
        if self.use_sql:
            # SQL backend: delete from database
            term = self.glossary_repo.get_term_by_source(self.novel_id, source)
            if not term or term.get('status') != 'pending':
                return False
            
            self.glossary_repo.delete_term(term['id'])
            logger.info(f"Rejected pending term (SQL): {source}")
            return True
        
        # JSON backend
        pending_data = FileHandler.read_json(self.pending_path)
        if not pending_data:
            return False

        pending_terms = pending_data.get("pending_terms", [])
        before = len(pending_terms)
        pending_data["pending_terms"] = [t for t in pending_terms if t.get("source") != source]

        if len(pending_data["pending_terms"]) == before:
            return False

        FileHandler.write_json(self.pending_path, pending_data)
        logger.info(f"Rejected pending term: {source}")
        return True

    def bulk_approve_all_pending(self) -> int:
        """Bulk approve ALL pending terms regardless of confidence.

        This is the --approve-glossary workflow:
        1. Read all pending terms
        2. Change status from "pending" to "approved"
        3. Add each to glossary.json
        4. Remove from pending list

        Returns:
            Number of terms promoted to glossary
        """
        if self.use_sql:
            # SQL backend: bulk approve all pending terms
            pending = self.glossary_repo.get_terms_by_novel(self.novel_id, status='pending')
            if not pending:
                logger.info("No pending terms to approve")
                return 0

            approved_count = 0
            for term in pending:
                try:
                    result = self.glossary_repo.update_term(
                        term['id'],
                        status='approved',
                        reviewed_at=datetime.now().isoformat()
                    )
                    if result:
                        approved_count += 1
                        logger.info(f"Approved: {term['source_term']} → {term['target_term']}")
                    else:
                        logger.warning(f"Failed to approve: {term['source_term']}")
                except Exception as e:
                    logger.warning(f"Failed to approve term '{term['source_term']}': {e}")

            logger.info(f"Bulk approval complete: {approved_count}/{len(pending)} terms approved")
            return approved_count

        # JSON backend
        pending_data = FileHandler.read_json(self.pending_path)
        if not pending_data:
            logger.info("No pending glossary file found")
            return 0

        pending_terms = pending_data.get("pending_terms", [])
        if not pending_terms:
            logger.info("No pending terms to approve")
            return 0

        approved_count = 0
        remaining = []

        for term in pending_terms:
            source = term.get("source", "")
            target = term.get("target", "")
            category = term.get("category", "general")

            if not source or not target:
                remaining.append(term)
                continue

            # Add to approved glossary
            if self.add_term(source, target, category, term.get("extracted_from_chapter", 0)):
                approved_count += 1
                logger.info(f"Approved: {source} → {target}")
            else:
                logger.warning(f"Failed to approve (validation failed): {source}")
                remaining.append(term)

        # Update pending file with remaining terms
        pending_data["pending_terms"] = remaining
        FileHandler.write_json(self.pending_path, pending_data)

        # Save glossary
        self.save_memory()

        logger.info(f"Bulk approval complete: {approved_count} terms added to glossary")
        return approved_count

    def auto_approve_pending_terms(self) -> int:
        """Automatically promote pending terms with status 'approved'.

        User writes 'approved' in the status field of glossary_pending.json,
        then on next pipeline run, these terms are auto-promoted to the
        main glossary and removed from the pending list.

        Returns:
            Number of terms promoted
        """
        if self.use_sql:
            # SQL backend: promote terms already marked as 'approved' in the database
            pending = self.glossary_repo.get_terms_by_novel(self.novel_id, status='pending')
            approved = [t for t in pending if t.get('user_marked_approved')]
            
            if not approved:
                return 0
            
            promoted_count = 0
            for term in approved:
                result = self.glossary_repo.update_term(
                    term['id'],
                    status='approved',
                    reviewed_at=datetime.now().isoformat()
                )
                if result:
                    promoted_count += 1
            
            logger.info(f"Auto-approved {promoted_count}/{len(approved)} pending glossary terms")
            return promoted_count
        
        # JSON backend
        pending_data = FileHandler.read_json(self.pending_path)
        if not pending_data:
            return 0

        pending_terms = pending_data.get("pending_terms", [])
        approved = [t for t in pending_terms if t.get("status") == "approved"]

        if not approved:
            return 0

        promoted_count = 0
        not_promoted = []
        for term in approved:
            source = term.get("source", "")
            target = term.get("target", "")
            category = term.get("category", "term")
            chapter = term.get("extracted_from_chapter", 0)
            if source and target:
                if self.add_term(source, target, category, chapter):
                    promoted_count += 1
                else:
                    not_promoted.append(term)

        # Remove promoted terms from pending (keep those that failed validation)
        failed_sources = {n.get("source") for n in not_promoted}
        pending_data["pending_terms"] = [
            t for t in pending_terms
            if t.get("status") != "approved" or t.get("source") in failed_sources
        ]
        FileHandler.write_json(self.pending_path, pending_data)
        logger.info(f"Auto-approved {promoted_count}/{len(approved)} pending glossary terms")
        return promoted_count

    def auto_approve_by_confidence(self, confidence_threshold: float = 0.75) -> int:
        """Auto-approve pending terms based on confidence heuristics.

        Confidence rules (each adds to the confidence score):
          1. Seen in ≥3 different chapters            → +0.40
          2. Seen in ≥2 different chapters            → +0.25
          3. Category is "character" or "place"        → +0.20
          4. Target is not a placeholder (not 【?..?】) → +0.15
          5. Target is proper Myanmar (no Latin chars) → +0.10
          6. Source matches known name pattern         → +0.10
             (2-3 Chinese chars = likely person name)

        Terms with confidence >= threshold are auto-promoted to
        the approved glossary. This removes the bottleneck of
        manually editing JSON to set status='approved'.

        Args:
            confidence_threshold: Minimum confidence to auto-approve (0.0-1.0)

        Returns:
            Number of terms auto-approved
        """
        if self.use_sql:
            # SQL backend: get pending terms from database
            pending = self.glossary_repo.get_terms_by_novel(self.novel_id, status='pending')
            if not pending:
                return 0
            
            to_approve = []
            for term in pending:
                confidence = 0.0
                source = term.get('source_term', '')
                target = term.get('target_term', '')
                category = term.get('category', 'general')
                # Use confidence field from database or calculate
                chapter_count = term.get('usage_count', 0)
                
                # Rule 1: Multi-chapter appearance
                if chapter_count >= 3:
                    confidence += 0.40
                elif chapter_count >= 2:
                    confidence += 0.25
                
                # Rule 2: Known category types
                if category in ("character", "place"):
                    confidence += 0.20
                
                # Rule 3: Not a placeholder
                if target and not target.startswith("【?") and not target.startswith("[") and "?" not in target:
                    confidence += 0.15
                
                # Rule 4: Proper Myanmar target
                if target and not any(ord(c) < 128 for c in target):
                    confidence += 0.10
                
                # Rule 5: Chinese name pattern
                if source and all('\u4e00' <= c <= '\u9fff' for c in source) and 2 <= len(source) <= 3:
                    confidence += 0.10
                
                if confidence >= confidence_threshold:
                    to_approve.append((term['id'], source, confidence))
            
            if not to_approve:
                return 0
            
            # Promote approved terms
            promoted_count = 0
            for term_id, source, confidence in to_approve:
                try:
                    result = self.glossary_repo.update_term(
                        term_id,
                        status='approved',
                        reviewed_at=datetime.now().isoformat()
                    )
                    if result:
                        promoted_count += 1
                        logger.debug(f"Auto-approved: {source} (confidence={confidence:.2f})")
                except Exception as e:
                    logger.warning(f"Failed to auto-approve term '{source}': {e}")
            
            logger.info(f"Auto-approved {promoted_count}/{len(to_approve)} terms by confidence (threshold={confidence_threshold})")
            return promoted_count
        
        # JSON backend
        pending_data = FileHandler.read_json(self.pending_path)
        if not pending_data:
            return 0

        pending_terms = pending_data.get("pending_terms", [])
        if not pending_terms:
            return 0

        to_approve: list = []
        for term in pending_terms:
            # Skip already approved or rejected
            if term.get("status") in ("approved", "rejected"):
                continue

            confidence = 0.0
            source = term.get("source", "")
            target = term.get("target", "")
            category = term.get("category", "general")
            chapter_count = term.get("chapter_count", 0)

            # Rule 1: Multi-chapter appearance (strongest signal)
            if chapter_count >= 3:
                confidence += 0.40
            elif chapter_count >= 2:
                confidence += 0.25

            # Rule 2: Known category types get higher trust
            if category in ("character", "place"):
                confidence += 0.20

            # Rule 3: Not a placeholder
            if target and not target.startswith("【?") and not target.startswith("[") and "?" not in target:
                confidence += 0.15

            # Rule 4: Proper Myanmar target (no Latin script leakage)
            if target and not any(ord(c) < 128 for c in target):
                confidence += 0.10

            # Rule 5: Chinese name pattern (2-3 chars = likely person name)
            if source and all('\u4e00' <= c <= '\u9fff' for c in source) and 2 <= len(source) <= 3:
                confidence += 0.10

            if confidence >= confidence_threshold:
                to_approve.append(term)
                logger.debug(
                    f"Auto-approve candidate: {source} -> {target} "
                    f"(confidence={confidence:.2f}, chapters={chapter_count})"
                )

        if not to_approve:
            return 0

        # Promote approved terms
        promoted_sources = set()
        for term in to_approve:
            source = term.get("source", "")
            target = term.get("target", "")
            category = term.get("category", "general")
            chapter = term.get("extracted_from_chapter", 0)
            if source and target:
                try:
                    if self.add_term(source, target, category, chapter):
                        promoted_sources.add(source)
                        # Mark as verified since it passed confidence check
                        for t in self.glossary.get("terms", []):
                            ts = t.get("source") or t.get("source_term", "")
                            if ts == source:
                                t["verified"] = True
                                t["auto_approved"] = True
                                break
                    else:
                        logger.warning(f"Auto-approve rejected term '{source}' — target '{target}' failed validation")
                except Exception as e:
                    logger.warning(f"Failed to auto-approve term '{source}': {e}")

        # Remove only successfully promoted terms from pending
        pending_data["pending_terms"] = [
            t for t in pending_terms if t.get("source") not in promoted_sources
        ]
        FileHandler.write_json(self.pending_path, pending_data)
        self.save_memory()

        logger.info(f"Auto-approved {len(promoted_sources)}/{len(to_approve)} terms by confidence (threshold={confidence_threshold})")
        return len(promoted_sources)

    def get_all_memory_for_prompt(self, scene_tone: str = "") -> Dict[str, str]:
        """Get all memory tiers formatted for prompts.

        Args:
            scene_tone: Optional scene tone for voice selection
                        ("formal", "casual", "hostile", "pleading", "intimate").
                        When empty, emits all variants (legacy behavior).
        """
        current_chapter = self.context_memory.get("current_chapter", 0)
        if scene_tone:
            voices = self.get_character_voices_for_scene(
                scene_tone=scene_tone,
                active_only=True,
                current_chapter=current_chapter,
            )
        else:
            voices = self.get_character_voices(active_only=True, current_chapter=current_chapter)
        return {
            "glossary": self.get_glossary_for_prompt(),
            "context": self.get_context_buffer(),
            "rules": self.get_session_rules(),
            "summary": self.get_summary(),
            "voices": voices,
        }

    # ── SQL Backend Overrides ─────────────────────────────────────────────

    def save_memory(self):
        """Save all memory to disk (JSON) or no-op (SQL — already persisted)."""
        if self.use_sql:
            return  # SQL writes are immediate
        self.context_memory["paragraph_buffer"] = list(self.paragraph_buffer)
        FileHandler.write_json(self.glossary_path, self.glossary)
        FileHandler.write_json(self.context_path, self.context_memory)
        logger.debug("Memory saved to disk")

    def add_term(self, source: str, target: str, category: str = "general",
                 chapter: int = 0, scope: str = "novel") -> bool:
        """Add a new term to glossary (SQL or JSON backend).
        
        Args:
            source: Source term text
            target: Myanmar translation
            category: Term category
            chapter: Chapter number where term was found
            scope: 'novel' (novel-specific) or 'global' (all novels)
        """
        if self.use_sql:
            if not self._is_valid_myanmar_text(target):
                logger.warning(f"Rejected non-Myanmar target for '{source}': '{target}'")
                return False
            existing = self.glossary_repo.get_term_by_source(self.novel_id, source)
            if existing:
                return False
            self.glossary_repo.add_term(
                novel_id=self.novel_id, source_term=source, target_term=target,
                category=category, status="pending", enforcement_level="soft",
                scope=scope,
            )
            logger.info(f"Added glossary term (SQL): {source} -> {target} (scope={scope})")
            return True
        return self._json_add_term(source, target, category, chapter)

    def add_global_term(self, source: str, target: str,
                        category: str = "general", status: str = "approved",
                        confidence: float = 0.95) -> bool:
        """Add a global xianxia term available to ALL novels.
        
        Global terms are automatically included in every novel's glossary prompt.
        Only works with SQL backend.
        """
        if not self.use_sql:
            logger.error("Global terms require SQL backend")
            return False
        if not self._is_valid_myanmar_text(target):
            logger.warning(f"Rejected non-Myanmar target for global term '{source}': '{target}'")
            return False
        existing = self.glossary_repo.get_term_by_source(self.novel_id, source)
        if existing:
            return False
        self.glossary_repo.add_global_term(
            source_term=source, target_term=target,
            category=category, status=status, confidence=confidence,
        )
        logger.info(f"Added global glossary term: {source} -> {target}")
        return True

    def _json_add_term(self, source: str, target: str, category: str, chapter: int) -> bool:
        """JSON backend add_term (original logic preserved)."""
        terms = self.glossary.get("terms", [])
        existing = {t.get("source") or t.get("source_term", "") for t in terms}
        if source in existing:
            return False
        if not self._is_valid_myanmar_text(target):
            logger.warning(f"Rejected non-Myanmar target for '{source}': '{target}'")
            return False
        similar_source = self._check_target_similarity(source, target)
        if similar_source:
            logger.warning(
                f"Near-duplicate target for '{source}': '{target}' "
                f"is too similar to existing term '{similar_source}'. "
                f"Manual review recommended before approving."
            )
        new_term = {
            "id": f"term_{len(terms) + 1:03d}",
            "source": source, "target": target, "category": category,
            "chapter_first_seen": chapter, "chapter_last_seen": chapter,
            "verified": False, "added_at": datetime.now().isoformat()
        }
        terms.append(new_term)
        self.glossary["terms"] = terms
        self.glossary["total_terms"] = len(terms)
        self.glossary["last_updated"] = datetime.now().isoformat()
        self.save_memory()
        logger.info(f"Added glossary term: {source} -> {target}")
        return True

    def get_term(self, source: str) -> Optional[str]:
        """Get target translation for a source term (SQL or JSON)."""
        if self.use_sql:
            term = self.glossary_repo.get_term_by_source(self.novel_id, source)
            return term["target_term"] if term else None
        terms = self.glossary.get("terms", [])
        for term in terms:
            term_source = term.get("source") or term.get("source_term", "")
            if term_source == source:
                return term.get("target") or term.get("target_term")
        if self.use_universal:
            universal_terms = self.universal_glossary.get("terms", [])
            for term in universal_terms:
                term_source = term.get("source_term") or term.get("source", "")
                if term_source == source:
                    return term.get("target_term") or term.get("target")
        return None

    def get_all_terms(self) -> List[Dict[str, Any]]:
        """Get all glossary terms (SQL or JSON), including global xianxia terms."""
        if self.use_sql:
            terms = self.glossary_repo.get_terms_by_novel(self.novel_id, include_global=True)
            return [
                {
                    "id": t["id"], "source": t["source_term"], "target": t["target_term"],
                    "category": t["category"], "verified": t["status"] == "approved",
                    "chapter_last_seen": t["usage_count"],
                    "scope": t.get("scope", "novel"),
                }
                for t in terms
            ]
        combined = []
        per_novel = self.glossary.get("terms", [])
        combined.extend(per_novel)
        if self.use_universal:
            per_novel_sources = {t.get("source") or t.get("source_term", "") for t in per_novel}
            universal = self.universal_glossary.get("terms", [])
            for term in universal:
                source = term.get("source_term") or term.get("source", "")
                if source not in per_novel_sources:
                    combined.append(term)
        return combined

    def get_global_terms(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get global xianxia terms (SQL only)."""
        if not self.use_sql:
            return []
        terms = self.glossary_repo.get_global_terms(status=status)
        return [
            {
                "id": t["id"], "source": t["source_term"], "target": t["target_term"],
                "category": t["category"], "verified": t["status"] == "approved",
                "scope": "global",
            }
            for t in terms
        ]

    def get_glossary_for_prompt(self, limit: int = 20) -> str:
        """Get formatted glossary for prompt injection (SQL or JSON)."""
        if self.use_sql:
            terms = self.glossary_repo.get_terms_for_prompt(self.novel_id, limit)
        else:
            all_terms = self.get_all_terms()
            terms = sorted(all_terms, key=lambda t: t.get("chapter_last_seen", 0) or 0, reverse=True)[:limit]

        if not terms:
            return "No glossary entries yet."

        lines = ["GLOSSARY (Use these exact translations):"]
        for term in terms:
            verified = "✓" if term.get("verified") else "○"
            source = self._sanitize_for_prompt(term.get("source") or term.get("source_term", ""))
            target = self._sanitize_for_prompt(term.get("target") or term.get("target_term", ""))
            category = self._sanitize_for_prompt(term.get('category', 'general'))
            lines.append(f"  [{verified}] {source} = {target} ({category})")
        return "\n".join(lines)

    def update_chapter_context(self, chapter_num: int, translated_text: str = "", summary: str = "", source_text: str = "") -> None:
        """Update context after chapter translation (SQL or JSON)."""
        active_chars: list = []  # ensure always bound (fix UnboundLocalError in SQL path)
        if self.use_sql:
            chapter_id = f"chapter_{self.novel_id}_{chapter_num:04d}"
            chapter = self.chapter_repo.get_by_id(chapter_id)
            if not chapter:
                self.chapter_repo.create(
                    novel_id=self.novel_id, chapter_num=chapter_num,
                    file_path="", translation_status="translated",
                )
            if translated_text or summary:
                snap_summary = summary or self._generate_summary_from_text(translated_text)
                # Extract active characters and events like JSON path does
                active_chars = []
                try:
                    self._update_active_characters(translated_text)
                    active_chars = list(self.context_memory.get("active_characters", {}).keys())
                except Exception as e:
                    logger.debug(f"Active characters extraction failed: {e}")
                events = []
                try:
                    self._update_recent_events(translated_text, chapter_num)
                    events = self.context_memory.get("recent_events", [])
                except Exception as e:
                    logger.debug(f"Recent events extraction failed: {e}")
                # Extract character voices
                try:
                    if source_text:
                        self.extract_character_voices_from_text(source_text, translated_text, chapter_num)
                except Exception as e:
                    logger.debug(f"Character voice extraction failed: {e}")
                # Collect extracted voices for snapshot persistence
                try:
                    voice_data = self.context_memory.get("character_voices", {})
                except Exception:
                    voice_data = {}
                snapshot = {
                    "active_chars": active_chars,
                    "events": events,
                    "summary": snap_summary,
                    "character_voices": voice_data,
                    "new_terms": [],
                    "updated_at": datetime.now().isoformat(),
                }
                self.context_repo.create_snapshot(chapter_id, _json.dumps(snapshot, ensure_ascii=False))
            self.chapter_repo.update_status(chapter_id, "translated")
            logger.info(f"SQL context updated for chapter {chapter_num}: {len(active_chars)} active chars, {len(events)} events")
            return

        self.context_memory["last_translated_chapter"] = self.context_memory.get("current_chapter", 0)
        self.context_memory["current_chapter"] = chapter_num
        if summary:
            self.context_memory["summary"] = summary
        elif translated_text:
            self.context_memory["summary"] = self._generate_summary_from_text(translated_text)
        if translated_text:
            try:
                self._update_active_characters(translated_text)
            except Exception as e:
                logger.warning(f"Active characters update failed: {e}")
            try:
                self._update_recent_events(translated_text, chapter_num)
            except Exception as e:
                logger.warning(f"Recent events update failed: {e}")
            try:
                self.extract_character_voices_from_text(source_text or "", translated_text, chapter_num)
            except Exception as e:
                logger.debug(f"Character voice extraction failed (non-fatal): {e}")
        self.save_memory()

    def close(self):
        """Close SQL connection if using SQL backend."""
        if self.use_sql and hasattr(self, "db"):
            self.db.close()

    def log_term_usage_for_chapter(self, chapter_num: int, translated_text: str) -> int:
        """Scan translated text for glossary terms and log their usage.
        
        For each approved glossary term (novel-specific + global), checks if
        the Myanmar translation appears in the translated text. If found,
        logs the usage to the term_usage table.
        
        Args:
            chapter_num: Current chapter number
            translated_text: Full translated Myanmar text
            
        Returns:
            Number of term usages logged
        """
        if not self.use_sql:
            return 0
        
        from src.db.repositories.glossary_repo import GLOBAL_NOVEL_ID
        
        # Get all approved terms (novel-specific + global)
        all_terms = self.glossary_repo.get_terms_by_novel(
            self.novel_id, status="approved", include_global=True, limit=500
        )
        
        chapter_id = f"chapter_{self.novel_id}_{chapter_num:04d}"
        logged_count = 0
        
        for term in all_terms:
            target = term.get("target_term", "")
            term_id = term.get("id")
            if not target or not term_id or target.startswith("【?"):
                continue
            
            # Check if the Myanmar translation appears in the text
            if target in translated_text:
                # Find the first paragraph where it appears for context snippet
                paragraphs = translated_text.split("\n\n")
                for idx, para in enumerate(paragraphs):
                    if target in para:
                        try:
                            snippet = para[:200] if len(para) > 200 else para
                            self.glossary_repo.log_term_usage(
                                term_id=term_id,
                                chapter_id=chapter_id,
                                paragraph_idx=idx,
                                variant_used=target,
                                confidence=1.0,
                                context_snippet=snippet,
                            )
                            # Increment usage_count on the term itself
                            self.glossary_repo.increment_usage(term_id)
                            logged_count += 1
                        except Exception as e:
                            logger.debug(
                                f"Skipped term usage log for '{target}' (id={term_id}): {e}"
                            )
                        break
        
        if logged_count > 0:
            logger.info(f"Logged {logged_count} term usages for chapter {chapter_num}")
        
        return logged_count
