"""
Unit tests for core agents (Translator, Refiner, Checker, ContextUpdater).
Mocks OllamaClient to avoid real API calls.
"""

import unittest
from unittest.mock import MagicMock
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.translator import Translator
from src.agents.refiner import Refiner
from src.agents.checker import Checker
from src.agents.context_updater import ContextUpdater
from src.memory.memory_manager import MemoryManager
from src.utils.ollama_client import OllamaClient


class TestTranslator(unittest.TestCase):
    def setUp(self):
        self.mock_ollama = MagicMock(spec=OllamaClient)
        self.mock_memory = MagicMock(spec=MemoryManager)

        # Default memory mock return
        self.mock_memory.get_all_memory_for_prompt.return_value = {
            'glossary': 'GLOSSARY: 主角="အဓိကနေရာ၊ မင်းသားနေရာ"',
            'context': 'No previous context.',
            'rules': 'No session rules.',
            'summary': ''
        }

        self.translator = Translator(self.mock_ollama, self.mock_memory)

    def test_build_prompt(self):
        """Test that translation prompt includes glossary and context."""
        text = "你好"
        prompt = self.translator.build_prompt(text)

        self.assertIn("GLOSSARY", prompt)
        self.assertIn("အဓိကနေရာ", prompt)
        self.assertIn("你好", prompt)

    def test_translate_paragraph(self):
        """Test single paragraph translation."""
        self.mock_ollama.chat.return_value = "မင်္ဂလာပါ"

        result = self.translator.translate_paragraph("你好")

        self.assertEqual(result, "မင်္ဂလာပါ")
        self.mock_memory.push_to_buffer.assert_called_with("မင်္ဂလာပါ")

    def test_translate_strips_think_tags(self):
        """Test translation strips <think> tags from output."""
        self.mock_ollama.chat.return_value = "<think>thought</think>မင်္ဂလာပါ"

        result = self.translator.translate_paragraph("你好")

        self.assertNotIn("<think>", result)
        self.assertNotIn("</think>", result)
        self.assertNotIn("thought", result)
        self.assertIn("မင်္ဂလာပါ", result)

    def test_translate_strips_answer_tags(self):
        """Test translation strips <answer> tags from output."""
        self.mock_ollama.chat.return_value = "<answer>မင်္ဂလာပါ</answer>"

        result = self.translator.translate_paragraph("你好")

        self.assertNotIn("<answer>", result)
        self.assertNotIn("</answer>", result)
        self.assertIn("မင်္ဂလာပါ", result)

    def test_translate_uses_hardened_prompt(self):
        """Test translator uses hardened prompt with STRICT RULES."""
        self.mock_ollama.chat.return_value = "မင်္ဂလာပါ"

        self.translator.translate_paragraph("你好")

        # Verify the system prompt contains STRICT RULES
        call_args = self.mock_ollama.chat.call_args
        system_prompt = call_args.kwargs.get('system_prompt', call_args[1].get('system_prompt', ''))
        self.assertIn("STRICT RULES", system_prompt)
        self.assertIn("ONLY", system_prompt)
        self.assertIn("Myanmar", system_prompt)


class TestRefiner(unittest.TestCase):
    def setUp(self):
        self.mock_ollama = MagicMock(spec=OllamaClient)
        self.refiner = Refiner(self.mock_ollama)

    def test_refine_paragraph(self):
        """Test refinement call."""
        self.mock_ollama.chat.return_value = "မြန်မာစာ"

        result = self.refiner.refine_paragraph("Raw Myanmar")

        self.assertEqual(result, "မြန်မာစာ")
        self.mock_ollama.chat.assert_called()

    def test_refine_strips_think_tags(self):
        """Test refinement strips <think> tags from output."""
        self.mock_ollama.chat.return_value = "<think>editing...</think>မြန်မာစာ"

        result = self.refiner.refine_paragraph("Raw Myanmar")

        self.assertNotIn("<think>", result)
        self.assertNotIn("editing...", result)
        self.assertIn("မြန်မာစာ", result)

    def test_refine_uses_hardened_prompt(self):
        """Test refiner uses hardened prompt with strict rules."""
        self.mock_ollama.chat.return_value = "မြန်မာစာ"

        self.refiner.refine_paragraph("Raw Myanmar")

        # Verify the system prompt contains required elements
        call_args = self.mock_ollama.chat.call_args
        system_prompt = call_args.kwargs.get('system_prompt', call_args[1].get('system_prompt', ''))
        self.assertIn("Myanmar", system_prompt)
        self.assertIn("natural, literary Myanmar", system_prompt)


