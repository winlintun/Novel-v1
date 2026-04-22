#!/usr/bin/env python3
"""
Unified Resource Manager - Single Entry Point for All Novel Resources

This module consolidates all resource management into one unified interface:
- GlossaryManager: Character names, places, terminology
- ContextManager: Character details, story events, chapter summaries
- NameConverter: Auto-learning, phonetic conversion, name suggestions
- CultivationTerms: Built-in cultivation dictionary + custom terms

Usage:
    from scripts.resource_manager import ResourceManager
    
    # Initialize for a novel (loads all resources automatically)
    resources = ResourceManager("novel_name", source_lang="English")
    
    # Get all resources for translation
    glossary_text = resources.get_glossary_text()
    context_text = resources.get_context_for_chapter(5)
    
    # Add new names/terms (syncs across all systems)
    resources.add_character("Li Wei", "လီဝေ့", importance="major")
    resources.add_cultivation_term("Golden Core", "ရွှေအနှောင်း")
    
    # Auto-learn from chapter
    resources.learn_from_chapter(chapter_text, translated_text)
    
    # Save all changes
    resources.save_all()
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime

# Import existing managers
try:
    from scripts.glossary_manager import GlossaryManager
    from scripts.context_manager import ContextManager, Character, StoryEvent
    from scripts.name_converter import NameConverter, NameEntry, CULTIVATION_TERMS
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from scripts.glossary_manager import GlossaryManager
    from scripts.context_manager import ContextManager, Character, StoryEvent
    from scripts.name_converter import NameConverter, NameEntry, CULTIVATION_TERMS


@dataclass
class CultivationTerm:
    """Represents a cultivation term with metadata."""
    source_term: str  # Original Chinese/English term
    myanmar_term: str  # Burmese translation
    category: str  # realm, title, technique, item, place, organization
    description: str = ""  # Optional description
    first_seen: int = 0  # Chapter where first seen
    usage_count: int = 0
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'CultivationTerm':
        return cls(**data)


@dataclass
class TitleTerm:
    """Represents a title/honorific term."""
    source_title: str
    myanmar_title: str
    gender: str = "neutral"  # male, female, neutral
    formality: str = "formal"  # formal, informal, honorific
    usage_context: str = "general"  # general, sect, imperial, family
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'TitleTerm':
        return cls(**data)


class ResourceManager:
    """
    Unified resource manager that consolidates glossary, context, name converter,
    cultivation terms, and titles into a single interface.
    
    This class ensures all resources stay synchronized and provides:
    - Single entry point for all resource operations
    - Automatic syncing between glossary and context
    - Unified save/load operations
    - Comprehensive resource queries
    """
    
    def __init__(self, novel_name: str, source_lang: str = "English", 
                 auto_create: bool = True, load_all: bool = True):
        """
        Initialize the unified resource manager.
        
        Args:
            novel_name: Name of the novel (used for all file paths)
            source_lang: Source language (Chinese, English, etc.)
            auto_create: Create resource files if they don't exist
            load_all: Load all resources on initialization
        """
        self.novel_name = novel_name
        self.source_lang = source_lang
        
        # Initialize all component managers
        self._glossary: Optional[GlossaryManager] = None
        self._context: Optional[ContextManager] = None
        self._name_converter: Optional[NameConverter] = None
        
        # Additional resource stores
        self.cultivation_terms: Dict[str, CultivationTerm] = {}
        self.custom_terms: Dict[str, str] = {}  # Source -> Myanmar
        self.title_terms: Dict[str, TitleTerm] = {}
        
        # Resource directories
        self.resources_dir = Path("resources") / novel_name
        self.resources_dir.mkdir(parents=True, exist_ok=True)
        
        # File paths for additional resources
        self.cultivation_file = self.resources_dir / "cultivation_terms.json"
        self.titles_file = self.resources_dir / "titles.json"
        self.custom_terms_file = self.resources_dir / "custom_terms.json"
        
        # Load all resources if requested
        if load_all:
            self._load_all_resources(auto_create)
    
    def _load_all_resources(self, auto_create: bool = True):
        """Load all resource components."""
        # Load glossary manager
        self._glossary = GlossaryManager(self.novel_name, auto_create=auto_create)
        
        # Load context manager
        self._context = ContextManager(self.novel_name, self.source_lang, auto_create=auto_create)
        
        # Load name converter (will sync glossary and context)
        self._name_converter = NameConverter(self.novel_name, self.source_lang)
        
        # Load additional resources
        self._load_cultivation_terms()
        self._load_title_terms()
        self._load_custom_terms()
    
    # ========================================================================
    # Property Accessors for Component Managers
    # ========================================================================
    
    @property
    def glossary(self) -> GlossaryManager:
        """Get the glossary manager."""
        if self._glossary is None:
            self._glossary = GlossaryManager(self.novel_name, auto_create=True)
        return self._glossary
    
    @property
    def context(self) -> ContextManager:
        """Get the context manager."""
        if self._context is None:
            self._context = ContextManager(self.novel_name, self.source_lang, auto_create=True)
        return self._context
    
    @property
    def name_converter(self) -> NameConverter:
        """Get the name converter."""
        if self._name_converter is None:
            self._name_converter = NameConverter(self.novel_name, self.source_lang)
        return self._name_converter
    
    # ========================================================================
    # Resource Loading/Saving
    # ========================================================================
    
    def _load_cultivation_terms(self):
        """Load cultivation terms from file or initialize with defaults."""
        if self.cultivation_file.exists():
            try:
                with open(self.cultivation_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for term_data in data.get("terms", []):
                        term = CultivationTerm.from_dict(term_data)
                        self.cultivation_terms[term.source_term] = term
            except Exception as e:
                print(f"⚠ Warning: Could not load cultivation terms: {e}")
        
        # Merge with built-in terms (built-ins are defaults)
        for source, myanmar in CULTIVATION_TERMS.items():
            if source not in self.cultivation_terms:
                # Determine category from content
                category = self._determine_term_category(source)
                self.cultivation_terms[source] = CultivationTerm(
                    source_term=source,
                    myanmar_term=myanmar,
                    category=category
                )
    
    def _load_title_terms(self):
        """Load title terms from file."""
        if self.titles_file.exists():
            try:
                with open(self.titles_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for title_data in data.get("titles", []):
                        title = TitleTerm.from_dict(title_data)
                        self.title_terms[title.source_title] = title
            except Exception as e:
                print(f"⚠ Warning: Could not load title terms: {e}")
    
    def _load_custom_terms(self):
        """Load custom terms from file."""
        if self.custom_terms_file.exists():
            try:
                with open(self.custom_terms_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.custom_terms = data.get("terms", {})
            except Exception as e:
                print(f"⚠ Warning: Could not load custom terms: {e}")
    
    def save_all(self) -> bool:
        """
        Save all resources to their respective files.
        
        Returns:
            True if all saves successful, False otherwise
        """
        success = True
        
        # Save component managers
        try:
            if self._glossary:
                self._glossary.save()
        except Exception as e:
            print(f"✗ Error saving glossary: {e}")
            success = False
        
        try:
            if self._context:
                self.context.save()
        except Exception as e:
            print(f"✗ Error saving context: {e}")
            success = False
        
        # Save additional resources
        try:
            self._save_cultivation_terms()
        except Exception as e:
            print(f"✗ Error saving cultivation terms: {e}")
            success = False
        
        try:
            self._save_title_terms()
        except Exception as e:
            print(f"✗ Error saving title terms: {e}")
            success = False
        
        try:
            self._save_custom_terms()
        except Exception as e:
            print(f"✗ Error saving custom terms: {e}")
            success = False
        
        return success
    
    def _save_cultivation_terms(self):
        """Save cultivation terms to file."""
        data = {
            "novel_name": self.novel_name,
            "updated_at": datetime.now().isoformat(),
            "terms": [term.to_dict() for term in self.cultivation_terms.values()]
        }
        with open(self.cultivation_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _save_title_terms(self):
        """Save title terms to file."""
        data = {
            "novel_name": self.novel_name,
            "updated_at": datetime.now().isoformat(),
            "titles": [title.to_dict() for title in self.title_terms.values()]
        }
        with open(self.titles_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _save_custom_terms(self):
        """Save custom terms to file."""
        data = {
            "novel_name": self.novel_name,
            "updated_at": datetime.now().isoformat(),
            "terms": self.custom_terms
        }
        with open(self.custom_terms_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    # ========================================================================
    # Character Management
    # ========================================================================
    
    def add_character(self, name: str, myanmar_name: str, 
                      importance: str = "supporting",
                      description: str = "",
                      aliases: List[str] = None,
                      first_appearance: int = 0,
                      traits: List[str] = None,
                      auto_sync: bool = True) -> bool:
        """
        Add a character to all resource systems.
        
        Args:
            name: Original character name
            myanmar_name: Burmese translation
            importance: Character importance (major, supporting, minor)
            description: Physical/character description
            aliases: Alternative names
            first_appearance: Chapter number of first appearance
            traits: Character traits list
            auto_sync: Sync to all systems automatically
            
        Returns:
            True if added successfully
        """
        # Add to glossary (for translation consistency)
        self.glossary.add_name(name, myanmar_name, source_chapter=first_appearance)
        
        # Add to context (for context injection)
        self.context.add_character(
            name=name,
            burmese_name=myanmar_name,
            description=description,
            aliases=aliases or [],
            first_appearance=first_appearance,
            importance=importance,
            traits=traits or []
        )
        
        # Add to name converter
        self.name_converter.add_name(name, myanmar_name, "character")
        
        if auto_sync:
            self.glossary.save()
            self.context.save()
        
        return True
    
    def get_character(self, name: str) -> Optional[Dict]:
        """
        Get comprehensive character info from all systems.
        
        Returns:
            Dictionary with combined character information
        """
        # Get from context
        char = self.context.get_character(name)
        
        # Get from glossary
        glossary_name = self.glossary.get_name(name)
        
        if char or glossary_name:
            return {
                "name": name,
                "myanmar_name": char.burmese_name if char else glossary_name,
                "description": char.description if char else "",
                "importance": char.importance if char else "unknown",
                "first_appearance": char.first_appearance if char else 0,
                "aliases": char.aliases if char else [],
                "traits": char.traits if char else [],
                "in_glossary": name in self.glossary.names,
                "in_context": name in self.context.characters
            }
        return None
    
    def get_all_characters(self) -> List[Dict]:
        """Get all characters with comprehensive info."""
        characters = []
        
        # Combine glossary and context
        all_names = set(self.glossary.names.keys()) | set(self.context.characters.keys())
        
        for name in all_names:
            char_info = self.get_character(name)
            if char_info:
                characters.append(char_info)
        
        return sorted(characters, key=lambda x: x["name"])
    
    # ========================================================================
    # Cultivation Terms Management
    # ========================================================================
    
    def add_cultivation_term(self, source_term: str, myanmar_term: str,
                            category: str = "", description: str = "",
                            first_seen: int = 0) -> bool:
        """
        Add a cultivation term.
        
        Args:
            source_term: Original term (English/Chinese)
            myanmar_term: Burmese translation
            category: realm, title, technique, item, place, organization
            description: Optional description
            first_seen: Chapter where first seen
        """
        if not category:
            category = self._determine_term_category(source_term)
        
        term = CultivationTerm(
            source_term=source_term,
            myanmar_term=myanmar_term,
            category=category,
            description=description,
            first_seen=first_seen
        )
        
        self.cultivation_terms[source_term] = term
        
        # Also add to glossary for translation consistency
        self.glossary.add_name(source_term, myanmar_term, source_chapter=first_seen)
        
        return True
    
    def get_cultivation_term(self, source_term: str) -> Optional[CultivationTerm]:
        """Get a cultivation term by source name."""
        return self.cultivation_terms.get(source_term)
    
    def get_cultivation_terms_by_category(self, category: str) -> List[CultivationTerm]:
        """Get all cultivation terms in a category."""
        return [term for term in self.cultivation_terms.values() if term.category == category]
    
    def get_cultivation_text(self) -> str:
        """
        Get formatted cultivation terms for prompt injection.
        
        Returns:
            Formatted text with all cultivation terms organized by category
        """
        if not self.cultivation_terms:
            return ""
        
        lines = ["\n## CULTIVATION TERMINOLOGY", ""]
        
        # Group by category
        categories = {}
        for term in self.cultivation_terms.values():
            cat = term.category
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(term)
        
        # Format each category
        category_order = ["realm", "title", "technique", "item", "place", "organization"]
        category_names = {
            "realm": "Cultivation Realms",
            "title": "Titles & Honorifics",
            "technique": "Techniques & Skills",
            "item": "Items & Treasures",
            "place": "Places & Locations",
            "organization": "Sects & Organizations"
        }
        
        for cat in category_order:
            if cat in categories:
                lines.append(f"**{category_names.get(cat, cat)}:**")
                for term in sorted(categories[cat], key=lambda x: x.source_term):
                    lines.append(f'- "{term.source_term}" → "{term.myanmar_term}"')
                lines.append("")
        
        return "\n".join(lines)
    
    def _determine_term_category(self, term: str) -> str:
        """Determine the category of a term based on keywords."""
        term_lower = term.lower()
        
        # Realms
        realm_keywords = ['stage', 'realm', 'level', 'qi', 'core', 'soul', 'immortal', 
                         'refining', 'foundation', 'tribulation', '炼气', '筑基', '金丹']
        if any(kw in term_lower for kw in realm_keywords):
            return "realm"
        
        # Titles
        title_keywords = ['master', 'elder', 'sect leader', 'patriarch', 'prince', 'princess',
                         'emperor', 'king', 'queen', 'lord', 'saint', '长老', '掌门', '公子', '小姐']
        if any(kw in term_lower for kw in title_keywords):
            return "title"
        
        # Techniques
        technique_keywords = ['technique', 'method', 'art', 'palm', 'fist', 'sword', 'blade',
                             'manual', '功法', '秘籍', '掌法', '剑法']
        if any(kw in term_lower for kw in technique_keywords):
            return "technique"
        
        # Items
        item_keywords = ['stone', 'treasure', 'ring', 'bag', 'pill', 'elixir', 'herb',
                        'sword', 'weapon', 'stone', '石', '法宝', '丹药']
        if any(kw in term_lower for kw in item_keywords):
            return "item"
        
        # Places
        place_keywords = ['sect', 'school', 'palace', 'valley', 'peak', 'mountain', 'city',
                         'kingdom', 'empire', 'realm', '宗', '山', '谷', '城']
        if any(kw in term_lower for kw in place_keywords):
            return "place"
        
        # Organizations
        org_keywords = ['sect', 'school', 'palace', 'hall', 'union', 'alliance', 'school',
                       '宗门', '学院', '宫', '殿']
        if any(kw in term_lower for kw in org_keywords):
            return "organization"
        
        return "general"
    
    # ========================================================================
    # Title Management
    # ========================================================================
    
    def add_title(self, source_title: str, myanmar_name: str,
                  gender: str = "neutral", formality: str = "formal",
                  usage_context: str = "general") -> bool:
        """
        Add a title/honorific term.
        
        Args:
            source_title: Original title (e.g., "Young Master")
            myanmar_title: Burmese translation
            gender: male, female, neutral
            formality: formal, informal, honorific
            usage_context: general, sect, imperial, family
        """
        title = TitleTerm(
            source_title=source_title,
            myanmar_title=myanmar_name,
            gender=gender,
            formality=formality,
            usage_context=usage_context
        )
        
        self.title_terms[source_title] = title
        
        # Also add to glossary
        self.glossary.add_name(source_title, myanmar_name)
        
        return True
    
    def get_title(self, source_title: str) -> Optional[TitleTerm]:
        """Get a title by source name."""
        return self.title_terms.get(source_title)
    
    def get_titles_text(self) -> str:
        """Get formatted titles for prompt injection."""
        if not self.title_terms:
            return ""
        
        lines = ["\n## TITLES & HONORIFICS", ""]
        
        for title in sorted(self.title_terms.values(), key=lambda x: x.source_title):
            lines.append(f'- "{title.source_title}" → "{title.myanmar_title}" ({title.formality})')
        
        return "\n".join(lines)
    
    # ========================================================================
    # Custom Terms Management
    # ========================================================================
    
    def add_custom_term(self, source: str, myanmar: str, 
                        source_chapter: int = None) -> bool:
        """Add a custom term to the glossary."""
        self.custom_terms[source] = myanmar
        self.glossary.add_name(source, myanmar, source_chapter=source_chapter)
        return True
    
    def get_custom_term(self, source: str) -> Optional[str]:
        """Get custom term translation."""
        return self.custom_terms.get(source)
    
    # ========================================================================
    # Context Management
    # ========================================================================
    
    def get_context_for_chapter(self, chapter_num: int, max_chars: int = 3000) -> str:
        """
        Get full context for a chapter translation.
        
        Combines character info, story context, previous chapters, and terms.
        
        Args:
            chapter_num: Current chapter number
            max_chars: Maximum characters for context
            
        Returns:
            Formatted context string
        """
        sections = []
        
        # Get base context from context manager
        base_context = self.context.get_context_for_chapter(chapter_num, max_chars=max_chars)
        if base_context:
            sections.append(base_context)
        
        # Add cultivation terms if available
        cultivation_text = self.get_cultivation_text()
        if cultivation_text:
            sections.append(cultivation_text)
        
        # Add titles if available
        titles_text = self.get_titles_text()
        if titles_text:
            sections.append(titles_text)
        
        # Combine all sections
        full_context = "\n\n---\n\n".join(sections)
        
        # Truncate if too long
        if len(full_context) > max_chars:
            full_context = full_context[:max_chars] + "\n\n[Context truncated...]"
        
        return full_context
    
    def get_glossary_text(self) -> str:
        """
        Get complete glossary text including names, terms, and cultivation terminology.
        
        Returns:
            Formatted glossary for system prompt
        """
        parts = []
        
        # Base glossary from glossary manager
        base_glossary = self.glossary.get_glossary_text()
        if base_glossary:
            parts.append(base_glossary)
        
        # Cultivation terms
        cultivation = self.get_cultivation_text()
        if cultivation:
            parts.append(cultivation)
        
        # Titles
        titles = self.get_titles_text()
        if titles:
            parts.append(titles)
        
        # Custom terms
        if self.custom_terms:
            lines = ["\n## CUSTOM TERMS", ""]
            for source, myanmar in sorted(self.custom_terms.items()):
                lines.append(f'- "{source}" → "{myanmar}"')
            parts.append("\n".join(lines))
        
        return "\n".join(parts) if parts else ""
    
    # ========================================================================
    # Auto-Learning
    # ========================================================================
    
    def learn_from_chapter(self, source_text: str, translated_text: str,
                           chapter_num: int = 0) -> Dict[str, Any]:
        """
        Auto-learn new names and terms from a chapter.
        
        Args:
            source_text: Original source text
            translated_text: Translated text
            chapter_num: Chapter number
            
        Returns:
            Dictionary with learned items
        """
        learned = {
            "characters": [],
            "terms": [],
            "potential_names": []
        }
        
        # Use name converter to extract potential names
        potential = self.name_converter.extract_potential_names(source_text)
        
        for name, ntype in potential:
            if name not in self.glossary.names and name not in self.context.characters:
                # New potential name
                learned["potential_names"].append({
                    "name": name,
                    "type": ntype,
                    "suggested_myanmar": self.name_converter.suggest_myanmar_name(name, ntype)
                })
        
        # Try to extract actual mappings from parallel text
        # This is a simplified heuristic - more sophisticated approaches could be used
        for name, ntype in potential[:20]:  # Limit to first 20
            if name in source_text and name not in translated_text:
                # Name was likely translated - try to find Myanmar equivalent
                # Look for Myanmar words that appear in similar positions
                myanmar_words = re.findall(r'[\u1000-\u109F]+', translated_text)
                if myanmar_words:
                    # Heuristic: Use a Myanmar word that might correspond
                    # In practice, this would need AI assistance for accuracy
                    pass
        
        return learned
    
    # ========================================================================
    # Sync Operations
    # ========================================================================
    
    def sync_all(self) -> Dict[str, int]:
        """
        Synchronize all resource systems.
        
        Ensures glossary, context, and name converter are all in sync.
        
        Returns:
            Dictionary with sync statistics
        """
        stats = {
            "glossary_to_context": 0,
            "context_to_glossary": 0,
            "terms_added": 0
        }
        
        # Sync glossary to context
        for source, myanmar in self.glossary.names.items():
            char = self.context.get_character(source)
            if char:
                if char.burmese_name != myanmar:
                    char.burmese_name = myanmar
                    stats["glossary_to_context"] += 1
            else:
                self.context.add_character(
                    name=source,
                    burmese_name=myanmar,
                    first_appearance=1,
                    importance="supporting"
                )
                stats["glossary_to_context"] += 1
        
        # Sync context to glossary
        for char_name, char in self.context.characters.items():
            if char.burmese_name and char_name not in self.glossary.names:
                self.glossary.add_name(char_name, char.burmese_name)
                stats["context_to_glossary"] += 1
        
        # Sync cultivation terms to glossary
        for term in self.cultivation_terms.values():
            if term.source_term not in self.glossary.names:
                self.glossary.add_name(term.source_term, term.myanmar_term)
                stats["terms_added"] += 1
        
        # Save all changes
        self.save_all()
        
        return stats
    
    # ========================================================================
    # Statistics and Summary
    # ========================================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive resource statistics."""
        return {
            "novel_name": self.novel_name,
            "source_language": self.source_lang,
            "characters": {
                "total": len(self.glossary.names),
                "in_context": len(self.context.characters),
                "major": len(self.context.get_major_characters())
            },
            "cultivation_terms": {
                "total": len(self.cultivation_terms),
                "by_category": {
                    cat: len(self.get_cultivation_terms_by_category(cat))
                    for cat in ["realm", "title", "technique", "item", "place", "organization"]
                }
            },
            "titles": len(self.title_terms),
            "custom_terms": len(self.custom_terms),
            "chapters": {
                "total": len(self.context.chapters),
                "translated": sum(1 for ch in self.context.chapters.values() 
                                 if ch.translation_status == "translated")
            },
            "story_events": len(self.context.story_events)
        }
    
    def print_summary(self):
        """Print comprehensive resource summary."""
        stats = self.get_stats()
        
        print("=" * 60)
        print("RESOURCE MANAGER SUMMARY")
        print("=" * 60)
        print(f"Novel: {stats['novel_name']}")
        print(f"Source Language: {stats['source_language']}")
        print()
        print("CHARACTERS:")
        print(f"  Total in Glossary: {stats['characters']['total']}")
        print(f"  In Context: {stats['characters']['in_context']}")
        print(f"  Major Characters: {stats['characters']['major']}")
        print()
        print("CULTIVATION TERMS:")
        print(f"  Total: {stats['cultivation_terms']['total']}")
        for cat, count in stats['cultivation_terms']['by_category'].items():
            if count > 0:
                print(f"    {cat}: {count}")
        print()
        print(f"TITLES: {stats['titles']}")
        print(f"CUSTOM TERMS: {stats['custom_terms']}")
        print()
        print("CHAPTERS:")
        print(f"  Total: {stats['chapters']['total']}")
        print(f"  Translated: {stats['chapters']['translated']}")
        print(f"STORY EVENTS: {stats['story_events']}")
        print("=" * 60)


