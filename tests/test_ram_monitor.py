"""Tests for RAM Monitor utility."""

import unittest
from unittest.mock import patch, MagicMock
import time


class TestRAMMonitor(unittest.TestCase):
    """Test cases for RAMMonitor class."""

    def setUp(self):
        """Set up test fixtures."""
        from src.utils.ram_monitor import RAMMonitor
        self.RAMMonitor = RAMMonitor
        self.monitor = RAMMonitor(max_memory_mb=8000, check_interval=60)

    def test_init_defaults(self):
        """Test RAMMonitor initialization with defaults."""
        monitor = self.RAMMonitor()
        self.assertEqual(monitor.max_memory_mb, 8000)
        self.assertEqual(monitor.check_interval, 60)
        self.assertTrue(monitor.auto_unload)
        self.assertFalse(monitor.last_check)

    def test_init_custom(self):
        """Test RAMMonitor initialization with custom values."""
        monitor = self.RAMMonitor(max_memory_mb=16000, check_interval=120, auto_unload=False)
        self.assertEqual(monitor.max_memory_mb, 16000)
        self.assertEqual(monitor.check_interval, 120)
        self.assertFalse(monitor.auto_unload)

    def test_get_memory_usage_returns_dict(self):
        """Test get_memory_usage returns a dict."""
        usage = self.monitor.get_memory_usage()
        self.assertIsInstance(usage, dict)
        self.assertIn("ram_total_mb", usage)
        self.assertIn("vram_total_mb", usage)

    def test_check_memory_returns_true_when_no_check_needed(self):
        """Test check_memory returns True when interval not elapsed."""
        self.monitor.last_check = time.time()
        result = self.monitor.check_memory()
        self.assertTrue(result)

    def test_check_memory_returns_true_when_under_threshold(self):
        """Test check_memory returns True when memory OK."""
        with patch.object(self.monitor, 'get_memory_usage') as mock_usage:
            mock_usage.return_value = {"ram_percent": 50.0, "vram_percent": 40.0}
            self.monitor.last_check = 0
            result = self.monitor.check_memory()
            self.assertTrue(result)

    def test_check_memory_returns_false_when_ram_critical(self):
        """Test check_memory returns False when RAM critical."""
        with patch.object(self.monitor, 'get_memory_usage') as mock_usage:
            with patch.object(self.monitor, 'unload_models') as mock_unload:
                mock_usage.return_value = {"ram_percent": 95.0, "vram_percent": 40.0}
                self.monitor.last_check = 0
                self.monitor.auto_unload = True
                result = self.monitor.check_memory()
                self.assertFalse(result)

    def test_check_memory_returns_false_when_vram_critical(self):
        """Test check_memory returns False when VRAM critical."""
        with patch.object(self.monitor, 'get_memory_usage') as mock_usage:
            with patch.object(self.monitor, 'unload_models') as mock_unload:
                mock_usage.return_value = {"ram_percent": 50.0, "vram_percent": 95.0}
                self.monitor.last_check = 0
                self.monitor.auto_unload = True
                result = self.monitor.check_memory()
                self.assertFalse(result)

    @patch('subprocess.run')
    def test_unload_models_success(self, mock_subprocess):
        """Test unload_models successfully unloads models."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "NAME\tMODIFIED\nmodel1\t2 days ago\nmodel2\t1 day ago\n"
        mock_subprocess.return_value = mock_result

        result = self.monitor.unload_models()

        self.assertTrue(result)
        self.assertFalse(self.monitor.model_loaded)

    @patch('subprocess.run')
    def test_unload_models_no_ollama(self, mock_subprocess):
        """Test unload_models when ollama not installed."""
        mock_subprocess.side_effect = FileNotFoundError("ollama not found")

        result = self.monitor.unload_models()

        self.assertFalse(result)

    def test_get_status_text_no_vram(self):
        """Test get_status_text without VRAM."""
        with patch.object(self.monitor, 'get_memory_usage') as mock_usage:
            mock_usage.return_value = {"ram_percent": 50.0, "vram_percent": 0.0}
            status = self.monitor.get_status_text()
            self.assertEqual(status, "RAM: 50.0%")

    def test_get_status_text_with_vram(self):
        """Test get_status_text with VRAM."""
        with patch.object(self.monitor, 'get_memory_usage') as mock_usage:
            mock_usage.return_value = {"ram_percent": 50.0, "vram_percent": 60.0}
            status = self.monitor.get_status_text()
            self.assertEqual(status, "RAM: 50.0% | VRAM: 60.0%")

    def test_get_status_text_warning(self):
        """Test get_status_text shows warning at 80%."""
        with patch.object(self.monitor, 'get_memory_usage') as mock_usage:
            mock_usage.return_value = {"ram_percent": 85.0, "vram_percent": 50.0}
            status = self.monitor.get_status_text()
            self.assertIn("⚠️", status)

    def test_get_status_text_critical(self):
        """Test get_status_text shows critical at 90%."""
        with patch.object(self.monitor, 'get_memory_usage') as mock_usage:
            mock_usage.return_value = {"ram_percent": 95.0, "vram_percent": 50.0}
            status = self.monitor.get_status_text()
            self.assertIn("⚠️", status)


class TestModelUnloader(unittest.TestCase):
    """Test cases for ModelUnloader class."""

    def setUp(self):
        """Set up test fixtures."""
        from src.utils.ram_monitor import ModelUnloader
        self.ModelUnloader = ModelUnloader

    @patch('subprocess.run')
    def test_list_models_success(self, mock_subprocess):
        """Test list_models returns model names."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "NAME\tMODIFIED\npadauk-gemma:q8_0\t2 days ago\nqwen:7b\t1 day ago\n"
        mock_subprocess.return_value = mock_result

        models = self.ModelUnloader.list_models()

        self.assertIn("padauk-gemma:q8_0", models)
        self.assertIn("qwen:7b", models)

    @patch('subprocess.run')
    def test_list_models_empty(self, mock_subprocess):
        """Test list_models returns empty list on failure."""
        mock_subprocess.side_effect = Exception("Failed")

        models = self.ModelUnloader.list_models()

        self.assertEqual(models, [])

    @patch('subprocess.run')
    def test_unload_model_success(self, mock_subprocess):
        """Test unload_model returns True on success."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_subprocess.return_value = mock_result

        result = self.ModelUnloader.unload_model("padauk-gemma:q8_0")

        self.assertTrue(result)

    @patch('subprocess.run')
    def test_unload_model_failure(self, mock_subprocess):
        """Test unload_model returns False on failure."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_subprocess.return_value = mock_result

        result = self.ModelUnloader.unload_model("padauk-gemma:q8_0")

        self.assertFalse(result)

    def test_unload_all(self):
        """Test unload_all returns count."""
        with patch.object(self.ModelUnloader, 'list_models') as mock_list:
            with patch.object(self.ModelUnloader, 'unload_model') as mock_unload:
                mock_list.return_value = ["model1", "model2", "model3"]
                mock_unload.return_value = True

                count = self.ModelUnloader.unload_all()

                self.assertEqual(count, 3)

    def test_get_memory_summary(self):
        """Test get_memory_summary creates RAMMonitor and gets usage."""
        with patch('src.utils.ram_monitor.RAMMonitor') as MockRAMMonitor:
            mock_instance = MagicMock()
            mock_instance.get_memory_usage.return_value = {"ram_percent": 50.0}
            MockRAMMonitor.return_value = mock_instance

            result = self.ModelUnloader.get_memory_summary()

            mock_instance.get_memory_usage.assert_called_once()
            self.assertEqual(result["ram_percent"], 50.0)


if __name__ == "__main__":
    unittest.main()