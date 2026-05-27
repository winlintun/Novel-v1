"""
Dynamic Glossary Matcher
Extracts and injects only relevant glossary terms for the current chapter.
Uses SQLite glossary_term table data via MemoryManager — no JSON file access.
"""

import re
from typing import Dict, List, Optional


class GlossaryMatcher:
    """
    Matches glossary terms against source text and returns
    only relevant entries for translation context.
    
    Uses SQLite-backed MemoryManager as the single source of truth.
    """

    def __init__(self, memory_manager):
        """Initialize with MemoryManager (SQLite backend required).
        
        Args:
            memory_manager: MemoryManager instance (SQLite glossary_term table)
            
        Raises:
            ValueError: If memory_manager is None
        """
        if memory_manager is None:
            raise ValueError("memory_manager is required (SQLite glossary source)")
        self.memory = memory_manager
        self.terms: Dict[str, dict] = {}
        self.alias_map: Dict[str, str] = {}
        
        self._build_from_sql()

    def _build_from_sql(self):
        """Build indexes from SQLite via MemoryManager."""
        if not self.memory:
            return
        
        all_terms = self.memory.get_all_terms()
        for term in all_terms:
            source = term.get("source", "")
            if source:
                self.terms[source] = term
                # Index aliases from variant data if available
                for alias in term.get("aliases_cn", []):
                    if alias:
                        self.alias_map[alias] = source

    def extract_cn_terms(self, text: str) -> List[str]:
        """Find all 1-8 character Chinese terms in source text."""
        return list(set(re.findall(r'[\u4e00-\u9fff]{1,8}', text)))

    def get_relevant_terms(self, chapter_text: str) -> List[dict]:
        """Get glossary terms that appear in the chapter text."""
        cn_terms = self.extract_cn_terms(chapter_text)
        matched = []
        seen = set()

        for term in cn_terms:
            primary = self.alias_map.get(term, term)
            if primary in self.terms and primary not in seen:
                matched.append(self.terms[primary])
                seen.add(primary)

        return sorted(matched, key=lambda x: x.get("priority", 99))

    def get_relevant_glossary_snippet(self, chapter_text: str, max_entries: int = 20) -> str:
        """
        Return compact glossary table of terms found in current chapter.
        
        Args:
            chapter_text: Source chapter text
            max_entries: Maximum number of terms to include
            
        Returns:
            Markdown-formatted glossary snippet or empty string
        """
        terms = self.get_relevant_terms(chapter_text)

        if not terms:
            return ""

        lines = [
            "[GLOSSARY - USE EXACT TRANSLATIONS]",
            "| Chinese | Myanmar | Category | Notes |",
            "|---------|---------|----------|-------|"
        ]

        for term in terms[:max_entries]:
            notes = []
            if term.get("pronunciation_guide"):
                notes.append(f"pron: {term['pronunciation_guide']}")
            if term.get("exceptions"):
                notes.append(f"{len(term['exceptions'])} rules")

            src = term.get("source", term.get("source_term", "")).replace("|", "\\|")
            tgt = term.get("target", term.get("target_term", "")).replace("|", "\\|")
            cat = term.get("category", "general")
            note_str = "; ".join(notes[:2]) or "-"

            lines.append(f"| {src} | {tgt} | {cat} | {note_str} |")

        return "\n".join(lines)

    def get_term_translation(self, source_term: str) -> Optional[str]:
        """Get translation for a specific term."""
        if source_term in self.terms:
            return self.terms[source_term].get("target", self.terms[source_term].get("target_term"))
        primary = self.alias_map.get(source_term)
        if primary and primary in self.terms:
            return self.terms[primary].get("target", self.terms[primary].get("target_term"))
        return None
