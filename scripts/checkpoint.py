#!/usr/bin/env python3
"""
Checkpoint Manager - Save and resume translation progress
"""

import json
import shutil
import re
import fcntl
import os
from pathlib import Path
from typing import Dict, Optional


# Regex pattern for extracting chunk index from filename
CHUNK_FILENAME_PATTERN = re.compile(r'chunk_(\d+)\.txt$')


class CheckpointManager:
    """Manage translation checkpoints with file locking for thread safety."""
    
    def __init__(self, chapter_name: str):
        self.chapter_name = chapter_name
        self.checkpoint_dir = Path("working_data/checkpoints") / chapter_name
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.lock_file = self.checkpoint_dir / ".lock"
    
    def _acquire_lock(self, exclusive: bool = True) -> Optional[int]:
        """Acquire file lock for thread-safe access.
        
        Args:
            exclusive: If True, acquire exclusive lock. If False, shared lock.
            
        Returns:
            File descriptor if lock acquired, None otherwise.
        """
        try:
            fd = os.open(str(self.lock_file), os.O_RDWR | os.O_CREAT)
            if exclusive:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            else:
                fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
            return fd
        except (IOError, OSError):
            return None
    
    def _release_lock(self, fd: Optional[int]) -> None:
        """Release file lock."""
        if fd is not None:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
                os.close(fd)
            except (IOError, OSError):
                pass
    
    def save(self, chunk_index: int, translated_text: str) -> bool:
        """Save a translated chunk to checkpoint with file locking.
        
        Args:
            chunk_index: The index of the chunk.
            translated_text: The translated text to save.
            
        Returns:
            True if saved successfully, False otherwise.
        """
        fd = self._acquire_lock(exclusive=True)
        if fd is None:
            return False
        
        try:
            chunk_file = self.checkpoint_dir / f"chunk_{chunk_index:03d}.txt"
            with open(chunk_file, 'w', encoding='utf-8') as f:
                f.write(translated_text)
            return True
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to save checkpoint {chunk_index}: {e}")
            return False
        finally:
            self._release_lock(fd)
    
    def load(self, chunk_index: int) -> Optional[str]:
        """Load a specific checkpoint chunk with file locking."""
        fd = self._acquire_lock(exclusive=False)
        if fd is None:
            return None
        
        try:
            chunk_file = self.checkpoint_dir / f"chunk_{chunk_index:03d}.txt"
            if chunk_file.exists():
                with open(chunk_file, 'r', encoding='utf-8') as f:
                    return f.read()
            return None
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to load checkpoint {chunk_index}: {e}")
            return None
        finally:
            self._release_lock(fd)
    
    def load_all(self) -> Dict[int, str]:
        """Load all existing checkpoint files using regex for robust parsing."""
        fd = self._acquire_lock(exclusive=False)
        if fd is None:
            return {}
        
        try:
            checkpoints = {}
            
            for chunk_file in sorted(self.checkpoint_dir.glob("chunk_*.txt")):
                # Use regex for robust chunk index extraction
                match = CHUNK_FILENAME_PATTERN.search(chunk_file.name)
                if match:
                    index = int(match.group(1))
                    try:
                        with open(chunk_file, 'r', encoding='utf-8') as f:
                            checkpoints[index] = f.read()
                    except Exception as e:
                        import logging
                        logging.getLogger(__name__).warning(f"Failed to read chunk file {chunk_file}: {e}")
            
            return checkpoints
        finally:
            self._release_lock(fd)
    
    def is_done(self, chunk_index: int) -> bool:
        """Check if a chunk has been translated."""
        fd = self._acquire_lock(exclusive=False)
        if fd is None:
            return False
        
        try:
            chunk_file = self.checkpoint_dir / f"chunk_{chunk_index:03d}.txt"
            return chunk_file.exists() and chunk_file.stat().st_size > 0
        except Exception:
            return False
        finally:
            self._release_lock(fd)
    
    def get_completed_count(self) -> int:
        """Get number of completed chunks."""
        fd = self._acquire_lock(exclusive=False)
        if fd is None:
            return 0
        
        try:
            return len(list(self.checkpoint_dir.glob("chunk_*.txt")))
        finally:
            self._release_lock(fd)
    
    def clear_all(self):
        """Delete checkpoint folder after final assembly."""
        fd = self._acquire_lock(exclusive=True)
        if fd is None:
            return
        
        try:
            if self.checkpoint_dir.exists():
                shutil.rmtree(self.checkpoint_dir)
                print(f"✓ Cleared checkpoints for {self.chapter_name}")
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to clear checkpoints: {e}")
        finally:
            self._release_lock(fd)
    
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
