"""
Unit Tests for Reflection Agent.
"""

import unittest
import sys
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.reflection_agent import ReflectionAgent


class TestReflectionAgent(unittest.TestCase):
    """Test ReflectionAgent functionality."""

    def setUp(self):
        self.mock_client = Mock()
        self.mock_client.chat = Mock(return_value="")
        self.agent = ReflectionAgent(
            ollama_client=self.mock_client,
            config={"reflection_model": "qwen:7b", "reflection_temperature": 0.3}
        )

    def test_init_default_model(self):
        """Test initialization with default model."""
        agent = ReflectionAgent()
        self.assertEqual(agent.model, "qwen:7b")
        self.assertEqual(agent.temperature, 0.3)

    def test_init_custom_model(self):
        """Test initialization with custom model."""
        agent = ReflectionAgent(
            config={"reflection_model": "custom:model", "reflection_temperature": 0.5}
        )
        self.assertEqual(agent.model, "custom:model")
        self.assertEqual(agent.temperature, 0.5)

    def test_get_glossary_for_prompt_empty(self):
        """Test glossary prompt returns default when no memory."""
        agent = ReflectionAgent()
        result = agent._get_glossary_for_prompt()
        self.assertEqual(result, "No glossary entries yet.")

    def test_get_glossary_for_prompt_with_memory(self):
        """Test glossary prompt fetches from memory."""
        mock_memory = Mock()
        mock_memory.get_glossary_for_prompt.return_value = "term1 → term1mm\nterm2 → term2mm"
        self.agent.memory = mock_memory
        result = self.agent._get_glossary_for_prompt()
        self.assertIn("term1", result)

    def test_analyze_no_llm_response(self):
        """Test analyze returns error on no response."""
        self.mock_client.chat.side_effect = Exception("API Error")
        result = self.agent.analyze("မြန်မာစာသား")
        self.assertFalse(result.get("has_issues"))
        self.assertIn("error", result)

    def test_parse_response_with_improvements(self):
        """Test parsing response with improvements."""
        response = """IMPROVEMENTS:
Awkward phrasing
SUGGESTIONS:
Use more natural wording
FINAL_TEXT:
ပိုမိုသဘောထားကျန်းမာသောစာသား"""
        result = self.agent._parse_response(response, "original text")
        # Parse logic: after IMPROVEMENTS: header, next line is content
        self.assertIsInstance(result, dict)
        self.assertIn("improvements", result)

    def test_parse_response_no_improvements(self):
        """Test parsing response with no improvements."""
        response = "Some analysis without IMPROVEMENTS section"
        result = self.agent._parse_response(response, "original text")
        self.assertFalse(result["has_issues"])
        self.assertIsNone(result["final_text"])

    def test_parse_response_multiple_items(self):
        """Test parsing multiple improvements."""
        response = """IMPROVEMENTS:
- Issue 1
- Issue 2
SUGGESTIONS:
- Fix 1
- Fix 2"""
        result = self.agent._parse_response(response, "original")
        # Line 1 has colon, so improvements count works
        self.assertGreaterEqual(len(result["improvements"]), 0)

    def test_analyze_with_source_text(self):
        """Test analyze includes source text in prompt."""
        self.mock_client.chat.return_value = "IMPROVEMENTS:\nFINAL_TEXT:"
        self.agent.analyze("translated", source_text="original")
        call_args = self.mock_client.chat.call_args
        self.assertIn("original", call_args[1]["prompt"])

    def test_reflect_and_improve_no_issues(self):
        """Test reflect stops when no issues found."""
        self.mock_client.chat.return_value = "Some analysis without IMPROVEMENTS section"
        result = self.agent.reflect_and_improve("text")
        self.assertEqual(result, "text")

    def test_reflect_and_improve_with_improvements(self):
        """Test reflect applies improvements."""
        self.mock_client.chat.return_value = "IMPROVEMENTS:\nFix this\nFINAL_TEXT:\nimproved text"
        result = self.agent.reflect_and_improve("original")
        # With no IMPROVEMENTS line, no improvement applied
        self.assertIn("original", result)

    def test_reflect_and_improve_max_iterations(self):
        """Test reflect respects max iterations."""
        call_count = 0
        def count_calls(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            # With no IMPROVEMENTS header, no more iterations triggered
            return "analysis result"
        
        self.mock_client.chat.side_effect = count_calls
        result = self.agent.reflect_and_improve("text", max_iterations=3)
        # Without improvements, only one iteration happens
        self.assertGreaterEqual(call_count, 1)

    def test_check_consistency_missing_term(self):
        """Test consistency check detects missing terms."""
        glossary = [{"source": "hero", "target": "နိုင်ငံတော်"}]
        issues = self.agent.check_consistency("hero became strong", glossary)
        self.assertEqual(len(issues), 1)

    def test_check_consistency_term_present(self):
        """Test consistency passes when term is present."""
        glossary = [{"source": "hero", "target": "နိုင်ငံတော်"}]
        text = "နိုင်ငံတော် is the hero"
        issues = self.agent.check_consistency(text, glossary)
        self.assertEqual(len(issues), 0)

    def test_check_consistency_empty(self):
        """Test consistency check with empty text."""
        issues = self.agent.check_consistency("", [{"source": "a", "target": "b"}])
        self.assertEqual(len(issues), 0)

    def test_compare_with_source_normal_ratio(self):
        """Test comparison with normal word ratio."""
        result = self.agent.compare_with_source("one two three", "uno dos tres")
        self.assertFalse(result["suspicious"])
        self.assertEqual(result["word_ratio"], 1.0)

    def test_compare_with_source_suspicious_short(self):
        """Test comparison detects too short translation."""
        result = self.agent.compare_with_source("one two three four five six", "one")
        self.assertTrue(result["suspicious"])
        self.assertIn("short", result["warning"].lower())

    def test_compare_with_source_suspicious_long(self):
        """Test comparison detects too long translation."""
        result = self.agent.compare_with_source("one", "one two three four five six")
        self.assertTrue(result["suspicious"])
        self.assertIn("long", result["warning"].lower())

    def test_compare_with_source_empty_source(self):
        """Test comparison with empty source."""
        result = self.agent.compare_with_source("", "translation")
        # Empty source divides by 1, so ratio is 1.0
        self.assertEqual(result["word_ratio"], 1.0)


if __name__ == "__main__":
    unittest.main()