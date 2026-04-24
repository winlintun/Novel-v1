"""
Glossary v3.0 Loader - JSON I/O with Schema Validation
"""
import json
import logging
from pathlib import Path
from typing import Optional, Union
from datetime import datetime, timezone

from src.utils.glossary_v3_manager import GlossaryTerm, TermCategory, TranslationRule
from src.utils.file_handler import FileHandler

logger = logging.getLogger(__name__)


class GlossaryV3Loader:
    """Load, validate, and cache Glossary v3.0 JSON files."""
    
    REQUIRED_TOP_FIELDS = [
        "glossary_version", "novel_name", "source_language", 
        "target_language", "terms"
    ]
    
    REQUIRED_TERM_FIELDS = [
        "id", "source_term", "target_term", "category", 
        "translation_rule", "priority"
    ]
    
    def __init__(self, glossary_path: Union[str, Path]):
        """
        Initialize the glossary loader.
        
        Args:
            glossary_path: Path to the glossary JSON file
        """
        self.path = Path(glossary_path)
        self._cache: dict[str, GlossaryTerm] = {}
        self._alias_index: dict[str, str] = {}  # alias → primary_id
        self._metadata: dict = {}
        self._loaded = False
    
    def load(self, force_reload: bool = False) -> bool:
        """
        Load glossary JSON with validation. Returns success status.
        
        Args:
            force_reload: Force reload even if already loaded
            
        Returns:
            True if loaded successfully, False otherwise
        """
        if self._loaded and not force_reload:
            return True
        
        if not self.path.exists():
            return False
        
        try:
            data = FileHandler.read_json(str(self.path))

            # Handle empty or invalid data
            if not data:
                logger.error(f"Glossary file is empty or invalid: {self.path}")
                return False

            # Validate top-level structure
            if not all(field in data for field in self.REQUIRED_TOP_FIELDS):
                return False
            
            # Validate version compatibility
            version = data["glossary_version"]
            if not version.startswith(("3.", "2.", "1.")):
                return False  # Unsupported version
            
            # Parse terms
            self._cache.clear()
            self._alias_index.clear()
            
            for term_data in data.get("terms", []):
                # Validate required fields
                if not all(f in term_data for f in self.REQUIRED_TERM_FIELDS):
                    continue  # Skip invalid entries
                
                # Create GlossaryTerm instance
                term = GlossaryTerm(
                    id=term_data["id"],
                    source_term=term_data["source_term"],
                    target_term=term_data["target_term"],
                    category=TermCategory(term_data["category"]),
                    translation_rule=TranslationRule(term_data["translation_rule"]),
                    priority=term_data["priority"],
                    # Optional fields with defaults
                    aliases_cn=term_data.get("aliases_cn", []),
                    aliases_mm=term_data.get("aliases_mm", []),
                    pronunciation_guide=term_data.get("pronunciation_guide"),
                    do_not_translate=term_data.get("do_not_translate", False),
                    usage_frequency=term_data.get("usage_frequency", "medium"),
                    semantic_tags=term_data.get("semantic_tags", []),
                    gender=term_data.get("gender"),
                    status=term_data.get("status", {}),
                    chapter_range=term_data.get("chapter_range", {}),
                    relationships=term_data.get("relationships", []),
                    dialogue_register=term_data.get("dialogue_register"),
                    exceptions=term_data.get("exceptions", []),
                    examples=term_data.get("examples", []),
                    verified=term_data.get("verified", False),
                    last_updated_chapter=term_data.get("last_updated_chapter"),
                )
                
                # Index by primary key
                self._cache[term.get_primary_key()] = term
                
                # Index aliases for fast lookup
                for alias in term.get_all_source_variants():
                    self._alias_index[alias] = term.get_primary_key()
            
            self._metadata = {
                "version": data["glossary_version"],
                "novel_name": data["novel_name"],
                "source_language": data["source_language"],
                "target_language": data["target_language"],
                "last_updated": data.get("last_updated"),
                "total_terms": len(self._cache),
                "loaded_at": datetime.now(timezone.utc).isoformat()
            }
            self._loaded = True
            return True
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Failed to load glossary from {self.path}: {e}")
            return False
    
    def lookup(
        self,
        source_text: str,
        category: Optional[TermCategory] = None
    ) -> Optional[GlossaryTerm]:
        """
        Smart lookup: exact match → alias match → fuzzy fallback.
        Returns GlossaryTerm or None.

        Note: If source_text exists in multiple categories and no category
        filter is provided, the first match found is returned (deterministic
        based on insertion order, but may be arbitrary).

        Args:
            source_text: The Chinese term to look up
            category: Optional category filter to disambiguate terms

        Returns:
            GlossaryTerm if found, None otherwise
        """
        # Exact match by source_term
        key = f"{source_text}:{category.value}" if category else source_text
        if key in self._cache:
            return self._cache[key]
        
        # Alias match
        if source_text in self._alias_index:
            primary_key = self._alias_index[source_text]
            return self._cache.get(primary_key)
        
        # Category-filtered search
        if category:
            for term in self._cache.values():
                if (
                    term.category == category and 
                    source_text in term.get_all_source_variants()
                ):
                    return term
        
        return None
    
    def lookup_in_text(
        self,
        text: str,
        categories: Optional[list[TermCategory]] = None
    ) -> list[GlossaryTerm]:
        """
        Extract all glossary terms found in text.
        Searches for all glossary terms (and aliases) within the text.

        Args:
            text: Text to search for glossary terms
            categories: Optional list of categories to filter by

        Returns:
            List of found GlossaryTerm objects
        """
        found = []
        seen_ids = set()

        # Search through all glossary terms
        for term in self._cache.values():
            if term.id in seen_ids:
                continue

            # Check if any variant of this term exists in the text
            for variant in term.get_all_source_variants():
                if variant in text:
                    # Category filter check
                    if categories and term.category not in categories:
                        break
                    found.append(term)
                    seen_ids.add(term.id)
                    break  # Found this term, move to next

        return found
    
    def export_for_prompt(
        self, 
        max_entries: int = 40,
        priority_threshold: int = 3,
        include_examples: bool = False,
        format: str = "markdown"
    ) -> str:
        """
        Generate AI-optimized glossary snippet.
        Priority: high-priority + high-frequency + verified terms first.
        
        Args:
            max_entries: Maximum number of entries to include
            priority_threshold: Only include terms with priority <= this value
            include_examples: Whether to include example sentences
            format: Output format ("markdown", "json", or "plain")
            
        Returns:
            Formatted glossary string for prompt injection
        """
        # Filter & sort
        candidates = [
            t for t in self._cache.values()
            if t.status.get("active", True) 
            and t.priority <= priority_threshold
        ]
        
        # Sort: priority asc, frequency desc, verified first
        freq_order = {"very_high": 0, "high": 1, "medium": 2, "low": 3, "very_low": 4}
        candidates.sort(key=lambda t: (
            t.priority,
            freq_order.get(t.usage_frequency, 2),
            0 if t.verified else 1
        ))
        
        # Limit entries
        selected = candidates[:max_entries]
        
        # Format output
        if format == "markdown":
            return self._format_markdown(selected, include_examples)
        elif format == "json":
            return json.dumps(
                [t.to_dict() for t in selected], 
                ensure_ascii=False, 
                indent=2
            )
        else:  # plain
            return "\n".join(
                [f"{t.source_term}→{t.target_term}" for t in selected]
            )
    
    def _format_markdown(
        self, 
        terms: list[GlossaryTerm], 
        include_examples: bool
    ) -> str:
        """
        Compact markdown table for prompt injection.
        
        Args:
            terms: List of terms to format
            include_examples: Whether to include examples
            
        Returns:
            Markdown formatted string
        """
        lines = ["[GLOSSARY v3.0 - MANDATORY TRANSLATIONS]"]
        lines.append("| CN Term | MM Translation | Type | Notes |")
        lines.append("|---------|---------------|------|-------|")
        
        for t in terms:
            notes = []
            if t.exceptions:
                notes.append(f"{len(t.exceptions)} exceptions")
            if t.pronunciation_guide:
                notes.append(f"pron: {t.pronunciation_guide}")
            notes_str = "; ".join(notes[:2]) if notes else "-"
            
            src = t.source_term.replace("|", "\\|")
            tgt = t.target_term.replace("|", "\\|")
            lines.append(
                f"| {src} | {tgt} | {t.category.value} | {notes_str} |"
            )
            
            if include_examples and t.examples:
                ex = t.examples[0]
                cn_ex = ex['cn_sentence'][:30] if len(ex['cn_sentence']) > 30 else ex['cn_sentence']
                mm_ex = ex['mm_sentence'][:30] if len(ex['mm_sentence']) > 30 else ex['mm_sentence']
                lines.append(f"| → Example | {cn_ex}… → {mm_ex}… | | |")
        
        return "\n".join(lines)
    
    def get_metadata(self) -> dict:
        """Return glossary metadata (version, counts, etc.)."""
        return self._metadata.copy()
    
    def get_term_count_by_category(self) -> dict[str, int]:
        """Aggregate term counts per category for analytics."""
        counts = {}
        for term in self._cache.values():
            cat = term.category.value
            counts[cat] = counts.get(cat, 0) + 1
        return counts
    
    def get_all_terms(self) -> list[GlossaryTerm]:
        """Return all loaded terms."""
        return list(self._cache.values())
    
    def is_loaded(self) -> bool:
        """Check if glossary has been loaded."""
        return self._loaded
