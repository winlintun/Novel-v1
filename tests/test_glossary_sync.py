"""
Unit tests for GlossarySyncAgent using unittest.
"""

import unittest
from unittest.mock import Mock, patch
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.glossary_sync import GlossarySyncAgent
from src.memory.memory_manager import MemoryManager
from src.utils.ollama_client import OllamaClient


class TestGlossarySyncAgent(unittest.TestCase):
    """Test GlossarySyncAgent terminology consistency."""

    def setUp(self):
        """Set up test fixtures."""
        self.memory = Mock(spec=MemoryManager)
        self.memory.get_all_terms.return_value = [{"source": "A", "target": "B"}]
        self.client = Mock(spec=OllamaClient)

    def test_check_consistency(self):
        """Test consistency checking with mock response."""
        # Mock OllamaClient response
        self.client.chat.return_value = '{"inconsistencies": [{"term_in_text": "C", "glossary_term": "B", "suggestion": "B"}], "new_candidates": []}'

        # Mock json extractor
        with patch('src.utils.json_extractor.extract_json_from_response') as mock_extract:
            mock_extract.return_value = {
                "inconsistencies": [{"term_in_text": "C", "glossary_term": "B", "suggestion": "B"}],
                "new_candidates": []
            }

            agent = GlossarySyncAgent(self.memory, self.client)
            result = agent.check_consistency("Test chapter text with C", 1)

            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["term_in_text"], "C")

    def test_check_consistency_empty_response(self):
        """Test consistency checking with empty response."""
        self.client.chat.return_value = '{}'

        agent = GlossarySyncAgent(self.memory, self.client)
        result = agent.check_consistency("Test text", 1)

        self.assertEqual(len(result), 0)

    def test_propose_merges(self):
        """Test merge proposal functionality."""
        self.client.chat.return_value = '{"merge_suggestions": [{"pending_id": "p1", "approved_id": "a1"}]}'

        with patch('src.utils.json_extractor.extract_json_from_response') as mock_extract:
            mock_extract.return_value = {"merge_suggestions": [{"pending_id": "p1", "approved_id": "a1"}]}

            agent = GlossarySyncAgent(self.memory, self.client)
            result = agent.propose_merges()

            self.assertIsInstance(result, list)


if __name__ == '__main__':
    unittest.main()
