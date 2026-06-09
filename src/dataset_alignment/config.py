"""Configuration loader for the Dataset Alignment Pipeline."""

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class AlignmentConfig:
    """Wraps settings.yaml + rule.yaml for alignment pipeline config."""

    def __init__(self, settings_path: Path, rules_path: Path):
        with settings_path.open(encoding="utf-8") as f:
            self.settings: dict[str, Any] = yaml.safe_load(f) or {}
        with rules_path.open(encoding="utf-8") as f:
            self.rules: dict[str, Any] = yaml.safe_load(f) or {}
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        alignment = self.settings.get("alignment_pipeline", {})
        paths = alignment.get("paths", {})
        for key in ("cache_dir", "reports_dir", "chroma_dir", "db_dir"):
            val = paths.get(key)
            if val:
                Path(val).mkdir(parents=True, exist_ok=True)

    def get(self, *keys: str, default: Any = None) -> Any:
        node: Any = self.settings
        for k in keys:
            if not isinstance(node, dict) or k not in node:
                return default
            node = node[k]
        return node

    def rule(self, *keys: str, default: Any = None) -> Any:
        node: Any = self.rules
        for k in keys:
            if not isinstance(node, dict) or k not in node:
                return default
            node = node[k]
        return node

    def path(self, key: str) -> Path:
        alignment = self.settings.get("alignment_pipeline", {})
        paths = alignment.get("paths", {})
        val = paths.get(key, "")
        return Path(val) if val else PROJECT_ROOT / "data"

    @property
    def db_path(self) -> Path:
        return self.path("db_dir") / "novel_alignment.db"

    @property
    def src_lang(self) -> str:
        return self.settings.get("alignment_pipeline", {}).get("source_lang", "en")

    @property
    def tgt_lang(self) -> str:
        return self.settings.get("alignment_pipeline", {}).get("target_lang", "my")

    @property
    def input_dir(self) -> Path:
        return PROJECT_ROOT / (self.settings.get("alignment_pipeline", {}).get("input_dir", "data/input"))

    @property
    def output_dir(self) -> Path:
        return PROJECT_ROOT / (self.settings.get("alignment_pipeline", {}).get("output_dir", "data/output"))


@lru_cache(maxsize=1)
def get_alignment_config() -> AlignmentConfig:
    return AlignmentConfig(
        settings_path=PROJECT_ROOT / "config" / "settings.yaml",
        rules_path=PROJECT_ROOT / "config" / "rule.yaml",
    )
