#!/usr/bin/env python3
"""
Exception hierarchy for the novel translation pipeline.

Provides structured error handling with context-aware exceptions
for different error categories (Model, Glossary, Validation, Resource).
"""

from typing import Dict, Any, Optional


class NovelTranslationError(Exception):
    """Base exception for the translation pipeline.
    
    All custom exceptions should inherit from this class to enable
    centralized error handling and context tracking.
    
    Attributes:
        message: Human-readable error description
        context: Additional context data for debugging
        error_code: Optional error code for categorization
    """

    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None
    ):
        super().__init__(message)
        self.message = message
        self.context = context or {}
        self.error_code = error_code

    def __str__(self) -> str:
        if self.context:
            return f"{self.message} (context: {self.context})"
        return self.message

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for logging/serialization."""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "error_code": self.error_code,
            "context": self.context,
        }


class ModelError(NovelTranslationError):
    """Exception raised for model-related errors.
    
    Includes errors from:
    - Ollama API failures
    - Cloud API (Gemini, OpenRouter) errors
    - Model not found or unavailable
    - Timeout or connection issues
    """

    def __init__(
        self,
        message: str,
        model_name: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        ctx = context or {}
        if model_name:
            ctx["model_name"] = model_name
        super().__init__(message, ctx, error_code="MODEL_ERROR")


class GlossaryError(NovelTranslationError):
    """Exception raised for glossary-related errors.
    
    Includes errors from:
    - Glossary file corruption or invalid format
    - Term lookup failures
    - Term validation errors
    - Duplicate term conflicts
    """

    def __init__(
        self,
        message: str,
        term: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        ctx = context or {}
        if term:
            ctx["term"] = term
        super().__init__(message, ctx, error_code="GLOSSARY_ERROR")


class ValidationError(NovelTranslationError):
    """Exception raised for validation errors.
    
    Includes errors from:
    - Configuration validation failures
    - Input file validation
    - Output quality validation
    - Schema mismatch errors
    """

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        ctx = context or {}
        if field:
            ctx["field"] = field
        super().__init__(message, ctx, error_code="VALIDATION_ERROR")


class ResourceError(NovelTranslationError):
    """Exception raised for resource-related errors.
    
    Includes errors from:
    - File I/O errors
    - Memory/resource exhaustion
    - Network connectivity issues
    - Missing required files or directories
    """

    def __init__(
        self,
        message: str,
        resource_path: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        ctx = context or {}
        if resource_path:
            ctx["resource_path"] = resource_path
        super().__init__(message, ctx, error_code="RESOURCE_ERROR")


class PipelineError(NovelTranslationError):
    """Exception raised for pipeline orchestration errors.
    
    Includes errors from:
    - Stage execution failures
    - Pipeline configuration errors
    - Dependency resolution issues
    """

    def __init__(
        self,
        message: str,
        stage: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        ctx = context or {}
        if stage:
            ctx["stage"] = stage
        super().__init__(message, ctx, error_code="PIPELINE_ERROR")


class ConfigurationError(NovelTranslationError):
    """Exception raised for configuration errors.
    
    Includes errors from:
    - Missing required configuration values
    - Invalid configuration format
    - Environment variable issues
    """

    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        ctx = context or {}
        if config_key:
            ctx["config_key"] = config_key
        super().__init__(message, ctx, error_code="CONFIG_ERROR")
