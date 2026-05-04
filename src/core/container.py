#!/usr/bin/env python3
"""
Dependency injection container for the novel translation pipeline.

Provides centralized dependency management for:
- OllamaClient instances
- MemoryManager instances
- Agent instances
- Pipeline instances

This enables:
- Easy mocking for unit tests
- Clear dependency graph
- Runtime configuration switching
- Reduced coupling between components
"""

from typing import Optional, Any
from dataclasses import dataclass, field

from src.config import AppConfig


@dataclass
class Container:
    """Dependency injection container.

    Manages the lifecycle of all application components
    and provides factory methods for creating instances.
    """

    config: AppConfig
    novel_name: Optional[str] = field(default=None)

    # Cached instances (singletons)
    _ollama_client: Optional[Any] = field(default=None, repr=False)
    _memory_manager: Optional[Any] = field(default=None, repr=False)
    _translator: Optional[Any] = field(default=None, repr=False)
    _refiner: Optional[Any] = field(default=None, repr=False)
    _checker: Optional[Any] = field(default=None, repr=False)

    def get_ollama_client(self) -> Any:
        """Get or create OllamaClient instance.
        
        Returns:
            OllamaClient instance
        """
        if self._ollama_client is None:
            from src.utils.ollama_client import OllamaClient
            self._ollama_client = OllamaClient(
                model=self.config.models.translator,
                base_url=self.config.models.ollama_base_url,
                timeout=self.config.models.timeout,
                use_gpu=getattr(self.config.models, 'use_gpu', True),
                use_generate_endpoint=getattr(self.config.models, 'use_generate_endpoint', False),
                num_ctx=getattr(self.config.models, 'num_ctx', 8192),
                gpu_layers=getattr(self.config.models, 'gpu_layers', -1),
                main_gpu=getattr(self.config.models, 'main_gpu', 0)
            )
        return self._ollama_client

    def get_memory_manager(self, novel_name: Optional[str] = None) -> Any:
        """Get or create MemoryManager instance.

        If novel_name is provided (or detectable from config paths), paths are
        resolved per-novel. Config paths containing '{novel_name}' are treated
        as templates and resolved automatically.
        """
        if self._memory_manager is None:
            from src.memory.memory_manager import MemoryManager

            glossary_path = self.config.paths.glossary_file
            context_path = self.config.paths.context_memory_file

            # Caller arg takes priority, then container-level novel_name
            effective_novel = novel_name or self.novel_name

            # Detect template placeholders — resolve via novel_name
            has_template = "{novel_name}" in glossary_path or "{novel_name}" in context_path

            if has_template or effective_novel:
                self._memory_manager = MemoryManager(novel_name=effective_novel)
            else:
                self._memory_manager = MemoryManager(
                    glossary_path=glossary_path,
                    context_path=context_path,
                )
        return self._memory_manager

    def get_translator(self) -> Any:
        """Get or create Translator instance.
        
        Returns:
            Translator instance
        """
        if self._translator is None:
            from src.agents.translator import Translator
            self._translator = Translator(
                ollama_client=self.get_ollama_client(),
                memory_manager=self.get_memory_manager(self.novel_name),
                config=self.config.model_dump()
            )
        return self._translator

    def get_refiner(self) -> Any:
        """Get or create Refiner instance.
        
        Returns:
            Refiner instance
        """
        if self._refiner is None:
            from src.agents.refiner import Refiner
            self._refiner = Refiner(
                ollama_client=self.get_ollama_client(),
                memory_manager=self.get_memory_manager(self.novel_name),
                config=self.config.model_dump()
            )
        return self._refiner

    def get_checker(self) -> Any:
        """Get or create Checker instance.
        
        Returns:
            Checker instance
        """
        if self._checker is None:
            from src.agents.checker import Checker
            self._checker = Checker(
                memory_manager=self.get_memory_manager(self.novel_name),
                config=self.config.model_dump()
            )
        return self._checker

    def create_preprocessor(self) -> Any:
        """Create a new Preprocessor instance.
        
        Returns:
            Preprocessor instance
        """
        from src.agents.preprocessor import Preprocessor
        return Preprocessor(
            chunk_size=self.config.processing.chunk_size,
        )

    def create_pipeline(self) -> Any:
        """Create a new TranslationPipeline instance.
        
        Returns:
            TranslationPipeline instance
        """
        from src.pipeline.orchestrator import TranslationPipeline
        return TranslationPipeline(self.config)

    def cleanup(self) -> None:
        """Clean up all cached resources."""
        if self._ollama_client:
            try:
                self._ollama_client.cleanup()
            except Exception:
                pass
            self._ollama_client = None

        if self._memory_manager:
            try:
                self._memory_manager.save_memory()
            except Exception:
                pass
            self._memory_manager = None

        self._translator = None
        self._refiner = None
        self._checker = None


def create_container(config: AppConfig, novel_name: Optional[str] = None) -> Container:
    """Create a new container with the given configuration.

    Args:
        config: Application configuration
        novel_name: Novel name for per-novel glossary/context file resolution

    Returns:
        Configured Container instance
    """
    return Container(config=config, novel_name=novel_name)
