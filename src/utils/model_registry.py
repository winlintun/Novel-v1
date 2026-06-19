"""
Model Registry — Tracks translation quality per model version over time.

Stores eval results in data/evaluation/model_registry.json so you can
compare whether model changes actually improve output.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

REGISTRY_PATH = Path("data/evaluation/model_registry.json")


def _load_registry() -> Dict[str, Any]:
    """Load the full registry file, creating it if missing."""
    if not REGISTRY_PATH.exists():
        REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
        default = {
            "last_updated": datetime.now().isoformat(),
            "models_tested": [],
        }
        REGISTRY_PATH.write_text(json.dumps(default, indent=2, ensure_ascii=False), encoding="utf-8")
        return default
    try:
        return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        logger.warning(f"Corrupted registry at {REGISTRY_PATH}, resetting")
        default = {"last_updated": datetime.now().isoformat(), "models_tested": []}
        REGISTRY_PATH.write_text(json.dumps(default, indent=2, ensure_ascii=False), encoding="utf-8")
        return default


def log_run(
    model_name: str,
    novel: str,
    chapter: int,
    avg_quality_score: float,
    avg_myanmar_ratio: float,
    total_chunks: int,
    pipeline_mode: str,
    duration_seconds: float,
    chunk_metrics: Optional[List[Dict[str, Any]]] = None,
):
    """Log a translation run to the model registry.

    Args:
        model_name: Ollama model name (e.g., "padauk-gemma:q8_0")
        novel: Novel name
        chapter: Chapter number
        avg_quality_score: Average quality score across all chunks
        avg_myanmar_ratio: Average Myanmar ratio across all chunks
        total_chunks: Total chunk count
        pipeline_mode: Pipeline mode used (two_stage, full, lite, etc.)
        duration_seconds: Total translation duration
        chunk_metrics: Optional per-chunk metrics for detailed analysis
    """
    try:
        registry = _load_registry()

        entry = {
            "timestamp": datetime.now().isoformat(),
            "entry_type": "pipeline",
            "model": model_name,
            "novel": novel,
            "chapter": chapter,
            "avg_quality_score": round(avg_quality_score, 1),
            "avg_myanmar_ratio": round(avg_myanmar_ratio, 3),
            "total_chunks": total_chunks,
            "pipeline_mode": pipeline_mode,
            "duration_seconds": round(duration_seconds, 1),
        }
        if chunk_metrics:
            low_quality = sum(1 for m in chunk_metrics if m.get("quality_score", 100) < 70)
            low_ratio = sum(1 for m in chunk_metrics if m.get("myanmar_ratio", 1.0) < 0.7)
            entry["low_quality_chunks"] = low_quality
            entry["low_ratio_chunks"] = low_ratio

        registry.setdefault("models_tested", []).append(entry)
        registry["last_updated"] = datetime.now().isoformat()

        REGISTRY_PATH.write_text(json.dumps(registry, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info(f"Model registry updated: {model_name} on {novel} ch{chapter} (score={avg_quality_score})")

    except Exception as e:
        logger.warning(f"Failed to update model registry: {e}")



