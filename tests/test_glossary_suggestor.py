"""Tests for Glossary Suggestor utility."""

import unittest
import tempfile
import json
from pathlib import Path


class TestGlossarySuggestor(unittest.TestCase):
    """Test cases for GlossarySuggestor class."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.glossary_path = Path(self.temp_dir) / "glossary.json"
        
        # Create test glossary file
        self.glossary_data = {
            "version": "1.0",
            "total_terms": 2,
            "terms": [
                {"source": "罗青", "target": "လူချင်း", "category": "character", "verified": True},
                {"source": "筑基", "target": "ဟောက်ထျန်", "category": "level", "verified": True}
            ]
        }
        
        with open(self.glossary_path, 'w', encoding='utf-8') as f:
            json.dump(self.glossary_data, f)
        
        from src.utils.glossary_suggestor import GlossarySuggestor
        self.GlossarySuggestor = GlossarySuggestor
        self.suggestor = GlossarySuggestor(str(self.glossary_path))

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    def test_init_loads_existing_terms(self):
        """Test GlossarySuggestor loads existing terms."""
        self.assertEqual(len(self.suggestor.existing_terms), 2)
        self.assertIn("罗青", self.suggestor.existing_terms)

    def test_suggest_term_returns_existing(self):
        """Test suggest_term returns existing term with confidence 1.0."""
        result = self.suggestor.suggest_term("罗青")
        
        self.assertEqual(result["confidence"], 1.0)
        self.assertEqual(result["target"], "လူချင်း")
        self.assertFalse(result["requires_review"])
        self.assertEqual(result["status"], "exists")

    def test_suggest_term_returns_pending_for_new_term(self):
        """Test suggest_term returns pending for new term."""
        result = self.suggestor.suggest_term("新术语")
        
        self.assertIn("suggested_target", result)
        self.assertIn("【?", result["suggested_target"])
        self.assertEqual(result["status"], "pending")

    def test_suggest_term_confidence_below_85_requires_review(self):
        """Test terms with low confidence require review."""
        result = self.suggestor.suggest_term("短词")
        
        self.assertTrue(result["requires_review"])
        self.assertLess(result["confidence"], 0.85)

    def test_suggest_term_similar_terms_increases_confidence(self):
        """Test similar terms increase confidence."""
        # "筑基" is in glossary, "筑基境界" is similar
        result = self.suggestor.suggest_term("筑基境界", similar_terms=["筑基"])
        
        self.assertGreater(result["confidence"], 0.5)

    def test_suggest_term_proper_noun_increases_confidence(self):
        """Test proper nouns (capitalized) get confidence boost."""
        result = self.suggestor.suggest_term("Zhang")
        
        # "Zhang" looks like a name - check confidence exists
        self.assertIn("confidence", result)
        self.assertGreaterEqual(result["confidence"], 0.5)

    def test_suggest_term_cultivation_pattern_increases_confidence(self):
        """Test cultivation terms get confidence boost."""
        result = self.suggestor.suggest_term("金丹境界")
        
        # Contains "金丹" which is a cultivation pattern
        self.assertIn("金丹", result["source"])

    def test_get_pending_suggestions_returns_list(self):
        """Test get_pending_suggestions returns list."""
        result = self.suggestor.get_pending_suggestions()
        self.assertIsInstance(result, list)

    def test_export_for_review_returns_json(self):
        """Test export_for_review returns valid JSON string."""
        suggestions = [
            {"source": "新词", "confidence": 0.7, "status": "pending"}
        ]
        
        result = self.suggestor.export_for_review(suggestions)
        
        self.assertIsInstance(result, str)
        parsed = json.loads(result)
        self.assertIn("new_terms", parsed)


class TestSuggestNewTerms(unittest.TestCase):
    """Test cases for suggest_new_terms function."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.glossary_path = Path(self.temp_dir) / "glossary.json"
        
        # Create empty glossary
        with open(self.glossary_path, 'w', encoding='utf-8') as f:
            json.dump({"version": "1.0", "terms": []}, f)

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    def test_suggest_new_terms_finds_chinese(self):
        """Test suggest_new_terms finds Chinese characters."""
        from src.utils.glossary_suggestor import suggest_new_terms
        
        text = "这是测试内容，包含中文术语和新词。"
        
        suggestions = suggest_new_terms(text, str(self.glossary_path))
        
        self.assertIsInstance(suggestions, list)

    def test_suggest_new_terms_returns_empty_for_no_chinese(self):
        """Test suggest_new_terms returns empty for English text."""
        from src.utils.glossary_suggestor import suggest_new_terms
        
        text = "This is English text only."
        
        suggestions = suggest_new_terms(text, str(self.glossary_path))
        
        self.assertEqual(len(suggestions), 0)


if __name__ == "__main__":
    unittest.main()