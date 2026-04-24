"""
Progress Logger Utility
Real-time translation progress tracking with live log file updates.
"""

import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


class ProgressLogger:
    """
    Logs translation progress to a dedicated file that updates after each chunk.
    
    Creates a readable markdown file showing:
    - Progress summary (chunks completed/total)
    - Each translated chunk as it's completed
    - Timestamps and status
    """
    
    def __init__(
        self,
        book_id: str,
        chapter_name: str,
        total_chunks: int,
        log_dir: str = "logs/progress",
    ):
        """
        Initialize progress logger.
        
        Args:
            book_id: Novel/book identifier
            chapter_name: Chapter identifier
            total_chunks: Total number of chunks to translate
            log_dir: Directory to store progress logs
        """
        self.book_id = book_id
        self.chapter_name = chapter_name
        self.total_chunks = total_chunks
        self.completed_chunks = 0
        self.start_time = datetime.now()
        
        # Create log directory
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate log filename
        timestamp = self.start_time.strftime('%Y%m%d_%H%M%S')
        safe_book = self._sanitize_filename(book_id)
        safe_chapter = self._sanitize_filename(chapter_name)
        self.log_file = self.log_dir / f"progress_{safe_book}_{safe_chapter}_{timestamp}.md"
        
        # Initialize log file with header
        self._write_header()
    
    def _sanitize_filename(self, name: str) -> str:
        """Sanitize string for use in filename."""
        # Remove or replace unsafe characters
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', name)
        # Limit length
        return sanitized[:50]
    
    def _write_header(self) -> None:
        """Write initial header to log file."""
        header = f"""# Translation Progress Log

## Session Info
- **Book:** {self.book_id}
- **Chapter:** {self.chapter_name}
- **Total Chunks:** {self.total_chunks}
- **Start Time:** {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}
- **Status:** 🔄 IN PROGRESS

## Progress Summary
- **Completed:** 0/{self.total_chunks} chunks (0%)
- **Last Update:** {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}

---

## Translated Chunks

"""
        self._write_to_file(header, mode='w')
    
    def _write_to_file(self, content: str, mode: str = 'a') -> None:
        """Write content to log file with proper encoding."""
        try:
            with open(self.log_file, mode, encoding='utf-8-sig') as f:
                f.write(content)
        except Exception as e:
            # Don't let logging errors break translation
            print(f"⚠️  Warning: Could not write progress log: {e}")
    
    def log_chunk(
        self,
        chunk_index: int,
        chunk_text: str,
        source_text: Optional[str] = None,
    ) -> None:
        """
        Log a completed chunk translation.
        
        Args:
            chunk_index: Index of the chunk (0-based)
            chunk_text: Translated Myanmar text
            source_text: Optional original Chinese text for reference
        """
        self.completed_chunks += 1
        current_time = datetime.now()
        elapsed = current_time - self.start_time
        
        # Build chunk entry
        entry_parts = [
            f"### Chunk {chunk_index + 1}/{self.total_chunks}",
            f"**Timestamp:** {current_time.strftime('%H:%M:%S')}",
            f"**Elapsed:** {self._format_elapsed(elapsed)}",
            "",
            "#### Myanmar Translation",
            "```",
            chunk_text,
            "```",
        ]
        
        # Optionally include source text
        if source_text:
            entry_parts.extend([
                "",
                "#### Source (Chinese)",
                "```",
                source_text[:500] + "..." if len(source_text) > 500 else source_text,
                "```",
            ])
        
        entry_parts.extend([
            "",
            "---",
            "",
        ])
        
        entry = "\n".join(entry_parts)
        self._write_to_file(entry)
        
        # Update summary at the top (rewrite entire file with updated summary)
        self._update_summary()
    
    def _update_summary(self) -> None:
        """Update the progress summary in the log file."""
        current_time = datetime.now()
        elapsed = current_time - self.start_time
        percentage = (self.completed_chunks / self.total_chunks * 100) if self.total_chunks > 0 else 0
        
        # Read current content (without header)
        try:
            with open(self.log_file, 'r', encoding='utf-8-sig') as f:
                lines = f.readlines()
            
            # Find where translated chunks start
            chunks_start = 0
            for i, line in enumerate(lines):
                if "## Translated Chunks" in line:
                    chunks_start = i
                    break
            
            chunks_content = lines[chunks_start:] if chunks_start > 0 else []
            
            # Build new header with updated summary
            header = f"""# Translation Progress Log

## Session Info
- **Book:** {self.book_id}
- **Chapter:** {self.chapter_name}
- **Total Chunks:** {self.total_chunks}
- **Start Time:** {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}
- **Status:** 🔄 IN PROGRESS

## Progress Summary
- **Completed:** {self.completed_chunks}/{self.total_chunks} chunks ({percentage:.1f}%)
- **Elapsed Time:** {self._format_elapsed(elapsed)}
- **Last Update:** {current_time.strftime('%Y-%m-%d %H:%M:%S')}

---

"""
            
            # Rewrite file with updated header
            with open(self.log_file, 'w', encoding='utf-8-sig') as f:
                f.write(header)
                # Write all chunk entries (including "## Translated Chunks" header)
                if chunks_content:
                    f.writelines(chunks_content)
                
        except Exception as e:
            print(f"⚠️  Warning: Could not update progress summary: {e}")
    
    def finalize(self, success: bool = True) -> None:
        """
        Mark the translation as complete in the progress log.
        
        Args:
            success: Whether translation completed successfully
        """
        current_time = datetime.now()
        elapsed = current_time - self.start_time
        percentage = (self.completed_chunks / self.total_chunks * 100) if self.total_chunks > 0 else 0
        status = "✅ COMPLETE" if success else "❌ FAILED"
        
        # Final summary
        final_entry = f"""
## Final Status

**{status}**

- **Total Chunks:** {self.completed_chunks}/{self.total_chunks}
- **Completion:** {percentage:.1f}%
- **Total Time:** {self._format_elapsed(elapsed)}
- **End Time:** {current_time.strftime('%Y-%m-%d %H:%M:%S')}

---

*Progress log saved to: {self.log_file}*
"""
        self._write_to_file(final_entry)
    
    def _format_elapsed(self, elapsed: timedelta) -> str:
        """Format elapsed time as human-readable string."""
        total_seconds = int(elapsed.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        
        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
    
    def get_log_path(self) -> Path:
        """Return the path to the progress log file."""
        return self.log_file
