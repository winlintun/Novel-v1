"""Pipeline configuration for glossary mining."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class PipelineConfig:
    db_path: Path = Path("data/novel_translation.db")
    en_dir: Optional[Path] = None
    my_dir: Optional[Path] = None
    novel_id: str = ""
    limit_chapters: int = 0
    use_llm_verify: bool = True
    dry_run: bool = False
    log_level: str = "INFO"
    chapter_regex: str = r"chapter[_\-\s]*(\d+)"

    min_term_length: int = 3
    min_occurrences: int = 2
    min_alignment_score: float = 0.5
    candidate_max: int = 200
    llm_confidence_threshold: float = 0.7
    llm_model: str = "qwen2.5:14b"
    llm_timeout: int = 120
    llm_max_retries: int = 2
