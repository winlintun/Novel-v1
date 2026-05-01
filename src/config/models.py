#!/usr/bin/env python3
"""
Pydantic configuration models for the novel translation pipeline.

Provides validated configuration management with automatic type checking,
enforcement of constraints, and clear error messages for misconfiguration.
"""

from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field, validator, root_validator


class ProcessingConfig(BaseModel):
    """Processing and chunking configuration."""
    
    chunk_size: int = Field(
        default=800,
        ge=100,
        le=4000,
        description="Size of text chunks in characters (token-aware, never splits paragraphs)"
    )
    temperature: float = Field(
        default=0.2,
        ge=0.0,
        le=2.0,
        description="Sampling temperature for model generation"
    )
    top_p: float = Field(
        default=0.92,
        ge=0.0,
        le=1.0,
        description="Nucleus sampling parameter"
    )
    top_k: int = Field(
        default=50,
        ge=1,
        le=100,
        description="Top-k sampling parameter"
    )
    repeat_penalty: float = Field(
        default=1.5,
        ge=1.0,
        le=2.0,
        description="Repetition penalty for model generation"
    )
    max_retries: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum number of retry attempts"
    )
    request_timeout: int = Field(
        default=900,
        ge=60,
        le=3600,
        description="Request timeout in seconds"
    )
    stream: bool = Field(
        default=True,
        description="Whether to use streaming responses"
    )


class ModelsConfig(BaseModel):
    """Model configuration for different pipeline stages."""

    translator: str = Field(
        default="qwen2.5:14b",
        description="Model for translation stage"
    )
    editor: str = Field(
        default="qwen2.5:14b",
        description="Model for editing/refinement stage"
    )
    checker: str = Field(
        default="qwen:7b",
        description="Model for quality checking stage"
    )
    refiner: str = Field(
        default="qwen:7b",
        description="Model for refinement stage"
    )
    cloud_model: str = Field(
        default="gemini-2.5-flash",
        description="Cloud model for API-based translation"
    )
    provider: Literal["ollama", "gemini", "openrouter"] = Field(
        default="ollama",
        description="Model provider type"
    )
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Base URL for Ollama API"
    )
    timeout: int = Field(
        default=300,
        ge=30,
        le=600,
        description="API timeout in seconds"
    )
    # GPU Configuration
    use_gpu: bool = Field(
        default=True,
        description="Enable GPU acceleration for model inference"
    )
    gpu_layers: int = Field(
        default=-1,
        ge=-1,
        le=1000,
        description="Number of model layers to offload to GPU (-1 = auto/all)"
    )
    main_gpu: int = Field(
        default=0,
        ge=0,
        le=16,
        description="Primary GPU device index for multi-GPU setups"
    )


class ModelRolesConfig(BaseModel):
    """Model role assignments for different agents."""
    
    translator: List[str] = Field(
        default=["qwen2.5:14b", "qwen2.5:7b", "qwen:7b"],
        description="Models suitable for translation"
    )
    refiner: List[str] = Field(
        default=["qwen2.5:14b", "qwen:7b"],
        description="Models suitable for refinement"
    )
    checker: List[str] = Field(
        default=["qwen:7b", "gemma:7b"],
        description="Models suitable for quality checking"
    )
    qa_final: List[str] = Field(
        default=["qwen:7b", "gemma:7b"],
        description="Models suitable for final QA"
    )
    glossary_sync: List[str] = Field(
        default=["qwen:7b"],
        description="Models suitable for glossary synchronization"
    )


class ModelRouterConfig(BaseModel):
    """Model router configuration for automatic fallback."""
    
    enabled: bool = Field(
        default=True,
        description="Whether model routing is enabled"
    )
    max_fallback_depth: int = Field(
        default=2,
        ge=1,
        le=5,
        description="Maximum fallback attempts"
    )
    retry_on_failure: bool = Field(
        default=True,
        description="Whether to retry on model failure"
    )
    vram_budget_gb: float = Field(
        default=16.0,
        ge=4.0,
        le=128.0,
        description="VRAM budget in GB for model selection"
    )


