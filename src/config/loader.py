#!/usr/bin/env python3
"""
Configuration loader for the novel translation pipeline.

Provides functions to load and validate configuration from YAML files
using Pydantic models for type safety and validation.
"""

import os
import yaml
from pathlib import Path
from typing import Optional, Dict, Any, Union

from pydantic import ValidationError

from src.config.models import AppConfig
from src.exceptions import ConfigurationError


def load_config(config_path: Optional[Union[str, Path]] = None) -> AppConfig:
    """Load and validate configuration from YAML file.
    
    Args:
        config_path: Path to YAML config file. If None, uses default paths.
        
    Returns:
        Validated AppConfig instance
        
    Raises:
        ConfigurationError: If config file is missing, invalid, or fails validation
    """
    # Determine config path
    if config_path is None:
        config_path = _find_config_file()
    else:
        config_path = Path(config_path)

    # Check if file exists
    if not config_path.exists():
        raise ConfigurationError(
            f"Configuration file not found: {config_path}",
            config_key="config_path",
            context={"searched_path": str(config_path)}
        )

    # Load raw YAML
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            raw_config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigurationError(
            f"Failed to parse YAML configuration: {e}",
            config_key="yaml_parse",
            context={"file": str(config_path), "error": str(e)}
        )
    except Exception as e:
        raise ConfigurationError(
            f"Failed to read configuration file: {e}",
            config_key="file_read",
            context={"file": str(config_path), "error": str(e)}
        )

    # Handle empty config
    if raw_config is None:
        raw_config = {}

    # Validate with Pydantic
    try:
        config = AppConfig(**raw_config)
    except ValidationError as e:
        # Extract validation errors for clear messaging
        errors = []
        for error in e.errors():
            loc = ".".join(str(x) for x in error["loc"])
            errors.append(f"{loc}: {error['msg']}")

        raise ConfigurationError(
            "Configuration validation failed:\n" + "\n".join(f"  - {err}" for err in errors),
            context={"file": str(config_path), "validation_errors": errors}
        )

    return config


def load_config_from_dict(config_dict: Dict[str, Any]) -> AppConfig:
    """Load configuration from a dictionary.
    
    Args:
        config_dict: Configuration dictionary
        
    Returns:
        Validated AppConfig instance
        
    Raises:
        ConfigurationError: If validation fails
    """
    try:
        return AppConfig(**config_dict)
    except ValidationError as e:
        errors = []
        for error in e.errors():
            loc = ".".join(str(x) for x in error["loc"])
            errors.append(f"{loc}: {error['msg']}")

        raise ConfigurationError(
            "Configuration validation failed:\n" + "\n".join(f"  - {err}" for err in errors),
            context={"validation_errors": errors}
        )


def _find_config_file() -> Path:
    """Find configuration file using default search paths.
    
    Returns:
        Path to config file
        
    Raises:
        ConfigurationError: If no config file is found
    """
    # Search paths in order of priority
    search_paths = [
        Path("config/settings.yaml"),
        Path("config/settings.yml"),
        Path("settings.yaml"),
        Path("settings.yml"),
    ]

    for path in search_paths:
        if path.exists():
            return path

    # Check environment variable
    env_path = os.environ.get("NOVEL_CONFIG_PATH")
    if env_path:
        path = Path(env_path)
        if path.exists():
            return path
        raise ConfigurationError(
            f"Config file from NOVEL_CONFIG_PATH not found: {env_path}",
            config_key="NOVEL_CONFIG_PATH"
        )

    raise ConfigurationError(
        "No configuration file found. Searched: " + ", ".join(str(p) for p in search_paths),
        config_key="config_file",
        context={"searched_paths": [str(p) for p in search_paths]}
    )


CONFIG_PRESETS = {
    "en_us": "config/settings.yaml",
    "zh_cn": "config/settings.pivot.yaml",
    "default": "config/settings.yaml",
    "fast": "config/settings.fast.yaml",
    "pivot": "config/settings.pivot.yaml",
}


