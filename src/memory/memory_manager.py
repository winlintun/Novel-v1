"""
Memory Manager Module
Handles 3-tier memory system: Glossary and Context Memory.
Supports per-novel glossary (primary) + optional universal reference (read-only).

NOTE: Universal blueprint files are READ-ONLY reference templates.
They are NOT written to - only used as optional read-only fallback.
"""

import logging
import os
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
        use_universal: bool = False  # Default: disabled (per-novel only)
    ):
        # Resolve novel-specific paths when novel_name is provided
        if novel_name:
            glossary_path, context_path, self.pending_path = _resolve_glossary_path(novel_name)
        else:
            self.pending_path = "data/output/default/glossary/glossary_pending.json"

        self.glossary_path = glossary_path
        self.context_path = context_path
        self.novel_name = novel_name
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

        # Load all memory
        self._load_memory()

    def _load_memory(self):
        """Load all memory files including universal (shared) glossary."""
        
        # Load Universal (shared) glossary first if enabled
        if self.use_universal:
            self.universal_glossary = FileHandler.read_json(UNIVERSAL_GLOSSARY_REF)
            if not self.universal_glossary:
                self.universal_glossary = {
                    "metadata": {"schema_version": "3.2.1"},
                    "terms": []
                }
            else:
                # Strip template placeholder terms (e.g. <MAIN_CHARACTER> / <MYANMAR_NAME>)
                # so blueprint files can exist as reference docs without polluting prompts.
                raw = self.universal_glossary.get("terms", [])
                self.universal_glossary["terms"] = [
                    t for t in raw
                    if not (
                        (t.get("source_term") or t.get("source", "")).startswith("<")
                        and (t.get("source_term") or t.get("source", "")).endswith(">")
                    )
                ]
                logger.info(f"Loaded universal glossary: {len(self.universal_glossary.get('terms', []))} terms")
            
            # Load universal pending terms
            self.universal_pending = FileHandler.read_json(UNIVERSAL_PENDING_REF)
            if not self.universal_pending:
                self.universal_pending = {
                    "metadata": {"schema_version": "3.2.1-pending"},
                    "pending_terms": []
                }
            
            # Load universal context
            self.universal_context = FileHandler.read_json(UNIVERSAL_CONTEXT_REF)
            if not self.universal_context:
                self.universal_context = {
                    "metadata": {"schema_version": "3.2.1"},
                    "dynamic_character_states": [],
                    "translation_flow_buffer": []
                }
        
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
                "recent_events": [],
                "paragraph_buffer": []
            }
        else:
            # Restore paragraph buffer
            buffer_data = self.context_memory.get("paragraph_buffer", [])
            self.paragraph_buffer = deque(buffer_data, maxlen=10)

        logger.info(f"Memory loaded: {self.glossary.get('total_terms', 0)} glossary terms")

    def save_memory(self):
        """Save all memory to disk."""
        # Update context memory with buffer
        self.context_memory["paragraph_buffer"] = list(self.paragraph_buffer)

        # Save files
        FileHandler.write_json(self.glossary_path, self.glossary)
        FileHandler.write_json(self.context_path, self.context_memory)

        logger.debug("Memory saved to disk")

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

    def add_term(
        self,
        source: str,
        target: str,
        category: str = "general",
        chapter: int = 0
    ) -> bool:
        """Add a new term to glossary.
        
        Validates that the target contains Myanmar text before accepting.
        """
        terms = self.glossary.get("terms", [])

        # Check for duplicates
        existing = {t.get("source") or t.get("source_term", "") for t in terms}
        if source in existing:
            return False

        # Validate target contains Myanmar text (reject pure English/Latin/Chinese)
        if not self._is_valid_myanmar_text(target):
            logger.warning(f"Rejected non-Myanmar target for '{source}': '{target}'")
            return False

        # Check semantic deduplication: warn if target is too similar to existing term
        similar_source = self._check_target_similarity(source, target)
        if similar_source:
            logger.warning(
                f"Near-duplicate target for '{source}': '{target}' "
                f"is too similar to existing term '{similar_source}'. "
                f"Manual review recommended before approving."
            )

        new_term = {
            "id": f"term_{len(terms) + 1:03d}",
            "source": source,
            "target": target,
            "category": category,
            "chapter_first_seen": chapter,
            "chapter_last_seen": chapter,
            "verified": False,
            "added_at": datetime.now().isoformat()
        }

        terms.append(new_term)
        self.glossary["terms"] = terms
        self.glossary["total_terms"] = len(terms)
        self.glossary["last_updated"] = datetime.now().isoformat()

        self.save_memory()
        logger.info(f"Added glossary term: {source} -> {target}")
        return True

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

    def get_term(self, source: str) -> Optional[str]:
        """Get target translation for a source term.
        
        Dual-layer lookup:
        1. First check per-novel glossary
        2. Fall back to universal glossary (shared terms)
        """
        # First: Check per-novel glossary
        terms = self.glossary.get("terms", [])
        for term in terms:
            term_source = term.get("source") or term.get("source_term", "")
            if term_source == source:
                return term.get("target") or term.get("target_term")
        
        # Second: Check universal glossary (fallback)
        if self.use_universal:
            universal_terms = self.universal_glossary.get("terms", [])
            for term in universal_terms:
                term_source = term.get("source_term") or term.get("source", "")
                if term_source == source:
                    return term.get("target_term") or term.get("target")
        
        return None

    def get_glossary_for_prompt(self, limit: int = 20) -> str:
        """Get formatted glossary for prompt injection.

        Sorts terms by chapter_last_seen (most recent first) so freshest
        terms stay in the window as the glossary grows past `limit`.
        
        Includes both per-novel and universal glossary terms.
        """
        all_terms = self.get_all_terms()

        if not all_terms:
            return "No glossary entries yet."

        # Sort by chapter_last_seen descending, then take top `limit`
        sorted_terms = sorted(
            all_terms,
            key=lambda t: t.get("chapter_last_seen", 0) or 0,
            reverse=True
        )

        lines = ["GLOSSARY (Use these exact translations):"]

        for term in sorted_terms[:limit]:
            verified = "✓" if term.get("verified") else "○"
            # Handle both novel and universal term formats
            source = self._sanitize_for_prompt(
                term.get("source") or term.get("source_term", "")
            )
            target = self._sanitize_for_prompt(
                term.get("target") or term.get("target_term", "")
            )
            category = self._sanitize_for_prompt(term.get('category', 'general'))
            lines.append(
                f"  [{verified}] {source} = {target} "
                f"({category})"
            )

        return "\n".join(lines)

    def get_all_terms(self) -> List[Dict[str, Any]]:
        """Get all glossary terms (per-novel + universal).
        
        Returns combined list with per-novel terms first,
        then universal terms.
        """
        combined = []
        
        # Add per-novel terms first (takes priority)
        per_novel = self.glossary.get("terms", [])
        combined.extend(per_novel)
        
        # Add universal terms (skip duplicates)
        if self.use_universal:
            per_novel_sources = {t.get("source") or t.get("source_term", "") for t in per_novel}
            universal = self.universal_glossary.get("terms", [])
            for term in universal:
                source = term.get("source_term") or term.get("source", "")
                if source not in per_novel_sources:
                    combined.append(term)
        
        return combined

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

    def update_chapter_context(self, chapter_num: int, summary: str = ""):
        """Update context after chapter translation."""
        self.context_memory["last_translated_chapter"] = self.context_memory.get("current_chapter", 0)
        self.context_memory["current_chapter"] = chapter_num

        if summary:
            self.context_memory["summary"] = summary

        self.save_memory()

    def push_to_buffer(self, translated_text: str):
        """Add translated paragraph to FIFO buffer."""
        self.paragraph_buffer.append(translated_text)

    def get_context_buffer(self, count: int = 3) -> str:
        """Get recent translations for context."""
        if not self.paragraph_buffer:
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

    def auto_approve_pending_terms(self) -> int:
        """Automatically promote pending terms with status 'approved'.

        User writes 'approved' in the status field of glossary_pending.json,
        then on next pipeline run, these terms are auto-promoted to the
        main glossary and removed from the pending list.

        Returns:
            Number of terms promoted
        """
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

    def get_all_memory_for_prompt(self) -> Dict[str, str]:
        """Get all memory tiers formatted for prompts."""
        return {
            "glossary": self.get_glossary_for_prompt(),
            "context": self.get_context_buffer(),
            "rules": self.get_session_rules(),
            "summary": self.get_summary()
        }