class TestChecker(unittest.TestCase):
    def setUp(self):
        self.mock_memory = MagicMock(spec=MemoryManager)
        self.checker = Checker(self.mock_memory)

    def test_check_glossary_consistency_pass(self):
        """Test glossary check passes when correct term is used."""
        self.mock_memory.get_all_terms.return_value = [
            {'source': '主角', 'target': 'ဇော်ဂျီ'}
        ]

        # In translation, '主角' should NOT appear, 'ဇော်ဂျီ' SHOULD appear
        text = "ဇော်ဂျီ က ပြောတယ်"
        issues = self.checker.check_glossary_consistency(text)

        # Checker.check_glossary_consistency actually checks if SOURCE exists in target text
        self.assertEqual(len(issues), 0)

    def test_check_glossary_consistency_fail(self):
        """Test glossary check fails when source term is found in translation."""
        self.mock_memory.get_all_terms.return_value = [
            {'source': '主角', 'target': 'ဇော်ဂျီ'}
        ]

        text = "主角 က ပြောတယ်" # '主角' is still there!
        issues = self.checker.check_glossary_consistency(text)

        self.assertGreater(len(issues), 0)
        self.assertEqual(issues[0]['type'], 'untranslated_term')

    def test_target_missing_not_flagged_when_term_absent_from_chunk(self):
        """A verified name absent from this chunk's source must NOT be flagged.

        Regression: the old check reported one 'target_missing' issue per
        verified character/place term for every chunk that didn't mention it.
        """
        self.mock_memory.get_all_terms.return_value = [
            {'source': 'Bai Xiaochun', 'target': 'ဘိုင်',
             'category': 'character', 'verified': True}
        ]

        source_chunk = "The village was quiet that morning."
        translated = "ကျေးရွာက တိတ်ဆိတ်နေသည်။"
        issues = self.checker.check_glossary_consistency(translated, source_text=source_chunk)

        self.assertEqual(issues, [])

    def test_target_missing_flagged_when_source_present_target_absent(self):
        """A verified name present in the source but missing its approved
        spelling in the translation SHOULD be flagged as 'target_missing'."""
        self.mock_memory.get_all_terms.return_value = [
            {'source': 'Bai Xiaochun', 'target': 'ဘိုင်',
             'category': 'character', 'verified': True}
        ]

        source_chunk = "Bai Xiaochun left the village."
        translated = "someone left"  # approved target spelling missing
        issues = self.checker.check_glossary_consistency(translated, source_text=source_chunk)

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]['type'], 'target_missing')

    # ── Adequacy gate (BGE-M3) — uses a stub embedder so no model is loaded ──

    def _stub_embedder(self, table):
        """Return an embedder whose vectors are controlled by substring matches."""
        import numpy as np

        class StubEmb:
            def encode(self_inner, texts):
                out = []
                for t in texts:
                    vec = next((v for k, v in table.items() if k in t), [0.0, 0.0, 1.0])
                    out.append(vec)
                a = np.array(out, dtype=float)
                a /= np.linalg.norm(a, axis=1, keepdims=True)
                return a

        return StubEmb()

    def test_adequacy_faithful_translation_has_no_issues(self):
        self.checker._adequacy_embedder = self._stub_embedder(
            {'village': [1, 0, 0], 'ရွာ': [1, 0, 0], 'eagle': [0, 1, 0], 'ငှက်': [0, 1, 0]}
        )
        r = self.checker.check_adequacy(
            "The village was quiet. A baby eagle flew.",
            "ရွာ တိတ်ဆိတ်သည်။ ငှက် ပျံသည်။",
        )
        self.assertTrue(r['checked'])
        self.assertEqual(r['issues'], [])
        self.assertGreaterEqual(r['score'], 0.9)

    def test_adequacy_flags_omission(self):
        self.checker._adequacy_embedder = self._stub_embedder(
            {'village': [1, 0, 0], 'ရွာ': [1, 0, 0], 'eagle': [0, 1, 0], 'ငှက်': [0, 1, 0]}
        )
        r = self.checker.check_adequacy(
            "The village was quiet. A baby eagle flew.",
            "ရွာ တိတ်ဆိတ်သည်။",  # eagle sentence dropped
        )
        types = [i['type'] for i in r['issues']]
        self.assertIn('low_adequacy', types)

    def test_adequacy_flags_hallucination(self):
        self.checker._adequacy_embedder = self._stub_embedder(
            {'village': [1, 0, 0], 'ရွာ': [1, 0, 0]}
        )
        r = self.checker.check_adequacy(
            "The village was quiet.",
            "ရွာ တိတ်ဆိတ်သည်။ sky bridge ပေါ်မှာ။",  # unsupported addition
        )
        types = [i['type'] for i in r['issues']]
        self.assertIn('possible_hallucination', types)

    def test_adequacy_disabled_when_embedder_unavailable(self):
        self.checker._adequacy_embedder = None  # simulate missing model/deps
        r = self.checker.check_adequacy("anything", "ဘာမဆို")
        self.assertFalse(r['checked'])
        self.assertEqual(r['issues'], [])

    def test_check_markdown_formatting(self):
        """Test markdown preservation check."""
        original = "# Chapter 1\n**Bold**"
        translated = "# အခန်း ၁\n**စာလုံးကြီး**"

        issues = self.checker.check_markdown_formatting(original, translated)
        self.assertEqual(len(issues), 0)

        # Mismatch
        bad_translated = "အခန်း ၁\nစာလုံးကြီး" # No #, no **
        issues = self.checker.check_markdown_formatting(original, bad_translated)
        self.assertGreater(len(issues), 0)

    def test_quality_score(self):
        """Test quality score calculation."""
        # Use longer text (> 50 chars) to avoid automatic -50 penalty
        text = "နေကောင်းလား မင်္ဂလာပါ မြန်မာစာ သင်ယူနေပါတယ်ခင်ဗျာ။ အားလုံးပဲ မင်္ဂလာရှိသော နေ့လေးတစ်နေ့ ဖြစ်ပါစေလို့ ဆုတောင်းပေးပါတယ်"
        score = self.checker.calculate_quality_score(text)
        self.assertGreaterEqual(score, 90)

        bad_text = "abc 123 !@#" # No Myanmar
        score = self.checker.calculate_quality_score(bad_text)
        self.assertLess(score, 60)


