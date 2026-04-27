#!/usr/bin/env python3
"""
Pipeline orchestrator for the novel translation pipeline.

Coordinates all translation stages:
1. Preprocessing - Chunk input text
2. Translation - Translate chunks
3. Refinement - Literary quality editing
4. Reflection - Self-correction (optional)
5. Quality Check - Myanmar linguistic validation
6. Consistency - Glossary verification
7. QA Review - Final validation
"""

import os
import time
import signal
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from src.config import AppConfig
from src.types import PipelineResult, TranslationChunk
from src.exceptions import (
    NovelTranslationError,
    PipelineError,
    ModelError,
    ResourceError,
)

# Constants
INPUT_DIR = "data/input"
OUTPUT_DIR = "data/output"
WORKING_DIR = "working_data"


class TranslationPipeline:
    """Main translation pipeline orchestrator.
    
    Coordinates all agents and stages to translate novel chapters
    from Chinese to Myanmar with quality checks.
    """
    
    def __init__(self, config: AppConfig):
        """Initialize the pipeline with configuration.
        
        Args:
            config: Application configuration
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Initialize agents (lazy loading)
        self._preprocessor = None
        self._translator = None
        self._refiner = None
        self._reflection_agent = None
        self._myanmar_checker = None
        self._checker = None
        self._qa_tester = None
        self._context_updater = None
        self._memory_manager = None
        self._ollama_client = None
        
        # State
        self._shutdown_requested = False
        
        # Register signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum: int, frame: Any) -> None:
        """Handle shutdown signals gracefully."""
        self.logger.warning("Shutdown requested. Finishing current chunk...")
        self._shutdown_requested = True
    
    @property
    def memory_manager(self):
        """Lazy load memory manager."""
        if self._memory_manager is None:
            from src.memory.memory_manager import MemoryManager
            self._memory_manager = MemoryManager()
        return self._memory_manager
    
    @property
    def ollama_client(self):
        """Lazy load Ollama client."""
        if self._ollama_client is None:
            from src.utils.ollama_client import OllamaClient
            self._ollama_client = OllamaClient(
                model=self.config.models.translator,
                base_url=self.config.models.ollama_base_url,
                timeout=self.config.models.timeout,
                use_gpu=getattr(self.config.models, 'use_gpu', True),
                gpu_layers=getattr(self.config.models, 'gpu_layers', -1),
                main_gpu=getattr(self.config.models, 'main_gpu', 0)
            )
        return self._ollama_client
    
    @property
    def preprocessor(self):
        """Lazy load preprocessor."""
        if self._preprocessor is None:
            from src.agents.preprocessor import Preprocessor
            self._preprocessor = Preprocessor(
                chunk_size=self.config.processing.chunk_size,
                overlap_size=self.config.processing.chunk_overlap
            )
        return self._preprocessor
    
    @property
    def translator(self):
        """Lazy load translator."""
        if self._translator is None:
            from src.agents.translator import Translator
            self._translator = Translator(
                ollama_client=self.ollama_client,
                memory_manager=self.memory_manager,
                config=self.config.dict()
            )
        return self._translator
    
    @property
    def refiner(self):
        """Lazy load refiner."""
        if self._refiner is None:
            from src.agents.refiner import Refiner
            self._refiner = Refiner(
                ollama_client=self.ollama_client,
                memory_manager=self.memory_manager,
                config=self.config.dict()
            )
        return self._refiner
    
    @property
    def reflection_agent(self):
        """Lazy load reflection agent."""
        if self._reflection_agent is None:
            from src.agents.reflection_agent import ReflectionAgent
            self._reflection_agent = ReflectionAgent(
                ollama_client=self.ollama_client,
                memory_manager=self.memory_manager,
                config=self.config.dict()
            )
        return self._reflection_agent
    
    @property
    def myanmar_checker(self):
        """Lazy load Myanmar quality checker."""
        if self._myanmar_checker is None:
            from src.agents.myanmar_quality_checker import MyanmarQualityChecker
            self._myanmar_checker = MyanmarQualityChecker(
                ollama_client=self.ollama_client,
                memory_manager=self.memory_manager,
                config=self.config.dict()
            )
        return self._myanmar_checker
    
    @property
    def checker(self):
        """Lazy load consistency checker."""
        if self._checker is None:
            from src.agents.checker import Checker
            self._checker = Checker(
                ollama_client=self.ollama_client,
                memory_manager=self.memory_manager,
                config=self.config.dict()
            )
        return self._checker
    
    @property
    def qa_tester(self):
        """Lazy load QA tester."""
        if self._qa_tester is None:
            from src.agents.qa_tester import QATesterAgent
            self._qa_tester = QATesterAgent(
                config=self.config.dict()
            )
        return self._qa_tester
    
    @property
    def context_updater(self):
        """Lazy load context updater."""
        if self._context_updater is None:
            from src.agents.context_updater import ContextUpdater
            self._context_updater = ContextUpdater(
                memory_manager=self.memory_manager,
                config=self.config.dict()
            )
        return self._context_updater
    
    def translate_file(self, filepath: str) -> Dict[str, Any]:
        """Translate a single file.
        
        Args:
            filepath: Path to input file
            
        Returns:
            Pipeline result dictionary
        """
        self.logger.info(f"Starting translation of file: {filepath}")
        start_time = time.time()
        
        try:
            # Read file
            from src.utils.file_handler import FileHandler
            text = FileHandler.read_text(filepath)
            
            # Preprocess
            chunks = self._preprocess(text)
            
            # Translate
            translated_chunks = self._translate_chunks(chunks)
            
            # Postprocess
            result_text = self._postprocess(translated_chunks)
            
            # Save output
            output_path = self._save_output(filepath, result_text)
            
            duration = time.time() - start_time
            
            return {
                "success": True,
                "output_path": str(output_path),
                "glossary_updates": [],
                "errors": [],
                "metrics": {"duration_seconds": duration},
                "chapter": Path(filepath).stem,
                "duration_seconds": duration
            }
            
        except Exception as e:
            self.logger.error(f"Translation failed: {e}", exc_info=True)
            return {
                "success": False,
                "output_path": None,
                "glossary_updates": [],
                "errors": [str(e)],
                "metrics": {},
                "chapter": Path(filepath).stem
            }
    
    def translate_chapter(self, novel: str, chapter: int) -> Dict[str, Any]:
        """Translate a single chapter of a novel.
        
        Args:
            novel: Novel name
            chapter: Chapter number
            
        Returns:
            Pipeline result dictionary
        """
        chapter_file = Path(INPUT_DIR) / novel / f"{chapter:03d}.md"
        
        if not chapter_file.exists():
            return {
                "success": False,
                "output_path": None,
                "glossary_updates": [],
                "errors": [f"Chapter file not found: {chapter_file}"],
                "metrics": {},
                "chapter": str(chapter)
            }
        
        return self.translate_file(str(chapter_file))
    
    def translate_novel(self, novel: str, chapters: Optional[List[int]] = None) -> List[Dict[str, Any]]:
        """Translate multiple chapters of a novel.
        
        Args:
            novel: Novel name
            chapters: List of chapter numbers (None for all)
            
        Returns:
            List of pipeline results
        """
        # If no chapters specified, find all available
        if chapters is None:
            novel_dir = Path(INPUT_DIR) / novel
            if not novel_dir.exists():
                return [{
                    "success": False,
                    "output_path": None,
                    "glossary_updates": [],
                    "errors": [f"Novel directory not found: {novel_dir}"],
                    "metrics": {},
                    "chapter": "all"
                }]
            
            # Find all .md files
            chapter_files = sorted(novel_dir.glob("*.md"))
            chapters = [int(f.stem) for f in chapter_files if f.stem.isdigit()]
        
        results = []
        for chapter in chapters:
            if self._shutdown_requested:
                self.logger.warning("Shutdown requested, stopping translation")
                break
            
            result = self.translate_chapter(novel, chapter)
            results.append(result)
        
        return results
    
    def _preprocess(self, text: str) -> List[str]:
        """Preprocess text into chunks.
        
        Args:
            text: Input text
            
        Returns:
            List of text chunks
        """
        self.logger.info("Step 1/7: Preprocessing text...")

        # Clean and normalize
        text = self.preprocessor.clean_markdown(text)

        # Create chunks with overlap (returns list of dicts)
        chunk_dicts = self.preprocessor.create_chunks(text)

        # Extract text from chunk dictionaries
        chunks = [chunk['text'] for chunk in chunk_dicts]

        self.logger.info(f"Created {len(chunks)} chunks")
        return chunks
    
    def _translate_chunks(self, chunks: List[str]) -> List[str]:
        """Translate chunks through the pipeline.
        
        Args:
            chunks: List of text chunks
            
        Returns:
            List of translated chunks
        """
        translated = []
        
        for i, chunk in enumerate(chunks):
            if self._shutdown_requested:
                break
            
            self.logger.info(f"Step 2/7: Translating chunk {i+1}/{len(chunks)}...")
            
            # Stage 1: Translation
            translated_chunk = self.translator.translate_paragraph(chunk)

            # Stage 2: Refinement (if enabled and not skipped)
            if self.config.translation_pipeline.mode in ('full', 'lite'):
                self.logger.info(f"Step 3/7: Refining chunk {i+1}/{len(chunks)}...")
                translated_chunk = self.refiner.refine_paragraph(translated_chunk)

            # Stage 3: Reflection (if enabled)
            if self.config.translation_pipeline.use_reflection:
                self.logger.info(f"Step 4/7: Reflecting on chunk {i+1}/{len(chunks)}...")
                translated_chunk = self.reflection_agent.reflect_and_improve(translated_chunk, chunk)

            # Stage 4: Quality Check
            self.logger.info(f"Step 5/7: Checking quality for chunk {i+1}/{len(chunks)}...")
            quality_result = self.myanmar_checker.check_quality(translated_chunk)

            # Stage 5: Consistency Check
            self.logger.info(f"Step 6/7: Checking consistency for chunk {i+1}/{len(chunks)}...")
            consistency_issues = self.checker.check_glossary_consistency(translated_chunk)
            if consistency_issues:
                self.logger.warning(f"Found {len(consistency_issues)} consistency issues")
            
            translated.append(translated_chunk)
        
        return translated
    
    def _postprocess(self, chunks: List[str]) -> str:
        """Postprocess translated chunks.
        
        Args:
            chunks: List of translated chunks
            
        Returns:
            Final translated text
        """
        from src.utils.postprocessor import Postprocessor
        
        processor = Postprocessor()
        
        # Join chunks
        text = '\n\n'.join(chunks)
        
        # Clean up
        text = processor.clean(text)
        
        return text
    
    def _save_output(self, input_path: str, text: str) -> Path:
        """Save translated output.
        
        Args:
            input_path: Original input file path
            text: Translated text
            
        Returns:
            Path to output file
        """
        input_path = Path(input_path)
        
        # Determine output path
        relative = input_path.relative_to(INPUT_DIR) if str(input_path).startswith(INPUT_DIR) else input_path.name
        output_path = Path(OUTPUT_DIR) / relative
        output_path = output_path.with_suffix('.mm.md')
        
        # Ensure directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Add metadata if enabled
        if self.config.output.add_metadata:
            metadata = f"""<!--
Translated: {datetime.now().isoformat()}
Source: {input_path}
Pipeline: {self.config.translation_pipeline.mode}
-->

"""
            text = metadata + text
        
        # Write file
        from src.utils.file_handler import FileHandler
        FileHandler.write_text(str(output_path), text)
        
        self.logger.info(f"Step 7/7: Saved output to {output_path}")
        
        return output_path
    
    def cleanup(self) -> None:
        """Clean up resources."""
        self.logger.info("Cleaning up pipeline resources...")
        
        if self._ollama_client:
            try:
                self._ollama_client.cleanup()
            except Exception as e:
                self.logger.error(f"Error cleaning up Ollama client: {e}")
        
        if self._memory_manager:
            try:
                self._memory_manager.save_memory()
            except Exception as e:
                self.logger.error(f"Error saving memory: {e}")
