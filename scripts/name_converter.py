#!/usr/bin/env python3
"""
Name Converter - Chinese/English to Myanmar Auto-Learning System

This script provides intelligent name conversion with auto-learning capabilities.
It syncs between glossaries/ and context/ directories for consistency.

Features:
- Load existing names from glossaries and context
- Auto-extract new names from source text
- AI-assisted name translation
- Batch conversion with consistency checks
- Sync between glossary and context systems

Usage:
    # Interactive mode
    python scripts/name_converter.py
    
    # Auto-learn from chapter
    python scripts/name_converter.py --novel dao-equaling-the-heavens --learn-from english_chapters/dao-equaling-the-heavens/chapter_001.md
    
    # Convert names in a file
    python scripts/name_converter.py --novel dao-equaling-the-heavens --convert-file input.txt --output output.txt
    
    # Sync glossaries with context
    python scripts/name_converter.py --novel dao-equaling-the-heavens --sync
"""

import re
import json
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, asdict
from datetime import datetime

# Import project modules
try:
    from scripts.glossary_manager import GlossaryManager
    from scripts.context_manager import ContextManager
except ImportError:
    # Handle running as standalone script
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from scripts.glossary_manager import GlossaryManager
    from scripts.context_manager import ContextManager


@dataclass
class NameEntry:
    """Represents a name mapping with metadata."""
    source_name: str  # Original Chinese/English name
    myanmar_name: str  # Burmese translation
    source_type: str  # character, place, technique, item, etc.
    first_seen: str  # Where first encountered
    confidence: float = 1.0  # Confidence score (0.0-1.0)
    usage_count: int = 0  # How many times seen
    aliases: List[str] = None  # Alternative names
    
    def __post_init__(self):
        if self.aliases is None:
            self.aliases = []
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'NameEntry':
        return cls(**data)


