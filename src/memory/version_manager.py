"""
VersionManager — Central coordinator for versioning and change tracking.

Provides:
- Chapter version snapshots with rollback capability
- Glossary change impact analysis
- Sync job creation and execution
- Audit logging for all changes
"""

import logging
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.db.connection import DatabaseConnection
from src.db.repositories.chapter_repo import ChapterRepository
from src.db.repositories.sync_repo import SyncRepository
from src.db.repositories.glossary_repo import GlossaryRepository
from src.db.repositories.context_repo import ContextRepository

logger = logging.getLogger(__name__)


class VersionManager:
    """
    Central coordinator for versioning and change tracking across chapters.
    
    This class provides:
    1. Chapter version snapshots (who changed what and when)
    2. Glossary change impact analysis (preview affected chapters)
    3. Sync job execution (commit changes with single pass)
    4. Audit logging for all operations
    """

    def __init__(
        self,
        db: DatabaseConnection,
        output_dir: Path,
        versions_dir: Optional[Path] = None,
    ):
        """
        Initialize VersionManager.

        Args:
            db: Database connection
            output_dir: Base directory for novel outputs
            versions_dir: Directory to store version snapshots (default: output_dir/.versions)
        """
        self.db = db
        self.output_dir = Path(output_dir)
        self.versions_dir = versions_dir or self.output_dir / ".versions"
        self.versions_dir.mkdir(parents=True, exist_ok=True)

        self.chapter_repo = ChapterRepository(db)
        self.sync_repo = SyncRepository(db)
        self.glossary_repo = GlossaryRepository(db)
        self.context_repo = ContextRepository(db)

    # ═══════════════════════════════════════════════════════════════════════
    # Chapter Versioning
    # ═══════════════════════════════════════════════════════════════════════

    def snapshot_chapter(
        self,
        novel_name: str,
        chapter_num: int,
        reason: str = "translation",
        source: str = "pipeline",
    ) -> Optional[dict]:
        """
        Create a version snapshot of a chapter file.

        Args:
            novel_name: Novel slug/name
            chapter_num: Chapter number
            reason: Why this snapshot was created
            source: Who/what created it (pipeline, manual, sync_job, etc.)

        Returns:
            Version record dict or None if chapter file doesn't exist
        """
        chapter_file = self._get_chapter_file(novel_name, chapter_num)
        if not chapter_file.exists():
            logger.warning(f"Cannot snapshot: file not found: {chapter_file}")
            return None

        # Get or create chapter record
        novel_id = self._get_or_create_novel(novel_name)
        chapter = self.chapter_repo.get_by_number(novel_id, chapter_num)
        if not chapter:
            chapter = self.chapter_repo.create(
                novel_id=novel_id,
                chapter_num=chapter_num,
                file_path=str(chapter_file),
            )

        # Create version snapshot
        version_path = self._copy_to_versions(chapter_file, novel_name, chapter_num)
        version = self.chapter_repo.create_version(
            chapter_id=chapter["id"],
            file_snapshot_path=str(version_path),
            reason=f"{source}:{reason}",
        )

        # Audit log
        self.sync_repo.log_action(
            table_name="chapters",
            record_id=chapter["id"],
            action="version_created",
            new_data=f"v{version['version_num']}: {reason}",
            source=source,
        )

        logger.info(f"Chapter {chapter_num} version {version['version_num']} created: {reason}")
        return version

    def list_versions(self, novel_name: str, chapter_num: int) -> list[dict]:
        """
        List all versions for a chapter.

        Args:
            novel_name: Novel slug/name
            chapter_num: Chapter number

        Returns:
            List of version records
        """
        novel_id = self._get_novel_id(novel_name)
        if not novel_id:
            return []

        chapter = self.chapter_repo.get_by_number(novel_id, chapter_num)
        if not chapter:
            return []

        return self.chapter_repo.get_all_versions(chapter["id"])

    def rollback_chapter(
        self,
        novel_name: str,
        chapter_num: int,
        version_num: int,
        reason: str = "manual rollback",
    ) -> Optional[Path]:
        """
        Rollback a chapter to a specific version.

        Args:
            novel_name: Novel slug/name
            chapter_num: Chapter number
            version_num: Version to restore
            reason: Why the rollback is happening

        Returns:
            Path to the restored file or None if failed
        """
        novel_id = self._get_novel_id(novel_name)
        if not novel_id:
            logger.error(f"Novel not found: {novel_name}")
            return None

        chapter = self.chapter_repo.get_by_number(novel_id, chapter_num)
        if not chapter:
            logger.error(f"Chapter not found: {novel_name} #{chapter_num}")
            return None

        version = self.chapter_repo.get_version(chapter["id"], version_num)
        if not version:
            logger.error(f"Version {version_num} not found for chapter {chapter_num}")
            return None

        version_path = Path(version["file_snapshot_path"])
        if not version_path.exists():
            logger.error(f"Version file not found: {version_path}")
            return None

        # Snapshot current state before rollback
        current_file = self._get_chapter_file(novel_name, chapter_num)
        if current_file.exists():
            self.snapshot_chapter(novel_name, chapter_num, reason="pre-rollback", source="rollback")

        # Restore the version
        target_path = self._get_chapter_file(novel_name, chapter_num)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(version_path, target_path)

        # Update chapter status
        self.chapter_repo.update_status(chapter["id"], "rolled_back")

        # Audit log
        self.sync_repo.log_action(
            table_name="chapters",
            record_id=chapter["id"],
            action="rollback",
            old_data="current",
            new_data=f"v{version_num}",
            source="manual",
        )

        logger.info(f"Chapter {chapter_num} rolled back to version {version_num}")
        return target_path

    def diff_versions(
        self,
        novel_name: str,
        chapter_num: int,
        version_a: int,
        version_b: int,
    ) -> Optional[str]:
        """
        Generate a diff between two chapter versions.

        Args:
            novel_name: Novel slug/name
            chapter_num: Chapter number
            version_a: First version number
            version_b: Second version number

        Returns:
            Diff text or None if versions not found
        """
        novel_id = self._get_novel_id(novel_name)
        if not novel_id:
            return None

        chapter = self.chapter_repo.get_by_number(novel_id, chapter_num)
        if not chapter:
            return None

        v1 = self.chapter_repo.get_version(chapter["id"], version_a)
        v2 = self.chapter_repo.get_version(chapter["id"], version_b)

        if not v1 or not v2:
            return None

        path1 = Path(v1["file_snapshot_path"])
        path2 = Path(v2["file_snapshot_path"])

        if not path1.exists() or not path2.exists():
            return None

        try:
            text1 = path1.read_text(encoding="utf-8-sig")
            text2 = path2.read_text(encoding="utf-8-sig")
        except Exception as e:
            logger.error(f"Error reading version files: {e}")
            return None

        # Simple line-based diff
        lines1 = text1.splitlines()
        lines2 = text2.splitlines()

        diff_lines = []
        diff_lines.append(f"--- Version {version_a}")
        diff_lines.append(f"+++ Version {version_b}")
        diff_lines.append("")

        max_lines = max(len(lines1), len(lines2))
        for i in range(max_lines):
            line1 = lines1[i] if i < len(lines1) else None
            line2 = lines2[i] if i < len(lines2) else None

            if line1 != line2:
                if line1 is not None:
                    diff_lines.append(f"-{line1}")
                if line2 is not None:
                    diff_lines.append(f"+{line2}")

        return "\n".join(diff_lines)

    # ═══════════════════════════════════════════════════════════════════════
    # Glossary Change Impact Analysis
    # ═══════════════════════════════════════════════════════════════════════

    def preview_glossary_change(
        self,
        novel_name: str,
        term_id: str,
        new_value: str,
    ) -> dict:
        """
        Preview which chapters would be affected by a glossary change.

        Args:
            novel_name: Novel slug/name
            term_id: Glossary term ID
            new_value: Proposed new translation

        Returns:
            Dict with affected_chapters list and impact stats
        """
        novel_id = self._get_novel_id(novel_name)
        if not novel_id:
            return {"affected_chapters": [], "total_occurrences": 0, "error": "Novel not found"}

        # Get term details
        term = self.glossary_repo.get_term(term_id)
        if not term:
            return {"affected_chapters": [], "total_occurrences": 0, "error": "Term not found"}

        old_value = term["target_term"]

        # Find all occurrences
        usage_records = self.context_repo.get_usage_by_term(term_id)

        # Group by chapter
        chapter_impacts = {}
        for usage in usage_records:
            chapter_id = usage["chapter_id"]
            if chapter_id not in chapter_impacts:
                chapter = self.chapter_repo.get_by_id(chapter_id)
                chapter_impacts[chapter_id] = {
                    "chapter_id": chapter_id,
                    "chapter_num": chapter["chapter_num"] if chapter else 0,
                    "occurrences": 0,
                    "context_snippets": [],
                }
            chapter_impacts[chapter_id]["occurrences"] += 1
            if usage.get("context_snippet"):
                chapter_impacts[chapter_id]["context_snippets"].append(
                    usage["context_snippet"]
                )

        # Also scan current chapter files for the old term
        file_matches = self._scan_files_for_term(novel_name, old_value)

        affected_chapters = []
        for chapter_id, impact in chapter_impacts.items():
            chapter_num = impact["chapter_num"]
            # Check if file still contains the old term
            file_match = next((m for m in file_matches if m["chapter_num"] == chapter_num), None)
            if file_match:
                impact["file_occurrences"] = file_match["count"]
                affected_chapters.append(impact)

        return {
            "term_id": term_id,
            "source_term": term["source_term"],
            "old_value": old_value,
            "new_value": new_value,
            "affected_chapters": affected_chapters,
            "total_occurrences": len(usage_records),
            "chapters_with_files": len([c for c in affected_chapters if c.get("file_occurrences", 0) > 0]),
        }

    def create_sync_job(
        self,
        novel_name: str,
        term_id: str,
        new_value: str,
        chapter_nums: Optional[list[int]] = None,
    ) -> Optional[dict]:
        """
        Create a sync job to update a term across chapters.

        Args:
            novel_name: Novel slug/name
            term_id: Glossary term ID
            new_value: New translation value
            chapter_nums: Specific chapters to update (None = all affected)

        Returns:
            Sync job record or None if creation failed
        """
        novel_id = self._get_novel_id(novel_name)
        if not novel_id:
            return None

        term = self.glossary_repo.get_term(term_id)
        if not term:
            return None

        old_value = term["target_term"]

        # Create sync job
        job = self.sync_repo.create_job(
            term_id=term_id,
            old_value=old_value,
            new_value=new_value,
            status="pending_review",
        )

        # Determine which chapters to include
        if chapter_nums is None:
            # Auto-detect from usage records
            preview = self.preview_glossary_change(novel_name, term_id, new_value)
            chapter_nums = [c["chapter_num"] for c in preview["affected_chapters"]]

        # Get chapter IDs
        chapter_ids = []
        for num in chapter_nums:
            chapter = self.chapter_repo.get_by_number(novel_id, num)
            if chapter:
                chapter_ids.append(chapter["id"])

        # Link chapters to job
        if chapter_ids:
            self.sync_repo.add_job_chapters(job["id"], chapter_ids)

        logger.info(f"Sync job {job['id']} created for term '{term['source_term']}': {len(chapter_ids)} chapters")
        return job

    def execute_sync_job(
        self,
        job_id: int,
        dry_run: bool = False,
    ) -> dict:
        """
        Execute a sync job to update a term across all linked chapters.

        Args:
            job_id: Sync job ID
            dry_run: If True, preview changes without applying

        Returns:
            Execution result with stats
        """
        job = self.sync_repo.get_job(job_id)
        if not job:
            return {"success": False, "error": "Job not found"}

        if job["status"] == "applied" and not dry_run:
            return {"success": False, "error": "Job already applied"}

        term = self.glossary_repo.get_term(job["term_id"])
        if not term:
            return {"success": False, "error": "Term not found"}

        # Get novel name from term
        novel_id = term.get("novel_id")
        novel_row = self.db.fetchone("SELECT name FROM novels WHERE id = ?", (novel_id,))
        novel_name = novel_row["name"] if novel_row else "unknown"

        old_value = job["old_value"]
        new_value = job["new_value"]

        # Get pending chapters
        job_chapters = self.sync_repo.get_job_chapters(job_id)
        pending = [jc for jc in job_chapters if jc["status"] == "pending"]

        results = {
            "success": True,
            "job_id": job_id,
            "dry_run": dry_run,
            "term": term["source_term"],
            "old_value": old_value,
            "new_value": new_value,
            "chapters_total": len(job_chapters),
            "chapters_pending": len(pending),
            "chapters_updated": 0,
            "chapters_failed": 0,
            "replacements_total": 0,
            "details": [],
        }

        for jc in pending:
            chapter_id = jc["chapter_id"]
            chapter = self.chapter_repo.get_by_id(chapter_id)
            if not chapter:
                continue

            chapter_num = chapter["chapter_num"]
            chapter_file = self._get_chapter_file(novel_name, chapter_num)

            if not chapter_file.exists():
                results["chapters_failed"] += 1
                results["details"].append({
                    "chapter_num": chapter_num,
                    "status": "failed",
                    "error": "File not found",
                })
                continue

            try:
                # Snapshot before change
                if not dry_run:
                    self.snapshot_chapter(novel_name, chapter_num, reason=f"pre-sync-job-{job_id}", source="sync")

                # Read and replace
                text = chapter_file.read_text(encoding="utf-8-sig")
                count_before = text.count(old_value)

                if dry_run:
                    # Preview only
                    results["replacements_total"] += count_before
                    results["details"].append({
                        "chapter_num": chapter_num,
                        "status": "preview",
                        "replacements": count_before,
                    })
                else:
                    # Apply replacement
                    new_text = text.replace(old_value, new_value)
                    count_after = new_text.count(new_value)
                    actual_replacements = count_after - text.count(new_value) + count_before

                    # Write back
                    chapter_file.write_text(new_text, encoding="utf-8-sig")

                    # Update job chapter status
                    self.sync_repo.update_chapter_status(job_id, chapter_id, "applied")

                    results["chapters_updated"] += 1
                    results["replacements_total"] += actual_replacements
                    results["details"].append({
                        "chapter_num": chapter_num,
                        "status": "updated",
                        "replacements": actual_replacements,
                    })

            except Exception as e:
                logger.error(f"Sync failed for chapter {chapter_num}: {e}")
                results["chapters_failed"] += 1
                results["details"].append({
                    "chapter_num": chapter_num,
                    "status": "failed",
                    "error": str(e),
                })

        # Update job status
        if not dry_run and results["chapters_failed"] == 0:
            self.sync_repo.update_job_status(job_id, "applied")
            # Update glossary term
            self.glossary_repo.update_term(
                term_id=job["term_id"],
                target_term=new_value,
            )
        elif not dry_run:
            self.sync_repo.update_job_status(job_id, "partial")

        return results

    def list_sync_jobs(
        self,
        novel_name: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[dict]:
        """
        List sync jobs with optional filters.

        Args:
            novel_name: Filter by novel
            status: Filter by status (pending_review, applied, partial, rejected)

        Returns:
            List of sync job records
        """
        if novel_name:
            # Get all terms for this novel
            novel_id = self._get_novel_id(novel_name)
            if not novel_id:
                return []
            
            term_ids = self.glossary_repo.get_all_term_ids(novel_id)
            
            # Get jobs for these terms
            jobs = []
            for term_id in term_ids:
                term_jobs = self.sync_repo.get_jobs_by_term(term_id, status)
                jobs.extend(term_jobs)
            
            return sorted(jobs, key=lambda x: x["created_at"], reverse=True)
        else:
            # Get all jobs by status
            if status:
                rows = self.db.fetchall(
                    "SELECT * FROM sync_jobs WHERE status = ? ORDER BY created_at DESC",
                    (status,),
                )
            else:
                rows = self.db.fetchall(
                    "SELECT * FROM sync_jobs ORDER BY created_at DESC"
                )
            return [dict(r) for r in rows]

    # ═══════════════════════════════════════════════════════════════════════
    # Audit Logging
    # ═══════════════════════════════════════════════════════════════════════

    def get_audit_log(
        self,
        novel_name: Optional[str] = None,
        table_name: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict]:
        """
        Get audit log entries.

        Args:
            novel_name: Filter by novel (only for chapter-related entries)
            table_name: Filter by table
            limit: Max entries to return

        Returns:
            List of audit log entries
        """
        if novel_name:
            novel_id = self._get_novel_id(novel_name)
            if not novel_id:
                return []

            # Get all chapter IDs for this novel
            chapters = self.chapter_repo.get_chapters_by_novel(novel_id)
            chapter_ids = {c["id"] for c in chapters}

            # Fetch and filter
            all_logs = self.sync_repo.get_audit_log(table_name=table_name, limit=limit * 2)
            filtered = [log for log in all_logs if log["record_id"] in chapter_ids]
            return filtered[:limit]
        else:
            return self.sync_repo.get_audit_log(table_name=table_name, limit=limit)

    # ═══════════════════════════════════════════════════════════════════════
    # Helper Methods
    # ═══════════════════════════════════════════════════════════════════════

    def _get_chapter_file(self, novel_name: str, chapter_num: int) -> Path:
        """Get the path to a chapter output file."""
        return self.output_dir / novel_name / f"{novel_name}_chapter_{chapter_num:04d}.mm.md"

    def _get_or_create_novel(self, novel_name: str) -> str:
        """Get novel ID, creating if necessary."""
        novel_id = self._get_novel_id(novel_name)
        if novel_id:
            return novel_id

        # Create new novel record
        slug = re.sub(r'[^\w\-]', '-', novel_name.lower())
        self.db.execute(
            "INSERT INTO novels (id, name, source_language) VALUES (?, ?, ?)",
            (slug, novel_name, "chinese"),
        )
        return slug

    def _get_novel_id(self, novel_name: str) -> Optional[str]:
        """Get novel ID by name."""
        # Try exact match first
        row = self.db.fetchone(
            "SELECT id FROM novels WHERE name = ? OR id = ?",
            (novel_name, novel_name),
        )
        if row:
            return row["id"]
        return None

    def _copy_to_versions(self, source: Path, novel_name: str, chapter_num: int) -> Path:
        """Copy a chapter file to the versions directory."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")  # Include microseconds for uniqueness
        filename = f"{novel_name}_{chapter_num:04d}_{timestamp}.mm.md"
        dest = self.versions_dir / filename
        shutil.copy2(source, dest)
        return dest

    def _scan_files_for_term(self, novel_name: str, term: str) -> list[dict]:
        """Scan all chapter files for a term."""
        matches = []
        novel_dir = self.output_dir / novel_name
        if not novel_dir.exists():
            return matches

        for file_path in novel_dir.glob("*.mm.md"):
            # Extract chapter number from filename
            match = re.search(r'chapter_(\d+)', file_path.name)
            if not match:
                continue
            chapter_num = int(match.group(1))

            try:
                text = file_path.read_text(encoding="utf-8-sig")
                count = text.count(term)
                if count > 0:
                    matches.append({
                        "chapter_num": chapter_num,
                        "file_path": str(file_path),
                        "count": count,
                    })
            except Exception:
                continue

        return matches
