#!/usr/bin/env python3
"""
Checkpoint Manager - Save and resume translation progress
"""

import json
import shutil
from pathlib import Path
from typing import Dict, Optional


class CheckpointManager:
    """Manage translation checkpoints."""
    
    def __init__(self, chapter_name: str):
        self.chapter_name = chapter_name
        self.checkpoint_dir = Path("working_data/checkpoints") / chapter_name
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
    
    def save(self, chunk_index: int, translated_text: str):
        """Save a translated chunk to checkpoint."""
        chunk_file = self.checkpoint_dir / f"chunk_{chunk_index:03d}.txt"
        with open(chunk_file, 'w', encoding='utf-8') as f:
            f.write(translated_text)
    
    def load(self, chunk_index: int) -> Optional[str]:
        """Load a specific checkpoint chunk."""
        chunk_file = self.checkpoint_dir / f"chunk_{chunk_index:03d}.txt"
        if chunk_file.exists():
            with open(chunk_file, 'r', encoding='utf-8') as f:
                return f.read()
        return None
    
    def load_all(self) -> Dict[int, str]:
        """Load all existing checkpoint files."""
        checkpoints = {}
        
        for chunk_file in sorted(self.checkpoint_dir.glob("chunk_*.txt")):
            # Extract index from filename
            match = chunk_file.stem.split('_')
            if len(match) >= 2 and match[1].isdigit():
                index = int(match[1])
                with open(chunk_file, 'r', encoding='utf-8') as f:
                    checkpoints[index] = f.read()
        
        return checkpoints
    
    def is_done(self, chunk_index: int) -> bool:
        """Check if a chunk has been translated."""
        chunk_file = self.checkpoint_dir / f"chunk_{chunk_index:03d}.txt"
        return chunk_file.exists() and chunk_file.stat().st_size > 0
    
    def get_completed_count(self) -> int:
        """Get number of completed chunks."""
        return len(list(self.checkpoint_dir.glob("chunk_*.txt")))
    
    def clear_all(self):
        """Delete checkpoint folder after final assembly."""
        if self.checkpoint_dir.exists():
            shutil.rmtree(self.checkpoint_dir)
            print(f"✓ Cleared checkpoints for {self.chapter_name}")
    
    def print_resume_info(self, total_chunks: int):
        """Print resume detection message."""
        completed = self.get_completed_count()
        
        if completed > 0 and completed < total_chunks:
            print("┌─────────────────────────────────────────┐")
            print("│ Resume detected!                        │")
            print(f"│ Chunks already done : {completed} / {total_chunks:<10} │")
            print(f"│ Continuing from     : chunk {completed + 1:<9} │")
            print("└─────────────────────────────────────────┘")
            return completed
        return 0


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python checkpoint.py <chapter_name> [command]")
        print("Commands: list, clear")
        sys.exit(1)
    
    chapter_name = sys.argv[1]
    cmd = sys.argv[2] if len(sys.argv) >= 3 else "list"
    
    cm = CheckpointManager(chapter_name)
    
    if cmd == "list":
        checkpoints = cm.load_all()
        print(f"Checkpoints for {chapter_name}:")
        for idx in sorted(checkpoints.keys()):
            preview = checkpoints[idx][:50].replace('\n', ' ')
            print(f"  chunk_{idx:03d}.txt: {preview}...")
    elif cmd == "clear":
        cm.clear_all()
    else:
        print(f"Unknown command: {cmd}")
