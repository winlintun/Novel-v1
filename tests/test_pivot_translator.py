from unittest.mock import MagicMock, patch

from src.agents.pivot_translator import PivotTranslator
from src.utils.ollama_client import OllamaClient
from src.memory.memory_manager import MemoryManager

class TestPivotTranslator:
    def setup_method(self):
        self.mock_client = MagicMock(spec=OllamaClient)
        self.mock_client.model = "test-model"

        self.mock_memory = MagicMock(spec=MemoryManager)
        self.mock_memory.get_all_memory_for_prompt.return_value = {
            'glossary': "Test Glossary",
            'context': "Test Context",
            'rules': "Test Rules"
        }

        self.config = {
            'translation_pipeline': {
                'stage1_model': 'test-model',
                'stage2_model': 'test-model',
                'stage1_prompt': 'Translate: {text} with {glossary}',
                'stage2_prompt': 'Refine: {text} with {glossary}'
            },
            'models': {
                'translator': 'test-model',
                'editor': 'test-model'
            }
        }

        self.translator = PivotTranslator(self.mock_client, self.mock_memory, self.config)

    def test_init_loads_config_correctly(self):
        assert self.translator.stage1_model == 'test-model'
        assert self.translator.stage2_model == 'test-model'
        assert self.translator.stage1_prompt_template == 'Translate: {text} with {glossary}'
        assert self.translator.stage2_prompt_template == 'Refine: {text} with {glossary}'

    @patch('src.agents.pivot_translator.validate_output')
    @patch('src.agents.pivot_translator.clean_output')
    def test_translate_paragraph_success(self, mock_clean, mock_validate):
        # Setup mocks
        self.mock_client.chat.side_effect = ["English Stage 1", "Myanmar Stage 2"]
        mock_clean.return_value = "Cleaned Myanmar Stage 2"
        mock_validate.return_value = {"status": "APPROVED", "myanmar_ratio": 0.8}

        result = self.translator.translate_paragraph("Chinese text", chapter_num=1)

        assert result == "Cleaned Myanmar Stage 2"

        # Verify first call
        call1_args = self.mock_client.chat.call_args_list[0]
        assert "Chinese text" in call1_args.kwargs['prompt']
        assert "Test Glossary" in call1_args.kwargs['prompt']
        assert call1_args.kwargs['system_prompt'] == self.translator.stage1_system_prompt

        # Verify second call
        call2_args = self.mock_client.chat.call_args_list[1]
        assert "English Stage 1" in call2_args.kwargs['prompt']
        assert "Test Glossary" in call2_args.kwargs['prompt']
        assert call2_args.kwargs['system_prompt'] == self.translator.stage2_system_prompt

        # Memory push check
        self.mock_memory.push_to_buffer.assert_called_once_with("Cleaned Myanmar Stage 2")

    def test_translate_chunks(self):
        chunks = [{'text': 'Chunk 1'}, {'text': 'Chunk 2'}]

        # Mock translate_paragraph
        self.translator.translate_paragraph = MagicMock(side_effect=["Trans 1", "Trans 2"])

        results = self.translator.translate_chunks(chunks, chapter_num=1)

        assert len(results) == 2
        assert results == ["Trans 1", "Trans 2"]
        self.translator.translate_paragraph.assert_any_call('Chunk 1', 1)
        self.translator.translate_paragraph.assert_any_call('Chunk 2', 1)
