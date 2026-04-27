#!/usr/bin/env python3
"""
Type definitions for the novel translation pipeline.

Provides TypedDict definitions for complex data structures used throughout
the codebase, enabling better type safety and IDE autocomplete support.
"""

from typing import TypedDict, List, Dict, Any, Optional, Literal
from typing_extensions import NotRequired


class GlossaryTerm(TypedDict):
    """Schema for a glossary term entry.
    
    Attributes:
        id: Unique identifier for the term
        source: Source language term (e.g., Chinese)
        target: Target language translation (e.g., Myanmar)
        category: Term category (character, place, item, level, etc.)
        verified: Whether the term has been verified by a human
        chapter_first_seen: Chapter number where term first appeared
        added_at: ISO timestamp when term was added
        aliases: Alternative names for the term (optional)
        pronunciation: Pronunciation guide (optional)
        notes: Additional notes about the term (optional)
    """
    id: str
    source: str
    target: str
    category: str
    verified: bool
    chapter_first_seen: int
    added_at: str
    aliases: NotRequired[List[str]]
    pronunciation: NotRequired[str]
    notes: NotRequired[str]


class PendingGlossaryTerm(TypedDict):
    """Schema for a pending glossary term awaiting review.
    
    Attributes:
        source: Source language term
        target: Proposed target language translation
        category: Term category
        extracted_from_chapter: Chapter where term was extracted
        status: Current status (pending, approved, rejected)
        suggested_at: ISO timestamp when term was suggested
        confidence: Confidence score from extractor (0.0-1.0)
    """
    source: str
    target: str
    category: str
    extracted_from_chapter: int
    status: Literal["pending", "approved", "rejected"]
    suggested_at: str
    confidence: NotRequired[float]


class TranslationChunk(TypedDict):
    """Schema for a translation chunk.
    
    Attributes:
        index: Chunk index in the chapter
        original: Original source text
        translated: Translated text (None if not yet translated)
        meta: Additional metadata (word count, etc.)
        status: Current translation status
        stage: Current pipeline stage
        retries: Number of retry attempts
        error: Error message if failed
    """
    index: int
    original: str
    translated: Optional[str]
    meta: Dict[str, Any]
    status: Literal["pending", "processing", "completed", "failed"]
    stage: NotRequired[str]
    retries: NotRequired[int]
    error: NotRequired[Optional[str]]


class PipelineResult(TypedDict):
    """Schema for pipeline execution result.
    
    Attributes:
        success: Whether the pipeline completed successfully
        output_path: Path to the output file (None if failed)
        glossary_updates: List of new glossary terms extracted
        errors: List of error messages
        metrics: Performance and quality metrics
        chapter: Chapter number/name
        duration_seconds: Total execution time
    """
    success: bool
    output_path: Optional[str]
    glossary_updates: List[GlossaryTerm]
    errors: List[str]
    metrics: Dict[str, float]
    chapter: str
    duration_seconds: NotRequired[float]


class ContextMemory(TypedDict):
    """Schema for context memory state.
    
    Attributes:
        current_chapter: Currently processing chapter number
        last_translated_chapter: Last successfully translated chapter
        summary: Summary of previous chapter content
        active_characters: Dictionary of active characters and their states
        recent_events: List of recent story events
        paragraph_buffer: FIFO buffer of recent paragraphs for context
    """
    current_chapter: int
    last_translated_chapter: int
    summary: str
    active_characters: Dict[str, Any]
    recent_events: List[str]
    paragraph_buffer: List[str]


class ModelConfig(TypedDict):
    """Schema for model configuration.
    
    Attributes:
        translator: Model name for translation
        editor: Model name for editing/refinement
        checker: Model name for quality checking
        provider: Model provider (ollama, gemini, openrouter)
        base_url: API base URL for the provider
        timeout: Request timeout in seconds
    """
    translator: str
    editor: str
    checker: str
    provider: Literal["ollama", "gemini", "openrouter"]
    base_url: str
    timeout: int


class ProcessingConfig(TypedDict):
    """Schema for processing configuration.
    
    Attributes:
        chunk_size: Size of text chunks in characters
        chunk_overlap: Overlap between chunks in characters
        temperature: Sampling temperature (0.0-2.0)
        top_p: Nucleus sampling parameter (0.0-1.0)
        top_k: Top-k sampling parameter
        repeat_penalty: Repetition penalty (1.0+)
        max_retries: Maximum number of retry attempts
        request_timeout: Request timeout in seconds
    """
    chunk_size: int
    chunk_overlap: int
    temperature: float
    top_p: float
    top_k: int
    repeat_penalty: float
    max_retries: int
    request_timeout: int


class TranslationPipelineConfig(TypedDict):
    """Schema for translation pipeline configuration.
    
    Attributes:
        mode: Pipeline mode (full, lite, fast, single_stage, two_stage)
        use_reflection: Whether to use reflection agent
        stage1_model: Model for stage 1 (for two-stage)
        stage2_model: Model for stage 2 (for two-stage)
        reflection_model: Model for reflection agent
    """
    mode: Literal["full", "lite", "fast", "single_stage", "two_stage"]
    use_reflection: bool
    stage1_model: str
    stage2_model: str
    reflection_model: str


class QualityMetrics(TypedDict):
    """Schema for translation quality metrics.
    
    Attributes:
        myanmar_char_ratio: Ratio of Myanmar characters in output (0.0-1.0)
        glossary_consistency_score: Glossary term consistency score (0.0-1.0)
        placeholder_count: Number of unresolved placeholders
        repetition_score: Repetition detection score
        markdown_preservation: Whether markdown formatting is preserved
    """
    myanmar_char_ratio: float
    glossary_consistency_score: float
    placeholder_count: int
    repetition_score: float
    markdown_preservation: bool


class AgentMetadata(TypedDict):
    """Schema for agent metadata.
    
    Attributes:
        name: Agent name
        version: Agent version
        description: Agent description
        supported_languages: List of supported language codes
        requires_glossary: Whether agent requires glossary
        requires_memory: Whether agent requires memory manager
    """
    name: str
    version: str
    description: str
    supported_languages: List[str]
    requires_glossary: bool
    requires_memory: bool
