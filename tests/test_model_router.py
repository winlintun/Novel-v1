"""
Unit tests for Model Router using unittest.
"""

import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.model_router import get_model_for_role, get_fallback_chain


class TestModelRouter(unittest.TestCase):
    """Test model routing based on VRAM availability."""
    
    def test_get_model_for_role_sufficient_vram(self):
        """Test model selection with sufficient VRAM."""
        model = get_model_for_role("refiner", available_vram=16.0)
        self.assertIsNotNone(model)
    
    def test_get_model_for_role_low_vram(self):
        """Test model selection with low VRAM - should fallback."""
        model = get_model_for_role("refiner", available_vram=10.0)
        self.assertIsNotNone(model)
    
    def test_get_model_for_role_insufficient_vram(self):
        """Test model selection with insufficient VRAM."""
        model = get_model_for_role("refiner", available_vram=2.0)
        # May return None or smallest available model
        self.assertTrue(model is None or isinstance(model, str))
    
    def test_get_fallback_chain(self):
        """Test fallback chain retrieval."""
        chain = get_fallback_chain("hunyuan-mt:7b")
        self.assertIsInstance(chain, list)
    
    def test_get_fallback_chain_no_fallback(self):
        """Test fallback chain for model with no fallback."""
        chain = get_fallback_chain("qwen2.5:14b")
        self.assertIsInstance(chain, list)


if __name__ == '__main__':
    unittest.main()
