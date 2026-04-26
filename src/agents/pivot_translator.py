#!/usr/bin/env python3
"""
Pivot Translator Agent
Core Chinese to English to Myanmar two-stage translation using Ollama.
"""

import logging
from typing import Dict, List, Optional

from src.utils.ollama_client import OllamaClient
from src.memory.memory_manager import MemoryManager
from src.utils.progress_logger import ProgressLogger
from src.utils.postprocessor import clean_output, validate_output

logger = logging.getLogger(__name__)

class PivotTranslator:
    """
    Translates Chinese text to Myanmar using a two-stage pivot via English.
    Integrates glossary and context memory.
    """
    
    def __init__(
        self,
        ollama_client: OllamaClient,
        memory_manager: MemoryManager,
        config: dict
    ):
        self.ollama = ollama_client
        self.memory = memory_manager
        self.config = config
        
        # Load specific stage configurations
        pipeline = config.get('translation_pipeline', {})
        processing = config.get('processing', {})
        models = config.get('models', {})
        
        self.stage1_model = pipeline.get('stage1_model', models.get('translator', 'qwen2.5:14b'))
        self.stage2_model = pipeline.get('stage2_model', models.get('editor', 'qwen2.5:14b'))
        
        # Parameters
        self.temperature = processing.get('temperature', 0.3)
        self.repeat_penalty = processing.get('repeat_penalty', 1.15)
        self.top_p = processing.get('top_p', 0.92)
        self.top_k = processing.get('top_k', 50)
        
        # Prompt templates
        self.stage1_prompt_template = pipeline.get('stage1_prompt', '{text}')
        self.stage2_prompt_template = pipeline.get('stage2_prompt', '{text}')
        
        # System prompts
        self.stage1_system_prompt = pipeline.get('stage1_system_prompt', "You are an expert Chinese-to-English literary translator. Output ONLY English translation.")
        self.stage2_system_prompt = pipeline.get('stage2_system_prompt', "CRITICAL: Output ONLY Myanmar (Burmese) language using Myanmar Unicode script. NO English words or Chinese characters.")

    def translate_paragraph(self, paragraph: str, chapter_num: int = 0) -> str:
        """Translate a single paragraph using the two-stage pivot."""
        mem = self.memory.get_all_memory_for_prompt()
        glossary_text = mem['glossary'] if mem['glossary'] else ""
        
        # Format prompts safely
        prompt1 = self.stage1_prompt_template.replace('{text}', paragraph).replace('{glossary}', glossary_text)
        
        # Stage 1: CN -> EN
        try:
            if self.stage1_model == self.ollama.model:
                client1 = self.ollama
                cleanup1 = False
            else:
                client1 = OllamaClient(
                    model=self.stage1_model,
                    temperature=self.temperature,
                    top_p=self.top_p,
                    top_k=self.top_k,
                    repeat_penalty=self.repeat_penalty,
                    unload_on_cleanup=True
                )
                cleanup1 = True
            
            raw_en = client1.chat(prompt=prompt1, system_prompt=self.stage1_system_prompt)
            english_result = raw_en.strip()
            
            if cleanup1:
                client1.cleanup()
        except Exception as e:
            logger.error(f"Stage 1 (CN->EN) Failed: {e}")
            return f"[TRANSLATION ERROR STAGE 1: {e}]"

        # Stage 2: EN -> MM
        prompt2 = self.stage2_prompt_template.replace('{text}', english_result).replace('{glossary}', glossary_text)
        if mem['context'] and mem['context'] != "No previous context.":
            prompt2 += f"\n\nPREVIOUS CONTEXT:\n{mem['context']}"
            
        try:
            if self.stage2_model == self.ollama.model:
                client2 = self.ollama
                cleanup2 = False
            else:
                client2 = OllamaClient(
                    model=self.stage2_model,
                    temperature=min(0.2, self.temperature), # Use conservative temperature for Myanmar output
                    top_p=self.top_p,
                    top_k=self.top_k,
                    repeat_penalty=self.repeat_penalty,
                    unload_on_cleanup=True
                )
                cleanup2 = True
                
            raw_mm = client2.chat(prompt=prompt2, system_prompt=self.stage2_system_prompt)
            myanmar_result = clean_output(raw_mm.strip())
            
            if cleanup2:
                client2.cleanup()
                
            # Validate and log quality report
            report = validate_output(myanmar_result, chapter_num)
            if report["status"] == "REJECTED":
                logger.error(f"CRITICAL: Translation REJECTED in chapter {chapter_num}: {report}")
            elif report["status"] == "NEEDS_REVIEW":
                logger.warning(f"Translation quality issue in chapter {chapter_num}: {report}")
                
            # Push to context buffer
            self.memory.push_to_buffer(myanmar_result)
            return myanmar_result
            
        except Exception as e:
            logger.error(f"Stage 2 (EN->MM) Failed: {e}")
            return f"[TRANSLATION ERROR STAGE 2: {e}]"

    def translate_chunks(
        self,
        chunks: List[Dict],
        chapter_num: int = 0,
        progress_logger: Optional[ProgressLogger] = None,
    ) -> List[str]:
        translated = []
        total = len(chunks)
        for i, chunk in enumerate(chunks, 1):
            logger.info(f"Pivot Translating chunk {i}/{total}...")
            try:
                result = self.translate_paragraph(chunk['text'], chapter_num)
                translated.append(result)
                if progress_logger:
                    progress_logger.log_chunk(
                        chunk_index=i - 1,
                        chunk_text=result,
                        source_text=chunk.get('text', '')
                    )
            except Exception as e:
                logger.error(f"Failed to translate chunk {i}: {e}")
                translated.append(f"[TRANSLATION ERROR: {e}]")
        return translated

    def translate_chapter(self, text: str, chapter_num: int = 0, use_chunking: bool = True) -> str:
        from src.agents.preprocessor import Preprocessor
        logger.info(f"Pivot Translating Chapter {chapter_num}")
        self.memory.clear_buffer()
        if use_chunking:
            preprocessor = Preprocessor()
            chunks = preprocessor.create_chunks(text)
            translated_chunks = self.translate_chunks(chunks, chapter_num)
            return '\n\n'.join(translated_chunks)
        else:
            return self.translate_paragraph(text)
