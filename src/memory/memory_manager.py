"""
Memory Manager Module
Handles 3-tier memory system: Glossary and Context Memory.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from collections import deque
from pathlib import Path

from src.utils.file_handler import FileHandler

logger = logging.getLogger(__name__)


class MemoryManager:
    """
    3-Tier Memory Management System:
    - Tier 1: Global Glossary (Persistent)
    - Tier 2: Chapter Context (FIFO sliding window)
    - Tier 3: Session Rules (Dynamic corrections)
    """
    
    def __init__(
        self,
        glossary_path: str = "data/glossary.json",
        context_path: str = "data/context_memory.json"
    ):
        self.glossary_path = glossary_path
        self.context_path = context_path
        
        # Tier 1: Global Glossary
        self.glossary: Dict[str, Any] = {}
        
        # Tier 2: Context Memory
        self.context_memory: Dict[str, Any] = {}
        self.paragraph_buffer: deque = deque(maxlen=10)
        
        # Tier 3: Session Rules
        self.session_rules: Dict[str, str] = {}
        
        # Load all memory
        self._load_memory()
    
    def _load_memory(self):
        """Load all memory files."""
        # Load glossary
        self.glossary = FileHandler.read_json(self.glossary_path)
        if not self.glossary:
            self.glossary = {
                "version": "1.0",
                "terms": [],
                "total_terms": 0
            }
        
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
        """Add a new term to glossary."""
        terms = self.glossary.get("terms", [])
        
        # Check for duplicates
        existing = {t["source"] for t in terms}
        if source in existing:
            return False
        
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
        """Update an existing term."""
        terms = self.glossary.get("terms", [])
        
        for term in terms:
            if term["source"] == source:
                term["target"] = new_target
                term["chapter_last_seen"] = chapter
                term["updated_at"] = datetime.now().isoformat()
                
                self.save_memory()
                logger.info(f"Updated term: {source} -> {new_target}")
                return True
        
        return False
    
    def get_term(self, source: str) -> Optional[str]:
        """Get target translation for a source term."""
        terms = self.glossary.get("terms", [])
        
        for term in terms:
            if term["source"] == source:
                return term["target"]
        
        return None
    
    def get_glossary_for_prompt(self, limit: int = 20) -> str:
        """Get formatted glossary for prompt injection."""
        terms = self.glossary.get("terms", [])
        
        if not terms:
            return "No glossary entries yet."
        
        lines = ["GLOSSARY (Use these exact translations):"]
        
        for term in terms[:limit]:
            verified = "✓" if term.get("verified") else "○"
            lines.append(
                f"  [{verified}] {term['source']} = {term['target']} "
                f"({term.get('category', 'general')})"
            )
        
        return "\n".join(lines)
    
    def get_all_terms(self) -> List[Dict[str, Any]]:
        """Get all glossary terms."""
        return self.glossary.get("terms", [])
    
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
        
        recent = list(self.paragraph_buffer)[-count:]
        return "PREVIOUS CONTEXT:\n" + "\n".join(recent)
    
    def clear_buffer(self):
        """Clear paragraph buffer (e.g., at chapter end)."""
        self.paragraph_buffer.clear()
        logger.debug("Context buffer cleared")
    
    def get_summary(self) -> str:
        """Get summary of previous chapters."""
        return self.context_memory.get("summary", "")
    
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
            lines.append(f"  {incorrect} -> {correct}")
        
        return "\n".join(lines)
    
    def promote_rule_to_glossary(self, incorrect: str, correct: str, chapter: int = 0):
        """Promote a session rule to permanent glossary entry."""
        # Add to glossary
        self.add_term(incorrect, correct, "user_correction", chapter)
        
        # Remove from session rules
        if incorrect in self.session_rules:
            del self.session_rules[incorrect]
        
        logger.info(f"Promoted to glossary: {incorrect} -> {correct}")
    
    def get_all_memory_for_prompt(self) -> Dict[str, str]:
        """Get all memory tiers formatted for prompts."""
        return {
            "glossary": self.get_glossary_for_prompt(),
            "context": self.get_context_buffer(),
            "rules": self.get_session_rules(),
            "summary": self.get_summary()
        }
