"""
Tests for Glossary v3.0 Manager & Loader
Uses unittest (no pytest dependency)
"""
import unittest
import json
import tempfile
from pathlib import Path

from src.utils.glossary_v3_manager import (
    GlossaryTerm, 
    TermCategory, 
    TranslationRule,
    DialogueRegister
)
from src.utils.glossary_v3_loader import GlossaryV3Loader


class TestGlossaryV3Manager(unittest.TestCase):
    """Tests for GlossaryTerm and related classes."""
    
    def test_glossary_term_creation(self):
        """Test GlossaryTerm dataclass instantiation."""
        term = GlossaryTerm(
            id="term_test",
            source_term="测试",
            target_term="စမ်းသပ်",
            category=TermCategory.OTHER,
            translation_rule=TranslationRule.TRANSLATE,
            priority=2
        )
        self.assertEqual(term.get_primary_key(), "测试:other")
        self.assertIn("测试", term.get_all_source_variants())
    
    def test_term_category_enum(self):
        """Test TermCategory enum values."""
        self.assertEqual(TermCategory.PERSON_CHARACTER.value, "person_character")
        self.assertEqual(TermCategory.CULTIVATION_CONCEPT.value, "cultivation_concept")
        self.assertEqual(TermCategory.LOCATION.value, "location")
    
    def test_translation_rule_enum(self):
        """Test TranslationRule enum values."""
        self.assertEqual(TranslationRule.TRANSLITERATE.value, "transliterate")
        self.assertEqual(TranslationRule.TRANSLATE.value, "translate")
        self.assertEqual(TranslationRule.HYBRID.value, "hybrid")
        self.assertEqual(TranslationRule.KEEP_ORIGINAL.value, "keep_original")
    
    def test_exception_rule_application(self):
        """Test context-aware term selection via exceptions."""
        term = GlossaryTerm(
            id="term_exc",
            source_term="测试",
            target_term="စမ်းသပ်",
            category=TermCategory.OTHER,
            translation_rule=TranslationRule.TRANSLATE,
            priority=1,
            exceptions=[
                {"condition": "spoken_by_enemies", "use_term": "ဟဲ့ကောင်"}
            ]
        )
        
        # Default case
        self.assertEqual(term.get_target_for_context(), "စမ်းသပ်")
        
        # Exception case
        self.assertEqual(
            term.get_target_for_context(speaker_role="enemy"), 
            "ဟဲ့ကောင်"
        )
    
    def test_term_to_dict(self):
        """Test converting term to dictionary."""
        term = GlossaryTerm(
            id="term_001",
            source_term="测试",
            target_term="စမ်းသပ်",
            category=TermCategory.OTHER,
            translation_rule=TranslationRule.TRANSLATE,
            priority=1
        )
        
        data = term.to_dict()
        self.assertEqual(data["id"], "term_001")
        self.assertEqual(data["source_term"], "测试")
        self.assertEqual(data["category"], "other")  # Enum converted to string
        self.assertEqual(data["translation_rule"], "translate")
    
    def test_term_to_prompt_snippet(self):
        """Test generating prompt snippet."""
        term = GlossaryTerm(
            id="term_001",
            source_term="测试",
            target_term="စမ်းသပ်",
            category=TermCategory.OTHER,
            translation_rule=TranslationRule.TRANSLATE,
            priority=1,
            aliases_cn=["别名1", "别名2"],
            pronunciation_guide="ce4 shi4",
            exceptions=[{"condition": "test", "use_term": "test"}]
        )
        
        snippet = term.to_prompt_snippet()
        self.assertIn("测试", snippet)
        self.assertIn("စမ်းသပ်", snippet)
        self.assertIn("other", snippet)
        self.assertIn("别名1", snippet)  # Alias
        self.assertIn("Pronunciation:", snippet)  # Pronunciation
        self.assertIn("Exceptions:", snippet)


