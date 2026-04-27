#!/usr/bin/env python3
"""
Types module for the novel translation pipeline.

Provides TypedDict definitions for complex data structures
used throughout the codebase.
"""

from src.types.definitions import (
    GlossaryTerm,
    PendingGlossaryTerm,
    TranslationChunk,
    PipelineResult,
    ContextMemory,
    ModelConfig,
    ProcessingConfig,
    TranslationPipelineConfig,
    QualityMetrics,
    AgentMetadata,
)

__all__ = [
    "GlossaryTerm",
    "PendingGlossaryTerm",
    "TranslationChunk",
    "PipelineResult",
    "ContextMemory",
    "ModelConfig",
    "ProcessingConfig",
    "TranslationPipelineConfig",
    "QualityMetrics",
    "AgentMetadata",
]
