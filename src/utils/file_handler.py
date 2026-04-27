"""
File Handler Module
Handles reading and writing of all project files with proper encoding.
"""

import json
import logging
import yaml
import re
from pathlib import Path
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)


def _extract_chapter_num(filename: str) -> int:
    """Extract chapter number from filename for numeric sorting."""
    # New format: novel_name_chapter_XXX.md
    match = re.match(r'.+_chapter_(\d+)\.md', filename)
    if match:
        return int(match.group(1))
    # Legacy format: novel_name_XXX.md
    match = re.match(r'.+_(\d+)\.md', filename)
    if match:
        return int(match.group(1))
    return 0


class FileHandler:
    """Handles all file I/O operations with proper encoding and error handling."""
    
    @staticmethod
    def read_text(filepath: str) -> str:
        """Read text file with UTF-8-SIG encoding (handles BOM)."""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {filepath}")
        
        with open(path, 'r', encoding='utf-8-sig') as f:
            return f.read()
    
    @staticmethod
    def write_text(filepath: str, content: str) -> None:
        """Write text file with UTF-8 encoding."""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w', encoding='utf-8-sig') as f:
            f.write(content)
        
        logger.info(f"Written: {filepath}")
    
    @staticmethod
    def read_json(filepath: str) -> Dict[str, Any]:
        """Read JSON file with BOM handling."""
        path = Path(filepath)
        if not path.exists():
            return {}
        
        with open(path, 'r', encoding='utf-8-sig') as f:
            return json.load(f)
    
    @staticmethod
    def write_json(filepath: str, data: Dict[str, Any]) -> None:
        """Write JSON file atomically."""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        temp_path = path.with_suffix('.tmp')
        with open(temp_path, 'w', encoding='utf-8-sig') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        temp_path.replace(path)
        
        logger.debug(f"Saved JSON: {filepath}")
    
    @staticmethod
    def read_yaml(filepath: str) -> Dict[str, Any]:
        """Read YAML configuration file."""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Config not found: {filepath}")
        
        with open(path, 'r', encoding='utf-8-sig') as f:
            return yaml.safe_load(f)
    
    @staticmethod
    def list_chapters(input_dir: str, novel_name: str) -> List[Path]:
        """List all chapter files for a novel.
        
        Looks for files in:
        1. data/input/novel_name/novel_name_chapter_XXX.md (subdirectory)
        2. data/input/novel_name/novel_name_XXX.md (subdirectory, legacy)
        3. data/input/novel_name_chapter_XXX.md (flat structure)
        4. data/input/novel_name_XXX.md (flat structure, legacy)
        """
        path = Path(input_dir)
        if not path.exists():
            return []
        
        files = []
        
        # Pattern 1: Files in subdirectory (e.g., data/input/古道仙鸿/古道仙鸿_chapter_001.md)
        novel_dir = path / novel_name
        if novel_dir.exists() and novel_dir.is_dir():
            # Look for _chapter_ pattern first (new format)
            pattern1 = f"{novel_name}_chapter_*.md"
            files.extend(novel_dir.glob(pattern1))
            # Also look for legacy format (novel_name_XXX.md)
            pattern_legacy = f"{novel_name}_*.md"
            files.extend(novel_dir.glob(pattern_legacy))
        
        # Pattern 2: Flat structure in root input dir
        # Look for _chapter_ pattern first (new format)
        pattern2 = f"{novel_name}_chapter_*.md"
        files.extend(path.glob(pattern2))
        # Also look for legacy format (novel_name_XXX.md)
        pattern_flat_legacy = f"{novel_name}_*.md"
        files.extend(path.glob(pattern_flat_legacy))
        
        # Remove duplicates while preserving order
        seen = set()
        unique_files = []
        for f in files:
            if f not in seen:
                seen.add(f)
                unique_files.append(f)
        
        # Filter out non-chapter files like "(Copy)"
        files = [f for f in unique_files if '(Copy)' not in f.name and re.search(r'_\d+\.md$', f.name)]
        
        # Sort by chapter number to ensure correct numeric order
        def sort_key(p):
            name = p.name
            return _extract_chapter_num(name)
        
        files = sorted(files, key=sort_key)
        
        return files
    
    @staticmethod
    def ensure_dir(directory: str) -> Path:
        """Ensure directory exists, create if not."""
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        return path