def _normalize_lang_key(lang: str) -> str:
    """Normalize language code: en-US → en_us, zh-CN → zh_cn"""
    return lang.lower().replace("-", "_").replace(" ", "_")


def detect_config_by_source(
    source_language: Optional[str] = None,
    config_path: Optional[Union[str, Path]] = None,
    mode: Optional[str] = None,
) -> Path:
    """Auto-detect best config file based on source language or explicit mode.
    
    Priority:
    1. Explicit config_path (if provided and exists)
    2. Explicit mode (fast, pivot, default)
    3. Source language auto-detection (en-US → default, zh-CN → pivot)
    
    Args:
        source_language: Source language code (en-US, zh-CN, etc.)
        config_path: Explicit config path override
        mode: Explicit mode (fast, pivot, default)
        
    Returns:
        Path to detected config file
    """
    # 1. Explicit config path takes priority
    if config_path:
        path = Path(config_path)
        if path.exists():
            return path
    
    # 2. Explicit mode
    if mode and mode in CONFIG_PRESETS:
        path = Path(CONFIG_PRESETS[mode])
        if path.exists():
            return path
    
    # 3. Source language auto-detection
    if source_language:
        lang_key = _normalize_lang_key(source_language)
        if lang_key in CONFIG_PRESETS:
            path = Path(CONFIG_PRESETS[lang_key])
            if path.exists():
                return path
    
    # 4. Fallback to default
    default_path = Path(CONFIG_PRESETS["default"])
    if default_path.exists():
        return default_path
    
    # 5. Last resort: find any config
    return _find_config_file()


def load_and_merge_config(
    base_config: Optional[Union[str, Path]] = None,
    override_config: Optional[Union[str, Path]] = None,
    source_language: Optional[str] = None,
    mode: Optional[str] = None,
) -> AppConfig:
    """Load config with auto-detection and optional merge.
    
    This function:
    1. Detects appropriate config file based on source_language or mode
    2. Optionally merges a second config file on top
    
    Args:
        base_config: Base config file path (None = auto-detect)
        override_config: Override config to merge on top
        source_language: Source language for auto-detection
        mode: Explicit mode (fast, pivot, default)
        
    Returns:
        Merged and validated AppConfig
    """
    # Detect base config
    if base_config is None:
        base_path = detect_config_by_source(source_language=source_language, mode=mode)
    else:
        base_path = Path(base_config)
    
    base = load_config(base_path)
    
    # Merge override if provided
    if override_config:
        override_path = Path(override_config)
        if override_path.exists():
            override_dict = yaml.safe_load(open(override_path, encoding='utf-8'))
            if override_dict:
                base = merge_configs(base, override_dict)
    
    return base


def get_default_config() -> AppConfig:
    """Get default configuration.
    
    Returns:
        AppConfig with default values
    """
    return AppConfig()


def save_config(config: AppConfig, output_path: Union[str, Path]) -> None:
    """Save configuration to YAML file.
    
    Args:
        config: Configuration to save
        output_path: Path to output file
        
    Raises:
        ConfigurationError: If save fails
    """
    output_path = Path(output_path)

    # Ensure directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Convert to dict
        config_dict = config.model_dump()

        # Write YAML
        with open(output_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_dict, f, default_flow_style=False, allow_unicode=True)
    except Exception as e:
        raise ConfigurationError(
            f"Failed to save configuration: {e}",
            config_key="save",
            context={"output_path": str(output_path), "error": str(e)}
        )


def merge_configs(base_config: AppConfig, override_dict: Dict[str, Any]) -> AppConfig:
    """Merge override values into base configuration.
    
    Args:
        base_config: Base configuration
        override_dict: Dictionary of override values
        
    Returns:
        New AppConfig with merged values
    """
    # Convert base to dict
    base_dict = base_config.model_dump()

    # Deep merge
    merged = _deep_merge(base_dict, override_dict)

    # Validate and return
    return AppConfig(**merged)


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Deep merge two dictionaries.
    
    Args:
        base: Base dictionary
        override: Override dictionary
        
    Returns:
        Merged dictionary
    """
    result = base.copy()

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value

    return result
