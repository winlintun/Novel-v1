"""Database helpers for the glossary extraction pipeline."""

import logging
from pathlib import Path
from typing import Optional

from src.db.connection import DatabaseConnection
from src.db.schema import SchemaManager
from src.db.repositories.glossary_repo import GlossaryRepository, GLOBAL_NOVEL_ID
from src.db.repositories.novel_repo import NovelRepository
from src.db.repositories.chapter_repo import ChapterRepository

logger = logging.getLogger(__name__)


class ExtractionDB:
    """DB access wrapper for the mining pipeline — DB-only, no JSON."""

    def __init__(self, db_path: Path):
        self.db = DatabaseConnection(str(db_path))
        self.schema = SchemaManager(self.db)
        self.schema.create_all()
        self.glossary_repo = GlossaryRepository(self.db)
        self.novel_repo = NovelRepository(self.db)
        self.chapter_repo = ChapterRepository(self.db)

    def ensure_novel(self, novel_id: str, name: str = "") -> None:
        if not self.novel_repo.exists(novel_id):
            self.novel_repo.create(novel_id, name or novel_id, "english")

    def ensure_chapter(self, novel_id: str, chapter_num: int, file_path: str) -> str:
        chapter_id = f"chapter_{novel_id}_{chapter_num:04d}"
        existing = self.chapter_repo.get_chapter(chapter_id)
        if existing:
            return chapter_id
        self.chapter_repo.create_chapter(
            novel_id=novel_id,
            chapter_num=chapter_num,
            file_path=file_path,
            translation_status="completed",
        )
        return chapter_id

    def term_exists(self, novel_id: str, source_term: str) -> bool:
        return self.glossary_repo.get_term_by_source(novel_id, source_term) is not None

    def add_pending_term(
        self,
        novel_id: str,
        source_term: str,
        target_term: str,
        category: str = "general",
        confidence: float = 0.5,
        source: str = "auto_extract_alignment",
        chapter_id: str = "",
    ) -> Optional[str]:
        if self.term_exists(novel_id, source_term):
            return None
        try:
            result = self.glossary_repo.add_term(
                novel_id=novel_id,
                source_term=source_term,
                target_term=target_term,
                category=category,
                status="pending",
                enforcement_level="soft",
                confidence=confidence,
                scope="novel",
            )
            if result and chapter_id:
                self.glossary_repo.log_term_usage(
                    term_id=result["id"],
                    chapter_id=chapter_id,
                    paragraph_idx=0,
                    confidence=confidence,
                )
                self.glossary_repo.increment_usage(result["id"])
            return result["id"] if result else None
        except Exception as e:
            logger.warning(f"Failed to add pending term '{source_term}': {e}")
            return None

    def add_variant(self, term_id: str, variant_text: str) -> None:
        try:
            self.glossary_repo.add_variant(term_id, variant_text, match_type="exact")
        except Exception as e:
            logger.debug(f"Failed to add variant '{variant_text}': {e}")

    def add_global_pending_term(
        self,
        source_term: str,
        target_term: str,
        category: str = "general",
        confidence: float = 0.5,
    ) -> Optional[str]:
        if self.term_exists(GLOBAL_NOVEL_ID, source_term):
            return None
        try:
            result = self.glossary_repo.add_term(
                novel_id=GLOBAL_NOVEL_ID,
                source_term=source_term,
                target_term=target_term,
                category=category,
                status="pending",
                enforcement_level="soft",
                confidence=confidence,
                scope="global",
            )
            return result["id"] if result else None
        except Exception as e:
            logger.warning(f"Failed to add global term '{source_term}': {e}")
            return None

    def close(self) -> None:
        self.db.close()