class TestContextUpdater(unittest.TestCase):
    def setUp(self):
        self.mock_ollama = MagicMock(spec=OllamaClient)
        self.mock_memory = MagicMock(spec=MemoryManager)
        self.updater = ContextUpdater(self.mock_ollama, self.mock_memory)

    def test_process_chapter(self):
        """Test post-chapter processing."""
        # Mock term extraction
        self.mock_ollama.chat.return_value = '{"new_terms": [{"source": "新词", "target": "သစ်", "category": "item"}]}'

        original = "新词"
        translated = "သစ်"

        self.updater.process_chapter(original, translated, 1)

        # Verify glossary_pending update
        self.mock_memory.update_chapter_context.assert_called_with(1)

    def test_extract_entities_handles_malformed_json(self):
        """Test entity extraction handles malformed JSON gracefully."""
        # Mock malformed response
        self.mock_ollama.chat.return_value = "Not valid JSON"

        entities = self.updater.extract_entities("some text")

        # Should not crash, return empty structure
        self.assertIsInstance(entities, dict)
        self.assertEqual(entities.get('characters', []), [])

    def test_extract_entities_parses_valid_json(self):
        """Test entity extraction parses valid JSON correctly."""
        self.mock_ollama.chat.return_value = '{"new_terms": [{"source": "林渊", "target": "လင်ယွန်း", "category": "character"}]}'

        entities = self.updater.extract_entities("some text")

        # Should extract the character
        self.assertEqual(len(entities.get('characters', [])), 1)
        self.assertEqual(entities['characters'][0]['name'], '林渊')

    def test_extract_entities_handles_json_in_prose(self):
        """Test extraction handles JSON embedded in prose."""
        self.mock_ollama.chat.return_value = 'Here is the result:\n```json\n{"new_terms": [{"source": "X", "target": "Y", "category": "item"}]}\n```'

        entities = self.updater.extract_entities("some text")

        # Should extract from markdown fence
        self.assertEqual(len(entities.get('items_artifacts', [])), 1)


if __name__ == '__main__':
    # Define ANY for assertion
    unittest.main()
