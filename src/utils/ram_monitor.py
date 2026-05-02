"""
Auto RAM Monitor & Model Unloader
Monitors system/GPU memory and auto-unloads models when memory is low.
"""

import time
import subprocess
import logging
from typing import Dict, Any


logger = logging.getLogger(__name__)


class RAMMonitor:
    """Monitor RAM/VRAM usage and manage model unloading."""

    def __init__(
        self,
        max_memory_mb: int = 8000,
        check_interval: int = 60,
        auto_unload: bool = True
    ):
        self.max_memory_mb = max_memory_mb
        self.check_interval = check_interval
        self.auto_unload = auto_unload
        self.last_check = 0
        self.model_loaded = False

    def get_memory_usage(self) -> Dict[str, Any]:
        """Get current memory usage."""
        usage = {
            "ram_total_mb": 0,
            "ram_used_mb": 0,
            "ram_percent": 0.0,
            "vram_total_mb": 0,
            "vram_used_mb": 0,
            "vram_percent": 0.0,
        }

        # Get RAM usage (Linux)
        try:
            with open('/proc/meminfo', 'r') as f:
                for line in f:
                    if line.startswith('MemTotal:'):
                        usage["ram_total_mb"] = int(line.split()[1]) // 1024
                    elif line.startswith('MemAvailable:'):
                        available = int(line.split()[1]) // 1024
                        usage["ram_used_mb"] = usage["ram_total_mb"] - available
                        pct = 0.0
                        if usage["ram_total_mb"] > 0:
                            pct = float(usage["ram_used_mb"]) / float(usage["ram_total_mb"]) * 100.0
                        usage["ram_percent"] = round(pct, 1)
        except Exception as e:
            logger.warning(f"Could not read RAM: {e}")

        # Get VRAM usage (nvidia-smi)
        try:
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=memory.used,memory.total', '--format=csv,noheader,nounits'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if lines:
                    used, total = map(int, lines[0].split(','))
                    usage["vram_used_mb"] = used
                    usage["vram_total_mb"] = total
                    pct = 0.0
                    if total > 0:
                        pct = float(used) / float(total) * 100.0
                    usage["vram_percent"] = round(pct, 1)
        except FileNotFoundError:
            logger.debug("nvidia-smi not found (no GPU)")
        except Exception as e:
            logger.warning(f"Could not read VRAM: {e}")

        return usage

    def check_memory(self) -> bool:
        """Check if memory is getting low. Returns True if OK."""
        current = time.time()
        if current - self.last_check < self.check_interval:
            return True

        self.last_check = current
        usage = self.get_memory_usage()

        # Check RAM
        if usage["ram_percent"] > 90:
            logger.warning(f"RAM critical: {usage['ram_percent']}% used")
            if self.auto_unload:
                self.unload_models()
            return False

        # Check VRAM
        vram_pct = usage.get("vram_percent", 0)
        if vram_pct > 90:
            logger.warning(f"VRAM critical: {vram_pct}% used")
            if self.auto_unload:
                self.unload_models()
            return False

        return True

    def unload_models(self) -> bool:
        """Unload models from Ollama to free memory."""
        logger.info("Auto-unloading Ollama models...")

        try:
            result = subprocess.run(
                ['ollama', 'list'],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')[1:]
                for line in lines:
                    if line.strip():
                        model_name = line.split()[0]
                        logger.info(f"Unloading model: {model_name}")
                        subprocess.run(
                            ['ollama', 'stop', model_name],
                            capture_output=True,
                            timeout=30
                        )
                self.model_loaded = False
                return True

        except FileNotFoundError:
            logger.debug("Ollama not installed")
        except Exception as e:
            logger.error(f"Failed to unload models: {e}")

        return False

    def get_status_text(self) -> str:
        """Get formatted status text for UI."""
        usage = self.get_memory_usage()

        ram = usage["ram_percent"]
        vram = usage.get("vram_percent", 0)

        status = f"RAM: {ram}%"
        if vram > 0:
            status = f"RAM: {ram}% | VRAM: {vram}%"

        if ram > 80 or vram > 80:
            status = status + " ⚠️"
        elif ram > 90 or vram > 90:
            status = status + " 🔴 CRITICAL"

        return status


class ModelUnloader:
    """Utility class to manually unload Ollama models."""

    @staticmethod
    def list_models() -> list:
        """List running Ollama models."""
        try:
            result = subprocess.run(
                ['ollama', 'list'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')[1:]
                return [line.split()[0] for line in lines if line.strip()]
        except Exception as e:
            logger.error(f"Failed to list models: {e}")
        return []

    @staticmethod
    def unload_model(model_name: str) -> bool:
        """Unload a specific model."""
        try:
            result = subprocess.run(
                ['ollama', 'stop', model_name],
                capture_output=True,
                timeout=30
            )
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Failed to unload {model_name}: {e}")
            return False

    @staticmethod
    def unload_all() -> int:
        """Unload all models. Returns count of unloaded models."""
        count = 0
        for model in ModelUnloader.list_models():
            if ModelUnloader.unload_model(model):
                count += 1
        return count

    @staticmethod
    def get_memory_summary() -> Dict[str, Any]:
        """Get memory summary."""
        monitor = RAMMonitor()
        return monitor.get_memory_usage()


if __name__ == "__main__":
    # Test
    monitor = RAMMonitor()
    print(f"Memory Status: {monitor.get_status_text()}")
    print(f"Details: {monitor.get_memory_usage()}")

    print("\nRunning models:")
    for model in ModelUnloader.list_models():
        print(f"  - {model}")
