"""
Integration Tests for Novel Translation Pipeline
"""

import unittest
import sys
import tempfile
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.file_handler import FileHandler
from src.agents.preprocessor import Preprocessor
from src.memory.memory_manager import MemoryManager


class TestEndToEnd(unittest.TestCase):
    """End-to-end integration tests."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        
        # Create test directory structure
        self.input_dir = Path(self.temp_dir) / "input"
        self.output_dir = Path(self.temp_dir) / "output"
        self.input_dir.mkdir()
        self.output_dir.mkdir()
        
        # Create test chapter file
        self.chapter_file = self.input_dir / "test_novel_001.md"
        self.chapter_file.write_text(
            "# 第001章 测试章节\n\n这是第一段内容。\n\n这是第二段内容。\n\n这是第三段内容。",
            encoding='utf-8'
        )
    
    def tearDown(self):
        """Clean up."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_preprocessor_loads_chapter(self):
        """Test that preprocessor can load a chapter."""
        preprocessor = Preprocessor()
        
        chunks = preprocessor.load_and_preprocess(str(self.chapter_file))
        
        self.assertGreater(len(chunks), 0)
        self.assertIn("测试", chunks[0]['text'])
    
    def test_file_handler_lists_chapters(self):
        """Test listing chapter files."""
        chapters = FileHandler.list_chapters(str(self.input_dir), "test_novel")
        
        self.assertEqual(len(chapters), 1)
        self.assertEqual(chapters[0].name, "test_novel_001.md")
    
    def test_chapter_info_extraction(self):
        """Test chapter info extraction."""
        preprocessor = Preprocessor()
        info = preprocessor.get_chapter_info(str(self.chapter_file))
        
        self.assertEqual(info['novel_name'], 'test_novel')
        self.assertEqual(info['chapter_num'], 1)
    
    def test_memory_manager_persistence(self):
        """Test memory manager save/load cycle."""
        glossary_path = Path(self.temp_dir) / "glossary.json"
        context_path = Path(self.temp_dir) / "context.json"
        
        # Create and populate
        memory = MemoryManager(str(glossary_path), str(context_path))
        memory.add_term("主角", "ဇော်ဂျီ", "character", 1)
        memory.push_to_buffer("Test paragraph")
        memory.save_memory()
        
        # Load and verify
        new_memory = MemoryManager(str(glossary_path), str(context_path))
        
        self.assertEqual(new_memory.get_term("主角"), "ဇော်ဂျီ")


class TestChunking(unittest.TestCase):
    """Test text chunking behavior."""
    
    def test_small_text_single_chunk(self):
        """Test small text creates single chunk."""
        preprocessor = Preprocessor(chunk_size=1000)
        
        text = "Short text.\n\nAnother paragraph."
        chunks = preprocessor.create_chunks(text)
        
        self.assertEqual(len(chunks), 1)
    
    def test_large_text_multiple_chunks(self):
        """Test large text creates multiple chunks."""
        preprocessor = Preprocessor(chunk_size=100)
        
        # Create text larger than chunk size with multiple paragraphs
        paragraphs = ["这是一段中文测试内容。" for _ in range(50)]
        text = "\n\n".join(paragraphs)
        chunks = preprocessor.create_chunks(text)
        
        self.assertGreater(len(chunks), 1)
    
    def test_smart_chunk_paragraph_only(self):
        """Test that chunks never split inside paragraphs (per need_to_fix.md spec)."""
        from src.utils.chunker import smart_chunk
        
        paragraphs = [f"第{i}段内容在这里。" for i in range(10)]
        text = "\n\n".join(paragraphs)

        chunks = smart_chunk(text, max_tokens=100)
        
        # Verify: no paragraph appears in more than one chunk
        all_paragraphs = set()
        for chunk_text in chunks:
            for para in chunk_text.split('\n\n'):
                self.assertNotIn(para, all_paragraphs,
                    f"Paragraph '{para[:20]}...' appears in multiple chunks!")
                all_paragraphs.add(para)
        
        # Verify: all original paragraphs are present
        self.assertEqual(len(all_paragraphs), len(paragraphs))


class TestConfigLoading(unittest.TestCase):
    """Test configuration loading."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_load_yaml_config(self):
        """Test loading YAML configuration."""
        config_path = Path(self.temp_dir) / "config.yaml"
        config_content = """
models:
  translator: "qwen2.5:14b"
  provider: "ollama"

paths:
  input_dir: "data/input"
  output_dir: "data/output"
"""
        config_path.write_text(config_content, encoding='utf-8')
        
        config = FileHandler.read_yaml(str(config_path))
        
        self.assertEqual(config['models']['translator'], "qwen2.5:14b")
        self.assertEqual(config['paths']['input_dir'], "data/input")


class TestFileOperations(unittest.TestCase):
    """Test file operations."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_atomic_json_write(self):
        """Test atomic JSON write doesn't corrupt on failure."""
        filepath = Path(self.temp_dir) / "test.json"
        data = {"key": "value", "number": 42}
        
        FileHandler.write_json(str(filepath), data)
        
        # Verify file exists and is valid JSON
        self.assertTrue(filepath.exists())
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            loaded = json.load(f)
        
        self.assertEqual(loaded, data)
    
    def test_read_text_with_bom(self):
        """Test reading text with UTF-8 BOM."""
        filepath = Path(self.temp_dir) / "bom.txt"
        
        # Write with BOM
        content = "Test content with Myanmar: မြန်မာ"
        with open(filepath, 'w', encoding='utf-8-sig') as f:
            f.write(content)
        
        # Read should handle BOM
        result = FileHandler.read_text(str(filepath))
        self.assertEqual(result, content)


if __name__ == '__main__':
    unittest.main(verbosity=2)
