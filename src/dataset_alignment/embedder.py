"""BGE-M3 multilingual embedder with disk caching for RAG ingestion."""

import hashlib
from pathlib import Path
from typing import Optional

import numpy as np

from src.dataset_alignment.config import get_alignment_config


class BGEEmbedder:
    """BGE-M3 embedder with numpy disk cache and lazy model loading."""

    def __init__(self, model_name: Optional[str] = None):
        cfg = get_alignment_config()
        self.model_name = model_name or cfg.get(
            "alignment_pipeline", "embedding", "model", default="BAAI/bge-m3",
        )
        self.device = cfg.get(
            "alignment_pipeline", "embedding", "device", default="cpu",
        )
        self.batch_size = cfg.get(
            "alignment_pipeline", "embedding", "batch_size", default=32,
        )
        self.cache_dir = cfg.path("cache_dir") / "embeddings"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._model = None

    @property
    def model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(
                    self.model_name, device=self.device,
                )
            except Exception as e:
                raise RuntimeError(f"Failed to load BGE-M3: {e}")
        return self._model

    def encode(self, texts: list[str]) -> np.ndarray:
        """Encode texts and return normalized embeddings."""
        if not texts:
            return np.array([])

        cache_key = self._cache_key(texts)
        cached = self._load_cache(cache_key)
        if cached is not None:
            return cached

        embeddings = self.model.encode(
            texts, batch_size=self.batch_size,
            normalize_embeddings=True, show_progress_bar=False,
        )
        self._save_cache(cache_key, embeddings)
        return embeddings

    def _cache_key(self, texts: list[str]) -> str:
        content = "|".join(texts) + f"|len={len(texts)}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _load_cache(self, key: str) -> Optional[np.ndarray]:
        cache_file = self.cache_dir / f"{key}.npy"
        if cache_file.exists():
            return np.load(cache_file)
        return None

    def _save_cache(self, key: str, embeddings: np.ndarray) -> None:
        cache_file = self.cache_dir / f"{key}.npy"
        np.save(cache_file, embeddings)

    def embed_query(self, text: str) -> Optional[list[float]]:
        """Encode a single query and return as list (for ChromaDB)."""
        vec = self.encode([text])
        if vec.size == 0:
            return None
        return vec[0].tolist()
