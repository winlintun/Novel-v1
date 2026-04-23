"""
Unit tests for QATesterAgent using unittest.
"""

import unittest
from unittest.mock import Mock
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.qa_tester import QATesterAgent
from src.memory.memory_manager import MemoryManager


class TestQATesterAgent(unittest.TestCase):
    """Test QATesterAgent quality checks."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.memory = Mock(spec=MemoryManager)
        self.memory.get_all_terms.return_value = [
            {"source": "A", "target": "မြန်မာစာ", "frequency": 10}
        ]
        self.qa_agent = QATesterAgent(self.memory)
    
    def test_validate_output_passed(self):
        """Test validation passes for good output."""
        text = "# Chapter 1\n\nမြန်မာစာသည်လှပသည်။ မြန်မာစာသည်လှပသည်။ မြန်မာစာသည်လှပသည်။"
        report = self.qa_agent.validate_output(text, 1)
        
        self.assertTrue(report["passed"])
        self.assertEqual(len(report["issues"]), 0)
        self.assertEqual(report["chapter"], 1)
    
    def test_validate_output_failed_markdown(self):
        """Test validation fails for bad markdown."""
        text = "# Chapter 1\n# Title 2\n**Bold text without close"
        report = self.qa_agent.validate_output(text, 1)
        
        self.assertFalse(report["passed"])
        self.assertTrue(any("chapter title" in str(issue).lower() for issue in report["issues"]))
    
    def test_validate_output_low_myanmar_ratio(self):
        """Test validation fails for low Myanmar content."""
        text = "# Chapter 1\n\nEnglish text here."
        report = self.qa_agent.validate_output(text, 1)
        
        self.assertFalse(report["passed"])
        self.assertTrue(any("myanmar" in str(issue).lower() for issue in report["issues"]))
    
    def test_validate_output_short_text(self):
        """Test validation fails for very short text."""
        text = "Short"
        report = self.qa_agent.validate_output(text, 1)
        
        # Short text should fail due to low Myanmar ratio or missing chapter title
        self.assertFalse(report["passed"])


if __name__ == '__main__':
    unittest.main()
