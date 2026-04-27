"""Helpers to load available Ollama models for UI selectors."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import yaml


DEFAULT_MODELS = [
    "qwen2.5:14b",
    "qwen2.5:7b",
    "qwen:7b",
    "gemma:7b",
]


def _dedupe_keep_order(models: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for model in models:
        if not model or model in seen:
            continue
        seen.add(model)
        result.append(model)
    return result


def _load_models_from_ollama_api(base_url: str) -> list[str]:
    try:
        with urlopen(f"{base_url.rstrip('/')}/api/tags", timeout=2) as response:
            data = json.loads(response.read().decode("utf-8"))
        models = [item.get("name", "").strip() for item in data.get("models", [])]
        return _dedupe_keep_order(models)
    except (URLError, TimeoutError, json.JSONDecodeError, ValueError):
        return []
    except Exception:
        return []


def _load_models_from_ollama_cli() -> list[str]:
    try:
        proc = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except Exception:
        return []

    if proc.returncode != 0 or not proc.stdout:
        return []

    models: list[str] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line or line.startswith("NAME"):
            continue
        model = line.split()[0].strip()
        if model:
            models.append(model)
    return _dedupe_keep_order(models)


def _load_models_from_config(config_path: Path) -> list[str]:
    if not config_path.exists():
        return []
    try:
        with config_path.open("r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    except Exception:
        return []

    models: list[str] = []
    roles = cfg.get("model_roles", {})
    if isinstance(roles, dict):
        translator_models = roles.get("translator", [])
        if isinstance(translator_models, list):
            models.extend(str(item).strip() for item in translator_models)

    model_cfg = cfg.get("models", {})
    if isinstance(model_cfg, dict):
        for key in ("translator", "editor", "checker", "refiner"):
            value = model_cfg.get(key)
            if isinstance(value, str):
                models.append(value.strip())

    return _dedupe_keep_order(models)


def get_available_models(
    config_path: str = "config/settings.yaml",
    ollama_base_url: str = "http://localhost:11434",
) -> list[str]:
    """Return installed Ollama models with config/default fallbacks."""
    models = _load_models_from_ollama_api(ollama_base_url)
    if not models:
        models = _load_models_from_ollama_cli()
    if not models:
        models = _load_models_from_config(Path(config_path))
    if not models:
        models = DEFAULT_MODELS.copy()
    return models
