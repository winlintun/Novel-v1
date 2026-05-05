"""Tests for Performance Logger utility."""

import unittest
import tempfile
import json
import time
from pathlib import Path


class TestPerformanceLogger(unittest.TestCase):
    """Test cases for PerformanceLogger class."""

    def setUp(self):
        """Set up test fixtures."""
        from src.utils.performance_logger import PerformanceLogger
        self.PerformanceLogger = PerformanceLogger
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    def test_init_sets_novel_and_chapter(self):
        """Test PerformanceLogger initialization."""
        logger = self.PerformanceLogger("test-novel", 5)
        self.assertEqual(logger.novel_id, "test-novel")
        self.assertEqual(logger.chapter_num, 5)

    def test_init_sets_default_metrics(self):
        """Test PerformanceLogger has default metrics."""
        logger = self.PerformanceLogger("test-novel", 1)
        self.assertEqual(logger.metrics["words_translated"], 0)
        self.assertEqual(logger.metrics["api_calls"], 0)
        self.assertEqual(logger.metrics["glossary_hits"], 0)
        self.assertEqual(logger.metrics["glossary_misses"], 0)
        self.assertEqual(logger.metrics["errors"], 0)
        self.assertEqual(logger.metrics["retry_count"], 0)

    def test_log_api_call_increments_count(self):
        """Test log_api_call increments api_calls."""
        logger = self.PerformanceLogger("test-novel", 1)
        logger.log_api_call()
        self.assertEqual(logger.metrics["api_calls"], 1)

    def test_log_api_call_failure_increments_errors(self):
        """Test log_api_call with success=False increments errors."""
        logger = self.PerformanceLogger("test-novel", 1)
        logger.log_api_call(success=False)
        self.assertEqual(logger.metrics["api_calls"], 1)
        self.assertEqual(logger.metrics["errors"], 1)

    def test_log_glossary_hit_increments_count(self):
        """Test log_glossary_hit increments glossary_hits."""
        logger = self.PerformanceLogger("test-novel", 1)
        logger.log_glossary_hit()
        logger.log_glossary_hit()
        self.assertEqual(logger.metrics["glossary_hits"], 2)

    def test_log_glossary_miss_increments_count(self):
        """Test log_glossary_miss increments glossary_misses."""
        logger = self.PerformanceLogger("test-novel", 1)
        logger.log_glossary_miss()
        self.assertEqual(logger.metrics["glossary_misses"], 1)

    def test_log_words_translated_sets_count(self):
        """Test log_words_translated sets words count."""
        logger = self.PerformanceLogger("test-novel", 1)
        logger.log_words_translated(500)
        self.assertEqual(logger.metrics["words_translated"], 500)

    def test_log_retry_increments_count(self):
        """Test log_retry increments retry_count."""
        logger = self.PerformanceLogger("test-novel", 1)
        logger.log_retry()
        logger.log_retry()
        self.assertEqual(logger.metrics["retry_count"], 2)

    def test_get_words_per_minute_returns_zero_initially(self):
        """Test get_words_per_minute returns 0 when no words translated."""
        logger = self.PerformanceLogger("test-novel", 1)
        wpm = logger.get_words_per_minute()
        self.assertEqual(wpm, 0.0)

    def test_get_words_per_minute_calculates_correctly(self):
        """Test get_words_per_minute calculates correctly."""
        logger = self.PerformanceLogger("test-novel", 1)
        # Wait a bit to have elapsed time
        time.sleep(0.1)
        logger.log_words_translated(60)  # 60 words
        wpm = logger.get_words_per_minute()
        # Should be approximately 60 words / (some elapsed time in minutes)
        self.assertGreater(wpm, 0)

    def test_get_glossary_hit_ratio_returns_zero_when_no_data(self):
        """Test get_glossary_hit_ratio returns 0 when no hits or misses."""
        logger = self.PerformanceLogger("test-novel", 1)
        ratio = logger.get_glossary_hit_ratio()
        self.assertEqual(ratio, 0.0)

    def test_get_glossary_hit_ratio_calculates_correctly(self):
        """Test get_glossary_hit_ratio calculates correctly."""
        logger = self.PerformanceLogger("test-novel", 1)
        logger.log_glossary_hit()
        logger.log_glossary_hit()
        logger.log_glossary_miss()
        ratio = logger.get_glossary_hit_ratio()
        self.assertEqual(ratio, 2/3)  # 2 hits / 3 total

    def test_generate_report_returns_metrics_dict(self):
        """Test generate_report returns complete metrics."""
        logger = self.PerformanceLogger("test-novel", 1)
        logger.log_words_translated(100)
        logger.log_api_call()
        logger.log_glossary_hit()
        
        report = logger.generate_report()
        
        self.assertIn("words_translated", report)
        self.assertIn("api_calls", report)
        self.assertIn("glossary_hits", report)
        self.assertIn("elapsed_seconds", report)
        self.assertIn("words_per_minute", report)
        self.assertIn("glossary_hit_ratio", report)
        self.assertIn("start_time", report)
        self.assertIn("end_time", report)

    def test_generate_report_includes_novel_and_chapter(self):
        """Test generate_report includes novel_id and chapter_num."""
        logger = self.PerformanceLogger("my-novel", 10)
        report = logger.generate_report()
        self.assertEqual(report["novel_id"], "my-novel")
        self.assertEqual(report["chapter_num"], 10)

    def test_save_report_creates_file(self):
        """Test save_report creates JSON file."""
        logger = self.PerformanceLogger("test-novel", 1)
        logger.log_words_translated(100)
        
        filepath = logger.save_report(self.temp_dir)
        
        self.assertTrue(filepath.exists())
        
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            data = json.load(f)
        
        self.assertEqual(data["novel_id"], "test-novel")
        self.assertEqual(data["chapter_num"], 1)
        self.assertEqual(data["words_translated"], 100)

    def test_save_report_creates_performance_subdir(self):
        """Test save_report creates performance subdirectory."""
        logger = self.PerformanceLogger("test-novel", 1)
        
        filepath = logger.save_report(self.temp_dir)
        
        # File should be in logs/performance/
        self.assertIn("performance", str(filepath))

    def test_save_report_filename_format(self):
        """Test save_report creates properly named file."""
        logger = self.PerformanceLogger("mybook", 5)
        
        filepath = logger.save_report(self.temp_dir)
        
        # Should contain novel_chapter and timestamp
        filename = filepath.name
        self.assertIn("mybook", filename)
        self.assertIn("ch5", filename)


if __name__ == "__main__":
    unittest.main()