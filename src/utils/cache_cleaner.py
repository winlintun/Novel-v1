#!/usr/bin/env python3
"""
Cache Cleaner Utility
Clears Python __pycache__ directories and .pyc files to ensure fresh code execution.
"""

import os
import shutil
import logging
from pathlib import Path
from typing import List, Tuple

logger = logging.getLogger(__name__)


def clean_python_cache(project_root: str = ".") -> Tuple[int, int]:
    """Clean all Python cache files and directories.
    
    Args:
        project_root: Root directory to start cleaning from
        
    Returns:
        Tuple of (directories_removed, files_removed)
    """
    dirs_removed = 0
    files_removed = 0
    
    root_path = Path(project_root).resolve()
    
    logger.info(f"🧹 Cleaning Python cache from: {root_path}")
    
    # Walk through all directories
    for path in root_path.rglob("*"):
        if path.is_dir():
            # Remove __pycache__ directories
            if path.name == "__pycache__":
                try:
                    shutil.rmtree(path)
                    dirs_removed += 1
                    logger.debug(f"  Removed directory: {path.relative_to(root_path)}")
                except Exception as e:
                    logger.warning(f"  Failed to remove {path}: {e}")
                    
        elif path.is_file():
            # Remove .pyc and .pyo files
            if path.suffix in ('.pyc', '.pyo'):
                try:
                    path.unlink()
                    files_removed += 1
                    logger.debug(f"  Removed file: {path.relative_to(root_path)}")
                except Exception as e:
                    logger.warning(f"  Failed to remove {path}: {e}")
    
    if dirs_removed > 0 or files_removed > 0:
        logger.info(f"✅ Cache cleaned: {dirs_removed} directories, {files_removed} files removed")
    else:
        logger.info("✅ No cache files found (already clean)")
    
    return dirs_removed, files_removed


def clean_cache_with_report(project_root: str = ".") -> None:
    """Clean cache and print a formatted report.
    
    Args:
        project_root: Root directory to start cleaning from
    """
    print("=" * 70)
    print("  🧹 CLEANING PYTHON CACHE")
    print("=" * 70)
    print()
    
    dirs, files = clean_python_cache(project_root)
    
    print(f"  Directories removed: {dirs}")
    print(f"  Files removed: {files}")
    print()
    print("=" * 70)
    print()


if __name__ == "__main__":
    # Setup basic logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(message)s'
    )
    
    # Run cleaner
    clean_cache_with_report()
