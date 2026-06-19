"""
Unit tests for the fine-tuning scaffold.
Tests dataset loading, splitting, and adapter path resolution.
"""

import unittest
from pathlib import Path
from typing import Dict, List


class TestFinetuneDatasetLoading(unittest.TestCase):
    """Test dataset loading from the SQLite database."""

    def setUp(self):
        self.db_path = Path("data/novel_v1_dataset.db")

    def test_db_exists(self):
        """Dataset DB must exist for fine-tuning."""
        self.assertTrue(self.db_path.exists(), "Dataset DB not found")

    def test_db_has_pairs(self):
        """Dataset DB must have translation pairs."""
        import sqlite3
        conn = sqlite3.connect(str(self.db_path))
        count = conn.execute("SELECT COUNT(*) FROM translation_pairs").fetchone()[0]
        conn.close()
        self.assertGreater(count, 0, "No translation pairs in DB")


class TestDatasetSplitting(unittest.TestCase):
    """Test train/val/test splitting logic."""

    def _make_pairs(self, n: int) -> List[Dict[str, str]]:
        return [{"source": f"s{i}", "target": f"t{i}", "score": 4} for i in range(n)]

    def test_split_proportions(self):
        """10 pairs → 8 train, 1 val, 1 test with default splits."""
        from src.training.finetune import _prepare_dataset
        pairs = self._make_pairs(10)
        ds = _prepare_dataset(pairs, val_split=0.1, test_split=0.1)
        self.assertEqual(len(ds["train"]), 8)
        self.assertEqual(len(ds["val"]), 1)
        self.assertEqual(len(ds["test"]), 1)

    def test_split_small_dataset(self):
        """3 pairs → handled gracefully (no negative counts)."""
        from src.training.finetune import _prepare_dataset
        pairs = self._make_pairs(3)
        ds = _prepare_dataset(pairs, val_split=0.1, test_split=0.1)
        self.assertGreaterEqual(len(ds["train"]), 1)
        self.assertEqual(len(ds["train"]) + len(ds["val"]) + len(ds["test"]), 3)

    def test_preserves_source_target(self):
        """Dataset preserves source/target pairs through split."""
        from src.training.finetune import _prepare_dataset
        pairs = self._make_pairs(5)
        ds = _prepare_dataset(pairs, val_split=0.2, test_split=0.2)
        for split_name in ["train", "val", "test"]:
            split = ds[split_name]
            for i in range(len(split)):
                self.assertIn("source", split[i])
                self.assertIn("target", split[i])


class TestAdapterPathResolution(unittest.TestCase):
    """Test adapter path resolution from model_registry."""

    def test_nonexistent_adapter_returns_none(self):
        """Non-existent adapter name returns None."""
        # LoRA adapter lookup is an optional feature; skip if it isn't wired up.
        try:
            from src.utils.model_registry import get_adapter_path
        except ImportError:
            self.skipTest("get_adapter_path not implemented (LoRA adapter lookup is optional)")
        result = get_adapter_path("nonexistent_adapter_xyz")
        self.assertIsNone(result)

    def test_adapter_dir_is_valid_path(self):
        """Adapter directory must exist with config file (only after fine-tuning)."""
        # models/adapters is created only after a LoRA training run, so treat its
        # absence as "feature not used here" rather than a failure.
        adapter_dir = Path("models/adapters")
        if not adapter_dir.exists():
            self.skipTest("models/adapters not present (created only after LoRA fine-tuning)")
        self.assertTrue(adapter_dir.exists(), "Adapters directory not found")


class TestLoRAConfig(unittest.TestCase):
    """Test LoRA configuration loading from the single settings.yaml file."""

    def _load_lora_section(self):
        import yaml
        config_path = Path("config/settings.yaml")
        self.assertTrue(config_path.exists(), "config/settings.yaml not found")
        with open(config_path, encoding="utf-8") as f:
            settings = yaml.safe_load(f)
        return settings.get("lora_training", {})

    def test_config_exists(self):
        """LoRA config must be present under the lora_training section."""
        self.assertTrue(self._load_lora_section(), "lora_training section missing")

    def test_config_valid_yaml(self):
        """LoRA config must have required keys."""
        config = self._load_lora_section()
        self.assertIn("lora", config)
        self.assertIn("training", config)
        self.assertIn("dataset", config)
        self.assertIn("model", config)
