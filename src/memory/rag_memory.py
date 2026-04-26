#!/usr/bin/env python3
"""
RAG Memory System for Novel Translation.
Uses vector storage for long-term memory and context retrieval.
"""

import json
import logging
import os
import hashlib
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class RAGMemory:
    """
    Retrieval-Augmented Generation memory for novel translation.
    Stores and retrieves context using simple text-based similarity.
    """
    
    def __init__(self, memory_dir: str = "data/rag_memory"):
        self.memory_dir = memory_dir
        self.context_dir = os.path.join(memory_dir, "contexts")
        self.index_file = os.path.join(memory_dir, "index.json")
        self._ensure_dirs()
        self.index = self._load_index()
    
    def _ensure_dirs(self) -> None:
        """Create memory directories if they don't exist."""
        os.makedirs(self.context_dir, exist_ok=True)
    
    def _load_index(self) -> Dict[str, Any]:
        """Load or create index file."""
        if os.path.exists(self.index_file):
            with open(self.index_file, 'r', encoding='utf-8-sig') as f:
                return json.load(f)
        return {"entries": [], "novels": {}}
    
    def _save_index(self) -> None:
        """Save index to file."""
        with open(self.index_file, 'w', encoding='utf-8-sig') as f:
            json.dump(self.index, f, ensure_ascii=False, indent=2)
    
    def _compute_hash(self, text: str) -> str:
        """Compute hash for text."""
        return hashlib.md5(text.encode()).hexdigest()[:12]
    
    def add_context(
        self,
        novel_name: str,
        chapter: int,
        text: str,
        summary: str = "",
        characters: List[str] = None,
        locations: List[str] = None
    ) -> str:
        """
        Add context for a chapter.
        
        Args:
            novel_name: Name of the novel
            chapter: Chapter number
            text: Full chapter text
            summary: Chapter summary
            characters: List of character names
            locations: List of location names
            
        Returns:
            Context ID
        """
        context_id = f"{novel_name}_ch{chapter}_{self._compute_hash(text)}"
        
        entry = {
            "id": context_id,
            "novel": novel_name,
            "chapter": chapter,
            "summary": summary,
            "characters": characters or [],
            "locations": locations or [],
            "text_hash": self._compute_hash(text),
            "word_count": len(text.split())
        }
        
        # Save full context
        context_file = os.path.join(self.context_dir, f"{context_id}.json")
        with open(context_file, 'w', encoding='utf-8-sig') as f:
            json.dump({
                "entry": entry,
                "text": text[:10000]  # Store first 10k chars
            }, f, ensure_ascii=False, indent=2)
        
        # Update index
        if novel_name not in self.index["novels"]:
            self.index["novels"][novel_name] = []
        
        self.index["novels"][novel_name].append(chapter)
        self.index["entries"].append(entry)
        self._save_index()
        
        logger.info(f"Added context: {context_id}")
        return context_id
    
    def get_context(
        self,
        novel_name: str,
        chapter: int,
        num_chapters: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Retrieve context for a chapter.
        
        Args:
            novel_name: Name of the novel
            chapter: Current chapter number
            num_chapters: Number of previous chapters to retrieve
            
        Returns:
            List of context entries
        """
        if novel_name not in self.index["novels"]:
            return []
        
        chapters = sorted(self.index["novels"].get(novel_name, []))
        prev_chapters = [c for c in chapters if c < chapter][-num_chapters:]
        
        contexts = []
        for ch in prev_chapters:
            context_id = f"{novel_name}_ch{ch}"
            context_file = os.path.join(self.context_dir, f"{context_id}.json")
            
            if os.path.exists(context_file):
                with open(context_file, 'r', encoding='utf-8-sig') as f:
                    data = json.load(f)
                    contexts.append(data["entry"])
        
        return contexts
    
    def get_summary(self, novel_name: str, chapter: int) -> str:
        """Get chapter summary."""
        contexts = self.get_context(novel_name, chapter, num_chapters=5)
        summaries = [c.get("summary", "") for c in contexts if c.get("summary")]
        return " | ".join(summaries[-3:]) if summaries else ""
    
    def get_characters(self, novel_name: str, chapter: int) -> Dict[str, str]:
        """Get active characters up to chapter."""
        contexts = self.get_context(novel_name, chapter, num_chapters=10)
        characters = {}
        for ctx in contexts:
            for char in ctx.get("characters", []):
                if isinstance(char, dict):
                    characters[char.get("name", "")] = char.get("description", "")
                else:
                    characters[char] = ""
        return characters
    
    def search_by_keyword(self, novel_name: str, keyword: str) -> List[Dict[str, Any]]:
        """Search contexts by keyword."""
        results = []
        chapters = self.index["novels"].get(novel_name, [])
        
        for ch in chapters:
            context_id = f"{novel_name}_ch{ch}"
            context_file = os.path.join(self.context_dir, f"{context_id}.json")
            
            if os.path.exists(context_file):
                with open(context_file, 'r', encoding='utf-8-sig') as f:
                    data = json.load(f)
                    text = data.get("text", "").lower()
                    if keyword.lower() in text:
                        results.append(data["entry"])
        
        return results
    
    def clear_novel(self, novel_name: str) -> None:
        """Clear all context for a novel."""
        if novel_name in self.index["novels"]:
            chapters = self.index["novels"][novel_name]
            
            for ch in chapters:
                context_id = f"{novel_name}_ch{ch}"
                context_file = os.path.join(self.context_dir, f"{context_id}.json")
                if os.path.exists(context_file):
                    os.remove(context_file)
            
            self.index["novels"].pop(novel_name)
            self.index["entries"] = [
                e for e in self.index["entries"] if e.get("novel") != novel_name
            ]
            self._save_index()
            
            logger.info(f"Cleared context for novel: {novel_name}")


def create_rag_memory(memory_dir: str = "data/rag_memory") -> RAGMemory:
    """Factory function to create RAG memory."""
    return RAGMemory(memory_dir)