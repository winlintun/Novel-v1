"""
Performance Monitoring Module
Tracks translation speed, memory usage, API calls, and glossary hit/miss ratio.
Per need_fix.md Cross-Cutting Concerns.
"""

import time
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any


class PerformanceLogger:
    """Track performance metrics for translation pipeline."""

    def __init__(self, novel_id: str, chapter_num: int):
        self.novel_id = novel_id
        self.chapter_num = chapter_num
        self.start_time = time.time()
        self.metrics: Dict[str, Any] = {
            "novel_id": novel_id,
            "chapter_num": chapter_num,
            "start_time": datetime.now().isoformat(),
            "words_translated": 0,
            "api_calls": 0,
            "glossary_hits": 0,
            "glossary_misses": 0,
            "errors": 0,
            "retry_count": 0,
        }

    def log_api_call(self, success: bool = True) -> None:
        """Log an API call."""
        self.metrics["api_calls"] += 1
        if not success:
            self.metrics["errors"] += 1

    def log_glossary_hit(self) -> None:
        """Log a glossary term hit."""
        self.metrics["glossary_hits"] += 1

    def log_glossary_miss(self) -> None:
        """Log a glossary term miss."""
        self.metrics["glossary_misses"] += 1

    def log_words_translated(self, count: int) -> None:
        """Log word count."""
        self.metrics["words_translated"] = count

    def log_retry(self) -> None:
        """Log a retry attempt."""
        self.metrics["retry_count"] += 1

    def get_words_per_minute(self) -> float:
        """Calculate translation speed in words/minute."""
        elapsed = time.time() - self.start_time
        if elapsed > 0:
            return (self.metrics["words_translated"] / elapsed) * 60
        return 0.0

    def get_glossary_hit_ratio(self) -> float:
        """Calculate glossary hit ratio."""
        total = self.metrics["glossary_hits"] + self.metrics["glossary_misses"]
        if total > 0:
            return self.metrics["glossary_hits"] / total
        return 0.0

    def generate_report(self) -> Dict[str, Any]:
        """Generate performance report."""
        elapsed = time.time() - self.start_time
        self.metrics["elapsed_seconds"] = round(elapsed, 2)
        self.metrics["words_per_minute"] = round(self.get_words_per_minute(), 1)
        self.metrics["glossary_hit_ratio"] = round(self.get_glossary_hit_ratio(), 2)
        self.metrics["end_time"] = datetime.now().isoformat()
        return self.metrics

    def save_report(self, output_dir: str = "logs") -> Path:
        """Save performance report to file."""
        report_dir = Path(output_dir) / "performance"
        report_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{self.novel_id}_ch{self.chapter_num}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = report_dir / filename

        with open(filepath, 'w', encoding='utf-8-sig') as f:
            json.dump(self.generate_report(), f, indent=2, ensure_ascii=False)

        return filepath
