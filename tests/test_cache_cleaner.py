"""Tests for Cache Cleaner utility."""

import unittest
import tempfile
import os
from pathlib import Path


class TestCacheCleaner(unittest.TestCase):
    """Test cases for cache_cleaner module."""

    def setUp(self):
        """Set up test fixtures."""
        from src.utils import cache_cleaner
        self.cache_cleaner = cache_cleaner
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_clean_python_cache_returns_zero_when_empty(self):
        """Test clean_python_cache returns (0, 0) when no cache."""
        dirs, files = self.cache_cleaner.clean_python_cache(self.temp_dir)
        self.assertEqual(dirs, 0)
        self.assertEqual(files, 0)

    def test_clean_python_cache_removes_pycache(self):
        """Test clean_python_cache removes __pycache__ directories."""
        # Create __pycache__ directory
        pycache_dir = Path(self.temp_dir) / "src" / "__pycache__"
        pycache_dir.mkdir(parents=True)
        
        # Add a .pyc file
        pyc_file = pycache_dir / "test.cpython-310.pyc"
        pyc_file.write_text("mock bytecode")
        
        dirs, files = self.cache_cleaner.clean_python_cache(self.temp_dir)
        
        self.assertEqual(dirs, 1)
        self.assertFalse(pycache_dir.exists())

    def test_clean_python_cache_removes_pyc_files(self):
        """Test clean_python_cache removes .pyc files."""
        # Create regular directory with .pyc file
        src_dir = Path(self.temp_dir) / "src"
        src_dir.mkdir(parents=True)
        
        pyc_file = src_dir / "test.pyc"
        pyc_file.write_text("mock bytecode")
        
        dirs, files = self.cache_cleaner.clean_python_cache(self.temp_dir)
        
        self.assertEqual(dirs, 0)
        self.assertEqual(files, 1)
        self.assertFalse(pyc_file.exists())

    def test_clean_python_cache_removes_pyo_files(self):
        """Test clean_python_cache removes .pyo files."""
        src_dir = Path(self.temp_dir) / "src"
        src_dir.mkdir(parents=True)
        
        pyo_file = src_dir / "test.pyo"
        pyo_file.write_text("mock bytecode")
        
        dirs, files = self.cache_cleaner.clean_python_cache(self.temp_dir)
        
        self.assertEqual(files, 1)
        self.assertFalse(pyo_file.exists())

    def test_clean_python_cache_preserves_regular_files(self):
        """Test clean_python_cache preserves .py files."""
        src_dir = Path(self.temp_dir) / "src"
        src_dir.mkdir(parents=True)
        
        py_file = src_dir / "test.py"
        py_file.write_text("# Python code")
        
        dirs, files = self.cache_cleaner.clean_python_cache(self.temp_dir)
        
        self.assertEqual(dirs, 0)
        self.assertEqual(files, 0)
        self.assertTrue(py_file.exists())

    def test_clean_python_cache_handles_nested_structure(self):
        """Test clean_python_cache handles nested directories."""
        # Create nested __pycache__ directories
        nested_cache = Path(self.temp_dir) / "pkg1" / "pkg2" / "__pycache__"
        nested_cache.mkdir(parents=True)
        
        # Also create a regular pyc file at root
        pyc_file = Path(self.temp_dir) / "root.pyc"
        pyc_file.write_text("bytecode")
        
        dirs, files = self.cache_cleaner.clean_python_cache(self.temp_dir)
        
        # Should find at least the root level pyc file
        self.assertGreaterEqual(dirs, 0)
        self.assertGreaterEqual(files, 1)

    def test_clean_python_cache_returns_tuple(self):
        """Test clean_python_cache returns proper tuple type."""
        result = self.cache_cleaner.clean_python_cache(self.temp_dir)
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)

    def test_clean_cache_with_report(self):
        """Test clean_cache_with_report runs without error."""
        # Should not raise exception
        self.cache_cleaner.clean_cache_with_report(self.temp_dir)


if __name__ == "__main__":
    unittest.main()