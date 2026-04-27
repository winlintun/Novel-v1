#!/usr/bin/env python3
"""
Configuration module for the novel translation pipeline.

Provides Pydantic models for type-safe configuration management
with automatic validation and clear error messages.
"""

from src.config.models import (
    AppConfig,
    ProcessingConfig,
    ModelsConfig,
    ModelRolesConfig,
    ModelRouterConfig,
    TranslationPipelineConfig,
    PathsConfig,
    ProjectConfig,
    OutputConfig,
    QATestingConfig,
    MyanmarReadabilityConfig,
    GlossaryV3Config,
    FastConfig,
)

from src.config.loader import (
    load_config,
    load_config_from_dict,
    get_default_config,
    save_config,
    merge_configs,
)

__all__ = [
    # Config models
    "AppConfig",
    "ProcessingConfig",
    "ModelsConfig",
    "ModelRolesConfig",
    "ModelRouterConfig",
    "TranslationPipelineConfig",
    "PathsConfig",
    "ProjectConfig",
    "OutputConfig",
    "QATestingConfig",
    "MyanmarReadabilityConfig",
    "GlossaryV3Config",
    "FastConfig",
    # Loader functions
    "load_config",
    "load_config_from_dict",
    "get_default_config",
    "save_config",
    "merge_configs",
]