class NameConverter:
    """
    Intelligent name converter with auto-learning capabilities.
    
    Manages the relationship between:
    - glossaries/{novel}.json (primary name storage for translation)
    - context/{novel}/characters.json (character details for context injection)
    - context/{novel}/story.json (story events)
    """
    
    def __init__(self, novel_name: str, source_lang: str = "English"):
        self.novel_name = novel_name
        self.source_lang = source_lang
        
        # Initialize managers
        self.glossary = GlossaryManager(novel_name, auto_create=True)
        self.context = ContextManager(novel_name, source_lang=source_lang)
        
        # In-memory name database (merged from all sources)
        self.names: Dict[str, NameEntry] = {}
        
        # Load all existing names
        self._load_all_names()
    
    def _load_all_names(self):
        """Load names from both glossaries and context."""
        # 1. Load from glossary (primary source)
        for source, myanmar in self.glossary.names.items():
            if source not in self.names:
                self.names[source] = NameEntry(
                    source_name=source,
                    myanmar_name=myanmar,
                    source_type="character",  # Default assumption
                    first_seen="glossary",
                    confidence=1.0
                )
        
        # 2. Load from context characters
        for char_name, char in self.context.characters.items():
            if char_name not in self.names:
                self.names[char_name] = NameEntry(
                    source_name=char_name,
                    myanmar_name=char.burmese_name or "",
                    source_type="character",
                    first_seen=f"context_ch{char.first_appearance}",
                    confidence=0.9,
                    aliases=char.aliases
                )
            else:
                # Merge aliases
                if char.aliases:
                    self.names[char_name].aliases.extend(char.aliases)
                    self.names[char_name].aliases = list(set(self.names[char_name].aliases))
    
    def extract_potential_names(self, text: str) -> List[Tuple[str, str]]:
        """
        Extract potential names from source text.
        
        Returns list of (name, type) tuples.
        """
        potential_names = []
        
        if self.source_lang.lower() == "chinese":
            # Chinese name patterns
            # Pattern 1: Common Chinese names (2-4 characters)
            chinese_names = re.findall(r'[\u4e00-\u9fa5]{2,4}', text)
            for name in chinese_names:
                if self._looks_like_chinese_name(name):
                    potential_names.append((name, "character"))
            
            # Pattern 2: Places with common suffixes
            place_pattern = r'([\u4e00-\u9fa5]{2,5})(?:山|城|国|府|谷|岛|门|教|派|宫)'
            places = re.findall(place_pattern, text)
            for place in places:
                potential_names.append((place, "place"))
                
        else:  # English
            # English name patterns
            # Pattern 1: Capitalized words that appear multiple times
            words = re.findall(r'\b[A-Z][a-z]+\b', text)
            from collections import Counter
            word_counts = Counter(words)
            
            for word, count in word_counts.items():
                if count >= 3 and len(word) >= 3:
                    # Could be a name
                    if word not in ['The', 'And', 'But', 'For', 'With', 'From', 'This', 'That']:
                        potential_names.append((word, "potential_name"))
            
            # Pattern 2: Multi-word names (e.g., "Dragon Bridge", "Vermilion Bird Gate")
            multi_word = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}\b', text)
            for name in multi_word:
                if name not in ['The', 'And', 'But', 'For', 'With']:
                    potential_names.append((name, "place_or_title"))
        
        # Remove duplicates while preserving order
        seen = set()
        unique_names = []
        for name, ntype in potential_names:
            if name not in seen and name not in self.names:
                seen.add(name)
                unique_names.append((name, ntype))
        
        return unique_names[:50]  # Limit to 50 candidates
    
    def _looks_like_chinese_name(self, text: str) -> bool:
        """Heuristic to check if text looks like a Chinese name."""
        # Common Chinese name indicators
        common_surnames = ['李', '王', '张', '刘', '陈', '杨', '赵', '黄', '周', '吴', 
                          '徐', '孙', '胡', '朱', '高', '林', '何', '郭', '马', '罗',
                          '魏', '古', '孟', '孙', '云', '风', '雷', '电', '龙', '凤']
        
        # Check if starts with common surname
        if any(text.startswith(surname) for surname in common_surnames):
            return True
        
        # Check if appears in cultivation/xianxia contexts
        cultivation_indicators = ['仙', '魔', '道', '神', '帝', '皇', '尊', '圣', '王', '主']
        if any(ind in text for ind in cultivation_indicators):
            return True
        
        return False
    
    def suggest_myanmar_name(self, source_name: str, source_type: str = "character") -> str:
        """
        Suggest a Myanmar name based on phonetic/semantic translation.
        
        This is a simple rule-based suggestion. For production, 
        this could call an AI API for better suggestions.
        """
        # Check if already exists
        if source_name in self.names:
            return self.names[source_name].myanmar_name
        
        # Phonetic approximation rules for common patterns
        phonetic_map = {
            # Common English sounds
            'Gu': 'ဂူ', 'Wen': 'ဝမ်', 'Wang': 'ဝမ်', 'Wei': 'ဝေ့',
            'Lan': 'လန်', 'Li': 'လီ', 'Zhang': 'ကျANNEL', 'Liu': 'လျို',
            'Chen': 'ချင်း', 'Yang': 'ယန်', 'Zhao': 'ကျော', 'Huang': 'ခွမ်',
            'Zhou': 'ကျို', 'Wu': 'ဝူ', 'Xu': 'ရှီးူ', 'Sun': 'သွန်',
            'Hu': 'ဟူ', 'Zhu': 'ကျု', 'Gao': 'ကောဝ်', 'Lin': 'လင်',
            'He': 'ဟိုး', 'Guo': 'ကိုဝ်', 'Ma': 'မာ', 'Luo': 'လော',
            'Long': 'လုံး', 'Feng': 'ဖုန်း', 'Yun': 'ယွန်', 'Lei': 'လိုင့်',
            'Dian': 'တျှင်', 'Long': 'လုံ', 'Feng': 'ဖုန်',
            
            # Common Chinese sounds
            '龙': 'လုံး', '凤': 'ဖုန်း', '云': 'ယွန်', '风': 'ဖုန်',
            '雷': 'လိုင့်', '电': 'တျှင်', '仙': 'ရှန်', '魔': 'မော',
            '道': 'တောဝ်', '神': 'ရှင်', '帝': 'တီး', '皇': 'ခွမ်း',
        }
        
        # Try to build phonetic name
        if self.source_lang.lower() == "english":
            parts = source_name.split()
            myanmar_parts = []
            for part in parts:
                # Try exact match first
                if part in phonetic_map:
                    myanmar_parts.append(phonetic_map[part])
                else:
                    # Try partial matches
                    matched = False
                    for eng, mya in phonetic_map.items():
                        if part.startswith(eng):
                            myanmar_parts.append(mya)
                            matched = True
                            break
                    if not matched:
                        # Keep original if no match
                        myanmar_parts.append(part)
            
            return ''.join(myanmar_parts) if myanmar_parts else source_name
        else:
            # For Chinese, character-by-character approximation
            result = []
            for char in source_name:
                if char in phonetic_map:
                    result.append(phonetic_map[char])
                else:
                    # Skip unknown characters or use placeholder
                    pass
            
            return ''.join(result) if result else source_name
    
    def add_name(self, source_name: str, myanmar_name: str, 
                 source_type: str = "character", confidence: float = 1.0) -> bool:
        """
        Add a new name mapping.
        
        Updates both glossary and context systems.
        """
        if not source_name or not myanmar_name:
            return False
        
        # 1. Update in-memory database
        self.names[source_name] = NameEntry(
            source_name=source_name,
            myanmar_name=myanmar_name,
            source_type=source_type,
            first_seen="manual",
            confidence=confidence
        )
        
        # 2. Update glossary (for translation)
        self.glossary.add_name(source_name, myanmar_name)
        self.glossary.save()
        
        # 3. Update context (for context injection)
        if source_type == "character":
            self.context.add_character(
                name=source_name,
                burmese_name=myanmar_name,
                first_appearance=1,
                importance="supporting"
            )
            self.context.save()
        
        return True
    
    def convert_text(self, text: str, confidence_threshold: float = 0.8) -> str:
        """
        Convert all known names in text to Myanmar.
        
        Only converts names with confidence >= threshold.
        """
        converted = text
        
        # Sort by length (longest first) to avoid partial replacements
        sorted_names = sorted(
            self.names.items(),
            key=lambda x: len(x[0]),
            reverse=True
        )
        
        for source_name, entry in sorted_names:
            if entry.confidence >= confidence_threshold and entry.myanmar_name:
                # Use word boundaries for English, exact match for Chinese
                if self.source_lang.lower() == "english":
                    pattern = r'\b' + re.escape(source_name) + r'\b'
                else:
                    pattern = re.escape(source_name)
                
                converted = re.sub(pattern, entry.myanmar_name, converted)
                entry.usage_count += 1
        
        return converted
    
    def auto_learn_from_chapter(self, chapter_path: str, translated_path: Optional[str] = None):
        """
        Auto-learn names from a chapter by comparing source and translation.
        
        If translated_path is provided, tries to extract name mappings.
        Otherwise, just extracts potential names for manual review.
        """
        print(f"Learning from: {chapter_path}")
        
        # Read source text
        with open(chapter_path, 'r', encoding='utf-8') as f:
            source_text = f.read()
        
        # Extract potential names
        potential = self.extract_potential_names(source_text)
        print(f"Found {len(potential)} potential names")
        
        if translated_path and Path(translated_path).exists():
            # Read translated text
            with open(translated_path, 'r', encoding='utf-8') as f:
                translated_text = f.read()
            
            # Try to find name mappings
            new_mappings = self._extract_mappings_from_parallel_text(
                source_text, translated_text, potential
            )
            
            print(f"\nAuto-detected {len(new_mappings)} name mappings:")
            for source, myanmar, confidence in new_mappings:
                print(f"  {source} → {myanmar} (confidence: {confidence:.2f})")
                self.add_name(source, myanmar, confidence=confidence)
            
            return new_mappings
        else:
            # Just show suggestions
            print("\nSuggested Myanmar names (review and confirm):")
            for name, ntype in potential[:10]:
                suggested = self.suggest_myanmar_name(name, ntype)
                print(f"  [{ntype}] {name} → {suggested}")
            
            return potential
    
    def _extract_mappings_from_parallel_text(self, source: str, translated: str,
                                             candidates: List[Tuple[str, str]]) -> List[Tuple[str, str, float]]:
        """
        Try to extract name mappings by comparing source and translated text.
        
        Returns list of (source_name, myanmar_name, confidence) tuples.
        """
        mappings = []
        
        # This is a simplified heuristic-based approach
        # In production, this could use AI or more sophisticated alignment
        
        for name, ntype in candidates:
            if name in source:
                # Count occurrences in source
                source_count = source.count(name)
                
                # Look for potential Myanmar equivalents in translation
                # (Burmese characters: \u1000-\u109F)
                myanmar_words = re.findall(r'[\u1000-\u109F]+', translated)
                
                # Find words that appear with similar frequency
                from collections import Counter
                word_counts = Counter(myanmar_words)
                
                for word, count in word_counts.most_common(10):
                    # Heuristic: similar frequency might indicate name match
                    if abs(count - source_count) <= 2 and len(word) >= 2:
                        confidence = 0.6 if abs(count - source_count) <= 1 else 0.4
                        mappings.append((name, word, confidence))
                        break
        
        return mappings
    
    def sync_glossary_to_context(self):
        """Sync all glossary names to context characters."""
        print(f"Syncing glossary to context for '{self.novel_name}'...")
        
        synced = 0
        for source, myanmar in self.glossary.names.items():
            char = self.context.get_character(source)
            if char:
                if char.burmese_name != myanmar:
                    char.burmese_name = myanmar
                    synced += 1
            else:
                self.context.add_character(
                    name=source,
                    burmese_name=myanmar,
                    first_appearance=1,
                    importance="supporting"
                )
                synced += 1
        
        self.context.save()
        print(f"  Synced {synced} names")
        return synced
    
    def sync_context_to_glossary(self):
        """Sync all context characters to glossary."""
        print(f"Syncing context to glossary for '{self.novel_name}'...")
        
        synced = 0
        for char_name, char in self.context.characters.items():
            if char.burmese_name and char_name not in self.glossary.names:
                self.glossary.add_name(char_name, char.burmese_name)
                synced += 1
        
        self.glossary.save()
        print(f"  Synced {synced} names")
        return synced
    
    def export_names(self, output_path: str):
        """Export all names to a JSON file."""
        data = {
            "novel_name": self.novel_name,
            "source_language": self.source_lang,
            "exported_at": datetime.now().isoformat(),
            "names": {name: entry.to_dict() for name, entry in self.names.items()}
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"Exported {len(self.names)} names to {output_path}")
    
    def import_names(self, input_path: str, overwrite: bool = False):
        """Import names from a JSON file."""
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        imported = 0
        for name, entry_data in data.get("names", {}).items():
            if name not in self.names or overwrite:
                entry = NameEntry.from_dict(entry_data)
                self.names[name] = entry
                self.glossary.add_name(name, entry.myanmar_name)
                imported += 1
        
        self.glossary.save()
        self.sync_glossary_to_context()
        
        print(f"Imported {imported} names from {input_path}")
        return imported
    
    def interactive_mode(self):
        """Run interactive name entry mode."""
        print(f"\n=== Name Converter: {self.novel_name} ===")
        print(f"Current names: {len(self.names)}")
        print("Commands: add, list, convert, learn, sync, export, import, quit\n")
        
        while True:
            try:
                cmd = input("\n> ").strip().lower()
                
                if cmd == "quit" or cmd == "q":
                    break
                
                elif cmd == "add" or cmd == "a":
                    source = input("Source name: ").strip()
                    myanmar = input("Myanmar name: ").strip()
                    ntype = input("Type (character/place/technique): ").strip() or "character"
                    
                    if self.add_name(source, myanmar, ntype):
                        print(f"✓ Added: {source} → {myanmar}")
                    else:
                        print("✗ Failed to add")
                
                elif cmd == "list" or cmd == "l":
                    print(f"\n{'Source':<30} {'Myanmar':<30} {'Type':<15}")
                    print("-" * 75)
                    for name, entry in sorted(self.names.items()):
                        print(f"{name:<30} {entry.myanmar_name:<30} {entry.source_type:<15}")
                
                elif cmd == "convert" or cmd == "c":
                    text = input("Text to convert: ").strip()
                    result = self.convert_text(text)
                    print(f"Result: {result}")
                
                elif cmd == "learn":
                    path = input("Chapter file path: ").strip()
                    trans = input("Translated file path (optional): ").strip()
                    if path:
                        self.auto_learn_from_chapter(path, trans or None)
                
                elif cmd == "sync":
                    self.sync_glossary_to_context()
                    self.sync_context_to_glossary()
                
                elif cmd == "export":
                    path = input("Export file path: ").strip() or f"{self.novel_name}_names.json"
                    self.export_names(path)
                
                elif cmd == "import":
                    path = input("Import file path: ").strip()
                    if path:
                        self.import_names(path)
                
                else:
                    print("Unknown command. Try: add, list, convert, learn, sync, export, import, quit")
            
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error: {e}")
        
        print("\nGoodbye!")


