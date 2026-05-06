"""
JSON-to-SQLite migration script.
Backs up existing JSON files, imports data into SQLite, and validates.
"""

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional
from src.db.connection import DatabaseConnection
from src.db.schema import SchemaManager
from src.db.repositories.novel_repo import NovelRepository
from src.db.repositories.glossary_repo import GlossaryRepository
from src.db.repositories.chapter_repo import ChapterRepository
from src.db.repositories.context_repo import ContextRepository

logger = logging.getLogger(__name__)


class JsonToSqlMigrator:
    """Migrates JSON-based glossary/context data to SQLite."""

    def __init__(self, db: DatabaseConnection, novel_slug: str):
        self.db = db
        self.novel_slug = novel_slug
        self.schema = SchemaManager(db)
        self.novel_repo = NovelRepository(db)
        self.glossary_repo = GlossaryRepository(db)
        self.chapter_repo = ChapterRepository(db)
        self.context_repo = ContextRepository(db)

    def migrate(self, backup_dir: str = "backups/glossary_migration") -> dict:
        """Run the full migration pipeline.

        Returns a summary dict with counts of migrated items.
        """
        summary: dict = {
            "novel_id": f"novel_{self.novel_slug}",
            "backup_dir": None,
            "glossary_terms": 0,
            "pending_terms": 0,
            "chapters": 0,
            "context_snapshots": 0,
            "errors": [],
        }

        # Step 1: Create schema
        self.schema.create_all()

        # Step 2: Backup JSON files
        backup_path = self._backup_json_files(backup_dir)
        summary["backup_dir"] = str(backup_path)

        # Step 3: Create novel record
        novel_id = f"novel_{self.novel_slug}"
        if not self.novel_repo.exists(novel_id):
            self.novel_repo.create(novel_id, self.novel_slug, "chinese")

        # Step 4: Migrate glossary
        summary["glossary_terms"] = self._migrate_glossary(novel_id)

        # Step 5: Migrate pending terms
        summary["pending_terms"] = self._migrate_pending(novel_id)

        # Step 6: Migrate chapters (discover from output directory)
        summary["chapters"] = self._migrate_chapters(novel_id)

        # Step 7: Migrate context memory
        summary["context_snapshots"] = self._migrate_context(novel_id)

        logger.info(f"Migration complete: {summary}")
        return summary

    def _backup_json_files(self, backup_dir: str) -> Path:
        """Copy all relevant JSON files to backup directory."""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = Path(f"{backup_dir}_{self.novel_slug}_{ts}")
        backup_path.mkdir(parents=True, exist_ok=True)

        glossary_dir = Path(f"data/output/{self.novel_slug}/glossary")
        if glossary_dir.exists():
            for json_file in glossary_dir.glob("*.json"):
                dest = backup_path / json_file.name
                shutil.copy2(json_file, dest)
                logger.info(f"Backed up: {json_file} -> {dest}")

        return backup_path

    def _migrate_glossary(self, novel_id: str) -> int:
        """Import glossary.json terms into SQLite. Returns count from file."""
        glossary_path = Path(f"data/output/{self.novel_slug}/glossary/glossary.json")
        if not glossary_path.exists():
            logger.info(f"No glossary file found at {glossary_path}")
            return 0

        with open(glossary_path, encoding="utf-8-sig") as f:
            data = json.load(f)

        terms = data.get("terms", [])
        for term in terms:
            source = term.get("source") or term.get("source_term", "")
            target = term.get("target") or term.get("target_term", "")
            if not source or not target:
                continue

            # Skip if term already exists (idempotent)
            existing = self.glossary_repo.get_term_by_source(novel_id, source)
            if existing:
                continue

            status = "approved" if term.get("verified") else "pending"
            self.glossary_repo.add_term(
                novel_id=novel_id,
                source_term=source,
                target_term=target,
                category=term.get("category", "general"),
                status=status,
                enforcement_level="strict" if term.get("verified") else "soft",
            )

        logger.info(f"Processed {len(terms)} glossary terms")
        return len(terms)

    def _migrate_pending(self, novel_id: str) -> int:
        """Import glossary_pending.json terms into SQLite. Returns count from file."""
        pending_path = Path(f"data/output/{self.novel_slug}/glossary/glossary_pending.json")
        if not pending_path.exists():
            return 0

        with open(pending_path, encoding="utf-8-sig") as f:
            data = json.load(f)

        pending = data.get("pending_terms", [])
        for term in pending:
            source = term.get("source", "")
            target = term.get("target", "")
            if not source or not target:
                continue

            # Skip if term already exists (idempotent)
            existing = self.glossary_repo.get_term_by_source(novel_id, source)
            if existing:
                continue

            self.glossary_repo.add_term(
                novel_id=novel_id,
                source_term=source,
                target_term=target,
                category=term.get("category", "general"),
                status=term.get("status", "pending"),
                enforcement_level="soft",
            )

        logger.info(f"Processed {len(pending)} pending terms")
        return len(pending)

    def _migrate_chapters(self, novel_id: str) -> int:
        """Discover and register chapter files in SQLite. Returns count of files found."""
        output_dir = Path(f"data/output/{self.novel_slug}")
        if not output_dir.exists():
            return 0

        count = 0
        for mm_file in sorted(output_dir.glob("*_chapter_*.mm.md")):
            # Extract chapter number from filename
            # Pattern: novel_chapter_NNNN.mm.md
            stem = mm_file.stem.replace(".mm", "")  # Remove .mm suffix if present
            parts = stem.rsplit("_chapter_", 1)
            if len(parts) != 2:
                continue
            try:
                chapter_num = int(parts[1])
            except ValueError:
                continue

            chapter_id = f"chapter_{novel_id}_{chapter_num:04d}"
            if not self.chapter_repo.get_by_id(chapter_id):
                self.chapter_repo.create(
                    novel_id=novel_id,
                    chapter_num=chapter_num,
                    file_path=str(mm_file),
                    translation_status="translated",
                )
            count += 1

        logger.info(f"Chapter migration complete: {count} files")
        return count

    def _migrate_context(self, novel_id: str) -> int:
        """Import context_memory.json as a context snapshot. Returns 1 if created, 0 otherwise."""
        context_path = Path(f"data/output/{self.novel_slug}/glossary/context_memory.json")
        if not context_path.exists():
            return 0

        with open(context_path, encoding="utf-8-sig") as f:
            data = json.load(f)

        chapter_num = data.get("current_chapter", 0)
        if chapter_num == 0:
            return 0

        chapter_id = f"chapter_{novel_id}_{chapter_num:04d}"

        # Ensure chapter record exists before creating snapshot
        existing = self.chapter_repo.get_by_id(chapter_id)
        if not existing:
            self.chapter_repo.create(
                novel_id=novel_id,
                chapter_num=chapter_num,
                file_path="",
                translation_status="translated",
            )

        summary_json = json.dumps({
            "active_chars": list(data.get("active_characters", {}).keys()),
            "events": data.get("recent_events", []),
            "summary": data.get("summary", ""),
            "new_terms": [],
        }, ensure_ascii=False)

        self.context_repo.create_snapshot(chapter_id, summary_json)
        logger.info("Context migration complete")
        return 1
