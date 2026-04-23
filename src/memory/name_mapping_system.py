#!/usr/bin/env python3
"""
Name Mapping System - Auto-detect, Type-based Translation, and Persistence

This module provides a comprehensive name mapping system that:
1. Auto-detects names from source text
2. Applies type-based translation rules:
   - person → phonetic (e.g., "Li Wei" → "လီဝေ့")
   - place → phonetic + suffix (e.g., "Phoenix City" → "ဖီးနစ်မြို့")
   - sect → name + "ဇုံ" (e.g., "Cloud Sect" → "မိုးအုပ်ဇုံ")
3. Persists mappings to file
4. Applies mappings before translation
5. Injects mappings into prompts
6. Auto-updates from parallel text analysis

Usage:
    from scripts.name_mapping_system import NameMappingSystem
    
    # Initialize for a novel
    nms = NameMappingSystem("novel_name", source_lang="English")
    
    # Auto-detect names from chapter
    detected = nms.detect_names(chapter_text)
    
    # Apply name mappings before translation
    prepared_text = nms.apply_mappings(chapter_text)
    
    # Get prompt injection text
    prompt_text = nms.get_prompt_text()
    
    # Learn from parallel text (source + translated)
    nms.learn_from_parallel(source_text, translated_text)
"""

import re
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum


class NameType(Enum):
    """Types of names with different translation rules."""
    PERSON = "person"           # Phonetic only
    PLACE = "place"             # Phonetic + suffix
    SECT = "sect"               # Name + ဇုံ
    ORGANIZATION = "organization"  # Name + အဖွဲ့/ဂိုဏ်း
    TITLE = "title"             # Context-based
    ITEM = "item"               # Phonetic or meaning
    TECHNIQUE = "technique"     # Phonetic or meaning
    UNKNOWN = "unknown"         # Default


@dataclass
class NameMapping:
    """Represents a name mapping with metadata."""
    source_name: str
    myanmar_name: str
    name_type: str
    confidence: float = 1.0
    auto_detected: bool = False
    first_seen_chapter: int = 0
    last_seen_chapter: int = 0
    occurrence_count: int = 1
    aliases: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'NameMapping':
        return cls(**data)


@dataclass
class TypeRule:
    """Translation rule for a name type."""
    name_type: str
    description: str
    suffix: str = ""           # e.g., "မြို့" for places
    prefix: str = ""           # e.g., "ဇုံ" for sects (as suffix in practice)
    use_phonetic: bool = True  # Whether to use phonetic translation
    phonetic_hints: Dict[str, str] = field(default_factory=dict)