def main():
    parser = argparse.ArgumentParser(
        description="Chinese/English to Myanmar Name Converter with Auto-Learning"
    )
    parser.add_argument("--novel", required=True, help="Novel name")
    parser.add_argument("--source-lang", default="English", help="Source language")
    parser.add_argument("--learn-from", help="Auto-learn from chapter file")
    parser.add_argument("--translated", help="Translated file for comparison")
    parser.add_argument("--convert-file", help="File to convert names in")
    parser.add_argument("--output", help="Output file for converted text")
    parser.add_argument("--sync", action="store_true", help="Sync glossary and context")
    parser.add_argument("--export", help="Export names to file")
    parser.add_argument("--import-file", help="Import names from file")
    parser.add_argument("--interactive", action="store_true", help="Interactive mode")
    
    args = parser.parse_args()
    
    # Initialize converter
    converter = NameConverter(args.novel, args.source_lang)
    
    if args.interactive:
        converter.interactive_mode()
    
    elif args.learn_from:
        converter.auto_learn_from_chapter(args.learn_from, args.translated)
    
    elif args.convert_file:
        with open(args.convert_file, 'r', encoding='utf-8') as f:
            text = f.read()
        
        converted = converter.convert_text(text)
        
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(converted)
            print(f"Converted text saved to {args.output}")
        else:
            print(converted)
    
    elif args.sync:
        converter.sync_glossary_to_context()
        converter.sync_context_to_glossary()
        print("Sync complete!")
    
    elif args.export:
        converter.export_names(args.export)
    
    elif args.import_file:
        converter.import_names(args.import_file)
    
    else:
        print(f"Name Converter for '{args.novel}'")
        print(f"Total names loaded: {len(converter.names)}")
        print("\nUse --interactive for interactive mode")
        print("Use --learn-from to auto-learn from a chapter")
        print("Use --sync to sync glossary and context")


if __name__ == "__main__":
    main()