# =============================================================================
# CLI Interface
# =============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Unified Resource Manager for Novel Translation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Show resource summary
  python scripts/resource_manager.py --novel dao-equaling-the-heavens
  
  # Add a character
  python scripts/resource_manager.py --novel dao-equaling-the-heavens \\
      --add-character "Li Wei" "လီဝေ့" --importance major
  
  # Add a cultivation term
  python scripts/resource_manager.py --novel dao-equaling-the-heavens \\
      --add-term "Golden Core" "ရွှေအနှောင်း" --category realm
  
  # Sync all resources
  python scripts/resource_manager.py --novel dao-equaling-the-heavens --sync
  
  # Export all resources
  python scripts/resource_manager.py --novel dao-equaling-the-heavens \\
      --export resources_export.json
        """
    )
    
    parser.add_argument("--novel", required=True, help="Novel name")
    parser.add_argument("--source-lang", default="English", help="Source language")
    parser.add_argument("--summary", action="store_true", help="Show resource summary")
    
    # Character commands
    parser.add_argument("--add-character", nargs=2, metavar=("NAME", "MYANMAR"),
                       help="Add a character (source name, Myanmar name)")
    parser.add_argument("--importance", default="supporting",
                       choices=["major", "supporting", "minor"],
                       help="Character importance")
    parser.add_argument("--description", default="", help="Character description")
    parser.add_argument("--first-appearance", type=int, default=0,
                       help="Chapter of first appearance")
    
    # Term commands
    parser.add_argument("--add-term", nargs=2, metavar=("TERM", "MYANMAR"),
                       help="Add a cultivation term")
    parser.add_argument("--category", default="",
                       help="Term category (realm, title, technique, item, place)")
    
    # Title commands
    parser.add_argument("--add-title", nargs=2, metavar=("TITLE", "MYANMAR"),
                       help="Add a title")
    
    # Management commands
    parser.add_argument("--sync", action="store_true", help="Sync all resources")
    parser.add_argument("--save", action="store_true", help="Save all resources")
    parser.add_argument("--export", help="Export all resources to JSON file")
    parser.add_argument("--import-file", help="Import resources from JSON file")
    parser.add_argument("--learn-from", help="Learn from chapter file")
    
    args = parser.parse_args()
    
    # Initialize resource manager
    resources = ResourceManager(args.novel, args.source_lang)
    
    # Execute commands
    if args.summary or not any([
        args.add_character, args.add_term, args.add_title,
        args.sync, args.save, args.export, args.import_file, args.learn_from
    ]):
        resources.print_summary()
    
    if args.add_character:
        name, myanmar = args.add_character
        resources.add_character(
            name=name,
            myanmar_name=myanmar,
            importance=args.importance,
            description=args.description,
            first_appearance=args.first_appearance
        )
        print(f"✓ Added character: {name} → {myanmar}")
    
    if args.add_term:
        term, myanmar = args.add_term
        resources.add_cultivation_term(
            source_term=term,
            myanmar_term=myanmar,
            category=args.category
        )
        print(f"✓ Added term: {term} → {myanmar}")
    
    if args.add_title:
        title, myanmar = args.add_title
        resources.add_title(title, myanmar)
        print(f"✓ Added title: {title} → {myanmar}")
    
    if args.sync:
        stats = resources.sync_all()
        print("✓ Sync complete:")
        print(f"  Glossary → Context: {stats['glossary_to_context']}")
        print(f"  Context → Glossary: {stats['context_to_glossary']}")
        print(f"  Terms added: {stats['terms_added']}")
    
    if args.save or args.add_character or args.add_term or args.add_title:
        resources.save_all()
        print("✓ All resources saved")
    
    if args.export:
        data = {
            "novel_name": args.novel,
            "source_language": args.source_lang,
            "exported_at": datetime.now().isoformat(),
            "characters": resources.get_all_characters(),
            "cultivation_terms": [t.to_dict() for t in resources.cultivation_terms.values()],
            "titles": [t.to_dict() for t in resources.title_terms.values()],
            "custom_terms": resources.custom_terms,
            "stats": resources.get_stats()
        }
        with open(args.export, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✓ Exported to {args.export}")
    
    if args.import_file:
        with open(args.import_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Import characters
        for char_data in data.get("characters", []):
            resources.add_character(
                name=char_data["name"],
                myanmar_name=char_data.get("myanmar_name", ""),
                importance=char_data.get("importance", "supporting"),
                description=char_data.get("description", ""),
                first_appearance=char_data.get("first_appearance", 0)
            )
        
        # Import terms
        for term_data in data.get("cultivation_terms", []):
            resources.add_cultivation_term(
                source_term=term_data["source_term"],
                myanmar_term=term_data["myanmar_term"],
                category=term_data.get("category", "general"),
                description=term_data.get("description", "")
            )
        
        resources.save_all()
        print(f"✓ Imported from {args.import_file}")
    
    if args.learn_from:
        from pathlib import Path
        path = Path(args.learn_from)
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                text = f.read()
            learned = resources.learn_from_chapter(text, "")
            print(f"✓ Learned from {path.name}:")
            print(f"  Potential names: {len(learned['potential_names'])}")
            for item in learned['potential_names'][:5]:
                print(f"    - {item['name']} → {item['suggested_myanmar']}")
        else:
            print(f"✗ File not found: {args.learn_from}")


if __name__ == "__main__":
    main()
