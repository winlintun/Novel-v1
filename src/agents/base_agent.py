#!/usr/bin/env python3
"""
Base Agent class for all translation pipeline agents.
Provides common functionality: logging, error handling, ollama client.
"""

import logging
from typing import Optional, Dict, Any

from src.utils.ollama_client import OllamaClient
from src.memory.memory_manager import MemoryManager

logger = logging.getLogger(__name__)


class BaseAgent:
    """
    Base class for all agents in the translation pipeline.
    Provides common functionality for logging, error handling, and memory management.
    """

    def __init__(
        self,
        ollama_client: Optional[OllamaClient] = None,
        memory_manager: Optional[MemoryManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.client = ollama_client
        self.memory = memory_manager or MemoryManager()
        self.config = config or {}
        self._setup_logging()

    def _setup_logging(self) -> None:
        """Setup agent-specific logging."""
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)

    def log_info(self, message: str) -> None:
        """Log info message."""
        logger.info(f"[{self.__class__.__name__}] {message}")

    def log_warning(self, message: str) -> None:
        """Log warning message."""
        logger.warning(f"[{self.__class__.__name__}] {message}")

    def log_error(self, message: str, exception: Optional[Exception] = None) -> None:
        """Log error message with optional exception."""
        logger.error(f"[{self.__class__.__name__}] {message}")
        if exception:
            logger.error(f"Exception: {str(exception)}")

    def handle_error(self, error: Exception, context: str = "") -> None:
        """Centralized error handling."""
        self.log_error(f"{context}: {str(error)}", error)

    def validate_config(self, required_keys: list) -> bool:
        """Validate required config keys exist."""
        missing = [k for k in required_keys if k not in self.config]
        if missing:
            self.log_warning(f"Missing config keys: {missing}")
            return False
        return True

    def get_config(self, key: str, default: Any = None) -> Any:
        """Get config value with default."""
        return self.config.get(key, default)
