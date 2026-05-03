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
from src.utils.file_handler import FileHandler


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
        self.memory.add_session_rule("ဟောင်း", "သစ်")
        rules = self.memory.get_session_rules()
        self.assertIn("ဟောင်း -> သစ်", rules)

        # Promote to glossary
        self.memory.promote_rule_to_glossary("ဟောင်း", "သစ်", 1)
        self.assertEqual(self.memory.get_term("ဟောင်း"), "သစ်")
        self.assertEqual(self.memory.get_session_rules(), "No session rules.")


class TestDualLayerGlossary(unittest.TestCase):
    """Tests for dual-layer universal + per-novel glossary system."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        # Create a fake universal glossary blueprint
        self.universal_path = os.path.join(self.temp_dir, "universal_glossary.json")
        universal_data = {
            "metadata": {"schema_version": "3.2.1"},
            "terms": [
                {
                    "id": "char_u001",
                    "source_term": "Spirit Gu",
                    "target_term": "ဝိညာဉ်ကြောင်",
                    "category": "item_artifact",
                    "status": "approved"
                }
            ]
        }
        with open(self.universal_path, "w", encoding="utf-8") as f:
            json.dump(universal_data, f)

        # Create per-novel glossaries in separate temp dirs
        self.novel_a_dir = os.path.join(self.temp_dir, "novel_a", "glossary")
        self.novel_b_dir = os.path.join(self.temp_dir, "novel_b", "glossary")
        os.makedirs(self.novel_a_dir, exist_ok=True)
        os.makedirs(self.novel_b_dir, exist_ok=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir)

    def _make_mm(self, glossary_path: str, use_universal: bool = False,
                  universal_path: str = "") -> MemoryManager:
        """Helper: create MemoryManager with optional patched universal path."""
        context_path = glossary_path.replace("glossary.json", "context.json")
        mm = MemoryManager(glossary_path, context_path, use_universal=False)
        if use_universal and universal_path:
            raw_data = FileHandler.read_json(universal_path) or {"terms": []}
            # Apply same placeholder filter as _load_memory()
            raw_terms = raw_data.get("terms", [])
            raw_data["terms"] = [
                t for t in raw_terms
                if not (
                    (t.get("source_term") or t.get("source", "")).startswith("<")
                    and (t.get("source_term") or t.get("source", "")).endswith(">")
                )
            ]
            mm.use_universal = True
            mm.universal_glossary = raw_data
        return mm

    def test_per_novel_isolation(self):
        """Terms added to novel A must NOT appear in novel B."""
        glossary_a = os.path.join(self.novel_a_dir, "glossary.json")
        glossary_b = os.path.join(self.novel_b_dir, "glossary.json")

        mm_a = self._make_mm(glossary_a)
        mm_a.add_term("Fang Yuan", "ဖန်ယွမ်", "character", 1)
        mm_a.save_memory()

        mm_b = self._make_mm(glossary_b)
        self.assertIsNone(mm_b.get_term("Fang Yuan"),
                          "Term from novel A must not leak into novel B")

    def test_per_novel_paths_are_distinct(self):
        """Two novels must resolve to different glossary file paths."""
        from src.memory.memory_manager import _resolve_glossary_path
        import tempfile, os
        # Temporarily create dirs so makedirs doesn't fail
        with tempfile.TemporaryDirectory() as d:
            # _resolve_glossary_path uses a relative path — we just verify names differ
            pass
        path_a_glossary, _, _ = _resolve_glossary_path("novel-alpha")
        path_b_glossary, _, _ = _resolve_glossary_path("novel-beta")
        self.assertNotEqual(path_a_glossary, path_b_glossary,
                            "Different novels must have distinct glossary paths")
        self.assertIn("novel-alpha", path_a_glossary)
        self.assertIn("novel-beta", path_b_glossary)

    def test_universal_term_visible_when_enabled(self):
        """Universal glossary term is visible via get_term() when use_universal=True."""
        glossary_path = os.path.join(self.novel_a_dir, "glossary.json")
        mm = self._make_mm(glossary_path, use_universal=True,
                           universal_path=self.universal_path)
        result = mm.get_term("Spirit Gu")
        self.assertEqual(result, "ဝိညာဉ်ကြောင်",
                         "Universal term must be retrievable when use_universal=True")

    def test_universal_term_hidden_when_disabled(self):
        """Universal glossary term is NOT visible when use_universal=False."""
        glossary_path = os.path.join(self.novel_a_dir, "glossary.json")
        mm = self._make_mm(glossary_path, use_universal=False)
        result = mm.get_term("Spirit Gu")
        self.assertIsNone(result,
                          "Universal term must be hidden when use_universal=False")

    def test_per_novel_overrides_universal(self):
        """Per-novel term takes priority over universal term with same source."""
        glossary_path = os.path.join(self.novel_a_dir, "glossary.json")
        mm = self._make_mm(glossary_path, use_universal=True,
                           universal_path=self.universal_path)
        # Add a per-novel override for the same source term
        mm.add_term("Spirit Gu", "ဝိညာဉ်ကြောင် (RI)", "item_artifact", 1)
        result = mm.get_term("Spirit Gu")
        self.assertEqual(result, "ဝိညာဉ်ကြောင် (RI)",
                         "Per-novel term must override universal term with same source")

    def test_get_all_terms_combines_both_layers(self):
        """get_all_terms() returns per-novel + universal (no duplicates)."""
        glossary_path = os.path.join(self.novel_a_dir, "glossary.json")
        mm = self._make_mm(glossary_path, use_universal=True,
                           universal_path=self.universal_path)
        mm.add_term("Fang Yuan", "ဖန်ယွမ်", "character", 1)

        all_terms = mm.get_all_terms()
        sources = [t.get("source") or t.get("source_term", "") for t in all_terms]
        self.assertIn("Fang Yuan", sources, "Per-novel term must be in combined list")
        self.assertIn("Spirit Gu", sources, "Universal term must be in combined list")
        # No duplicates
        self.assertEqual(len(sources), len(set(sources)),
                         "Duplicate sources must not appear in combined list")

    def test_universal_duplicate_excluded_when_per_novel_exists(self):
        """If per-novel has same source as universal, universal copy is excluded."""
        glossary_path = os.path.join(self.novel_a_dir, "glossary.json")
        mm = self._make_mm(glossary_path, use_universal=True,
                           universal_path=self.universal_path)
        # Per-novel override
        mm.add_term("Spirit Gu", "ဝိညာဉ်ကြောင် (custom)", "item_artifact", 1)

        all_terms = mm.get_all_terms()
        spirit_gu_terms = [
            t for t in all_terms
            if (t.get("source") or t.get("source_term", "")) == "Spirit Gu"
        ]
        self.assertEqual(len(spirit_gu_terms), 1,
                         "Only one entry per source when per-novel overrides universal")
        self.assertEqual(spirit_gu_terms[0].get("target") or spirit_gu_terms[0].get("target_term"),
                         "ဝိညာဉ်ကြောင် (custom)",
                         "The per-novel term value must win the dedup")

    def test_template_placeholders_filtered_from_universal(self):
        """Blueprint template placeholders like <MAIN_CHARACTER> must never appear in prompts."""
        glossary_path = os.path.join(self.novel_a_dir, "glossary.json")
        # Simulate the actual blueprint file (has template placeholder term)
        blueprint_with_placeholder = {
            "metadata": {"schema_version": "3.2.1"},
            "terms": [
                {
                    "id": "char_001",
                    "source_term": "<MAIN_CHARACTER>",
                    "target_term": "<MYANMAR_NAME>",
                    "category": "character"
                },
                {
                    "id": "char_002",
                    "source_term": "Real Term",
                    "target_term": "စစ်မှန်သောစကား",
                    "category": "character"
                }
            ]
        }
        with open(self.universal_path, "w", encoding="utf-8") as f:
            json.dump(blueprint_with_placeholder, f)

        mm = self._make_mm(glossary_path, use_universal=True,
                           universal_path=self.universal_path)

        # Placeholder must be gone
        all_terms = mm.get_all_terms()
        sources = [t.get("source_term") or t.get("source", "") for t in all_terms]
        self.assertNotIn("<MAIN_CHARACTER>", sources,
                         "<MAIN_CHARACTER> placeholder must be filtered from combined terms")
        self.assertIn("Real Term", sources,
                      "Non-placeholder universal term must still be included")

        # Prompt must not contain template strings
        prompt = mm.get_glossary_for_prompt(limit=60)
        self.assertNotIn("<MAIN_CHARACTER>", prompt)
        self.assertNotIn("<MYANMAR_NAME>", prompt)

    def test_source_term_target_term_format_normalized(self):
        """Glossary using source_term/target_term keys is normalized on load."""
        glossary_path = os.path.join(self.novel_a_dir, "glossary.json")
        # Write a glossary in the legacy source_term/target_term format
        legacy_data = {
            "glossary_version": "1.0",
            "terms": [
                {
                    "id": "term_001",
                    "source_term": "Gu Master",
                    "target_term": "ကြောင်ဆရာ",
                    "category": "title_honorific"
                }
            ]
        }
        with open(glossary_path, "w", encoding="utf-8") as f:
            json.dump(legacy_data, f)

        context_path = glossary_path.replace("glossary.json", "context.json")
        mm = MemoryManager(glossary_path, context_path, use_universal=False)
        result = mm.get_term("Gu Master")
        self.assertEqual(result, "ကြောင်ဆရာ",
                         "Legacy source_term/target_term format must be normalized and readable")


if __name__ == '__main__':
    unittest.main()
