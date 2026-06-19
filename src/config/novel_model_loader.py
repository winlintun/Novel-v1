"""Per-novel model configuration loader.

Loads novel-specific model assignments and genre settings from
config/novel_models.yaml. Enables different novels to use different
translation models, temperatures, chunk sizes, and genre-aware prompts.

Usage:
    from src.config.novel_model_loader import get_novel_config

    novel_cfg = get_novel_config("reverend-insanity")
    # Returns: {"genre": "xianxia", "translator": "padauk-gemma:q8_0", ...}
"""

from pathlib import Path
from typing import Any, Optional
import yaml

_NOVEL_CONFIG_PATH = Path("config/novel_models.yaml")
_CACHE: Optional[dict[str, Any]] = None


def _load() -> dict[str, Any]:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    if not _NOVEL_CONFIG_PATH.exists():
        _CACHE = {"novels": {}, "defaults": _default_fallback()}
        return _CACHE
    with open(_NOVEL_CONFIG_PATH, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    _CACHE = raw
    return _CACHE


def _default_fallback() -> dict[str, Any]:
    return {
        "genre": "xianxia",
        "translator": "padauk-gemma:q8_0",
        "refiner": "padauk-gemma:q8_0",
        "checker": "qwen:7b",
        "temperature": 0.2,
        "chunk_size": 1200,
        "pipeline_mode": "single_stage",
    }


def get_novel_config(novel_name: str) -> dict[str, Any]:
    """Get model configuration for a specific novel.

    Args:
        novel_name: Novel directory name (e.g. "reverend-insanity")

    Returns:
        Dict with keys: genre, translator, refiner, checker,
        temperature, chunk_size, pipeline_mode (and any extras from YAML).
        Falls back to defaults if novel is not listed.
    """
    data = _load()
    novels = data.get("novels", {})
    defaults = data.get("defaults", _default_fallback())

    novel_key = novel_name.lower().replace(" ", "-").replace("_", "-")
    for key, cfg in novels.items():
        if key.lower().replace(" ", "-").replace("_", "-") == novel_key:
            merged = dict(defaults)
            merged.update(cfg)
            return merged
    return dict(defaults)


def get_novel_genre(novel_name: str) -> str:
    """Get the genre tag for a novel (xianxia, wuxia, fantasy, romance)."""
    return get_novel_config(novel_name).get("genre", "xianxia")


def apply_novel_config_to_appconfig(novel_name: str, app_config) -> None:
    """Mutate an AppConfig in-place with per-novel overrides.

    This sets .models.translator, .models.refiner, .models.checker,
    .processing.temperature, .processing.chunk_size, and
    .translation_pipeline.mode on the given config object.

    Args:
        novel_name: Novel directory name
        app_config: An AppConfig instance (mutated in-place)
    """
    cfg = get_novel_config(novel_name)

    app_config.models.translator = cfg.get("translator", app_config.models.translator)
    app_config.models.refiner = cfg.get("refiner", app_config.models.refiner)
    app_config.models.checker = cfg.get("checker", app_config.models.checker)
    app_config.models.editor = cfg.get("refiner", app_config.models.editor)

    temp = cfg.get("temperature")
    if temp is not None:
        app_config.processing.temperature = temp

    chunk = cfg.get("chunk_size")
    if chunk is not None:
        app_config.processing.chunk_size = chunk


def reload() -> None:
    """Force reload from disk on next call."""
    global _CACHE
    _CACHE = None
