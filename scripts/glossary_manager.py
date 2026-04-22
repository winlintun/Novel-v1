#!/usr/bin/env python3
"""
Glossary Manager - Per-Novel Character Name Consistency

Manages character names and terminology glossaries for each novel separately.
Glossaries are saved as JSON files in the glossaries/ directory with naming
convention: <novel_name>.json

Features:
- Load/save per-novel glossaries (novel_one.json, novel_two.json, etc.)
- Extract potential character names from Chinese text
- Update glossary with new names discovered during translation
- Merge glossary into translator prompts for consistency

Usage:
    from scripts.glossary_manager import GlossaryManager
    
    # Initialize for a specific novel
    glossary = GlossaryManager("novel_one")
    
    # Get glossary for prompt injection
    glossary_text = glossary.get_glossary_text()
    
    # Add new names discovered during translation
    glossary.add_name("魏无羡", "ဝေ့ဝူရှျန်")
    glossary.save()
"""

import json
import re
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

# Default directory for glossary files
GLOSSARY_DIR = Path("glossaries")


class GlossaryManager:
    """
    Manages character names and terminology for a specific novel.
    
    Each novel gets its own JSON file: glossaries/<novel_name>.json
    """
    
    def __init__(self, novel_name: str, auto_create: bool = True):
        """
        Initialize glossary manager for a novel.
        
        Args:
            novel_name: Name of the novel (used as filename base)
            auto_create: Create glossary file if it doesn't exist
        """
        self.novel_name = novel_name
        self.glossary_dir = GLOSSARY_DIR
        self.glossary_dir.mkdir(parents=True, exist_ok=True)
        
        self.glossary_file = self.glossary_dir / f"{novel_name}.json"
        self.names: Dict[str, str] = {}  # Chinese -> Burmese mapping
        self.metadata: Dict = {
            "novel_name": novel_name,
            "created_at": None,
            "updated_at": None,
            "total_names": 0,
            "chapter_count": 0
        }
        
        # Load existing or create new
        if self.glossary_file.exists():
            self.load()
        elif auto_create:
            self.metadata["created_at"] = datetime.now().isoformat()
            self.save()
    
    def load(self) -> bool:
        """
        Load glossary from JSON file.
        
        Returns:
            True if loaded successfully, False otherwise
        """
        try:
            with open(self.glossary_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            self.names = data.get("names", {})
            self.metadata = data.get("metadata", self.metadata)
            
            # Update metadata
            self.metadata["total_names"] = len(self.names)
            
            return True
            
        except FileNotFoundError:
            return False
        except json.JSONDecodeError as e:
            print(f"⚠ Warning: Corrupted glossary file {self.glossary_file}: {e}")
            # Backup corrupted file and start fresh
            backup_path = self.glossary_file.with_suffix('.json.backup')
            self.glossary_file.rename(backup_path)
            print(f"  Backed up corrupted file to {backup_path}")
            self.names = {}
            self.metadata["created_at"] = datetime.now().isoformat()
            self.save()
            return False
        except Exception as e:
            print(f"✗ Error loading glossary: {e}")
            return False
    
    def save(self) -> bool:
        """
        Save glossary to JSON file.
        
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            # Update metadata
            self.metadata["updated_at"] = datetime.now().isoformat()
            self.metadata["total_names"] = len(self.names)
            
            data = {
                "names": self.names,
                "metadata": self.metadata
            }
            
            # Write to temporary file first, then rename (atomic operation)
            temp_file = self.glossary_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            # Atomic rename
            temp_file.replace(self.glossary_file)
            
            return True
            
        except Exception as e:
            print(f"✗ Error saving glossary: {e}")
            return False
    
    def add_name(self, chinese_name: str, burmese_name: str, 
                 source_chapter: Optional[int] = None) -> bool:
        """
        Add or update a name mapping.
        
        Args:
            chinese_name: Original Chinese name
            burmese_name: Translated Burmese name
            source_chapter: Chapter number where name was discovered (optional)
            
        Returns:
            True if added/updated, False if unchanged
        """
        chinese_name = chinese_name.strip()
        burmese_name = burmese_name.strip()
        
        if not chinese_name or not burmese_name:
            return False
        
        # Check if name already exists with same translation
        if chinese_name in self.names and self.names[chinese_name] == burmese_name:
            return False
        
        # Add or update
        self.names[chinese_name] = burmese_name
        
        # Track which chapter discovered this name
        if source_chapter and "discovered_in" not in self.metadata:
            self.metadata["discovered_in"] = {}
        if source_chapter:
            self.metadata["discovered_in"][chinese_name] = source_chapter
        
        return True
    
    def get_name(self, chinese_name: str) -> Optional[str]:
        """
        Get Burmese translation for a Chinese name.
        
        Args:
            chinese_name: Original Chinese name
            
        Returns:
            Burmese name if found, None otherwise
        """
        return self.names.get(chinese_name.strip())
    
    def get_glossary_text(self) -> str:
        """
        Get formatted glossary text for prompt injection.
        
        Returns:
            Formatted glossary text for system prompt
        """
        if not self.names:
            return ""
        
        glossary_text = "\n\nTERMINOLOGY MAPPING (Use these exact Burmese translations - CRITICAL for consistency):\n"
        
        # Sort by Chinese name for consistent ordering
        for chinese in sorted(self.names.keys()):
            burmese = self.names[chinese]
            glossary_text += f'- "{chinese}" → "{burmese}"\n'
        
        glossary_text += "\n⚠️ WARNING: Do NOT translate these names. Use the EXACT provided name mappings. Keep all names consistent.\n"
        
        return glossary_text
    
    def get_names_list(self) -> List[Tuple[str, str]]:
        """
        Get list of all name mappings.
        
        Returns:
            List of (chinese, burmese) tuples
        """
        return [(k, v) for k, v in sorted(self.names.items())]
    
    def extract_potential_names(self, text: str) -> List[str]:
        """
        Extract potential character names from Chinese text using regex patterns.
        
        This is a heuristic extraction - names should be verified before adding.
        
        Args:
            text: Chinese text to analyze
            
        Returns:
            List of potential names found
        """
        potential_names = set()
        
        # Pattern 1: 2-4 character sequences that look like names
        # Chinese names typically have specific patterns
        name_patterns = [
            r'[一二三四五六七八九十百千]+[爷兄妹姐弟]',  # Titles like 三爷, 五妹
            r'[甲乙丙丁戊己庚辛壬癸]+[某]',  # Generic names like 甲某
            r'[赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜戚谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳酆鲍史唐费廉岑薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅皮卞齐康伍余元卜顾孟平黄和穆萧尹姚邵湛汪祁毛禹狄米贝明臧计伏成戴谈宋茅庞熊纪舒屈项祝董梁杜阮蓝闵席季麻强贾路娄危江童颜郭梅盛林刁钟徐邱骆高夏蔡田樊胡凌霍虞万支柯昝管卢莫经房裘缪干解应宗丁宣贲邓郁单杭洪包诸左石崔吉钮龚程嵇邢滑裴陆荣翁荀羊於惠甄曲家封芮羿储靳汲邴糜松井段富巫乌焦巴弓牧隗山谷车侯宓蓬全郗班仰秋仲伊宫宁仇栾暴甘钭厉戎祖武符刘景詹束龙叶幸司韶郜黎蓟薄印宿白怀蒲邰从鄂索咸籍赖卓蔺屠蒙池乔阴鬱胥能苍双闻莘党翟谭贡劳逄姬申扶堵冉宰郦雍卻璩桑桂濮牛寿通边扈燕冀郏浦尚农温别庄晏柴瞿阎充慕连茹习宦艾鱼容向古易慎戈廖庾终暨居衡步都耿满弘匡国文寇广禄阙东欧殳沃利蔚越夔隆师巩厍聂晁勾敖融冷訾辛阚那简饶空曾毋沙乜养鞠须丰巢关蒯相查后荆红游竺权逯盖益桓公]+[氏家主宗掌门]',  # Surnames with titles
        ]
        
        for pattern in name_patterns:
            matches = re.findall(pattern, text)
            potential_names.update(matches)
        
        # Pattern 2: Look for repeated 2-4 character sequences that might be names
        # Names often appear multiple times in a chapter
        char_sequences = re.findall(r'[\u4e00-\u9fa5]{2,4}', text)
        from collections import Counter
        seq_counts = Counter(char_sequences)
        
        # Sequences that appear 3+ times might be names
        for seq, count in seq_counts.items():
            if count >= 3 and len(seq) >= 2:
                potential_names.add(seq)
        
        # Pattern 3: Names followed by titles
        title_pattern = r'([\u4e00-\u9fa5]{2,4})(?:师兄|师弟|师姐|师妹|师父|师娘|师祖|师叔|师伯|掌门|宗主|长老|弟子|门主|教主|帮主|岛主|谷主|城主|阁主|楼主|庄主|家主|老爷|夫人|少爷|小姐|公子|姑娘|道长|法师|大师|神医|阁下|前辈|晚辈)'
        matches = re.findall(title_pattern, text)
        potential_names.update(matches)
        
        return sorted(list(potential_names))
    
    def merge_with_existing(self, other_glossary: 'GlossaryManager') -> int:
        """
        Merge another glossary into this one.
        
        Args:
            other_glossary: Another GlossaryManager instance
            
        Returns:
            Number of new names added
        """
        added = 0
        for chinese, burmese in other_glossary.names.items():
            if chinese not in self.names:
                self.names[chinese] = burmese
                added += 1
        
        if added > 0:
            self.save()
        
        return added
    
    def update_from_translation(self, source_text: str, translated_text: str, 
                                 chapter_num: Optional[int] = None) -> List[Tuple[str, str]]:
        """
        Update glossary by comparing source and translated text.
        Attempts to identify new name mappings from the translation.
        
        This is a best-effort extraction - it looks for patterns where
        Chinese characters appear to have been replaced with Burmese text.
        
        Args:
            source_text: Original Chinese text
            translated_text: Translated Burmese text
            chapter_num: Chapter number (for tracking)
            
        Returns:
            List of newly discovered (chinese, burmese) tuples
        """
        new_mappings = []
        
        # Extract potential names from source
        potential_names = self.extract_potential_names(source_text)
        
        # For each potential name not already in glossary,
        # check if it appears in the translation context
        for chinese_name in potential_names:
            if chinese_name in self.names:
                continue  # Already known
            
            # Simple heuristic: if the name appears in source but not in translation,
            # it was likely translated
            if chinese_name not in translated_text:
                # This is a potential new name - mark for review
                # In practice, you'd use AI to extract the actual Burmese translation
                new_mappings.append((chinese_name, None))
        
        return new_mappings
    
    def get_stats(self) -> Dict:
        """
        Get glossary statistics.
        
        Returns:
            Dictionary with statistics
        """
        return {
            "novel_name": self.novel_name,
            "total_names": len(self.names),
            "file_path": str(self.glossary_file),
            "file_size_bytes": self.glossary_file.stat().st_size if self.glossary_file.exists() else 0,
            "last_updated": self.metadata.get("updated_at", "Never"),
            "created": self.metadata.get("created_at", "Unknown")
        }
    
    def print_summary(self):
        """Print glossary summary to console."""
        stats = self.get_stats()
        print("┌─────────────────────────────────────────┐")
        print("│ Glossary Summary                        │")
        print(f"│ Novel: {stats['novel_name']:<33} │")
        print(f"│ Names: {stats['total_names']:<33} │")
        print(f"│ File:  {self.glossary_file.name:<33} │")
        print("└─────────────────────────────────────────┘")


def get_glossary_for_novel(novel_name: str) -> GlossaryManager:
    """
    Factory function to get glossary manager for a novel.
    
    Args:
        novel_name: Name of the novel
        
    Returns:
        GlossaryManager instance
    """
    return GlossaryManager(novel_name)


def list_available_glossaries() -> List[str]:
    """
    List all available glossary files.
    
    Returns:
        List of novel names with glossaries
    """
    glossary_dir = GLOSSARY_DIR
    if not glossary_dir.exists():
        return []
    
    glossaries = []
    for f in glossary_dir.glob("*.json"):
        if f.stem != "":  # Skip empty names
            glossaries.append(f.stem)
    
    return sorted(glossaries)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python glossary_manager.py <novel_name> [command]")
        print("Commands:")
        print("  list              - List all names in glossary")
        print("  add <zh> <my>     - Add a name mapping")
        print("  stats             - Show glossary statistics")
        print("  extract <file>    - Extract potential names from file")
        print("\nAvailable glossaries:")
        for name in list_available_glossaries():
            print(f"  - {name}")
        sys.exit(1)
    
    novel_name = sys.argv[1]
    command = sys.argv[2] if len(sys.argv) > 2 else "stats"
    
    glossary = GlossaryManager(novel_name)
    
    if command == "list":
        names = glossary.get_names_list()
        if names:
            print(f"\nNames in {novel_name}:")
            for zh, my in names:
                print(f'  "{zh}" → "{my}"')
        else:
            print(f"No names in glossary for {novel_name}")
    
    elif command == "add" and len(sys.argv) >= 5:
        zh = sys.argv[3]
        my = sys.argv[4]
        if glossary.add_name(zh, my):
            glossary.save()
            print(f'✓ Added: "{zh}" → "{my}"')
        else:
            print(f'✗ Failed to add (may already exist)')
    
    elif command == "stats":
        glossary.print_summary()
    
    elif command == "extract" and len(sys.argv) >= 4:
        file_path = sys.argv[3]
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()
            names = glossary.extract_potential_names(text)
            print(f"\nPotential names found in {file_path}:")
            for name in names[:20]:  # Show first 20
                print(f"  - {name}")
            if len(names) > 20:
                print(f"  ... and {len(names) - 20} more")
        except Exception as e:
            print(f"✗ Error reading file: {e}")
    
    else:
        print(f"Unknown command: {command}")
        print("Run without arguments for usage help.")
