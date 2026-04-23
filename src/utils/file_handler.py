"""
File Handler Module
Handles reading and writing of all project files with proper encoding.
"""

import json
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


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
        
        with open(path, 'w', encoding='utf-8') as f:
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
        with open(temp_path, 'w', encoding='utf-8') as f:
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
        """List all chapter files for a novel."""
        path = Path(input_dir)
        if not path.exists():
            return []
        
        # Find files matching pattern: novel_name_XXX.md
        pattern = f"{novel_name}_*.md"
        files = sorted(path.glob(pattern))
        
        return files
    
    @staticmethod
    def ensure_dir(directory: str) -> Path:
        """Ensure directory exists, create if not."""
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        return path