class TranslationPipelineConfig(BaseModel):
    """Translation pipeline configuration."""
    
    mode: Literal["full", "lite", "fast", "single_stage", "two_stage"] = Field(
        default="full",
        description="Pipeline execution mode"
    )
    use_reflection: bool = Field(
        default=False,
        description="Whether to use reflection agent"
    )
    stage1_model: str = Field(
        default="qwen2.5:14b",
        description="Model for stage 1 (two-stage mode)"
    )
    stage2_model: str = Field(
        default="qwen:7b",
        description="Model for stage 2 (two-stage mode)"
    )
    reflection_model: str = Field(
        default="qwen:7b",
        description="Model for reflection agent"
    )


class PathsConfig(BaseModel):
    """File path configuration."""
    
    input_dir: str = Field(
        default="data/input",
        description="Input directory for source files"
    )
    output_dir: str = Field(
        default="data/output",
        description="Output directory for translations"
    )
    books_dir: str = Field(
        default="books",
        description="Books directory"
    )
    glossary_file: str = Field(
        default="data/glossary.json",
        description="Path to glossary file"
    )
    context_memory_file: str = Field(
        default="data/context_memory.json",
        description="Path to context memory file"
    )
    log_file: str = Field(
        default="logs/translation.log",
        description="Path to log file"
    )
    templates_dir: str = Field(
        default="templates",
        description="Templates directory"
    )


class ProjectConfig(BaseModel):
    """Project metadata configuration."""
    
    name: str = Field(
        default="novel_translation",
        description="Project name"
    )
    novel_genre: str = Field(
        default="Xianxia/Cultivation",
        description="Novel genre"
    )
    source_language: str = Field(
        default="zh-CN",
        description="Source language code"
    )
    target_language: str = Field(
        default="my-MM",
        description="Target language code"
    )


class OutputConfig(BaseModel):
    """Output formatting configuration."""
    
    format: Literal["markdown", "txt", "json"] = Field(
        default="markdown",
        description="Output file format"
    )
    preserve_formatting: bool = Field(
        default=True,
        description="Whether to preserve original formatting"
    )
    add_metadata: bool = Field(
        default=True,
        description="Whether to add metadata headers"
    )
    add_translator_notes: bool = Field(
        default=False,
        description="Whether to add translator notes"
    )


class QATestingConfig(BaseModel):
    """QA testing configuration."""
    
    enabled: bool = Field(
        default=True,
        description="Whether QA testing is enabled"
    )
    auto_retry: bool = Field(
        default=False,
        description="Whether to auto-retry on QA failure"
    )
    fail_on_placeholders: bool = Field(
        default=False,
        description="Whether to fail on unresolved placeholders"
    )
    markdown_strict: bool = Field(
        default=True,
        description="Whether to enforce strict markdown validation"
    )
    min_myanmar_ratio: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum Myanmar character ratio"
    )


class MyanmarReadabilityConfig(BaseModel):
    """Myanmar readability checking configuration."""
    
    enabled: bool = Field(
        default=True,
        description="Whether readability checking is enabled"
    )
    min_myanmar_ratio: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum Myanmar character ratio"
    )
    block_on_fail: bool = Field(
        default=False,
        description="Whether to block on readability failure"
    )
    flag_on_fail: bool = Field(
        default=True,
        description="Whether to flag readability issues"
    )