class NameMappingSystem:
    """
    Comprehensive name mapping system with auto-detection and type-based rules.
    
    Features:
    - Auto-detect names from text using patterns
    - Apply type-based translation rules
    - Persist mappings to JSON file
    - Apply mappings before translation
    - Inject into prompts
    - Auto-learn from parallel texts
    """
    
    # Default type rules
    DEFAULT_RULES = {
        NameType.PERSON.value: TypeRule(
            name_type=NameType.PERSON.value,
            description="Character names - phonetic translation",
            use_phonetic=True,
            phonetic_hints={}
        ),
        NameType.PLACE.value: TypeRule(
            name_type=NameType.PLACE.value,
            description="Places - phonetic + suffix",
            suffix="မြို့",  # City/town suffix
            use_phonetic=True
        ),
        NameType.SECT.value: TypeRule(
            name_type=NameType.SECT.value,
            description="Sects - name + ဇုံ",
            suffix="ဇုံ",
            use_phonetic=True
        ),
        NameType.ORGANIZATION.value: TypeRule(
            name_type=NameType.ORGANIZATION.value,
            description="Organizations - name + ဂိုဏ်း/အဖွဲ့",
            suffix="ဂိုဏ်း",
            use_phonetic=True
        ),
        NameType.TITLE.value: TypeRule(
            name_type=NameType.TITLE.value,
            description="Titles - context-based translation",
            use_phonetic=False
        ),
        NameType.ITEM.value: TypeRule(
            name_type=NameType.ITEM.value,
            description="Items - phonetic or meaning",
            use_phonetic=True
        ),
        NameType.TECHNIQUE.value: TypeRule(
            name_type=NameType.TECHNIQUE.value,
            description="Techniques - phonetic or meaning",
            use_phonetic=True
        ),
    }
    
    # Phonetic mapping for common sounds
    PHONETIC_MAP = {
        # English consonants
        'a': 'အေ', 'b': 'ဘီ', 'c': 'စီ', 'd': 'ဒီ', 'e': 'အီ',
        'f': 'အက်ဖ်', 'g': 'ဂျီ', 'h': 'အေချ်', 'i': 'အိုင်', 'j': 'ဂျေ',
        'k': 'ကေ', 'l': 'အဲလ်', 'm': 'အမ်', 'n': 'အန်', 'o': 'အို',
        'p': 'ပီ', 'q': 'ကျူ', 'r': 'အာ', 's': 'အက်စ်', 't': 'တီ',
        'u': 'ယူ', 'v': 'ဗီ', 'w': 'ဒဗလျူ', 'x': 'အက်စ်', 'y': 'ဝိုင်း',
        'z': 'ဇီ',
        
        # Common Chinese pinyin
        'li': 'လီ', 'wei': 'ဝေ့', 'wang': 'ဝမ်', 'zhang': 'ကျန်းချင်',
        'liu': 'လျို', 'chen': 'ချင်း', 'yang': 'ယန်', 'zhao': 'ကျော့',
        'wu': 'ဝူ', 'xu': 'ရှူး', 'sun': 'သွန်', 'zhu': 'ကျု',
        'gao': 'ကောဝ်', 'lin': 'လင်', 'guo': 'ကိုဝ်', 'ma': 'မာ',
        'luo': 'လော', 'long': 'လုံ', 'feng': 'ဖုန်', 'yun': 'ယွန်',
        'lei': 'လိုင်', 'dian': 'တျှင်', 'xian': 'ရှန်', 'mo': 'မော',
        'dao': 'တောဝ်', 'shen': 'ရှင်', 'di': 'တီ', 'huang': 'ခွမ်း',
        'gu': 'ဂူ', 'wen': 'ဝမ်', 'lan': 'လန်', 'qian': "ချিয়န်မ်",
        'ming': "မင်း", 'tian': "ထျန်", 'qing': "ကျင်းချင်း",
        'bai': "ဘိုင်", 'ling': "လင်း", 'jie': "ကျီး",
        
        # Common name components
        'city': 'မြို့', 'mountain': 'တောင်', 'valley': 'ချိုင့်',
        'river': 'မြစ်', 'lake': 'ရေ', 'forest': 'တော', 'gate': 'တံခါး',
        'palace': 'နန်းတော်', 'hall': 'ခန်း', 'pavilion': 'တိုက်',
        'peak': 'တောင်ထိပ်', 'island': 'ကျွန်း', 'bridge': 'တံတား',
    }
    
    # Suffix patterns for auto-detection
    PLACE_SUFFIXES = ['city', 'town', 'village', 'mountain', 'valley', 'river', 
                      'lake', 'forest', 'gate', 'palace', 'hall', 'pavilion',
                      'peak', 'island', 'bridge', 'market', 'street', 'square',
                      'city', '城', '山', '谷', '河', '湖', '林', '门', '宫', '殿']
    
    SECT_SUFFIXES = ['sect', 'school', 'cult', 'clan', 'society', 'alliance',
                     '宗', '派', '门', '教', '帮', '会', '盟']
    
    ORG_SUFFIXES = ['palace', 'hall', 'pavilion', 'tower', 'union', 'association',
                    '宫', '殿', '阁', '楼', '盟', '会']
    
    TITLE_PATTERNS = ['master', 'elder', 'lord', 'king', 'emperor', 'prince', 
                      'princess', 'young master', 'miss', 'sir', 'madam',
                      '师傅', '长老', '主', '王', '帝', '公子', '小姐']
    
    def __init__(self, novel_name: str, source_lang: str = "English",
                 auto_create: bool = True):
        """
        Initialize the name mapping system.
        
        Args:
            novel_name: Name of the novel (used for file paths)
            source_lang: Source language (English, Chinese, etc.)
            auto_create: Create mapping file if it doesn't exist
        """
        self.novel_name = novel_name
        self.source_lang = source_lang
        
        # Storage
        self.mappings: Dict[str, NameMapping] = {}  # source_name -> NameMapping
        self.type_rules: Dict[str, TypeRule] = dict(self.DEFAULT_RULES)
        
        # File paths
        self.mappings_dir = Path("name_mappings")
        self.mappings_dir.mkdir(parents=True, exist_ok=True)
        self.mappings_file = self.mappings_dir / f"{novel_name}.json"
        self.rules_file = self.mappings_dir / f"{novel_name}_rules.json"
        
        # Statistics
        self.stats = {
            "total_mappings": 0,
            "auto_detected": 0,
            "manual_mappings": 0,
            "by_type": {t.value: 0 for t in NameType}
        }
        
        # Load existing data if file exists (regardless of auto_create)
        # auto_create only affects whether we create new files if none exist
        if self.mappings_file.exists() or auto_create:
            self.load()
    
    # ====================================================================
    # File Operations
    # ====================================================================
    
    def load(self) -> bool:
        """Load mappings from file."""
        try:
            # Load mappings
            if self.mappings_file.exists():
                with open(self.mappings_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for name, mapping_data in data.get("mappings", {}).items():
                        self.mappings[name] = NameMapping.from_dict(mapping_data)
                
                self.stats = data.get("stats", self.stats)
                print(f"✓ Loaded {len(self.mappings)} name mappings for '{self.novel_name}'")
            
            # Load custom rules
            if self.rules_file.exists():
                with open(self.rules_file, 'r', encoding='utf-8') as f:
                    rules_data = json.load(f)
                    for type_name, rule_data in rules_data.get("rules", {}).items():
                        self.type_rules[type_name] = TypeRule(**rule_data)
            
            return True
        except Exception as e:
            print(f"⚠ Warning: Could not load name mappings: {e}")
            return False
    
    def save(self) -> bool:
        """Save mappings to file."""
        try:
            # Update stats
            self.stats["total_mappings"] = len(self.mappings)
            self.stats["auto_detected"] = sum(1 for m in self.mappings.values() if m.auto_detected)
            self.stats["manual_mappings"] = self.stats["total_mappings"] - self.stats["auto_detected"]
            self.stats["by_type"] = {}
            for m in self.mappings.values():
                t = m.name_type
                self.stats["by_type"][t] = self.stats["by_type"].get(t, 0) + 1
            
            # Save mappings
            data = {
                "novel_name": self.novel_name,
                "source_language": self.source_lang,
                "updated_at": datetime.now().isoformat(),
                "mappings": {name: m.to_dict() for name, m in self.mappings.items()},
                "stats": self.stats
            }
            
            with open(self.mappings_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            # Save rules
            rules_data = {
                "novel_name": self.novel_name,
                "rules": {name: asdict(rule) for name, rule in self.type_rules.items()}
            }
            with open(self.rules_file, 'w', encoding='utf-8') as f:
                json.dump(rules_data, f, ensure_ascii=False, indent=2)
            
            return True
        except Exception as e:
            print(f"✗ Error saving name mappings: {e}")
            return False
    
    # ====================================================================
    # Name Detection
    # ====================================================================
    
    def detect_names(self, text: str, chapter_num: int = 0) -> List[Tuple[str, str, float]]:
        """
        Auto-detect potential names from text.
        
        Returns:
            List of (name, name_type, confidence) tuples
        """
        detected = []
        
        if self.source_lang.lower() == "english":
            detected.extend(self._detect_english_names(text))
        else:  # Chinese
            detected.extend(self._detect_chinese_names(text))
        
        # Filter out already mapped names
        new_names = [(name, ntype, conf) for name, ntype, conf in detected 
                     if name not in self.mappings]
        
        # Create mappings for new names
        for name, ntype, confidence in new_names:
            myanmar_name = self._translate_by_type(name, ntype)
            self.add_mapping(name, myanmar_name, ntype, 
                           confidence=confidence, 
                           auto_detected=True,
                           chapter_num=chapter_num)
        
        # Update occurrence count for existing names
        for name, ntype, _ in detected:
            if name in self.mappings:
                self.mappings[name].occurrence_count += 1
                self.mappings[name].last_seen_chapter = chapter_num
        
        return new_names
    
    def _detect_english_names(self, text: str) -> List[Tuple[str, str, float]]:
        """Detect English names from text."""
        detected = []
        
        # Pattern 1: Capitalized words (potential names)
        # Look for Title Case words that appear multiple times
        words = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}\b', text)
        from collections import Counter
        word_counts = Counter(words)
        
        common_words = {'The', 'And', 'But', 'For', 'With', 'From', 'This', 'That',
                       'When', 'Where', 'What', 'How', 'Why', 'Who', 'Which',
                       'Then', 'Than', 'They', 'Them', 'Their', 'There',
                       'Chapter', 'Part', 'Section', 'Volume', 'Book'}
        
        for word, count in word_counts.items():
            if count >= 2 and word not in common_words and len(word) >= 3:
                name_type = self._classify_name_type(word)
                confidence = min(0.5 + (count - 2) * 0.1, 0.9)
                detected.append((word, name_type, confidence))
        
        # Pattern 2: Names with titles
        title_pattern = r'\b(Young Master|Miss|Master|Elder|Lord|King|Prince|Princess|Emperor|Sect Master)\s+([A-Z][a-z]+)\b'
        for match in re.finditer(title_pattern, text):
            full_title = match.group(0)
            name_type = NameType.TITLE.value
            detected.append((full_title, name_type, 0.85))
        
        # Pattern 3: Places with suffixes
        for suffix in self.PLACE_SUFFIXES:
            pattern = rf'\b([A-Z][a-z]*(?:\s+[A-Z][a-z]+)*)\s+{suffix}\b'
            for match in re.finditer(pattern, text, re.IGNORECASE):
                place_name = match.group(0)
                if place_name not in [d[0] for d in detected]:
                    detected.append((place_name, NameType.PLACE.value, 0.8))
        
        # Pattern 4: Sects with suffixes
        for suffix in self.SECT_SUFFIXES:
            pattern = rf'\b([A-Z][a-z]*(?:\s+[A-Z][a-z]+)*)\s+{suffix}\b'
            for match in re.finditer(pattern, text, re.IGNORECASE):
                sect_name = match.group(0)
                if sect_name not in [d[0] for d in detected]:
                    detected.append((sect_name, NameType.SECT.value, 0.8))
        
        # Remove duplicates while preserving highest confidence
        seen = {}
        for name, ntype, conf in detected:
            if name not in seen or seen[name][1] < conf:
                seen[name] = (ntype, conf)
        
        return [(name, ntype, conf) for name, (ntype, conf) in seen.items()]
    
    def _detect_chinese_names(self, text: str) -> List[Tuple[str, str, float]]:
        """Detect Chinese names from text."""
        detected = []
        
        # Pattern 1: Chinese names (2-4 characters)
        chinese_names = re.findall(r'[\u4e00-\u9fa5]{2,4}', text)
        from collections import Counter
        name_counts = Counter(chinese_names)
        
        common_surnames = ['李', '王', '张', '刘', '陈', '杨', '赵', '黄', '周', '吴',
                          '徐', '孙', '胡', '朱', '高', '林', '何', '郭', '马', '罗',
                          '梁', '宋', '郑', '谢', '韩', '唐', '冯', '于', '董', '萧',
                          '程', '曹', '袁', '邓', '许', '傅', '沈', '曾', '彭', '吕',
                          '苏', '卢', '蒋', '蔡', '贾', '丁', '魏', '薛', '叶', '阎']
        
        for name, count in name_counts.items():
            if count >= 2:
                # Check if it looks like a name
                confidence = 0.5
                if any(name.startswith(s) for s in common_surnames):
                    confidence = 0.8
                if len(name) == 2 or len(name) == 3:
                    confidence += 0.1
                
                name_type = NameType.PERSON.value
                # Check for place indicators
                if any(name.endswith(s) for s in ['城', '山', '谷', '河', '湖']):
                    name_type = NameType.PLACE.value
                # Check for sect indicators
                elif any(name.endswith(s) for s in ['宗', '派', '门', '教']):
                    name_type = NameType.SECT.value
                
                detected.append((name, name_type, min(confidence, 0.95)))
        
        return detected
    
    def _classify_name_type(self, name: str) -> str:
        """Classify the type of a name based on patterns."""
        name_lower = name.lower()
        
        # Check for place suffixes
        if any(name_lower.endswith(s.lower()) for s in self.PLACE_SUFFIXES):
            return NameType.PLACE.value
        
        # Check for sect suffixes
        if any(name_lower.endswith(s.lower()) for s in self.SECT_SUFFIXES):
            return NameType.SECT.value
        
        # Check for org suffixes
        if any(name_lower.endswith(s.lower()) for s in self.ORG_SUFFIXES):
            return NameType.ORGANIZATION.value
        
        # Check for title patterns
        if any(s.lower() in name_lower for s in self.TITLE_PATTERNS):
            return NameType.TITLE.value
        
        # Default to person
        return NameType.PERSON.value
    
    # ====================================================================
    # Translation by Type
    # ====================================================================
    
    def _translate_by_type(self, name: str, name_type: str) -> str:
        """Translate a name according to its type rules."""
        rule = self.type_rules.get(name_type, self.type_rules[NameType.PERSON.value])
        
        if name_type == NameType.PERSON.value:
            return self._phonetic_translate(name)
        
        elif name_type == NameType.PLACE.value:
            phonetic = self._phonetic_translate(name)
            # Remove English suffix if present
            for suffix in self.PLACE_SUFFIXES[:12]:  # English suffixes only
                if phonetic.lower().endswith(suffix.lower()):
                    phonetic = phonetic[:-len(suffix)].strip()
                    break
            return phonetic + rule.suffix
        
        elif name_type == NameType.SECT.value:
            phonetic = self._phonetic_translate(name)
            # Remove English suffix if present
            for suffix in self.SECT_SUFFIXES[:6]:  # English suffixes only
                if phonetic.lower().endswith(suffix.lower()):
                    phonetic = phonetic[:-len(suffix)].strip()
                    break
            return phonetic + rule.suffix
        
        elif name_type == NameType.ORGANIZATION.value:
            phonetic = self._phonetic_translate(name)
            return phonetic + rule.suffix
        
        elif name_type == NameType.TITLE.value:
            return self._translate_title(name)
        
        else:
            return self._phonetic_translate(name)
    
    def _phonetic_translate(self, name: str) -> str:
        """Translate a name phonetically to Myanmar."""
        # Check for exact match first
        if name.lower() in self.PHONETIC_MAP:
            return self.PHONETIC_MAP[name.lower()]
        
        # For multi-word names, translate each part
        parts = name.split()
        if len(parts) > 1:
            translated_parts = []
            for part in parts:
                if part.lower() in self.PHONETIC_MAP:
                    translated_parts.append(self.PHONETIC_MAP[part.lower()])
                else:
                    # Try to map individual characters/syllables
                    translated_parts.append(self._map_syllable(part))
            return ''.join(translated_parts)
        else:
            return self._map_syllable(name)
    
    def _map_syllable(self, syllable: str) -> str:
        """Map a syllable phonetically."""
        syllable_lower = syllable.lower()
        
        # Try exact match
        if syllable_lower in self.PHONETIC_MAP:
            return self.PHONETIC_MAP[syllable_lower]
        
        # Try partial matches
        result = []
        i = 0
        while i < len(syllable_lower):
            # Try longer matches first
            matched = False
            for length in [4, 3, 2, 1]:
                if i + length <= len(syllable_lower):
                    substr = syllable_lower[i:i+length]
                    if substr in self.PHONETIC_MAP:
                        result.append(self.PHONETIC_MAP[substr])
                        i += length
                        matched = True
                        break
            if not matched:
                # Keep original character
                result.append(syllable[i])
                i += 1
        
        return ''.join(result) if result else syllable
    
    def _translate_title(self, title: str) -> str:
        """Translate a title based on context."""
        title_lower = title.lower()
        
        # Common title translations
        title_map = {
            'young master': 'ကျွန်\u200bပေါင်း',
            'miss': 'အလှမယ်',
            'master': 'အရှင်',
            'elder': 'အကြီးအကဲ',
            'lord': 'သခင်',
            'king': 'ဘုရင်',
            'emperor': 'ဧကရာဇ်',
            'prince': 'မင်းသား',
            'princess': 'မင်းသမီး',
            'sect master': 'ဂိုဏ်းခေါင်းဆောင်',
        }
        
        for eng, mya in title_map.items():
            if eng in title_lower:
                # Replace the title part
                name_part = title_lower.replace(eng, '').strip()
                if name_part:
                    return mya + ' ' + self._phonetic_translate(name_part.title())
                return mya
        
        return self._phonetic_translate(title)
    
    # ====================================================================
    # Mapping Management
    # ====================================================================
    
    def add_mapping(self, source_name: str, myanmar_name: str, 
                    name_type: str = "person", confidence: float = 1.0,
                    auto_detected: bool = False, chapter_num: int = 0) -> bool:
        """
        Add a new name mapping.
        
        Args:
            source_name: Original name
            myanmar_name: Translated Myanmar name
            name_type: Type of name (person, place, sect, etc.)
            confidence: Confidence score (0.0-1.0)
            auto_detected: Whether this was auto-detected
            chapter_num: Chapter where first seen
        """
        if not source_name or not myanmar_name:
            return False
        
        now = datetime.now().isoformat()
        
        if source_name in self.mappings:
            # Update existing
            mapping = self.mappings[source_name]
            mapping.myanmar_name = myanmar_name
            mapping.name_type = name_type
            mapping.confidence = max(mapping.confidence, confidence)
            mapping.updated_at = now
            mapping.last_seen_chapter = chapter_num
        else:
            # Create new
            self.mappings[source_name] = NameMapping(
                source_name=source_name,
                myanmar_name=myanmar_name,
                name_type=name_type,
                confidence=confidence,
                auto_detected=auto_detected,
                first_seen_chapter=chapter_num,
                last_seen_chapter=chapter_num
            )
        
        return True
    
    def get_mapping(self, source_name: str) -> Optional[NameMapping]:
        """Get mapping for a source name."""
        return self.mappings.get(source_name)
    
    def remove_mapping(self, source_name: str) -> bool:
        """Remove a name mapping."""
        if source_name in self.mappings:
            del self.mappings[source_name]
            return True
        return False
    
    def get_mappings_by_type(self, name_type: str) -> List[NameMapping]:
        """Get all mappings of a specific type."""
        return [m for m in self.mappings.values() if m.name_type == name_type]
    
    # ====================================================================
    # Application and Prompt Injection
    # ====================================================================
    
    def apply_mappings(self, text: str, confidence_threshold: float = 0.6) -> str:
        """
        Apply name mappings to text before translation.
        
        Replaces source names with Myanmar names to help the translator
        maintain consistency.
        
        Args:
            text: Original text
            confidence_threshold: Minimum confidence to apply mapping
            
        Returns:
            Text with names replaced
        """
        result = text
        
        # Sort by length (longest first) to avoid partial replacements
        sorted_mappings = sorted(
            self.mappings.items(),
            key=lambda x: len(x[0]),
            reverse=True
        )
        
        for source_name, mapping in sorted_mappings:
            if mapping.confidence >= confidence_threshold:
                # Use word boundaries for English
                if self.source_lang.lower() == "english":
                    pattern = r'\b' + re.escape(source_name) + r'\b'
                    result = re.sub(pattern, mapping.myanmar_name, result, flags=re.IGNORECASE)
                else:
                    # Exact match for Chinese
                    result = result.replace(source_name, mapping.myanmar_name)
        
        return result
    
    def get_prompt_text(self, max_entries: int = 50) -> str:
        """
        Get formatted name mappings for prompt injection.
        
        Returns:
            Formatted text for system prompt
        """
        if not self.mappings:
            return ""
        
        lines = ["\n## NAME MAPPINGS (Use these EXACT translations):\n"]
        
        # Group by type
        by_type: Dict[str, List[NameMapping]] = {}
        for mapping in self.mappings.values():
            t = mapping.name_type
            if t not in by_type:
                by_type[t] = []
            by_type[t].append(mapping)
        
        # Format each type
        type_order = [NameType.PERSON.value, NameType.PLACE.value, 
                     NameType.SECT.value, NameType.ORGANIZATION.value,
                     NameType.TITLE.value, NameType.ITEM.value]
        type_labels = {
            NameType.PERSON.value: "Characters",
            NameType.PLACE.value: "Places",
            NameType.SECT.value: "Sects",
            NameType.ORGANIZATION.value: "Organizations",
            NameType.TITLE.value: "Titles",
            NameType.ITEM.value: "Items"
        }
        
        for name_type in type_order:
            if name_type in by_type:
                lines.append(f"**{type_labels.get(name_type, name_type)}:**")
                # Sort by confidence, highest first
                sorted_mappings = sorted(by_type[name_type], 
                                        key=lambda x: x.confidence, 
                                        reverse=True)[:max_entries//len(type_order)]
                for m in sorted_mappings:
                    conf_indicator = "✓" if m.confidence >= 0.9 else "~" if m.confidence >= 0.7 else "?"
                    lines.append(f'  [{conf_indicator}] "{m.source_name}" → "{m.myanmar_name}"')
                lines.append("")
        
        return "\n".join(lines)
    
    def get_glossary_text(self) -> str:
        """Alias for get_prompt_text() for compatibility."""
        return self.get_prompt_text()
    
    # ====================================================================
    # Learning from Parallel Text
    # ====================================================================
    
    def learn_from_parallel(self, source_text: str, translated_text: str,
                           chapter_num: int = 0) -> Dict[str, Any]:
        """
        Learn name mappings from parallel source and translated text.
        
        This analyzes the source text and the Myanmar translation to
        identify potential name mappings.
        
        Args:
            source_text: Original source text
            translated_text: Translated Myanmar text
            chapter_num: Chapter number
            
        Returns:
            Dictionary with learned mappings
        """
        learned = {
            "new_mappings": [],
            "confirmed_mappings": [],
            "potential_mappings": []
        }
        
        # Detect names in source
        if self.source_lang.lower() == "english":
            detected = self._detect_english_names(source_text)
        else:
            detected = self._detect_chinese_names(source_text)
        
        # For each detected name, try to find Myanmar equivalent
        for name, ntype, conf in detected:
            if name not in source_text:
                continue
                
            # Count occurrences in source
            source_count = source_text.count(name)
            
            # If name is not in translated text, it was translated
            if name not in translated_text:
                # Look for Myanmar words with similar frequency
                myanmar_words = re.findall(r'[\u1000-\u109F]{2,}', translated_text)
                from collections import Counter
                word_counts = Counter(myanmar_words)
                
                # Find candidates with similar frequency
                candidates = []
                for word, count in word_counts.most_common(20):
                    if abs(count - source_count) <= 2 and len(word) >= 2:
                        candidates.append((word, count))
                
                if candidates:
                    # Take the most frequent candidate
                    best_match = candidates[0][0]
                    
                    if name in self.mappings:
                        # Confirm existing mapping
                        if self.mappings[name].myanmar_name == best_match:
                            learned["confirmed_mappings"].append({
                                "source": name,
                                "myanmar": best_match
                            })
                    else:
                        # New mapping
                        self.add_mapping(name, best_match, ntype, 
                                       confidence=0.6, 
                                       auto_detected=True,
                                       chapter_num=chapter_num)
                        learned["new_mappings"].append({
                            "source": name,
                            "myanmar": best_match,
                            "type": ntype
                        })
        
        return learned
    
    # ====================================================================
    # Statistics and Export
    # ====================================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics."""
        return {
            "novel_name": self.novel_name,
            "source_language": self.source_lang,
            "total_mappings": len(self.mappings),
            "auto_detected": sum(1 for m in self.mappings.values() if m.auto_detected),
            "manual_mappings": sum(1 for m in self.mappings.values() if not m.auto_detected),
            "by_type": {t: len(self.get_mappings_by_type(t)) for t in self.type_rules.keys()},
            "high_confidence": sum(1 for m in self.mappings.values() if m.confidence >= 0.9),
            "medium_confidence": sum(1 for m in self.mappings.values() if 0.7 <= m.confidence < 0.9),
            "low_confidence": sum(1 for m in self.mappings.values() if m.confidence < 0.7)
        }
    
    def print_summary(self):
        """Print summary of name mappings."""
        stats = self.get_stats()
        
        print("=" * 60)
        print("NAME MAPPING SYSTEM SUMMARY")
        print("=" * 60)
        print(f"Novel: {stats['novel_name']}")
        print(f"Source Language: {stats['source_language']}")
        print()
        print(f"Total Mappings: {stats['total_mappings']}")
        print(f"  Auto-detected: {stats['auto_detected']}")
        print(f"  Manual: {stats['manual_mappings']}")
        print()
        print("By Type:")
        for t, count in stats['by_type'].items():
            if count > 0:
                print(f"  {t}: {count}")
        print()
        print("Confidence Levels:")
        print(f"  High (>=0.9): {stats['high_confidence']}")
        print(f"  Medium (0.7-0.9): {stats['medium_confidence']}")
        print(f"  Low (<0.7): {stats['low_confidence']}")
        print("=" * 60)
    
    def export_mappings(self, output_path: str):
        """Export mappings to JSON file."""
        data = {
            "novel_name": self.novel_name,
            "source_language": self.source_lang,
            "exported_at": datetime.now().isoformat(),
            "mappings": [m.to_dict() for m in self.mappings.values()],
            "stats": self.get_stats()
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"✓ Exported {len(self.mappings)} mappings to {output_path}")
    
    def import_mappings(self, input_path: str, overwrite: bool = False):
        """Import mappings from JSON file."""
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        imported = 0
        for mapping_data in data.get("mappings", []):
            source = mapping_data["source_name"]
            if source not in self.mappings or overwrite:
                self.mappings[source] = NameMapping.from_dict(mapping_data)
                imported += 1
        
        print(f"✓ Imported {imported} mappings from {input_path}")
        return imported


# =============================================================================
# CLI Interface
# =============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Name Mapping System - Auto-detect and manage name translations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Show summary
  python scripts/name_mapping_system.py --novel dao-equaling-the-heavens
  
  # Detect names from chapter
  python scripts/name_mapping_system.py --novel dao-equaling-the-heavens \\
      --detect-from chapter_001.txt --chapter 1
  
  # Add manual mapping
  python scripts/name_mapping_system.py --novel dao-equaling-the-heavens \\
      --add "Li Wei" "လီဝေ့" --type person
  
  # Learn from parallel text
  python scripts/name_mapping_system.py --novel dao-equaling-the-heavens \\
      --learn chapter_001.txt chapter_001_myanmar.txt --chapter 1
  
  # Export mappings
  python scripts/name_mapping_system.py --novel dao-equaling-the-heavens \\
      --export name_mappings_export.json
        """
    )
    
    parser.add_argument("--novel", required=True, help="Novel name")
    parser.add_argument("--source-lang", default="English", help="Source language")
    parser.add_argument("--summary", action="store_true", help="Show summary")
    
    # Detection
    parser.add_argument("--detect-from", help="Detect names from file")
    parser.add_argument("--chapter", type=int, default=0, help="Chapter number")
    
    # Manual add
    parser.add_argument("--add", nargs=2, metavar=("SOURCE", "MYANMAR"),
                       help="Add manual mapping")
    parser.add_argument("--type", default="person",
                       choices=["person", "place", "sect", "organization", "title", "item"],
                       help="Name type")
    parser.add_argument("--confidence", type=float, default=1.0,
                       help="Confidence score")
    
    # Learning
    parser.add_argument("--learn", nargs=2, metavar=("SOURCE_FILE", "TRANSLATED_FILE"),
                       help="Learn from parallel texts")
    
    # Export/Import
    parser.add_argument("--export", help="Export mappings to file")
    parser.add_argument("--import-file", help="Import mappings from file")
    
    # Apply
    parser.add_argument("--apply-to", help="Apply mappings to file")
    parser.add_argument("--output", help="Output file for applied mappings")
    
    args = parser.parse_args()
    
    # Initialize
    nms = NameMappingSystem(args.novel, args.source_lang)
    
    # Show summary by default
    if args.summary or not any([
        args.detect_from, args.add, args.learn, args.export, 
        args.import_file, args.apply_to
    ]):
        nms.print_summary()
    
    # Detect names
    if args.detect_from:
        path = Path(args.detect_from)
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                text = f.read()
            detected = nms.detect_names(text, args.chapter)
            print(f"\nDetected {len(detected)} new names:")
            for name, ntype, conf in detected[:10]:
                mapping = nms.get_mapping(name)
                if mapping:
                    print(f"  [{ntype}] {name} → {mapping.myanmar_name} (conf: {conf:.2f})")
            nms.save()
        else:
            print(f"✗ File not found: {args.detect_from}")
    
    # Add manual mapping
    if args.add:
        source, myanmar = args.add
        nms.add_mapping(source, myanmar, args.type, args.confidence)
        print(f"✓ Added mapping: {source} → {myanmar} ({args.type})")
        nms.save()
    
    # Learn from parallel text
    if args.learn:
        source_path, trans_path = args.learn
        if Path(source_path).exists() and Path(trans_path).exists():
            with open(source_path, 'r', encoding='utf-8') as f:
                source_text = f.read()
            with open(trans_path, 'r', encoding='utf-8') as f:
                trans_text = f.read()
            
            learned = nms.learn_from_parallel(source_text, trans_text, args.chapter)
            print(f"✓ Learned from parallel text:")
            print(f"  New mappings: {len(learned['new_mappings'])}")
            print(f"  Confirmed: {len(learned['confirmed_mappings'])}")
            for m in learned['new_mappings'][:5]:
                print(f"    - {m['source']} → {m['myanmar']}")
            nms.save()
        else:
            print("✗ One or both files not found")
    
    # Export
    if args.export:
        nms.export_mappings(args.export)
    
    # Import
    if args.import_file:
        nms.import_mappings(args.import_file)
        nms.save()
    
    # Apply mappings
    if args.apply_to:
        path = Path(args.apply_to)
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                text = f.read()
            
            result = nms.apply_mappings(text)
            
            if args.output:
                with open(args.output, 'w', encoding='utf-8') as f:
                    f.write(result)
                print(f"✓ Applied mappings and saved to {args.output}")
            else:
                print("Applied text (first 500 chars):")
                print(result[:500])
        else:
            print(f"✗ File not found: {args.apply_to}")


if __name__ == "__main__":
    main()
