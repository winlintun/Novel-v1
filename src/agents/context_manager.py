#!/usr/bin/env python3
"""
Context Manager - Tracks Characters, Story, and Chapter Context for Novel Translation

Workflow:
    Characters + Story + Chapter → translate → rewrite → refine → output

This module manages contextual information across chapters to ensure consistency
in character portrayal, story continuity, and narrative flow.

Storage:
    - Characters: context/{novel_name}/characters.json
    - Story: context/{novel_name}/story.json
    - Chapters: context/{novel_name}/chapters.json

Usage:
    from scripts.context_manager import ContextManager
    
    # Initialize for a novel
    context = ContextManager("novel_name", source_lang="English")
    
    # Get full context for translation
    context_text = context.get_context_for_chapter(chapter_num=5)
    
    # After translation, update context with new information
    context.update_from_translation(chapter_num, translated_text)
    context.save()
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from dataclasses import dataclass, field, asdict

# Default directory for context files
CONTEXT_DIR = Path("context")


@dataclass
class Character:
    """Represents a character in the novel."""
    name: str  # Original name (Chinese/English)
    burmese_name: Optional[str] = None  # Translated Burmese name
    description: str = ""  # Physical/character description
    aliases: List[str] = field(default_factory=list)  # Alternative names
    relationships: Dict[str, str] = field(default_factory=dict)  # relation -> character name
    first_appearance: int = 0  # Chapter number
    importance: str = "minor"  # major, supporting, minor
    traits: List[str] = field(default_factory=list)  # Character traits
    notes: str = ""  # Additional notes
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Character':
        return cls(**data)


@dataclass
class StoryEvent:
    """Represents a key story event."""
    chapter: int
    title: str
    summary: str
    key_moments: List[str] = field(default_factory=list)
    characters_involved: List[str] = field(default_factory=list)
    importance: str = "normal"  # critical, major, normal, minor
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'StoryEvent':
        return cls(**data)


@dataclass
class ChapterInfo:
    """Represents information about a translated chapter."""
    chapter_num: int
    title: str
    summary: str = ""
    key_events: List[str] = field(default_factory=list)
    characters_appearing: List[str] = field(default_factory=list)
    new_characters: List[str] = field(default_factory=list)
    translation_status: str = "pending"  # pending, translated, refined
    word_count: int = 0
    translated_at: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ChapterInfo':
        return cls(**data)


class ContextManager:
    """
    Manages context (characters, story, chapters) for novel translation.
    
    Ensures consistency across chapters by tracking:
    - Character information and relationships
    - Story progression and key events
    - Chapter summaries for context injection
    """
    
    def __init__(self, novel_name: str, source_lang: str = "English", auto_create: bool = True):
        """
        Initialize context manager for a novel.
        
        Args:
            novel_name: Name of the novel (used as directory name)
            source_lang: Source language (English, Chinese, etc.)
            auto_create: Create context files if they don't exist
        """
        self.novel_name = novel_name
        self.source_lang = source_lang
        
        # Setup directories
        self.context_dir = CONTEXT_DIR / novel_name
        self.context_dir.mkdir(parents=True, exist_ok=True)
        
        # File paths
        self.characters_file = self.context_dir / "characters.json"
        self.story_file = self.context_dir / "story.json"
        self.chapters_file = self.context_dir / "chapters.json"
        
        # Data storage
        self.characters: Dict[str, Character] = {}  # name -> Character
        self.story_events: List[StoryEvent] = []
        self.chapters: Dict[int, ChapterInfo] = {}  # chapter_num -> ChapterInfo
        
        # Story metadata
        self.story_metadata: Dict = {
            "novel_name": novel_name,
            "source_lang": source_lang,
            "target_lang": "Burmese",
            "total_chapters": 0,
            "translated_chapters": 0,
            "created_at": None,
            "updated_at": None,
            "genre": "",
            "setting": "",
            "main_plot": "",
        }
        
        # Load existing or create new
        if self._context_exists():
            self.load()
        elif auto_create:
            self.story_metadata["created_at"] = datetime.now().isoformat()
            self.save()
    
    def _context_exists(self) -> bool:
        """Check if any context file exists."""
        return (self.characters_file.exists() or 
                self.story_file.exists() or 
                self.chapters_file.exists())
    
    def load(self) -> bool:
        """
        Load all context from JSON files.
        
        Returns:
            True if loaded successfully, False otherwise
        """
        try:
            # Load characters
            if self.characters_file.exists():
                with open(self.characters_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.characters = {
                        name: Character.from_dict(char_data)
                        for name, char_data in data.get("characters", {}).items()
                    }
                    self.story_metadata.update(data.get("metadata", {}))
            
            # Load story events
            if self.story_file.exists():
                with open(self.story_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.story_events = [
                        StoryEvent.from_dict(evt) for evt in data.get("events", [])
                    ]
                    self.story_metadata.update(data.get("metadata", {}))
            
            # Load chapters
            if self.chapters_file.exists():
                with open(self.chapters_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.chapters = {
                        int(num): ChapterInfo.from_dict(ch_data)
                        for num, ch_data in data.get("chapters", {}).items()
                    }
                    self.story_metadata.update(data.get("metadata", {}))
            
            return True
            
        except Exception as e:
            print(f"⚠ Warning: Could not load context: {e}")
            return False
    
    def save(self) -> bool:
        """
        Save all context to JSON files.
        
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            self.story_metadata["updated_at"] = datetime.now().isoformat()
            self.story_metadata["total_chapters"] = len(self.chapters)
            self.story_metadata["translated_chapters"] = sum(
                1 for ch in self.chapters.values() 
                if ch.translation_status == "translated"
            )
            
            # Save characters
            characters_data = {
                "metadata": self.story_metadata,
                "characters": {
                    name: char.to_dict() for name, char in self.characters.items()
                }
            }
            with open(self.characters_file, 'w', encoding='utf-8') as f:
                json.dump(characters_data, f, ensure_ascii=False, indent=2)
            
            # Save story events
            story_data = {
                "metadata": self.story_metadata,
                "events": [evt.to_dict() for evt in self.story_events]
            }
            with open(self.story_file, 'w', encoding='utf-8') as f:
                json.dump(story_data, f, ensure_ascii=False, indent=2)
            
            # Save chapters
            chapters_data = {
                "metadata": self.story_metadata,
                "chapters": {
                    str(num): ch.to_dict() for num, ch in self.chapters.items()
                }
            }
            with open(self.chapters_file, 'w', encoding='utf-8') as f:
                json.dump(chapters_data, f, ensure_ascii=False, indent=2)
            
            return True
            
        except Exception as e:
            print(f"✗ Error saving context: {e}")
            return False
    
    # =========================================================================
    # Character Management
    # =========================================================================
    
    def add_character(self, name: str, burmese_name: Optional[str] = None,
                      description: str = "", aliases: List[str] = None,
                      first_appearance: int = 0, importance: str = "minor",
                      traits: List[str] = None, notes: str = "") -> Character:
        """
        Add a new character to the context.
        
        Args:
            name: Character's original name
            burmese_name: Translated Burmese name
            description: Physical/character description
            aliases: Alternative names for the character
            first_appearance: Chapter number where character first appears
            importance: Character importance (major, supporting, minor)
            traits: List of character traits
            notes: Additional notes
            
        Returns:
            The created Character object
        """
        if name in self.characters:
            # Update existing character
            char = self.characters[name]
            if burmese_name:
                char.burmese_name = burmese_name
            if description:
                char.description = description
            if aliases:
                char.aliases = list(set(char.aliases + aliases))
            if first_appearance and not char.first_appearance:
                char.first_appearance = first_appearance
            if traits:
                char.traits = list(set(char.traits + traits))
            if notes:
                char.notes = notes
        else:
            # Create new character
            char = Character(
                name=name,
                burmese_name=burmese_name,
                description=description,
                aliases=aliases or [],
                first_appearance=first_appearance,
                importance=importance,
                traits=traits or [],
                notes=notes
            )
            self.characters[name] = char
        
        return char
    
    def get_character(self, name: str) -> Optional[Character]:
        """Get a character by name."""
        return self.characters.get(name)
    
    def get_character_by_burmese_name(self, burmese_name: str) -> Optional[Character]:
        """Find a character by their Burmese name."""
        for char in self.characters.values():
            if char.burmese_name == burmese_name:
                return char
        return None
    
    def get_major_characters(self) -> List[Character]:
        """Get list of major characters."""
        return [c for c in self.characters.values() if c.importance == "major"]
    
    def get_characters_introduced_before(self, chapter_num: int) -> List[Character]:
        """Get all characters introduced up to a specific chapter."""
        return [c for c in self.characters.values() 
                if c.first_appearance <= chapter_num and c.first_appearance > 0]
    
    # =========================================================================
    # Story Event Management
    # =========================================================================
    
    def add_story_event(self, chapter: int, title: str, summary: str,
                        key_moments: List[str] = None,
                        characters_involved: List[str] = None,
                        importance: str = "normal") -> StoryEvent:
        """
        Add a new story event.
        
        Args:
            chapter: Chapter number where event occurs
            title: Event title
            summary: Event summary
            key_moments: List of key moments in this event
            characters_involved: List of character names involved
            importance: Event importance (critical, major, normal, minor)
            
        Returns:
            The created StoryEvent object
        """
        event = StoryEvent(
            chapter=chapter,
            title=title,
            summary=summary,
            key_moments=key_moments or [],
            characters_involved=characters_involved or [],
            importance=importance
        )
        self.story_events.append(event)
        # Sort by chapter
        self.story_events.sort(key=lambda e: e.chapter)
        return event
    
    def get_events_up_to_chapter(self, chapter_num: int) -> List[StoryEvent]:
        """Get all story events up to a specific chapter."""
        return [e for e in self.story_events if e.chapter <= chapter_num]
    
    def get_recent_events(self, chapter_num: int, count: int = 3) -> List[StoryEvent]:
        """Get the most recent events before a chapter."""
        events = [e for e in self.story_events if e.chapter < chapter_num]
        return events[-count:] if len(events) >= count else events
    
    # =========================================================================
    # Chapter Management
    # =========================================================================
    
    def register_chapter(self, chapter_num: int, title: str = "",
                        word_count: int = 0) -> ChapterInfo:
        """
        Register a chapter for tracking.
        
        Args:
            chapter_num: Chapter number
            title: Chapter title
            word_count: Original word count
            
        Returns:
            The created ChapterInfo object
        """
        if chapter_num not in self.chapters:
            self.chapters[chapter_num] = ChapterInfo(
                chapter_num=chapter_num,
                title=title,
                word_count=word_count
            )
        return self.chapters[chapter_num]
    
    def update_chapter_translation(self, chapter_num: int, summary: str,
                                   key_events: List[str] = None,
                                   characters_appearing: List[str] = None,
                                   new_characters: List[str] = None):
        """
        Update chapter info after translation.
        
        Args:
            chapter_num: Chapter number
            summary: Chapter summary
            key_events: Key events in this chapter
            characters_appearing: Characters appearing in this chapter
            new_characters: New characters introduced in this chapter
        """
        if chapter_num in self.chapters:
            ch = self.chapters[chapter_num]
            ch.summary = summary
            ch.key_events = key_events or []
            ch.characters_appearing = characters_appearing or []
            ch.new_characters = new_characters or []
            ch.translation_status = "translated"
            ch.translated_at = datetime.now().isoformat()
    
    def get_previous_chapter_summary(self, chapter_num: int) -> Optional[str]:
        """Get summary of the immediately preceding chapter."""
        prev_num = chapter_num - 1
        if prev_num in self.chapters and self.chapters[prev_num].summary:
            return self.chapters[prev_num].summary
        return None
    
    def get_chapter_context(self, chapter_num: int, num_previous: int = 2) -> str:
        """
        Get context from previous chapters.
        
        Args:
            chapter_num: Current chapter number
            num_previous: Number of previous chapters to include
            
        Returns:
            Formatted context string
        """
        context_parts = []
        
        for i in range(1, num_previous + 1):
            prev_num = chapter_num - i
            if prev_num in self.chapters:
                ch = self.chapters[prev_num]
                if ch.summary:
                    context_parts.append(f"Chapter {prev_num}: {ch.summary}")
        
        return "\n\n".join(reversed(context_parts))
    
    # =========================================================================
    # Context Injection for Translation
    # =========================================================================
    
    def get_context_for_chapter(self, chapter_num: int, 
                                include_characters: bool = True,
                                include_story: bool = True,
                                include_chapters: bool = True,
                                max_chars: int = 3000) -> str:
        """
        Get formatted context for translation injection.
        
        This is the main method for getting context to inject into the
        translation prompt. It combines character info, story events, and
        previous chapter summaries.
        
        Args:
            chapter_num: Current chapter number
            include_characters: Whether to include character information
            include_story: Whether to include story/plot information
            include_chapters: Whether to include previous chapter summaries
            max_chars: Maximum characters for context (to avoid token limits)
            
        Returns:
            Formatted context string for injection
        """
        sections = []
        
        # Section 1: Characters
        if include_characters:
            char_context = self._format_character_context(chapter_num)
            if char_context:
                sections.append(char_context)
        
        # Section 2: Story/Plot
        if include_story:
            story_context = self._format_story_context(chapter_num)
            if story_context:
                sections.append(story_context)
        
        # Section 3: Previous Chapters
        if include_chapters:
            chapter_context = self._format_chapter_context(chapter_num)
            if chapter_context:
                sections.append(chapter_context)
        
        # Combine sections
        full_context = "\n\n---\n\n".join(sections)
        
        # Truncate if too long
        if len(full_context) > max_chars:
            full_context = full_context[:max_chars] + "\n\n[Context truncated...]"
        
        return full_context
    
    def _format_character_context(self, chapter_num: int) -> str:
        """Format character information for context injection."""
        lines = ["## CHARACTERS", ""]
        
        # Get characters introduced before or in this chapter
        characters = self.get_characters_introduced_before(chapter_num)
        
        # Prioritize major characters
        major = [c for c in characters if c.importance == "major"]
        supporting = [c for c in characters if c.importance == "supporting"]
        
        if major:
            lines.append("**Major Characters:**")
            for char in major[:5]:  # Limit to 5 major characters
                name_display = f"{char.name}"
                if char.burmese_name:
                    name_display += f" ({char.burmese_name})"
                lines.append(f"- {name_display}: {char.description[:100]}")
                if char.traits:
                    lines.append(f"  Traits: {', '.join(char.traits[:3])}")
            lines.append("")
        
        if supporting:
            lines.append("**Supporting Characters:**")
            for char in supporting[:5]:
                name_display = f"{char.name}"
                if char.burmese_name:
                    name_display += f" ({char.burmese_name})"
                lines.append(f"- {name_display}")
            lines.append("")
        
        return "\n".join(lines) if len(lines) > 3 else ""
    
    def _format_story_context(self, chapter_num: int) -> str:
        """Format story/plot information for context injection."""
        lines = ["## STORY CONTEXT", ""]
        
        # Add main plot if available
        if self.story_metadata.get("main_plot"):
            lines.append(f"**Plot Summary:** {self.story_metadata['main_plot'][:200]}")
            lines.append("")
        
        # Add recent major events
        recent_events = self.get_recent_events(chapter_num, count=3)
        critical_events = [e for e in self.story_events 
                          if e.chapter <= chapter_num and e.importance == "critical"]
        
        if critical_events:
            lines.append("**Key Events So Far:**")
            for evt in critical_events[-3:]:
                lines.append(f"- Ch {evt.chapter}: {evt.title}")
            lines.append("")
        
        if recent_events:
            lines.append("**Recent Events:**")
            for evt in recent_events:
                lines.append(f"- Ch {evt.chapter}: {evt.summary[:100]}")
            lines.append("")
        
        return "\n".join(lines) if len(lines) > 3 else ""
    
    def _format_chapter_context(self, chapter_num: int) -> str:
        """Format previous chapter information for context injection."""
        lines = ["## PREVIOUS CHAPTERS", ""]
        
        # Get summaries of last 2 chapters
        prev_summaries = []
        for i in range(1, 3):
            prev_num = chapter_num - i
            if prev_num in self.chapters:
                ch = self.chapters[prev_num]
                if ch.summary:
                    prev_summaries.insert(0, (prev_num, ch.summary))
        
        if prev_summaries:
            for num, summary in prev_summaries:
                lines.append(f"**Chapter {num}:** {summary[:150]}")
                lines.append("")
        
        return "\n".join(lines) if len(lines) > 3 else ""
    
    # =========================================================================
    # Analysis and Extraction
    # =========================================================================
    
    def analyze_chapter_content(self, chapter_num: int, source_text: str,
                                translated_text: str) -> Dict:
        """
        Analyze chapter content to extract information.
        
        This method should be called after translation to update context
        with information from the new chapter.
        
        Args:
            chapter_num: Chapter number
            source_text: Original source text
            translated_text: Translated text
            
        Returns:
            Dictionary with extracted information
        """
        # Detect new characters (simple heuristic)
        new_chars = []
        for char_name, char in self.characters.items():
            if char.first_appearance == 0 and char_name in source_text:
                char.first_appearance = chapter_num
                new_chars.append(char_name)
        
        # Update chapter info
        if chapter_num in self.chapters:
            ch = self.chapters[chapter_num]
            ch.translation_status = "translated"
            ch.translated_at = datetime.now().isoformat()
            ch.new_characters = new_chars
        
        return {
            "new_characters": new_chars,
            "chapter_num": chapter_num,
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get context statistics."""
        return {
            "novel_name": self.novel_name,
            "source_lang": self.source_lang,
            "total_characters": len(self.characters),
            "major_characters": len(self.get_major_characters()),
            "total_events": len(self.story_events),
            "total_chapters": len(self.chapters),
            "translated_chapters": sum(1 for ch in self.chapters.values() 
                                      if ch.translation_status == "translated"),
            "context_dir": str(self.context_dir),
        }
    
    def print_summary(self):
        """Print context summary to console."""
        stats = self.get_stats()
        print("┌─────────────────────────────────────────┐")
        print("│ Context Summary                         │")
        print(f"│ Novel: {stats['novel_name']:<33} │")
        print(f"│ Language: {stats['source_lang']:<30} │")
        print(f"│ Characters: {stats['total_characters']:<28} │")
        print(f"│   Major: {stats['major_characters']:<31} │")
        print(f"│ Story Events: {stats['total_events']:<25} │")
        print(f"│ Chapters: {stats['translated_chapters']}/{stats['total_chapters']:<24} │")
        print("└─────────────────────────────────────────┘")


def get_context_for_novel(novel_name: str, source_lang: str = "English") -> ContextManager:
    """
    Factory function to get context manager for a novel.
    
    Args:
        novel_name: Name of the novel
        source_lang: Source language
        
    Returns:
        ContextManager instance
    """
    return ContextManager(novel_name, source_lang)


# ============================================================================
# CLI Interface
# ============================================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python context_manager.py <novel_name> [command]")
        print("Commands:")
        print("  stats             - Show context statistics")
        print("  characters        - List all characters")
        print("  events            - List all story events")
        print("  chapters          - List all chapters")
        print("  context <num>     - Show context for chapter <num>")
        print("  add-char <name>   - Add a character (interactive)")
        print("")
        print("Available context directories:")
        if CONTEXT_DIR.exists():
            for d in sorted(CONTEXT_DIR.iterdir()):
                if d.is_dir():
                    print(f"  - {d.name}")
        sys.exit(1)
    
    novel_name = sys.argv[1]
    command = sys.argv[2] if len(sys.argv) > 2 else "stats"
    
    context = ContextManager(novel_name)
    
    if command == "stats":
        context.print_summary()
    
    elif command == "characters":
        if context.characters:
            print(f"\nCharacters in {novel_name}:")
            for name, char in sorted(context.characters.items()):
                status = "✓" if char.burmese_name else "?"
                print(f"  [{status}] {name} -> {char.burmese_name or 'Not translated'}")
                print(f"       Importance: {char.importance}, First: Ch {char.first_appearance}")
        else:
            print(f"No characters registered for {novel_name}")
    
    elif command == "events":
        if context.story_events:
            print(f"\nStory events in {novel_name}:")
            for evt in context.story_events:
                print(f"  Ch {evt.chapter}: {evt.title} [{evt.importance}]")
                print(f"       {evt.summary[:80]}...")
        else:
            print(f"No story events registered for {novel_name}")
    
    elif command == "chapters":
        if context.chapters:
            print(f"\nChapters in {novel_name}:")
            for num in sorted(context.chapters.keys()):
                ch = context.chapters[num]
                status = "✓" if ch.translation_status == "translated" else "○"
                print(f"  [{status}] Ch {num}: {ch.title or 'Untitled'}")
        else:
            print(f"No chapters registered for {novel_name}")
    
    elif command == "context" and len(sys.argv) > 3:
        chapter_num = int(sys.argv[3])
        ctx_text = context.get_context_for_chapter(chapter_num)
        print(f"\nContext for Chapter {chapter_num}:")
        print("=" * 60)
        print(ctx_text)
        print("=" * 60)
    
    elif command == "add-char" and len(sys.argv) > 3:
        name = sys.argv[3]
        context.add_character(name, importance="supporting", first_appearance=1)
        context.save()
        print(f"✓ Added character: {name}")
    
    else:
        print(f"Unknown command: {command}")
        print("Run without arguments for usage help.")
