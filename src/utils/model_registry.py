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


def get_model_history(model_name: str) -> List[Dict[str, Any]]:
    """Get all recorded pipeline runs for a specific model.

    Args:
        model_name: Ollama model name

    Returns:
        List of pipeline run entries for this model, sorted by timestamp descending.
    """
    registry = _load_registry()
    runs = [e for e in registry.get("models_tested", [])
            if e.get("model") == model_name and e.get("entry_type") == "pipeline"]
    return sorted(runs, key=lambda x: x.get("timestamp", ""), reverse=True)


def get_best_model() -> Optional[str]:
    """Get the model name with the highest average pipeline quality score (min 3 runs).

    Returns:
        Model name string, or None if no model has 3+ runs.
    """
    registry = _load_registry()
    scores: Dict[str, List[float]] = {}
    for entry in registry.get("models_tested", []):
        if entry.get("entry_type") != "pipeline":
            continue
        model = entry.get("model", "")
        score = entry.get("avg_quality_score", 0)
        if model and score:
            scores.setdefault(model, []).append(score)

    best = None
    best_avg = 0
    for model, run_scores in scores.items():
        if len(run_scores) >= 3:
            avg = sum(run_scores) / len(run_scores)
            if avg > best_avg:
                best_avg = avg
                best = model
    return best


def summary() -> str:
    """Return a human-readable summary of all pipeline run performance."""
    registry = _load_registry()
    runs = [e for e in registry.get("models_tested", []) if e.get("entry_type") == "pipeline"]
    if not runs:
        return "No pipeline runs recorded yet."

    lines = ["Pipeline Run Summary", "=" * 40]
    by_model: Dict[str, List[float]] = {}
    for entry in runs:
        model = entry.get("model", "unknown")
        by_model.setdefault(model, []).append(entry.get("avg_quality_score", 0))

    for model, scores in sorted(by_model.items()):
        avg = sum(scores) / len(scores)
        lines.append(f"  {model}: {len(scores)} runs, avg score {avg:.1f}")

    latest = runs[-1]
    lines.append("")
    lines.append(f"Latest run: {latest.get('model')} on {latest.get('novel')} ch{latest.get('chapter')}")
    lines.append(f"  Score: {latest.get('avg_quality_score')} | Ratio: {latest.get('avg_myanmar_ratio'):.1%}")
    return "\n".join(lines)


def get_adapter_path(adapter_name: str) -> Optional[Path]:
    """Resolve adapter path from name.

    Args:
        adapter_name: Name of the adapter (directory under models/adapters/)

    Returns:
        Path to adapter directory, or None if not found
    """
    path = Path("models/adapters") / adapter_name
    if path.exists() and (path / "adapter_config.json").exists():
        return path
    # Try as absolute/relative path
    candidate = Path(adapter_name)
    if candidate.exists() and (candidate / "adapter_config.json").exists():
        return candidate
    logger.error(f"Adapter '{adapter_name}' not found at {path}")
    return None