class GlossaryV3Config(BaseModel):
    """Glossary v3 advanced configuration."""
    
    enabled: bool = Field(
        default=True,
        description="Whether glossary v3 is enabled"
    )
    path: str = Field(
        default="data/glossary_v3.json",
        description="Path to glossary v3 file"
    )
    lazy_load: bool = Field(
        default=True,
        description="Whether to lazy-load glossary entries"
    )
    cache_ttl_minutes: int = Field(
        default=30,
        ge=1,
        le=1440,
        description="Cache TTL in minutes"
    )
    max_prompt_entries: int = Field(
        default=40,
        ge=10,
        le=100,
        description="Maximum glossary entries in prompt"
    )
    alias_matching: bool = Field(
        default=True,
        description="Whether to match aliases"
    )
    exception_rules: bool = Field(
        default=True,
        description="Whether to apply exception rules"
    )
    include_examples: bool = Field(
        default=False,
        description="Whether to include examples in prompt"
    )
    track_usage: bool = Field(
        default=True,
        description="Whether to track term usage"
    )
    priority_threshold: int = Field(
        default=2,
        ge=1,
        le=10,
        description="Priority threshold for term inclusion"
    )
    show_exceptions_count: bool = Field(
        default=True,
        description="Whether to show exception count"
    )
    show_pronunciation: bool = Field(
        default=False,
        description="Whether to show pronunciation"
    )
    prompt_format: Literal["markdown", "json", "xml"] = Field(
        default="markdown",
        description="Glossary prompt format"
    )


class FastConfig(BaseModel):
    """Fast mode configuration."""
    
    enabled: bool = Field(
        default=False,
        description="Whether fast mode is enabled"
    )
    translator: str = Field(
        default="qwen:7b",
        description="Fast mode translator model"
    )
    editor: str = Field(
        default="qwen:7b",
        description="Fast mode editor model"
    )
    checker: str = Field(
        default="qwen:7b",
        description="Fast mode checker model"
    )
    refiner: str = Field(
        default="qwen:7b",
        description="Fast mode refiner model"
    )
    chunk_size: int = Field(
        default=1200,
        ge=100,
        le=4000,
        description="Fast mode chunk size"
    )
    temperature: float = Field(
        default=0.45,
        ge=0.0,
        le=2.0,
        description="Fast mode temperature"
    )
    repeat_penalty: float = Field(
        default=1.3,
        ge=1.0,
        le=2.0,
        description="Fast mode repeat penalty"
    )
    num_ctx: int = Field(
        default=4096,
        ge=2048,
        le=32768,
        description="Fast mode context window"
    )


class AppConfig(BaseModel):
    """Root application configuration.
    
    This is the main configuration class that combines all sub-configurations.
    """
    
    project: ProjectConfig = Field(
        default_factory=ProjectConfig,
        description="Project metadata"
    )
    models: ModelsConfig = Field(
        default_factory=ModelsConfig,
        description="Model configuration"
    )
    model_roles: ModelRolesConfig = Field(
        default_factory=ModelRolesConfig,
        description="Model role assignments"
    )
    model_router: ModelRouterConfig = Field(
        default_factory=ModelRouterConfig,
        description="Model router configuration"
    )
    processing: ProcessingConfig = Field(
        default_factory=ProcessingConfig,
        description="Processing configuration"
    )
    translation_pipeline: TranslationPipelineConfig = Field(
        default_factory=TranslationPipelineConfig,
        description="Translation pipeline configuration"
    )
    paths: PathsConfig = Field(
        default_factory=PathsConfig,
        description="File path configuration"
    )
    output: OutputConfig = Field(
        default_factory=OutputConfig,
        description="Output formatting configuration"
    )
    qa_testing: QATestingConfig = Field(
        default_factory=QATestingConfig,
        description="QA testing configuration"
    )
    myanmar_readability: MyanmarReadabilityConfig = Field(
        default_factory=MyanmarReadabilityConfig,
        description="Myanmar readability configuration"
    )
    glossary_v3: GlossaryV3Config = Field(
        default_factory=GlossaryV3Config,
        description="Glossary v3 configuration"
    )
    fast_config: FastConfig = Field(
        default_factory=FastConfig,
        description="Fast mode configuration"
    )
    
    class Config:
        """Pydantic configuration."""
        env_prefix = "NOVEL_"
        case_sensitive = False
        validate_assignment = True
