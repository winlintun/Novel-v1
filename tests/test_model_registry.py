"""
Unit tests for src/utils/model_registry.py.
"""

import unittest
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch


class TestModelRegistry(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.registry_path = Path(self.temp_dir) / "model_registry.json"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir)

    def _make_registry(self):
        """Mock the REGISTRY_PATH and import model_registry."""
        import importlib
        import src.utils.model_registry as mr
        mr.REGISTRY_PATH = self.registry_path
        return mr

    def test_log_run_creates_file(self):
        """First log_run should create the registry file."""
        mr = self._make_registry()
        mr.log_run(
            model_name="padauk-gemma:q8_0",
            novel="test_novel",
            chapter=1,
            avg_quality_score=85.0,
            avg_myanmar_ratio=0.95,
            total_chunks=10,
            pipeline_mode="two_stage",
            duration_seconds=300.0,
        )
        self.assertTrue(self.registry_path.exists())
        data = json.loads(self.registry_path.read_text(encoding="utf-8"))
        self.assertIn("models_tested", data)
        self.assertEqual(len(data["models_tested"]), 1)

    def test_log_run_entry_fields(self):
        """Each run entry should have the correct fields and entry_type."""
        mr = self._make_registry()
        mr.log_run(
            model_name="padauk-gemma:q8_0",
            novel="test_novel",
            chapter=2,
            avg_quality_score=78.0,
            avg_myanmar_ratio=0.92,
            total_chunks=8,
            pipeline_mode="full",
            duration_seconds=450.0,
        )
        data = json.loads(self.registry_path.read_text(encoding="utf-8"))
        entry = data["models_tested"][0]
        self.assertEqual(entry["entry_type"], "pipeline")
        self.assertEqual(entry["model"], "padauk-gemma:q8_0")
        self.assertEqual(entry["novel"], "test_novel")
        self.assertEqual(entry["chapter"], 2)
        self.assertEqual(entry["avg_quality_score"], 78.0)
        self.assertEqual(entry["pipeline_mode"], "full")

    def test_get_model_history(self):
        """get_model_history should return pipeline runs only, sorted by timestamp."""
        mr = self._make_registry()
        mr.log_run(model_name="model_a", novel="n1", chapter=1, avg_quality_score=80,
                   avg_myanmar_ratio=0.9, total_chunks=5, pipeline_mode="two_stage", duration_seconds=100)
        mr.log_run(model_name="model_a", novel="n2", chapter=2, avg_quality_score=85,
                   avg_myanmar_ratio=0.95, total_chunks=6, pipeline_mode="two_stage", duration_seconds=200)
        history = mr.get_model_history("model_a")
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["chapter"], 2)  # most recent first

    def test_get_model_history_excludes_canonical(self):
        """Canonical eval entries should not appear in pipeline history."""
        mr = self._make_registry()
        # Pipeline run
        mr.log_run(model_name="model_a", novel="n1", chapter=1, avg_quality_score=80,
                   avg_myanmar_ratio=0.9, total_chunks=5, pipeline_mode="two_stage", duration_seconds=100)
        # Manually add a canonical entry (simulating evaluate.py)
        registry = json.loads(self.registry_path.read_text(encoding="utf-8"))
        registry["models_tested"].append({
            "timestamp": "2026-01-01T00:00:00",
            "entry_type": "canonical",
            "model": "model_a",
            "avg_composite_score": 75.0,
        })
        self.registry_path.write_text(json.dumps(registry, indent=2), encoding="utf-8")
        # Pipeline history should still be 1
        history = mr.get_model_history("model_a")
        self.assertEqual(len(history), 1)

    def test_get_best_model_requires_min_3(self):
        """get_best_model should return None when fewer than 3 runs exist."""
        mr = self._make_registry()
        for i in range(2):
            mr.log_run(model_name="model_a", novel="n", chapter=i+1, avg_quality_score=80 + i*5,
                       avg_myanmar_ratio=0.9, total_chunks=5, pipeline_mode="two_stage", duration_seconds=100)
        best = mr.get_best_model()
        self.assertIsNone(best)

    def test_get_best_model_returns_best(self):
        """get_best_model should return model with highest avg score (3+ runs)."""
        mr = self._make_registry()
        for i in range(3):
            mr.log_run(model_name="good_model", novel="n", chapter=i+1, avg_quality_score=90,
                       avg_myanmar_ratio=0.95, total_chunks=5, pipeline_mode="two_stage", duration_seconds=100)
        for i in range(3):
            mr.log_run(model_name="ok_model", novel="n", chapter=i+1, avg_quality_score=75,
                       avg_myanmar_ratio=0.85, total_chunks=5, pipeline_mode="two_stage", duration_seconds=100)
        best = mr.get_best_model()
        self.assertEqual(best, "good_model")

    def test_summary_no_runs(self):
        """Summary should return appropriate message when no runs exist."""
        mr = self._make_registry()
        summary = mr.summary()
        self.assertIn("No", summary)

    def test_summary_with_runs(self):
        """Summary should include model names and scores."""
        mr = self._make_registry()
        mr.log_run(model_name="test_model", novel="n1", chapter=1, avg_quality_score=82,
                   avg_myanmar_ratio=0.93, total_chunks=5, pipeline_mode="two_stage", duration_seconds=100)
        summary = mr.summary()
        self.assertIn("test_model", summary)
        self.assertIn("82", summary)

    def test_log_run_with_chunk_metrics(self):
        """Chunk metrics should produce low_quality/low_ratio counts."""
        mr = self._make_registry()
        chunk_metrics = [
            {"quality_score": 60, "myanmar_ratio": 0.95},
            {"quality_score": 85, "myanmar_ratio": 0.98},
            {"quality_score": 50, "myanmar_ratio": 0.60},
        ]
        mr.log_run(model_name="m", novel="n", chapter=1, avg_quality_score=65,
                   avg_myanmar_ratio=0.84, total_chunks=3, pipeline_mode="two_stage",
                   duration_seconds=100, chunk_metrics=chunk_metrics)
        data = json.loads(self.registry_path.read_text(encoding="utf-8"))
        entry = data["models_tested"][0]
        self.assertEqual(entry["low_quality_chunks"], 2)  # 60 and 50 < 70
        self.assertEqual(entry["low_ratio_chunks"], 1)    # 0.60 < 0.7

    def test_corrupted_file_resets(self):
        """If registry file is corrupted, it should reset to default."""
        mr = self._make_registry()
        self.registry_path.write_text("not valid json", encoding="utf-8")
        # Should not crash
        mr.log_run(model_name="m", novel="n", chapter=1, avg_quality_score=80,
                   avg_myanmar_ratio=0.9, total_chunks=5, pipeline_mode="two_stage", duration_seconds=100)
        data = json.loads(self.registry_path.read_text(encoding="utf-8"))
        self.assertEqual(len(data["models_tested"]), 1)


if __name__ == '__main__':
    unittest.main()
