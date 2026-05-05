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
    TranslationPipelineConfig,
    PathsConfig,
    ProjectConfig,
    OutputConfig,
    QATestingConfig,
    MyanmarReadabilityConfig,
    FastConfig,
)

from src.config.loader import (
    load_config,
    load_config_from_dict,
    get_default_config,
    save_config,
    merge_configs,
    detect_config_by_source,
    load_and_merge_config,
    CONFIG_PRESETS,
)

__all__ = [
    # Config models
    "AppConfig",
    "ProcessingConfig",
    "ModelsConfig",
    "ModelRolesConfig",
    "TranslationPipelineConfig",
    "PathsConfig",
    "ProjectConfig",
    "OutputConfig",
    "QATestingConfig",
    "MyanmarReadabilityConfig",
    "FastConfig",
    # Loader functions
    "load_config",
    "load_config_from_dict",
    "get_default_config",
    "save_config",
    "merge_configs",
    "detect_config_by_source",
    "load_and_merge_config",
    "CONFIG_PRESETS",
]
