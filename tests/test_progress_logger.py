"""
Unit tests for ProgressLogger utility.
"""

import unittest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta

from src.utils.progress_logger import ProgressLogger


class TestProgressLogger(unittest.TestCase):
    """Test cases for ProgressLogger class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.book_id = "TestBook"
        self.chapter_name = "ch001"
        self.total_chunks = 5
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_initialization(self):
        """Test ProgressLogger initializes correctly."""
        logger = ProgressLogger(
            book_id=self.book_id,
            chapter_name=self.chapter_name,
            total_chunks=self.total_chunks,
            log_dir=self.temp_dir
        )
        
        self.assertEqual(logger.book_id, self.book_id)
        self.assertEqual(logger.chapter_name, self.chapter_name)
        self.assertEqual(logger.total_chunks, self.total_chunks)
        self.assertEqual(logger.completed_chunks, 0)
        self.assertTrue(logger.log_file.exists())
    
    def test_log_chunk(self):
        """Test logging a single chunk."""
        logger = ProgressLogger(
            book_id=self.book_id,
            chapter_name=self.chapter_name,
            total_chunks=3,
            log_dir=self.temp_dir
        )
        
        # Log a chunk
        logger.log_chunk(
            chunk_index=0,
            chunk_text="လူချင်း တောင်ထိပ်၌ ရပ်လျက်",
            source_text="罗青站在山巅"
        )
        
        self.assertEqual(logger.completed_chunks, 1)
        
        # Verify file content
        content = logger.log_file.read_text(encoding='utf-8-sig')
        self.assertIn("Chunk 1/3", content)
        self.assertIn("လူချင်း တောင်ထိပ်၌ ရပ်လျက်", content)
        self.assertIn("罗青站在山巅", content)
    
    def test_log_multiple_chunks(self):
        """Test logging multiple chunks."""
        logger = ProgressLogger(
            book_id=self.book_id,
            chapter_name=self.chapter_name,
            total_chunks=3,
            log_dir=self.temp_dir
        )
        
        # Log multiple chunks
        for i in range(3):
            logger.log_chunk(
                chunk_index=i,
                chunk_text=f"Myanmar text {i+1}",
                source_text=f"Chinese text {i+1}"
            )
        
        self.assertEqual(logger.completed_chunks, 3)
        
        # Verify all chunks are in file
        content = logger.log_file.read_text(encoding='utf-8-sig')
        self.assertIn("Chunk 1/3", content)
        self.assertIn("Chunk 2/3", content)
        self.assertIn("Chunk 3/3", content)
    
    def test_finalize_success(self):
        """Test finalizing with success status."""
        logger = ProgressLogger(
            book_id=self.book_id,
            chapter_name=self.chapter_name,
            total_chunks=2,
            log_dir=self.temp_dir
        )
        
        # Log some chunks
        logger.log_chunk(0, "Text 1", "Source 1")
        logger.finalize(success=True)
        
        # Verify final status
        content = logger.log_file.read_text(encoding='utf-8-sig')
        self.assertIn("COMPLETE", content)
        self.assertIn("1/2", content)
        self.assertIn("50.0%", content)
    
    def test_finalize_failure(self):
        """Test finalizing with failure status."""
        logger = ProgressLogger(
            book_id=self.book_id,
            chapter_name=self.chapter_name,
            total_chunks=5,
            log_dir=self.temp_dir
        )
        
        # Log some chunks then fail
        logger.log_chunk(0, "Text 1", "Source 1")
        logger.log_chunk(1, "Text 2", "Source 2")
        logger.finalize(success=False)
        
        # Verify final status
        content = logger.log_file.read_text(encoding='utf-8-sig')
        self.assertIn("FAILED", content)
        self.assertIn("2/5", content)
    
    def test_sanitize_filename(self):
        """Test filename sanitization."""
        logger = ProgressLogger(
            book_id="Book<>:Name",
            chapter_name="ch|001?",
            total_chunks=1,
            log_dir=self.temp_dir
        )
        
        # Filename should not contain special characters
        filename = logger.log_file.name
        self.assertNotIn("<", filename)
        self.assertNotIn(">", filename)
        self.assertNotIn(":", filename)
        self.assertNotIn("|", filename)
        self.assertNotIn("?", filename)
    
    def test_format_elapsed(self):
        """Test elapsed time formatting."""
        from datetime import timedelta
        
        logger = ProgressLogger(
            book_id=self.book_id,
            chapter_name=self.chapter_name,
            total_chunks=1,
            log_dir=self.temp_dir
        )
        
        # Test various durations
        self.assertEqual(logger._format_elapsed(timedelta(seconds=45)), "45s")
        self.assertEqual(logger._format_elapsed(timedelta(minutes=5, seconds=30)), "5m 30s")
        self.assertEqual(logger._format_elapsed(timedelta(hours=2, minutes=30)), "2h 30m 0s")
    
    def test_encoding_utf8_sig(self):
        """Test that files are written with UTF-8-SIG encoding."""
        logger = ProgressLogger(
            book_id=self.book_id,
            chapter_name=self.chapter_name,
            total_chunks=1,
            log_dir=self.temp_dir
        )
        
        logger.log_chunk(0, "မြန်မာစာ", "中文")
        
        # Read raw bytes to check for BOM
        raw_bytes = logger.log_file.read_bytes()
        # UTF-8-SIG should start with BOM (EF BB BF)
        self.assertTrue(raw_bytes.startswith(b'\xef\xbb\xbf') or 
                       b'\xef\xbb\xbf' in raw_bytes[:10])
    
    def test_get_log_path(self):
        """Test get_log_path method."""
        logger = ProgressLogger(
            book_id=self.book_id,
            chapter_name=self.chapter_name,
            total_chunks=1,
            log_dir=self.temp_dir
        )
        
        path = logger.get_log_path()
        self.assertIsInstance(path, Path)
        self.assertEqual(path, logger.log_file)
    
    def test_log_chunk_without_source(self):
        """Test logging chunk without source text."""
        logger = ProgressLogger(
            book_id=self.book_id,
            chapter_name=self.chapter_name,
            total_chunks=1,
            log_dir=self.temp_dir
        )
        
        logger.log_chunk(
            chunk_index=0,
            chunk_text="Myanmar text only"
        )
        
        content = logger.log_file.read_text(encoding='utf-8-sig')
        self.assertIn("Myanmar text only", content)
        self.assertNotIn("Source (Chinese)", content)
    
    def test_progress_summary_updates(self):
        """Test that progress summary is updated correctly."""
        logger = ProgressLogger(
            book_id=self.book_id,
            chapter_name=self.chapter_name,
            total_chunks=4,
            log_dir=self.temp_dir
        )
        
        # Log 2 out of 4 chunks
        logger.log_chunk(0, "Text 1", "Source 1")
        logger.log_chunk(1, "Text 2", "Source 2")
        
        # Check summary shows 50%
        content = logger.log_file.read_text(encoding='utf-8-sig')
        self.assertIn("**Completed:** 2/4 chunks (50.0%)", content)


if __name__ == '__main__':
    unittest.main()
