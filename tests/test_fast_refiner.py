"""
Tests for FastRefiner agent.
"""

import unittest
from unittest.mock import MagicMock


class TestFastRefiner(unittest.TestCase):
    """Test cases for FastRefiner."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_ollama = MagicMock()

    def test_initialization(self):
        """FastRefiner initializes with required parameters."""
        from src.agents.fast_refiner import FastRefiner
        
        refiner = FastRefiner(
            ollama_client=self.mock_ollama,
            batch_size=5
        )
        
        self.assertEqual(refiner.ollama, self.mock_ollama)
        self.assertEqual(refiner.batch_size, 5)

    def test_initialization_default_batch_size(self):
        """FastRefiner works with default batch size."""
        from src.agents.fast_refiner import FastRefiner
        
        refiner = FastRefiner(ollama_client=self.mock_ollama)
        
        self.assertEqual(refiner.batch_size, 5)

    def test_create_batches_splits_paragraphs(self):
        """create_batches groups paragraphs into batches."""
        from src.agents.fast_refiner import FastRefiner
        
        refiner = FastRefiner(ollama_client=self.mock_ollama, batch_size=2)
        
        paragraphs = ["para1", "para2", "para3", "para4"]
        batches = refiner.create_batches(paragraphs)
        
        self.assertIsInstance(batches, list)
        self.assertGreater(len(batches), 0)

    def test_create_batches_handles_empty_list(self):
        """create_batches handles empty input."""
        from src.agents.fast_refiner import FastRefiner
        
        refiner = FastRefiner(ollama_client=self.mock_ollama)
        
        batches = refiner.create_batches([])
        
        self.assertEqual(batches, [])

    def test_create_batches_single_paragraph(self):
        """create_batches works with single paragraph."""
        from src.agents.fast_refiner import FastRefiner
        
        refiner = FastRefiner(ollama_client=self.mock_ollama)
        
        batches = refiner.create_batches(["single"])
        
        self.assertIsInstance(batches, list)
        self.assertEqual(len(batches), 1)

    def test_refine_batch_returns_list(self):
        """refine_batch returns refined paragraphs."""
        from src.agents.fast_refiner import FastRefiner
        
        refiner = FastRefiner(ollama_client=self.mock_ollama)
        
        self.mock_ollama.chat.return_value = {"message": {"content": "refined"}}
        
        batch = ["original paragraph"]
        result = refiner.refine_batch(batch)
        
        self.assertIsInstance(result, list)

    def test_refine_chapter_returns_list(self):
        """refine_chapter processes all paragraphs."""
        from src.agents.fast_refiner import FastRefiner
        
        refiner = FastRefiner(ollama_client=self.mock_ollama)
        
        self.mock_ollama.chat.return_value = {"message": {"content": "refined"}}
        
        paragraphs = ["para1", "para2"]
        result = refiner.refine_chapter(paragraphs)
        
        self.assertIsInstance(result, list)

    def test_refine_full_text_returns_string(self):
        """refine_full_text returns combined text."""
        from src.agents.fast_refiner import FastRefiner
        
        refiner = FastRefiner(ollama_client=self.mock_ollama)
        
        self.mock_ollama.chat.return_value = {"message": {"content": "refined\n\nrefined"}}
        
        text = "original\n\noriginal"
        result = refiner.refine_full_text(text)
        
        self.assertIsInstance(result, str)


class TestFastRefinerEdgeCases(unittest.TestCase):
    """Test FastRefiner edge cases."""

    def test_refine_batch_empty_batch(self):
        """refine_batch handles empty batch."""
        from src.agents.fast_refiner import FastRefiner
        
        refiner = FastRefiner(ollama_client=MagicMock())
        
        result = refiner.refine_batch([])
        
        self.assertEqual(result, [])

    def test_create_batches_respects_size_limit(self):
        """create_batches respects max batch size."""
        from src.agents.fast_refiner import FastRefiner
        
        refiner = FastRefiner(ollama_client=MagicMock(), batch_size=2)
        
        paragraphs = ["p1", "p2", "p3", "p4", "p5"]
        batches = refiner.create_batches(paragraphs)
        
        for batch in batches:
            self.assertLessEqual(len(batch), 2)


if __name__ == "__main__":
    unittest.main()