"""Unit tests for PivotTranslator Stage 2 language leakage guard."""

import unittest
from unittest.mock import MagicMock, patch

from src.agents.pivot_translator import PivotTranslator
from src.memory.memory_manager import MemoryManager
from src.utils.ollama_client import OllamaClient


class TestPivotStage2Guard(unittest.TestCase):
    def setUp(self):
        self.mock_ollama = MagicMock(spec=OllamaClient)
        self.mock_memory = MagicMock(spec=MemoryManager)
        self.mock_memory.get_all_memory_for_prompt.return_value = {
            "glossary": "",
            "context": "No previous context.",
            "rules": "",
            "summary": "",
        }
        self.config = {
            "translation_pipeline": {
                "stage1_model": "model-a",
                "stage2_model": "model-b",
                "stage2_prompt": "{text}",
                "stage2_system_prompt": "Output Myanmar only",
            },
            "models": {"translator": "model-a", "editor": "model-b"},
            "processing": {"temperature": 0.2, "repeat_penalty": 1.1, "top_p": 0.9, "top_k": 40},
        }
        self.agent = PivotTranslator(self.mock_ollama, self.mock_memory, self.config)

    @patch("src.agents.pivot_translator.validate_output")
    def test_stage2_retries_on_english_leakage(self, mock_validate):
        # First response mostly English, second response Myanmar.
        self.mock_ollama.chat.side_effect = [
            "This is still English output with many words and no Myanmar text.",
            "မြန်မာ ဘာသာပြန် စာသား ဖြစ်သည်။",
        ]
        mock_validate.return_value = {"status": "APPROVED"}

        result = self.agent.translate_stage2("Sample English text", chapter_num=2, client=self.mock_ollama)

        self.assertIn("မြန်မာ", result)
        self.assertGreaterEqual(self.mock_ollama.chat.call_count, 2)


if __name__ == "__main__":
    unittest.main()
