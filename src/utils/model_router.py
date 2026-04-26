"""
Multi-Model Router for Ollama LLMs
- Routes tasks to best-fit model based on capability
- Handles VRAM constraints (14b single, 7b/2b batch)
- Fallback chain if primary model fails
"""
from typing import Literal, Optional
from dataclasses import dataclass

@dataclass
class ModelConfig:
    name: str
    role: Literal["translator", "refiner", "checker", "glossary", "qa"]
    vram_gb: float
    priority: int  # Lower = higher priority
    fallback: Optional[str] = None

MODEL_REGISTRY: dict[str, ModelConfig] = {
    # Padauk-Gemma (Local GGUF - Highest Quality Myanmar Output)
    "padauk-gemma:q8_0": ModelConfig("padauk-gemma:q8_0", "translator", 8.0, 1, fallback="qwen2.5:14b"),
    
    # Translation specialists
    # NOTE: hunyuan-mt:7b is EXCLUDED - produces THAI instead of Myanmar
    "translategemma:latest": ModelConfig("translategemma:latest", "translator", 8.0, 2, fallback="qwen2.5:7b"),
    
    # Reasoning & orchestration
    "qwen2.5:14b": ModelConfig("qwen2.5:14b", "refiner", 14.0, 2),  # Primary for literary editing
    
    # Fast validation
    "qwen:7b": ModelConfig("qwen:7b", "checker", 8.0, 1),
    "gemma:2b": ModelConfig("gemma:2b", "qa", 4.0, 2, fallback="qwen:7b"),
    
    # Terminology & consistency
    "aya-expanse:8b": ModelConfig("aya-expanse:8b", "glossary", 16.0, 1),
    
    # Burmese fluency specialist
    "seallm3:7b": ModelConfig("seallm3:7b", "refiner", 8.0, 3, fallback="padauk-gemma:q8_0"),
}

def get_model_for_role(
    role: Literal["translator", "refiner", "checker", "glossary", "qa"],
    available_vram: float = 16.0,
) -> Optional[str]:
    """
    Select best model for role given VRAM constraint.
    Returns model name or None if no suitable model.
    """
    # Filter by role and VRAM
    candidates = [
        (name, cfg) for name, cfg in MODEL_REGISTRY.items()
        if cfg.role == role and cfg.vram_gb <= available_vram
    ]
    if not candidates:
        return None
    
    # Sort by priority, return highest
    candidates.sort(key=lambda x: x[1].priority)
    return candidates[0][0]

def get_fallback_chain(model_name: str) -> list[str]:
    """Get fallback chain for a model (for retry logic)."""
    chain = []
    current = model_name
    while current and current in MODEL_REGISTRY:
        fallback = MODEL_REGISTRY[current].fallback
        if fallback:
            chain.append(fallback)
            current = fallback
        else:
            break
    return chain
