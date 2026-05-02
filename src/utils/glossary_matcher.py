"""
Dynamic Glossary Matcher
Extracts and injects only relevant glossary terms for the current chapter.
"""

import re
import json
from typing import Dict, List, Optional


class GlossaryMatcher:
    """
    Matches glossary terms against source text and returns
    only relevant entries for translation context.
    """

    def __init__(self, glossary_path: str):
        """Initialize with glossary file path."""
        self.glossary_path = glossary_path
        self.data = self._load_glossary()
        self.terms: Dict[str, dict] = {}
        self.alias_map: Dict[str, str] = {}
        self._build_indexes()

    def _load_glossary(self) -> dict:
        """Load glossary from JSON file."""
        try:
            with open(self.glossary_path, "r", encoding="utf-8-sig") as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Could not load glossary: {e}")
            return {"terms": []}

    def _build_indexes(self):
        """Build term and alias indexes for fast lookup."""
        for term in self.data.get("terms", []):
            source = term.get("source_term", "")
            if source:
                self.terms[source] = term
                # Index aliases
                for alias in term.get("aliases_cn", []):
                    if alias:
                        self.alias_map[alias] = source

    def extract_cn_terms(self, text: str) -> List[str]:
        """Find all 1-8 character Chinese terms in source text."""
        # Match Chinese characters (CJK Unified Ideographs)
        # Allow 1-char terms (e.g., 气) up to 8-char terms (e.g., 紫霄神雷诀)
        return list(set(re.findall(r'[\u4e00-\u9fff]{1,8}', text)))

    def get_relevant_terms(self, chapter_text: str) -> List[dict]:
        """Get glossary terms that appear in the chapter text."""
        cn_terms = self.extract_cn_terms(chapter_text)
        matched = []
        seen = set()

        for term in cn_terms:
            # Check if term is in glossary or alias map
            primary = self.alias_map.get(term, term)
            if primary in self.terms and primary not in seen:
                matched.append(self.terms[primary])
                seen.add(primary)

        # Sort by priority (lower number = higher priority)
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

            src = term.get("source_term", "").replace("|", "\\|")
            tgt = term.get("target_term", "").replace("|", "\\|")
            cat = term.get("category", "general")
            note_str = "; ".join(notes[:2]) or "-"

            lines.append(f"| {src} | {tgt} | {cat} | {note_str} |")

        return "\n".join(lines)

    def get_term_translation(self, source_term: str) -> Optional[str]:
        """Get translation for a specific term."""
        # Check direct match
        if source_term in self.terms:
            return self.terms[source_term].get("target_term")
        # Check aliases
        primary = self.alias_map.get(source_term)
        if primary and primary in self.terms:
            return self.terms[primary].get("target_term")
        return None
