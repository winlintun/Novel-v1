"""
Unit tests for Chinese-to-Myanmar linguistic rules using unittest.
"""

import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.prompts.cn_mm_rules import build_linguistic_context, SVO_TO_SOV_RULES, PRONOUN_HIERARCHY


class TestCNMMRules(unittest.TestCase):
    """Test Chinese-to-Myanmar linguistic rule prompts."""
    
    def test_build_linguistic_context(self):
        """Test linguistic context builder."""
        context = build_linguistic_context()
        self.assertIn("Chinese → Myanmar", context)
        self.assertIn("SVO", context)
        self.assertIn("Myanmar", context)
    
    def test_svo_to_sov_rules_exist(self):
        """Test SVO to SOV conversion rules exist."""
        self.assertIn("basic_structure", SVO_TO_SOV_RULES)
        rules_text = str(SVO_TO_SOV_RULES)
        self.assertIn("Subject", rules_text)
        self.assertIn("Object", rules_text)
        self.assertIn("Verb", rules_text)
    
    def test_pronoun_hierarchy_exists(self):
        """Test pronoun hierarchy rules exist."""
        self.assertIn("first_person", PRONOUN_HIERARCHY)
        self.assertIn("second_person", PRONOUN_HIERARCHY)
        self.assertIn("third_person", PRONOUN_HIERARCHY)
        # Check for Myanmar pronouns
        hierarchy_text = str(PRONOUN_HIERARCHY)
        self.assertTrue(
            any(pronoun in hierarchy_text for pronoun in ["မင်း", "နင်", "ခင်ဗျ", "ရှင်"]),
            "Myanmar pronouns should exist in hierarchy"
        )


if __name__ == '__main__':
    unittest.main()
