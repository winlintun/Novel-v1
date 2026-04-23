"""
Unit tests for MemoryManager.
"""

import unittest
import os
import json
import tempfile
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.memory.memory_manager import MemoryManager


class TestMemoryManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.glossary_path = os.path.join(self.temp_dir, "glossary.json")
        self.context_path = os.path.join(self.temp_dir, "context.json")
        
        # Initialize with empty files
        self.memory = MemoryManager(self.glossary_path, self.context_path)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_add_get_term(self):
        """Test adding and retrieving glossary terms."""
        self.memory.add_term("主角", "ဇော်ဂျီ", "character", 1)
        
        # Check retrieval
        target = self.memory.get_term("主角")
        self.assertEqual(target, "ဇော်ဂျီ")
        
        # Check glossary prompt formatting
        prompt = self.memory.get_glossary_for_prompt()
        self.assertIn("主角", prompt)
        self.assertIn("ဇော်ဂျီ", prompt)

    def test_context_buffer(self):
        """Test FIFO context buffer."""
        self.memory.push_to_buffer("Para 1")
        self.memory.push_to_buffer("Para 2")
        self.memory.push_to_buffer("Para 3")
        self.memory.push_to_buffer("Para 4")
        
        # Default get_context_buffer gets last 3
        context = self.memory.get_context_buffer(3)
        self.assertNotIn("Para 1", context)
        self.assertIn("Para 2", context)
        self.assertIn("Para 4", context)

    def test_persistence(self):
        """Test that data persists across instances."""
        self.memory.add_term("Item", "ပစ္စည်း", "item", 1)
        self.memory.push_to_buffer("Context text")
        self.memory.save_memory()
        
        # New instance
        new_memory = MemoryManager(self.glossary_path, self.context_path)
        self.assertEqual(new_memory.get_term("Item"), "ပစ္စည်း")
        self.assertIn("Context text", new_memory.get_context_buffer())

    def test_session_rules(self):
        """Test Tier 3 session rules."""
        self.memory.add_session_rule("Old", "New")
        rules = self.memory.get_session_rules()
        self.assertIn("Old -> New", rules)
        
        # Promote to glossary
        self.memory.promote_rule_to_glossary("Old", "New", 1)
        self.assertEqual(self.memory.get_term("Old"), "New")
        self.assertEqual(self.memory.get_session_rules(), "No session rules.")


if __name__ == '__main__':
    unittest.main()