class TestGlossaryV3Loader(unittest.TestCase):
    """Tests for GlossaryV3Loader."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.sample_glossary = {
            "glossary_version": "3.0",
            "novel_name": "test_novel",
            "source_language": "Chinese",
            "target_language": "Myanmar",
            "terms": [
                {
                    "id": "term_001",
                    "source_term": "李小龙",
                    "target_term": "လီရှောင်လုံ",
                    "aliases_cn": ["小李", "龙儿"],
                    "aliases_mm": ["ရှောင်လုံ"],
                    "category": "person_character",
                    "translation_rule": "transliterate",
                    "priority": 1,
                    "usage_frequency": "high",
                    "verified": True,
                    "exceptions": [
                        {
                            "condition": "spoken_by_enemies",
                            "use_term": "ကောင်လေးလီ",
                            "note": "Dismissive tone"
                        }
                    ],
                    "examples": [
                        {
                            "context_type": "narrative",
                            "cn_sentence": "李小龙走进了房间。",
                            "mm_sentence": "လီရှောင်လုံသည် အခန်းထဲသို့ ဝင်ရောက်ခဲ့သည်။"
                        }
                    ]
                }
            ]
        }
    
    def _create_temp_glossary_file(self, data):
        """Helper to create temporary glossary file."""
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.json',
            delete=False,
            encoding='utf-8-sig'
        ) as f:
            json.dump(data, f, ensure_ascii=False)
            return Path(f.name)
    
    def test_loader_load_valid_json(self):
        """Test loading valid glossary JSON."""
        glossary_file = self._create_temp_glossary_file(self.sample_glossary)
        
        try:
            loader = GlossaryV3Loader(glossary_file)
            self.assertTrue(loader.load())
            self.assertTrue(loader._loaded)
            
            # Test lookup
            term = loader.lookup("李小龙")
            self.assertIsNotNone(term)
            self.assertEqual(term.target_term, "လီရှောင်လုံ")
            
            # Test alias lookup
            term_alias = loader.lookup("小李")
            self.assertIsNotNone(term_alias)
            self.assertEqual(term_alias.id, "term_001")
        finally:
            glossary_file.unlink()
    
    def test_loader_load_nonexistent_file(self):
        """Test loading from non-existent file returns False."""
        loader = GlossaryV3Loader("/nonexistent/path/glossary.json")
        self.assertFalse(loader.load())
    
    def test_loader_load_invalid_json(self):
        """Test loading invalid JSON returns False."""
        with tempfile.NamedTemporaryFile(
            mode='w', 
            suffix='.json', 
            delete=False
        ) as f:
            f.write("not valid json")
            temp_path = Path(f.name)
        
        try:
            loader = GlossaryV3Loader(temp_path)
            self.assertFalse(loader.load())
        finally:
            temp_path.unlink()
    
    def test_loader_load_missing_required_fields(self):
        """Test loading JSON with missing required fields returns False."""
        incomplete = {
            "glossary_version": "3.0",
            "novel_name": "test"
            # Missing source_language, target_language, terms
        }
        
        glossary_file = self._create_temp_glossary_file(incomplete)
        
        try:
            loader = GlossaryV3Loader(glossary_file)
            self.assertFalse(loader.load())
        finally:
            glossary_file.unlink()
    
    def test_export_for_prompt_markdown(self):
        """Test prompt export in markdown format."""
        glossary_file = self._create_temp_glossary_file(self.sample_glossary)
        
        try:
            loader = GlossaryV3Loader(glossary_file)
            loader.load()
            
            snippet = loader.export_for_prompt(max_entries=10, format="markdown")
            self.assertIn("[GLOSSARY v3.0", snippet)
            self.assertIn("李小龙", snippet)
            self.assertIn("လီရှောင်လုံ", snippet)
            self.assertIn("person_character", snippet)
        finally:
            glossary_file.unlink()
    
    def test_export_for_prompt_plain(self):
        """Test prompt export in plain format."""
        glossary_file = self._create_temp_glossary_file(self.sample_glossary)
        
        try:
            loader = GlossaryV3Loader(glossary_file)
            loader.load()
            
            snippet = loader.export_for_prompt(max_entries=10, format="plain")
            self.assertIn("李小龙", snippet)
            self.assertIn("လီရှောင်လုံ", snippet)
        finally:
            glossary_file.unlink()
    
    def test_export_for_prompt_json(self):
        """Test prompt export in JSON format."""
        glossary_file = self._create_temp_glossary_file(self.sample_glossary)
        
        try:
            loader = GlossaryV3Loader(glossary_file)
            loader.load()
            
            snippet = loader.export_for_prompt(max_entries=10, format="json")
            data = json.loads(snippet)
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]["source_term"], "李小龙")
        finally:
            glossary_file.unlink()
    
    def test_export_for_prompt_priority_filter(self):
        """Test that priority threshold filters correctly."""
        # Add a lower priority term
        self.sample_glossary["terms"].append({
            "id": "term_002",
            "source_term": "次要术语",
            "target_term": "ဒုတိယအရေးပါသော",
            "category": "other",
            "translation_rule": "translate",
            "priority": 5  # Higher number = lower priority
        })
        
        glossary_file = self._create_temp_glossary_file(self.sample_glossary)
        
        try:
            loader = GlossaryV3Loader(glossary_file)
            loader.load()
            
            # With threshold of 3, only priority 1-3 should be included
            snippet = loader.export_for_prompt(priority_threshold=3, format="plain")
            self.assertIn("李小龙", snippet)
            self.assertNotIn("次要术语", snippet)
        finally:
            glossary_file.unlink()
    
    def test_lookup_in_text_extraction(self):
        """Test extracting terms from Chinese text."""
        glossary_file = self._create_temp_glossary_file(self.sample_glossary)
        
        try:
            loader = GlossaryV3Loader(glossary_file)
            loader.load()
            
            # Text containing the term (Chinese source text)
            text = "李小龙走进了房间。"
            found = loader.lookup_in_text(text)
            
            self.assertGreaterEqual(len(found), 1)
            self.assertTrue(any(t.source_term == "李小龙" for t in found))
        finally:
            glossary_file.unlink()
    
    def test_lookup_with_category_filter(self):
        """Test lookup with category filter."""
        glossary_file = self._create_temp_glossary_file(self.sample_glossary)
        
        try:
            loader = GlossaryV3Loader(glossary_file)
            loader.load()
            
            # Lookup with correct category
            term = loader.lookup("李小龙", category=TermCategory.PERSON_CHARACTER)
            self.assertIsNotNone(term)
        finally:
            glossary_file.unlink()
    
    def test_get_metadata(self):
        """Test getting glossary metadata."""
        glossary_file = self._create_temp_glossary_file(self.sample_glossary)
        
        try:
            loader = GlossaryV3Loader(glossary_file)
            loader.load()
            
            metadata = loader.get_metadata()
            self.assertEqual(metadata["version"], "3.0")
            self.assertEqual(metadata["novel_name"], "test_novel")
            self.assertEqual(metadata["source_language"], "Chinese")
            self.assertEqual(metadata["target_language"], "Myanmar")
            self.assertEqual(metadata["total_terms"], 1)
        finally:
            glossary_file.unlink()
    
    def test_get_term_count_by_category(self):
        """Test getting term counts by category."""
        glossary_file = self._create_temp_glossary_file(self.sample_glossary)
        
        try:
            loader = GlossaryV3Loader(glossary_file)
            loader.load()
            
            counts = loader.get_term_count_by_category()
            self.assertEqual(counts["person_character"], 1)
        finally:
            glossary_file.unlink()
    
    def test_is_loaded(self):
        """Test is_loaded method."""
        loader = GlossaryV3Loader("/fake/path.json")
        self.assertFalse(loader.is_loaded())
    
    def test_force_reload(self):
        """Test force reload functionality."""
        glossary_file = self._create_temp_glossary_file(self.sample_glossary)
        
        try:
            loader = GlossaryV3Loader(glossary_file)
            
            # First load
            self.assertTrue(loader.load())
            self.assertTrue(loader.is_loaded())
            
            # Second load without force should return True but not reload
            self.assertTrue(loader.load())
            
            # Force reload should work
            self.assertTrue(loader.load(force_reload=True))
        finally:
            glossary_file.unlink()
    
    def test_multiple_terms_lookup(self):
        """Test lookup with multiple terms in glossary."""
        # Add more terms
        self.sample_glossary["terms"].append({
            "id": "term_002",
            "source_term": "王五",
            "target_term": "ဝမ်ငါး",
            "category": "person_character",
            "translation_rule": "transliterate",
            "priority": 2
        })
        self.sample_glossary["terms"].append({
            "id": "term_003",
            "source_term": "青云门",
            "target_term": "စျင်းယွမ်စiendo",
            "category": "organization",
            "translation_rule": "hybrid",
            "priority": 1
        })
        
        glossary_file = self._create_temp_glossary_file(self.sample_glossary)
        
        try:
            loader = GlossaryV3Loader(glossary_file)
            loader.load()
            
            # Should find all terms
            self.assertIsNotNone(loader.lookup("李小龙"))
            self.assertIsNotNone(loader.lookup("王五"))
            self.assertIsNotNone(loader.lookup("青云门"))
            
            # Check metadata
            metadata = loader.get_metadata()
            self.assertEqual(metadata["total_terms"], 3)
        finally:
            glossary_file.unlink()


if __name__ == '__main__':
    unittest.main()
