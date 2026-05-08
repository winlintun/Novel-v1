#!/usr/bin/env python3
"""
Pipeline orchestrator for the novel translation pipeline.

Coordinates all translation stages:
1. Preprocessing - Chunk input text
2. Translation - Translate chunks
3. Refinement - Literary quality editing
4. Reflection - Self-correction (optional)
5. Quality Check - Myanmar linguistic validation
6. Consistency - Glossary verification
7. QA Review - Final validation
"""

import json
import time
import signal
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Callable
from datetime import datetime

from src.config import AppConfig
from src.utils.progress_logger import ProgressLogger

# Constants
INPUT_DIR = "data/input"
OUTPUT_DIR = "data/output"
WORKING_DIR = "working_data"


class TranslationPipeline:
    """Main translation pipeline orchestrator.
    
    Coordinates all agents and stages to translate novel chapters
    from Chinese to Myanmar with quality checks.
    """

    def __init__(self, config: AppConfig):
        """Initialize the pipeline with configuration.
        
        Args:
            config: Application configuration
        """
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Initialize agents (lazy loading)
        self._preprocessor = None
        self._translator = None
        self._refiner = None
        self._reflection_agent = None
        self._myanmar_checker = None
        self._checker = None
        self._qa_tester = None
        self._context_updater = None
        self._memory_manager = None
        
        # Separate Ollama clients for each role (to support different models)
        self._ollama_client_translator = None
        self._ollama_client_refiner = None
        self._ollama_client_checker = None

        # State
        self._shutdown_requested = False
        self._current_novel: Optional[str] = None
        self._progress_callback: Optional[Callable] = None
        self._version_manager = None

        # Register signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum: int, frame: Any) -> None:
        """Handle shutdown signals gracefully."""
        self.logger.warning("Shutdown requested. Finishing current chunk...")
        self._shutdown_requested = True

    def _check_stop_signal(self) -> bool:
        """Check if stop signal file exists (set by Web UI).

        Returns:
            True if stop signal detected, False otherwise.
        """
        stop_flag = Path("logs/translation_stop.flag")
        if stop_flag.exists():
            self.logger.warning("Stop signal detected from Web UI")
            return True
        return False

    def set_progress_callback(self, callback: Optional[Callable[[Dict[str, Any]], None]]) -> None:
        """Set a progress callback for live CLI output.
        
        Args:
            callback: Function that accepts a dict event, or None to disable
        """
        self._progress_callback = callback

    def _report(self, event: Dict[str, Any]) -> None:
        """Send a progress event to the callback if configured."""
        if self._progress_callback:
            try:
                self._progress_callback(event)
            except Exception:
                pass  # Never let progress reporting break the pipeline
        # Write live progress to file so the Flask web UI can poll it
        try:
            event_type = event.get("type", "")
            progress_file = Path("logs/progress_current.json")
            if progress_file.exists() and event_type in (
                "chunk_start", "chunk_translated", "chunk_complete", "summary"
            ):
                with open(progress_file, "r", encoding="utf-8") as _f:
                    pdata = json.load(_f)
                if event_type in ("chunk_start", "chunk_translated", "chunk_complete"):
                    pdata["status"] = "translating"
                    pdata["current_chunk"] = event.get("chunk_index", pdata.get("current_chunk", 0))
                    pdata["total_chunks"] = event.get("total_chunks", pdata.get("total_chunks", 0))
                    pdata["message"] = (
                        f"Chunk {pdata['current_chunk']}/{pdata['total_chunks']}"
                    )
                elif event_type == "summary":
                    pdata["status"] = "completed"
                    pdata["message"] = "Translation completed!"
                with open(progress_file, "w", encoding="utf-8") as _f:
                    json.dump(pdata, _f)
        except Exception:
            pass  # Never let progress reporting break the pipeline

    def _write_completion_report(
        self,
        filepath: str,
        output_path: Path,
        duration: float,
        chapter_num: Optional[int],
        total_chunks: int,
        avg_score: float
    ) -> None:
        """Write a detailed completion report to logs directory.
        
        Creates a human-readable log file with translation details including
        pipeline mode, model name, and duration in hours/minutes/seconds.
        """
        try:
            from datetime import datetime
            
            # Calculate duration in hours, minutes, seconds
            hours = int(duration // 3600)
            minutes = int((duration % 3600) // 60)
            seconds = int(duration % 60)
            
            # Format duration string
            if hours > 0:
                duration_str = f"{hours}h {minutes}m {seconds}s"
            elif minutes > 0:
                duration_str = f"{minutes}m {seconds}s"
            else:
                duration_str = f"{seconds}s"
            
            # Get pipeline info from config
            pipeline_mode = getattr(self.config.translation_pipeline, 'mode', 'unknown')
            model_name = getattr(self.config.models, 'translator', 'unknown')
            
            # Build report content
            report_lines = [
                "=" * 60,
                "TRANSLATION COMPLETION REPORT",
                "=" * 60,
                "",
                f"Timestamp:     {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"Input File:    {filepath}",
                f"Output File:   {output_path}",
                f"Chapter:       {chapter_num if chapter_num else 'N/A'}",
                "",
                "-" * 40,
                "PIPELINE CONFIGURATION",
                "-" * 40,
                f"Pipeline Mode: {pipeline_mode}",
                f"Model Name:    {model_name}",
                "",
                "-" * 40,
                "TRANSLATION METRICS",
                "-" * 40,
                f"Total Chunks:  {total_chunks}",
                f"Avg Quality:   {avg_score:.1f}/100",
                f"Duration:      {duration_str} ({duration:.1f}s)",
                "",
                "=" * 60,
                "",
            ]
            
            # Ensure logs directory exists
            report_dir = Path("logs/report")
            report_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate filename with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            novel_name = self._current_novel or "unknown"
            chapter_str = f"_ch{chapter_num:04d}" if chapter_num else ""
            report_file = report_dir / f"{novel_name}{chapter_str}_completion_{timestamp}.log"
            
            # Write report
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(report_lines))
            
            self.logger.info(f"Completion report saved: {report_file}")
            
        except Exception as e:
            self.logger.warning(f"Failed to write completion report: {e}")

    @property
    def memory_manager(self):
        """Lazy load memory manager with novel-specific glossary."""
        if self._memory_manager is None:
            from src.memory.memory_manager import MemoryManager
            # Determine storage backend from config
            use_sql = self.config.storage.backend == "sqlite"
            db_path = self.config.storage.db_path
            self._memory_manager = MemoryManager(
                novel_name=self._current_novel,
                use_sql=use_sql,
                db_path=db_path
            )
            self.logger.info(f"MemoryManager initialized with {'SQLite' if use_sql else 'JSON'} backend")
            # Auto-approve pending glossary terms marked 'approved' by user
            try:
                auto_count = self._memory_manager.auto_approve_pending_terms()
                if auto_count:
                    self.logger.info(f"Auto-promoted {auto_count} pending glossary terms")
            except Exception:
                pass
            # Auto-approve high-confidence terms (no manual review needed)
            try:
                confidence_count = self._memory_manager.auto_approve_by_confidence()
                if confidence_count:
                    self.logger.info(f"Confidence-based auto-approve: {confidence_count} terms promoted")
            except Exception:
                pass
        return self._memory_manager

    @property
    def version_manager(self):
        """Lazy load version manager for SQL backend."""
        if self._version_manager is None:
            from src.memory.version_manager import VersionManager
            from src.db.connection import DatabaseConnection
            use_sql = self.config.storage.backend == "sqlite"
            if use_sql:
                db = DatabaseConnection(self.config.storage.db_path)
                self._version_manager = VersionManager(
                    db=db,
                    output_dir=Path(OUTPUT_DIR),
                )
            else:
                self._version_manager = None
        return self._version_manager

    def _create_ollama_client(self, model: str) -> Any:
        """Create an OllamaClient with the specified model."""
        from src.utils.ollama_client import OllamaClient
        return OllamaClient(
            model=model,
            base_url=self.config.models.ollama_base_url,
            timeout=self.config.models.timeout,
            temperature=getattr(self.config.processing, 'temperature', 0.3),
            top_p=getattr(self.config.processing, 'top_p', 0.92),
            top_k=getattr(self.config.processing, 'top_k', 50),
            repeat_penalty=getattr(self.config.processing, 'repeat_penalty', 1.3),
            max_retries=getattr(self.config.processing, 'max_retries', 2),
            use_gpu=getattr(self.config.models, 'use_gpu', True),
            use_generate_endpoint=getattr(self.config.models, 'use_generate_endpoint', False),
            num_ctx=getattr(self.config.models, 'num_ctx', 8192),
            gpu_layers=getattr(self.config.models, 'gpu_layers', -1),
            main_gpu=getattr(self.config.models, 'main_gpu', 0)
        )

    @property
    def ollama_client_translator(self):
        """Lazy load Ollama client for translator."""
        if self._ollama_client_translator is None:
            self._ollama_client_translator = self._create_ollama_client(
                self.config.models.translator
            )
        return self._ollama_client_translator

    @property
    def ollama_client_refiner(self):
        """Lazy load Ollama client for refiner."""
        if self._ollama_client_refiner is None:
            # Use refiner model if specified, fallback to editor, then translator
            model = getattr(self.config.models, 'refiner', None) or \
                    getattr(self.config.models, 'editor', None) or \
                    self.config.models.translator
            self._ollama_client_refiner = self._create_ollama_client(model)
        return self._ollama_client_refiner

    @property
    def ollama_client_checker(self):
        """Lazy load Ollama client for checker."""
        if self._ollama_client_checker is None:
            # Use checker model if specified, fallback to translator
            model = getattr(self.config.models, 'checker', None) or \
                    self.config.models.translator
            self._ollama_client_checker = self._create_ollama_client(model)
        return self._ollama_client_checker

    @property
    def ollama_client(self):
        """Lazy load Ollama client (backward compatibility - uses translator model)."""
        return self.ollama_client_translator

    @property
    def preprocessor(self):
        """Lazy load preprocessor."""
        if self._preprocessor is None:
            from src.agents.preprocessor import Preprocessor
            self._preprocessor = Preprocessor(
                chunk_size=self.config.processing.chunk_size,
                memory_manager=self.memory_manager,
                config=self.config.dict(),
            )
        return self._preprocessor

    @property
    def translator(self):
        """Lazy load translator."""
        if self._translator is None:
            from src.agents.translator import Translator
            self._translator = Translator(
                ollama_client=self.ollama_client,
                memory_manager=self.memory_manager,
                config=self.config.dict()
            )
        return self._translator

    @property
    def refiner(self):
        """Lazy load refiner."""
        if self._refiner is None:
            from src.agents.refiner import Refiner
            self._refiner = Refiner(
                ollama_client=self.ollama_client_refiner,
                batch_size=getattr(self.config.processing, 'batch_size', 1),
                config=self.config.dict(),
                memory_manager=self.memory_manager
            )
        return self._refiner

    @property
    def reflection_agent(self):
        """Lazy load reflection agent."""
        if self._reflection_agent is None:
            from src.agents.reflection_agent import ReflectionAgent
            self._reflection_agent = ReflectionAgent(
                ollama_client=self.ollama_client_refiner,
                config=self.config.dict(),
                memory_manager=self.memory_manager
            )
        return self._reflection_agent

    @property
    def myanmar_checker(self):
        """Lazy load Myanmar quality checker."""
        if self._myanmar_checker is None:
            from src.agents.myanmar_quality_checker import MyanmarQualityChecker
            self._myanmar_checker = MyanmarQualityChecker(
                ollama_client=self.ollama_client_checker,
                memory_manager=self.memory_manager,
                config=self.config.dict()
            )
        return self._myanmar_checker

    @property
    def checker(self):
        """Lazy load consistency checker."""
        if self._checker is None:
            from src.agents.checker import Checker
            self._checker = Checker(
                memory_manager=self.memory_manager,
                config=self.config.dict()
            )
        return self._checker

    @property
    def qa_tester(self):
        """Lazy load QA tester."""
        if self._qa_tester is None:
            from src.agents.qa_tester import QATesterAgent
            self._qa_tester = QATesterAgent(
                memory_manager=self.memory_manager,
                config=self.config.dict()
            )
        return self._qa_tester

    @property
    def context_updater(self):
        """Lazy load context updater."""
        if self._context_updater is None:
            from src.agents.context_updater import ContextUpdater
            self._context_updater = ContextUpdater(
                ollama_client=self.ollama_client,
                memory_manager=self.memory_manager,
                config=self.config.dict()
            )
        return self._context_updater

    def translate_file(self, filepath: str, novel_name: Optional[str] = None) -> Dict[str, Any]:
        """Translate a single file.

        Args:
            filepath: Path to input file
            novel_name: Novel name for glossary resolution

        Returns:
            Pipeline result dictionary
        """
        self.logger.info(f"Starting translation of file: {filepath}")
        start_time = time.time()

        # Resolve novel name from filepath if not provided
        if novel_name:
            self._current_novel = novel_name
        else:
            self._current_novel = self._extract_novel_from_path(filepath)

        try:
            # Read file
            from src.utils.file_handler import FileHandler
            text = FileHandler.read_text(filepath)

            # Chapter label for progress display
            chapter_label = Path(filepath).name

            # Extract chapter number from filename (needed for meta + context update)
            import re
            chapter_num = None
            m = re.search(r'(\d+)', Path(filepath).stem)
            if m:
                chapter_num = int(m.group(1))

            # Preprocess
            chunks = self._preprocess(text, chapter_label)

            # Initialize progress logger for real-time tracking
            progress_logger = None
            try:
                progress_logger = ProgressLogger(
                    book_id=self._current_novel or "unknown",
                    chapter_name=chapter_label,
                    total_chunks=len(chunks),
                    log_dir="logs/progress"
                )
                self.logger.info(f"Progress logging to: {progress_logger.get_log_path()}")
            except Exception as e:
                self.logger.warning(f"Could not initialize progress logger: {e}")

            # Translate (now returns chunks + per-chunk metrics)
            translated_chunks, chunk_metrics = self._translate_chunks(chunks, progress_logger)

            # Postprocess
            result_text = self._postprocess(translated_chunks)

            # Stage 6: QA Validation — final quality gate on assembled chapter
            # Runs after postprocessing so it checks the full, clean output
            qa_result = None
            try:
                if self.config.translation_pipeline.mode in ('full', 'lite'):
                    qa_result = self.qa_tester.validate_output(result_text, chapter_num or 0)
                    if qa_result.get("issues"):
                        self.logger.warning(
                            f"QA found {len(qa_result['issues'])} issues: {qa_result['issues']}"
                        )
                    mya_ratio = qa_result.get("metrics", {}).get("myanmar_ratio", 0)
                    self.logger.info(
                        f"QA: passed={qa_result.get('passed')}, "
                        f"MyeRatio={mya_ratio:.1%}, issues={len(qa_result.get('issues', []))}"
                    )
            except Exception as e:
                self.logger.warning(f"QA validation failed (non-fatal): {e}")

            # ── Problem 2: Myanmar ratio quality gate ──────────────────────────
            # Block save if assembled output has Myanmar ratio < 70%.
            # This prevents saving garbage chunks that failed retry.
            overall_mm_ratio = self._calc_myanmar_ratio(result_text)
            if overall_mm_ratio < 0.70:
                self.logger.error(
                    f"Quality gate FAILED: overall Myanmar ratio {overall_mm_ratio:.1%} < 70%. "
                    f"File NOT saved. Please retranslate this chapter."
                )
                return {
                    "success": False,
                    "output_path": None,
                    "glossary_updates": [],
                    "errors": [
                        f"Quality gate: Myanmar ratio {overall_mm_ratio:.1%} < 70% — file not saved"
                    ],
                    "metrics": {"myanmar_ratio": overall_mm_ratio},
                    "chapter": Path(filepath).stem,
                }
            # Also block if any chunk produced < 40% Myanmar (severely broken chunk)
            if chunk_metrics:
                bad_chunks = [m for m in chunk_metrics if m.get("myanmar_ratio", 1.0) < 0.40]
                if bad_chunks:
                    self.logger.error(
                        f"Quality gate FAILED: {len(bad_chunks)} chunk(s) with Myanmar ratio < 40%. "
                        f"File NOT saved. Please retranslate."
                    )
                    return {
                        "success": False,
                        "output_path": None,
                        "glossary_updates": [],
                        "errors": [
                            f"Quality gate: {len(bad_chunks)} chunk(s) with Myanmar ratio < 40%"
                        ],
                        "metrics": {"bad_chunks": len(bad_chunks)},
                        "chapter": Path(filepath).stem,
                    }

            duration = time.time() - start_time

            # Save output
            output_path = self._save_output(filepath, result_text, extra_meta={
                "duration_seconds": round(duration, 1),
                "model": self.config.models.translator,
                "chunk_count": len(chunk_metrics) if chunk_metrics else None,
                "myanmar_ratio": round(
                    self._calc_myanmar_ratio(result_text), 3
                ) if result_text else 0.0,
                "char_count": len(result_text) if result_text else 0,
                "avg_quality_score": round(
                    sum(m["quality_score"] for m in chunk_metrics) / len(chunk_metrics), 1
                ) if chunk_metrics else None,
            })

            # Auto-review: generate quality report after saving
            try:
                self._auto_review(str(output_path), result_text)
            except Exception as e:
                self.logger.warning(f"Auto-review failed (non-fatal): {e}")

            # Context Update: extract new terms → pending glossary (non-fatal)
            try:
                ctx_result = self.context_updater.process_chapter(
                    original_text=text,
                    translated_text=result_text,
                    chapter_num=chapter_num or 0,
                )
                if ctx_result and ctx_result.get('new_terms_added', 0) > 0:
                    self.logger.info(
                        f"Context update: {ctx_result['new_terms_added']} new terms pending review, "
                        f"{ctx_result.get('entities_found', 0)} entities found"
                    )
            except Exception as e:
                self.logger.warning(f"Context update failed (non-fatal): {e}")

            # Update context_memory.json with chapter data
            try:
                if self.memory_manager:
                    self.memory_manager.update_chapter_context(
                        chapter_num=chapter_num or 0,
                        translated_text=result_text
                    )
                    self.logger.debug(f"Context memory updated for chapter {chapter_num or 0}")
            except Exception as e:
                self.logger.warning(f"Context memory update failed (non-fatal): {e}")

            # Compute summary metrics
            avg_score = 0
            total_issues = 0
            if chunk_metrics:
                avg_score = sum(m["quality_score"] for m in chunk_metrics) / len(chunk_metrics)
                total_issues = sum(m["issues"] for m in chunk_metrics)

            # Emit summary
            self._report({
                "type": "summary",
                "total_chunks": len(chunk_metrics),
                "avg_score": avg_score,
                "total_time": duration,
                "output_path": str(output_path),
                "file_size": len(result_text.encode('utf-8')),
                "issues_total": total_issues,
            })
            
            # Generate completion report
            self._write_completion_report(
                filepath=filepath,
                output_path=output_path,
                duration=duration,
                chapter_num=chapter_num,
                total_chunks=len(chunk_metrics),
                avg_score=avg_score
            )

            # Finalize progress logger
            if progress_logger:
                try:
                    progress_logger.finalize(success=True)
                    self.logger.info(f"Progress log saved: {progress_logger.get_log_path()}")
                except Exception as e:
                    self.logger.warning(f"Could not finalize progress logger: {e}")

            return {
                "success": True,
                "output_path": str(output_path),
                "glossary_updates": [],
                "errors": [],
                "metrics": {
                    "duration_seconds": duration,
                    "avg_quality_score": avg_score,
                    "total_chunks": len(chunk_metrics),
                    "chunk_metrics": chunk_metrics,
                    "qa_passed": qa_result.get("passed") if qa_result else None,
                    "qa_issues": len(qa_result.get("issues", [])) if qa_result else 0,
                },
                "chapter": Path(filepath).stem,
                "duration_seconds": duration
            }

        except Exception as e:
            self.logger.error(f"Translation failed: {e}", exc_info=True)
            # Finalize progress logger with failure
            if progress_logger:
                try:
                    progress_logger.finalize(success=False)
                except Exception:
                    pass
            return {
                "success": False,
                "output_path": None,
                "glossary_updates": [],
                "errors": [str(e)],
                "metrics": {},
                "chapter": Path(filepath).stem
            }
        finally:
            # Always cleanup to free RAM after translation
            self._cleanup_resources()
            # Clean up stop signal file if it exists
            try:
                stop_flag = Path("logs/translation_stop.flag")
                if stop_flag.exists():
                    stop_flag.unlink(missing_ok=True)
            except Exception:
                pass

    def translate_chapter(self, novel: str, chapter: int) -> Dict[str, Any]:
        """Translate a single chapter of a novel.
        
        Args:
            novel: Novel name
            chapter: Chapter number
            
        Returns:
            Pipeline result dictionary
        """
        chapter_file = self._find_chapter_file(novel, chapter)

        if not chapter_file:
            novel_dir = Path(INPUT_DIR) / novel
            attempted = [
                f"{chapter:03d}.md",
                f"{chapter:04d}.md",
                f"{novel}_chapter_{chapter:03d}.md",
                f"{novel}_{chapter:03d}.md",
                f"{novel}_{chapter:04d}.md",
            ]
            return {
                "success": False,
                "output_path": None,
                "glossary_updates": [],
                "errors": [f"Chapter file not found for chapter {chapter} in {novel_dir}. Tried: {', '.join(attempted)}"],
                "metrics": {},
                "chapter": str(chapter)
            }

        self._current_novel = novel
        return self.translate_file(str(chapter_file), novel_name=novel)

    @staticmethod
    def _extract_novel_from_path(filepath: str) -> Optional[str]:
        """Extract novel name from a filepath like data/input/{novel}/chapter.md."""
        path = Path(filepath)
        try:
            relative = path.relative_to(INPUT_DIR)
            parts = relative.parts
            if len(parts) >= 1:
                return parts[0]  # First component is novel name
        except ValueError:
            pass
        return None

    @staticmethod
    def _discover_chapters(novel_dir: Path) -> List[int]:
        """Discover chapter numbers from files in a novel directory.
        
        Handles multiple naming conventions:
        - {novel}_chapter_001.md, {novel}_0001.md, 001.md, chapter_001.md
        
        Args:
            novel_dir: Novel directory path
            
        Returns:
            Sorted list of unique chapter numbers
        """
        import re

        chapters: set = set()
        for f in novel_dir.glob("*.md"):
            # Try pure-digit stem: "009.md"
            if f.stem.isdigit():
                chapters.add(int(f.stem))
                continue

            # Try patterns like "xxx_chapter_009" or "xxx_0009"
            m = re.search(r'(?:chapter[\s_-]*)?(\d{3,4})$', f.stem)
            if m:
                chapters.add(int(m.group(1)))

        return sorted(chapters)

    @staticmethod
    def _find_chapter_file(novel: str, chapter: int) -> Optional[Path]:
        """Find a chapter file using multiple naming conventions.
        
        Args:
            novel: Novel name
            chapter: Chapter number
            
        Returns:
            Path to chapter file, or None if not found
        """
        novel_dir = Path(INPUT_DIR) / novel
        if not novel_dir.is_dir():
            return None

        patterns = [
            # Format 1: {novel}_chapter_{XXX}.md (e.g., 古道仙鸿_chapter_009.md)
            novel_dir / f"{novel}_chapter_{chapter:03d}.md",
            # Format 2: {chapter}.md (e.g., 009.md)
            novel_dir / f"{chapter:03d}.md",
            novel_dir / f"{chapter:04d}.md",
            # Format 3: {novel}_{chapter}.md (e.g., reverend-insanity_0009.md)
            novel_dir / f"{novel}_{chapter:03d}.md",
            novel_dir / f"{novel}_{chapter:04d}.md",
        ]

        for p in patterns:
            if p.exists():
                return p

        return None

    def translate_novel(self, novel: str, chapters: Optional[List[int]] = None) -> List[Dict[str, Any]]:
        """Translate multiple chapters of a novel.
        
        Args:
            novel: Novel name
            chapters: List of chapter numbers (None for all)
            
        Returns:
            List of pipeline results
        """
        # If no chapters specified, find all available
        if not chapters:
            novel_dir = Path(INPUT_DIR) / novel
            if not novel_dir.exists():
                return [{
                    "success": False,
                    "output_path": None,
                    "glossary_updates": [],
                    "errors": [f"Novel directory not found: {novel_dir}"],
                    "metrics": {},
                    "chapter": "all"
                }]

            chapters = self._discover_chapters(novel_dir)

        results = []
        for chapter in chapters:
            if self._shutdown_requested:
                self.logger.warning("Shutdown requested, stopping translation")
                break

            result = self.translate_chapter(novel, chapter)
            results.append(result)

        return results

    def _preprocess(self, text: str, chapter_label: str = "") -> List[str]:
        """Preprocess text into chunks using token-aware paragraph grouping.
        
        Args:
            text: Input text
            chapter_label: Label for progress display
            
        Returns:
            List of text chunks (complete paragraphs, never split mid-paragraph)
        """
        self.logger.info("Step 1/7: Preprocessing text...")
        t0 = time.time()

        self._report({
            "type": "preprocess_start",
            "char_count": len(text),
            "chapter": chapter_label,
        })

        # Use smart_chunk directly per need_to_fix.md spec
        from src.utils.chunker import smart_chunk, estimate_tokens

        # Strip translator/editor metadata lines BEFORE chunking
        text = self.preprocessor.strip_metadata(text)

        # Clean and normalize
        text = self.preprocessor.clean_markdown(text)

        # Auto-detect optimal chunk size based on model context window
        optimal_size = self._auto_detect_chunk_size(text)

        # Create chunks: paragraph-only, no splitting, overlap=0
        chunks = smart_chunk(text, max_tokens=optimal_size)

        self.logger.info(
            f"Created {len(chunks)} chunks (size={optimal_size} tokens, "
            f"auto-detected from model context window)"
        )
        total_tokens = sum(estimate_tokens(c) for c in chunks)
        self.logger.info(f"Estimated total tokens: {total_tokens}, avg: {total_tokens // max(len(chunks), 1)}")

        self._report({
            "type": "preprocess_done",
            "chunk_count": len(chunks),
            "chunk_size": optimal_size,
            "duration": time.time() - t0,
        })

        return chunks

    def _auto_detect_chunk_size(self, source_text: str = "") -> int:
        """Auto-detect optimal chunk size based on model context window.
        
        Formula:
          optimal = min(
              model_num_ctx * 0.35,     # 35% of model context window
              max_chunk_size,           # config ceiling (default 2000)
              len(source) * 1.5,        # don't chunk if source is tiny
          )
          clamp(optimal, 600, 2000)     # safety bounds
        
        The token budget is:
          system(400) + glossary(300) + context(400) + chunk + output(400) ≤ model_ctx
        So chunk ≤ model_ctx - 1500, but we use 35% for safety margin.
        
        Returns:
            Optimal max_tokens value for smart_chunk()
        """
        config_size = getattr(self.config.processing, 'chunk_size', 1500)

        # Try to get model context window from Ollama
        model_ctx = None
        try:
            client = self.ollama_client
            if hasattr(client, '_client') and client._client:
                # Ollama Python client
                pass
            # Fallback: use config or default
            model_ctx = getattr(self.config.models, 'num_ctx', 4096)
            if not model_ctx:
                model_ctx = 4096
        except Exception:
            model_ctx = 4096

        # Calculate optimal: 35% of context window, capped by config max
        optimal = min(
            int(model_ctx * 0.35),       # e.g., 8192*0.35 = 2867
            min(config_size, 2500),      # never exceed 2500
        )

        # If source text is very short, just use 1 chunk
        if source_text:
            source_tokens = int(len(source_text) * 1.5)
            if source_tokens <= optimal:
                optimal = max(optimal, source_tokens)  # single chunk

        # Safety bounds
        optimal = max(optimal, 600)   # minimum 600 tokens
        optimal = min(optimal, 2500)  # maximum 2500 tokens

        self.logger.debug(
            f"Auto-detected chunk_size={optimal} "
            f"(model_ctx={model_ctx}, config_size={config_size})"
        )
        return optimal

    def _translate_chunks(
        self,
        chunks: List[str],
        progress_logger: Optional[Any] = None
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        """Translate chunks through the pipeline with rolling context.

        Per need_to_fix.md: uses get_rolling_context() to pass tail of
        previous translated chunk as context. Token-limited to ≤400 tokens.
        Checkpoint logged after each chunk.

        Args:
            chunks: List of text chunks (complete paragraphs, never split)
            progress_logger: Optional progress logger for file-based progress tracking

        Returns:
            Tuple of (translated chunks list, list of per-chunk quality metrics)
        """
        from src.utils.chunker import get_rolling_context, estimate_tokens

        translated = []
        chunk_metrics = []
        rolling_context = ""  # first chunk: empty

        for i, chunk in enumerate(chunks):
            if self._shutdown_requested:
                break

            # Check for stop signal from Web UI
            if self._check_stop_signal():
                self._shutdown_requested = True
                self.logger.warning(f"Stopping translation at chunk {i+1}/{len(chunks)} due to stop signal")
                break

            chunk_t0 = time.time()
            total = len(chunks)

            self._report({
                "type": "chunk_start",
                "chunk_index": i + 1,
                "total_chunks": total,
                "char_count": len(chunk),
            })

            # Token budget check before sending (per spec: ≤2600 tokens total)
            est_chunk = estimate_tokens(chunk)
            est_context = estimate_tokens(rolling_context)
            est_total = 800 + est_context + est_chunk  # 400 system + 300 glossary + 100 rules ≈ 800
            if est_total > 2600:
                self.logger.warning(
                    f"Chunk {i+1}: estimated {est_total} tokens exceeds 2600 budget. "
                    f"Rolling context truncated to fit."
                )
                # Reduce rolling context to fit
                if rolling_context:
                    rolling_context = get_rolling_context(rolling_context, max_context_tokens=200)
                    est_context = estimate_tokens(rolling_context)

            self.logger.info(f"Step 2/7: Translating chunk {i+1}/{total}... "
                           f"[{len(chunk)} chars, est {est_chunk} tokens, "
                           f"ctx: {len(rolling_context)} chars]")

            # Stage 1: Translation with rolling context
            t1 = time.time()
            translated_chunk = self.translator.translate_paragraph(
                chunk, rolling_context=rolling_context
            )
            self._report({
                "type": "chunk_translated",
                "chunk_index": i + 1,
                "total_chunks": total,
                "duration": time.time() - t1,
            })

            # Stage 2: Refinement (if enabled and not skipped)
            if self.config.translation_pipeline.mode in ('full', 'lite'):
                self.logger.info(f"Step 3/7: Refining chunk {i+1}/{total}...")
                t2 = time.time()
                translated_chunk = self.refiner.refine_paragraph(translated_chunk)
                self._report({
                    "type": "chunk_refined",
                    "chunk_index": i + 1,
                    "total_chunks": total,
                    "duration": time.time() - t2,
                })

            # Stage 3: Reflection (if enabled)
            if self.config.translation_pipeline.use_reflection:
                self.logger.info(f"Step 4/7: Reflecting on chunk {i+1}/{total}...")
                t3 = time.time()
                translated_chunk = self.reflection_agent.reflect_and_improve(translated_chunk, chunk)
                self._report({
                    "type": "chunk_reflected",
                    "chunk_index": i + 1,
                    "total_chunks": total,
                    "duration": time.time() - t3,
                })

            # Stage 4: Quality Check
            self.logger.info(f"Step 5/7: Checking quality for chunk {i+1}/{total}...")
            quality_result = self.myanmar_checker.check_quality(translated_chunk)
            quality_score = quality_result.get("score", 0)
            quality_passed = quality_result.get("passed", False)
            quality_issues = len(quality_result.get("issues", []))

            # Calculate Myanmar ratio for display
            mm_ratio = self._calc_myanmar_ratio(translated_chunk)

            self._report({
                "type": "chunk_quality",
                "chunk_index": i + 1,
                "total_chunks": total,
                "score": quality_score,
                "passed": quality_passed,
                "issue_count": quality_issues,
                "myanmar_ratio": mm_ratio,
            })

            # Stage 5: Consistency Check
            self.logger.info(f"Step 6/7: Checking consistency for chunk {i+1}/{total}...")
            consistency_issues = self.checker.check_glossary_consistency(translated_chunk)
            cons_count = len(consistency_issues) if consistency_issues else 0
            if cons_count:
                self.logger.warning(f"Found {cons_count} consistency issues")
            self._report({
                "type": "chunk_consistency",
                "chunk_index": i + 1,
                "total_chunks": total,
                "issue_count": cons_count,
            })

            total_issues = quality_issues + cons_count
            chunk_duration = time.time() - chunk_t0
            self._report({
                "type": "chunk_complete",
                "chunk_index": i + 1,
                "total_chunks": total,
                "duration": chunk_duration,
            })

            # Per-chunk timeout guard: if a single chunk exceeds 15 min,
            # log an error and continue to the next chunk. Prevents
            # 4.8-hour sessions from stuck retry loops (e.g., Ch 15).
            if chunk_duration > 900:
                self.logger.error(
                    f"⚠ Chunk {i+1}/{total} exceeded 15-min timeout ({chunk_duration:.0f}s). "
                    f"Translation may be degraded. Skipping to next chunk."
                )
                chunk_metrics.append({
                    "chunk": i + 1,
                    "quality_score": 0,
                    "quality_passed": False,
                    "myanmar_ratio": 0.0,
                    "issues": 99,
                    "timed_out": True,
                })
                translated.append(chunk)  # Keep original untranslated text
                rolling_context = get_rolling_context("", max_context_tokens=400)
                continue

            chunk_metrics.append({
                "chunk": i + 1,
                "quality_score": quality_score,
                "quality_passed": quality_passed,
                "myanmar_ratio": mm_ratio,
                "issues": total_issues,
            })

            translated.append(translated_chunk)

            # Checkpoint: log progress after each chunk (resumability)
            self.logger.info(
                f"✓ Chunk {i+1}/{total} complete in {chunk_duration:.0f}s. "
                f"Quality: {quality_score}, Ratio: {mm_ratio:.1%}, Issues: {total_issues}"
            )

            # Auto-update paragraph buffer for context memory
            if self._memory_manager:
                try:
                    self._memory_manager.push_to_buffer(translated_chunk)
                except Exception as e:
                    self.logger.debug(f"Buffer push failed (non-fatal): {e}")

            # Advance rolling context: tail of this chunk for next iteration
            rolling_context = get_rolling_context(translated_chunk, max_context_tokens=400)

        return translated, chunk_metrics

    @staticmethod
    def _calc_myanmar_ratio(text: str) -> float:
        """Calculate ratio of Myanmar Unicode characters in text.

        Args:
            text: Text to analyze

        Returns:
            Ratio 0.0–1.0
        """
        if not text:
            return 0.0
        myanmar_ranges = [(0x1000, 0x109F), (0xAA60, 0xAA7F), (0xA9E0, 0xA9FF)]
        mm = 0
        total = 0
        for ch in text:
            code = ord(ch)
            if not ch.isspace():
                total += 1
                if any(lo <= code <= hi for lo, hi in myanmar_ranges):
                    mm += 1
        return mm / total if total > 0 else 0.0

    def _postprocess(self, chunks: List[str]) -> str:
        """Postprocess translated chunks.
        
        Args:
            chunks: List of translated chunks
            
        Returns:
            Final translated text
        """
        from src.utils.postprocessor import Postprocessor

        # Use aggressive mode to strip all reasoning/analysis content
        processor = Postprocessor(aggressive=True)

        # Deduplicate overlapping paragraphs between adjacent chunks
        before_count = sum(len(c) for c in chunks)
        chunks = self._deduplicate_chunks(chunks)
        after_count = sum(len(c) for c in chunks)

        # Join chunks
        text = '\n\n'.join(chunks)

        # Clean up
        text = processor.clean(text)

        self._report({
            "type": "postprocess",
            "dedup_removed": max(0, before_count - after_count),
            "final_chars": len(text),
        })

        return text

    def _deduplicate_chunks(self, chunks: List[str]) -> List[str]:
        """Remove duplicated overlapping paragraphs between adjacent chunks.
        
        The chunking algorithm may use overlap to preserve context. This function
        detects and removes paragraphs from chunk N+1 that already appeared at the
        end of chunk N, preventing duplicated content in the final output.
        
        Uses a high-similarity threshold (>0.90) and minimum-length checks to
        avoid false positives on short Myanmar paragraphs.
        
        Args:
            chunks: List of translated chunk texts
            
        Returns:
            Deduplicated chunk texts
        """
        if len(chunks) <= 1:
            return chunks

        def split_paragraphs(text: str) -> List[str]:
            """Split text into paragraphs."""
            return [p.strip() for p in text.split('\n\n') if p.strip()]

        def chars_overlap_ratio(p1: str, p2: str) -> float:
            """Compute sequence similarity between two strings.
            Uses SequenceMatcher to avoid false positives from Myanmar
            sentences that share common particles/characters."""
            from difflib import SequenceMatcher
            if not p1 or not p2:
                return 0.0
            return SequenceMatcher(None, p1, p2).ratio()

        result = [chunks[0]]

        for i in range(1, len(chunks)):
            prev_paras = split_paragraphs(result[-1])
            curr_paras = split_paragraphs(chunks[i])

            if not prev_paras or not curr_paras:
                result.append(chunks[i])
                continue

            # Only check the last paragraph of prev vs first paragraph of curr
            # to find overlap at chunk boundary
            remove_from_curr = 0
            last_prev = prev_paras[-1]
            first_curr = curr_paras[0]

            # Only attempt deduplication on paragraphs with substantial content (>50 chars)
            # to avoid false positives on short, similar-looking Myanmar sentences
            if len(last_prev) > 50 and len(first_curr) > 50:
                if chars_overlap_ratio(last_prev, first_curr) > 0.90:
                    remove_from_curr = 1
                    # Check if more consecutive boundary paragraphs match
                    for k in range(2, min(len(prev_paras), len(curr_paras)) + 1):
                        p = prev_paras[-k]
                        c = curr_paras[k-1]
                        if len(p) > 50 and len(c) > 50 and chars_overlap_ratio(p, c) > 0.90:
                            remove_from_curr = k
                        else:
                            break

            if remove_from_curr > 0:
                deduped = '\n\n'.join(curr_paras[remove_from_curr:])
                if deduped.strip():
                    result.append(deduped)
            else:
                result.append(chunks[i])

        return result

    def _save_output(self, input_path: str, text: str, extra_meta: Optional[Dict[str, Any]] = None) -> Path:
        """Save translated output and update per-novel cumulative meta.json.
        
        Args:
            input_path: Original input file path
            text: Translated text
            extra_meta: Additional metadata to save
            
        Returns:
            Path to output file
        """
        input_path = Path(input_path)

        # Determine output path
        relative = input_path.relative_to(INPUT_DIR) if str(input_path).startswith(INPUT_DIR) else input_path.name
        output_path = Path(OUTPUT_DIR) / relative
        output_path = output_path.with_suffix('.mm.md')

        # Ensure directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Extract chapter number from filename
        import re
        chapter_num = None
        m = re.search(r'(\d+)', output_path.stem)
        if m:
            chapter_num = int(m.group(1))

        # --- Write chapter .mm.md file ---
        from src.utils.file_handler import FileHandler
        FileHandler.write_text(str(output_path), text)

        # --- Create version snapshot (if SQL backend) ---
        if self.config.storage.backend == "sqlite" and self.version_manager and chapter_num:
            try:
                self.version_manager.snapshot_chapter(
                    novel_name=self._current_novel or "unknown",
                    chapter_num=chapter_num,
                    reason="translation_complete",
                    source="pipeline",
                )
            except Exception as e:
                self.logger.warning(f"Version snapshot failed: {e}")

        # --- Update cumulative per-novel meta.json ---
        # Single file: data/output/{novel}/{novel}.mm.meta.json
        # Updated cumulatively with each chapter translation
        if self._current_novel:
            novel_meta_path = output_path.parent / f"{self._current_novel}.mm.meta.json"

            # Load existing meta if it exists
            existing_meta = {}
            if novel_meta_path.exists():
                try:
                    existing_meta = json.loads(FileHandler.read_text(str(novel_meta_path)))
                except Exception:
                    existing_meta = {}

            # Build chapter entry
            chapter_entry = {
                "chapter": chapter_num,
                "translated_at": datetime.now().isoformat(),
                "source": str(input_path),
                "pipeline": self.config.translation_pipeline.mode,
                "model": self.config.models.translator,
                "char_count": len(text) if text else 0,
                "myanmar_ratio": round(
                    self._calc_myanmar_ratio(text), 3
                ) if text else 0.0,
            }
            if extra_meta:
                chapter_entry.update({k: v for k, v in extra_meta.items() if v is not None})

            # Update cumulative meta
            chapters_meta = existing_meta.get("chapters", {})
            chapters_meta[str(chapter_num)] = chapter_entry
            existing_meta["novel"] = self._current_novel
            existing_meta["last_updated"] = datetime.now().isoformat()
            existing_meta["total_chapters"] = len(chapters_meta)
            existing_meta["chapters"] = chapters_meta

            try:
                meta_content = json.dumps(existing_meta, indent=2, ensure_ascii=False)
                FileHandler.write_text(str(novel_meta_path), meta_content)
                self.logger.info(f"Updated meta: {novel_meta_path.name} (chapters: {len(chapters_meta)})")
            except Exception as e:
                self.logger.warning(f"Failed to write meta: {e}")

        # REMOVED: Per-chapter meta.json is no longer created
        # All metadata is stored in cumulative {novel}.mm.meta.json
        # translation_reviewer.py now reads from cumulative file

        self.logger.info(f"Step 7/7: Saved output to {output_path}")

        return output_path

    def _auto_review(self, output_path: str, translated_text: str = "") -> None:
        """Run automatic quality review on the translated output file.

        Generates a report in logs/report/ that can be read by an AI agent
        to determine what needs to be fixed or improved.

        Args:
            output_path: Path to the saved .mm.md file
            translated_text: The translated text (avoid re-reading file)
        """
        try:
            from src.utils.translation_reviewer import review_and_report

            report, report_path = review_and_report(
                output_path,
                novel=self._current_novel,
            )

            self.logger.info(
                f"Auto-review: score={report.total_score}/100, "
                f"passed={len(report.passed_checks)}, "
                f"warnings={len(report.warnings)}, "
                f"critical={len(report.critical_fixes)}"
            )
            self.logger.info(f"Review report saved: {report_path}")

            self._report({
                "type": "review_complete",
                "score": report.total_score,
                "passed": len(report.passed_checks),
                "warnings": len(report.warnings),
                "critical": len(report.critical_fixes),
                "report_path": str(report_path),
            })
        except ImportError as e:
            self.logger.debug(f"Review module not available: {e}")
        except Exception as e:
            self.logger.error(f"Auto-review failed: {e}")

    def _cleanup_resources(self) -> None:
        """Internal method to clean up resources and free RAM after translation."""
        self.logger.info("Cleaning up resources and freeing RAM...")

        # Unload all models from Ollama to free RAM
        clients_to_cleanup = [
            self._ollama_client_translator,
            self._ollama_client_refiner,
            self._ollama_client_checker,
        ]
        for client in clients_to_cleanup:
            if client:
                try:
                    self.logger.info(f"Unloading model {client.model} from Ollama...")
                    client.unload_all_models()
                    client.cleanup()
                    self.logger.info(f"Model {client.model} unloaded successfully")
                except Exception as e:
                    self.logger.error(f"Error cleaning up Ollama client: {e}")

        # Save memory manager state and close database connection
        if self._memory_manager:
            try:
                self._memory_manager.save_memory()
                self.logger.info("Memory saved successfully")
            except Exception as e:
                self.logger.error(f"Error saving memory: {e}")
            
            # Close database connection to prevent locking issues
            try:
                self._memory_manager.close()
                self.logger.info("Database connection closed")
            except Exception as e:
                self.logger.error(f"Error closing database connection: {e}")

    def cleanup(self) -> None:
        """Public cleanup method for manual resource cleanup."""
        self._cleanup_resources()
