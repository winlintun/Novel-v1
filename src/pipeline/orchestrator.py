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
import re
import sys
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
        self._fiction_editor = None
        self._myanmar_syntax_editor = None
        self._myanmar_checker = None
        self._checker = None
        self._qa_tester = None
        self._context_updater = None
        self._memory_manager = None
        
        # Separate Ollama clients for each role (to support different models)
        self._ollama_client_translator = None
        self._ollama_client_refiner = None
        self._ollama_client_checker = None

        # RAG components
        self._rag_retriever = None
        self._feedback_loop = None

        # State
        self._shutdown_requested = False
        self._current_novel: Optional[str] = None
        self._progress_callback: Optional[Callable] = None
        self._version_manager = None

        # Register signal handlers (SIGTERM not available on Windows)
        signal.signal(signal.SIGINT, self._signal_handler)
        if hasattr(signal, 'SIGTERM'):
            try:
                signal.signal(signal.SIGTERM, self._signal_handler)
            except (ValueError, OSError):
                pass

    def _signal_handler(self, signum: int, frame: Any) -> None:
        """Handle shutdown signals gracefully."""
        self.logger.warning("Shutdown requested. Stopping translation and unloading models...")
        self._shutdown_requested = True
        raise KeyboardInterrupt()

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
            from src.utils.file_handler import FileHandler
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
                FileHandler.write_json(str(progress_file), pdata)
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
            from src.utils.file_handler import FileHandler

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
            refiner_model = getattr(self.config.models, 'refiner', None) or \
                            getattr(self.config.models, 'editor', None) or 'N/A'
            
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
                f"Refiner Model: {refiner_model}",
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
            FileHandler.write_text(str(report_file), '\n'.join(report_lines))
            
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

    # Models that corrupt Myanmar output above a hard temperature ceiling.
    # See CLAUDE.md / AGENTS.md: "padauk-gemma:q8_0 temperature MUST be ≤ 0.2".
    _MODEL_MAX_TEMPERATURE = {"padauk-gemma": 0.2}

    def _effective_temperature(self, model: str) -> float:
        """Resolve sampling temperature, auto-selecting model-specific values.

        Priority:
        1. Model-specific config section (e.g. settings.yaml models.padauk_gemma.temperature)
        2. Shared processing.temperature default
        3. Per-model hard ceiling (clamp down if exceeded)
        """
        # Step 1: try to find a model-specific config section
        model_lower = (model or "").lower()
        model_sections = []
        try:
            models_cfg = self.config.models
            for attr in dir(models_cfg):
                if attr.startswith('_'):
                    continue
                val = getattr(models_cfg, attr)
                if isinstance(val, dict) and 'name' in val:
                    model_sections.append(val)
        except Exception:
            pass

        section_temp = None
        for section in model_sections:
            if section.get('name', '').lower() == model_lower:
                section_temp = section.get('temperature')
                if section_temp is not None:
                    break

        # Step 2: resolve base temperature
        if section_temp is not None:
            temp = float(section_temp)
        else:
            temp = float(getattr(self.config.processing, 'temperature', 0.3))

        # Step 3: enforce per-model hard ceiling
        for prefix, ceiling in self._MODEL_MAX_TEMPERATURE.items():
            if prefix in model_lower and temp > ceiling:
                self.logger.warning(
                    "Clamping temperature %.2f -> %.2f for model '%s' "
                    "(hard ceiling; higher values corrupt Myanmar output).",
                    temp, ceiling, model,
                )
                return ceiling
        return temp

    def _create_ollama_client(self, model: str) -> Any:
        """Create an OllamaClient with the specified model."""
        from src.utils.ollama_client import OllamaClient
        return OllamaClient(
            model=model,
            base_url=self.config.models.ollama_base_url,
            timeout=self.config.models.timeout,
            temperature=self._effective_temperature(model),
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
                config=self.config.dict(),
                rag_retriever=self.rag_retriever,
            )
        return self._translator

    @property
    def rag_retriever(self):
        """Lazy load RAG retriever."""
        if self._rag_retriever is None:
            rag_config = self.config.dict().get('rag', {})
            if rag_config.get('enabled', False):
                from src.data.rag_retriever import RAGRetriever
                chroma_path = rag_config.get('chroma_path', 'data/chroma_db')
                db_path = rag_config.get('db_path', 'data/alignment.db')
                # Note: RAGRetriever.__init__ only accepts chroma_path, db_path,
                # top_k, min_score, novel_filter — jsonl_path/min_similarity/
                # min_quality_tier are NOT valid params (caused TypeError).
                self._rag_retriever = RAGRetriever(
                    chroma_path=chroma_path,
                    db_path=db_path,
                    top_k=rag_config.get('top_k', 3),
                    min_score=rag_config.get('min_score', 2.5),
                    # RAG few-shot examples come from the cross-novel training
                    # corpus (e.g. a-will-eternal), which never contains the
                    # in-progress novel. Forcing novel_filter=current_novel would
                    # match zero rows and silently disable retrieval, so respect
                    # the configured filter (null = search the whole corpus).
                    novel_filter=rag_config.get('novel_filter'),
                    embedding_model=rag_config.get('embedding_model', 'models/bge-m3'),
                    embedding_device=rag_config.get('embedding_device', 'cpu'),
                    min_similarity=rag_config.get('min_similarity', 0.3),
                    collection_name=rag_config.get('collection', 'alignment_pairs'),
                )
                self.logger.info(f"RAG Retriever initialized: chroma={chroma_path}, db={db_path}")

                # Check if RAG has any usable data — warn if both backends are empty
                rag = self._rag_retriever
                chroma_ok = (
                    rag._chroma_collection is not None
                    and rag._chroma_collection.count() > 0
                )
                sqlite_ok = rag._sqlite_conn is not None
                if sqlite_ok:
                    try:
                        cnt = rag._sqlite_conn.execute(
                            "SELECT COUNT(*) FROM translation_pairs"
                        ).fetchone()[0]
                        sqlite_ok = cnt > 0
                    except Exception:
                        sqlite_ok = False

                if not chroma_ok and not sqlite_ok:
                    self.logger.warning("=" * 60)
                    self.logger.warning("⚠ RAG SYSTEM: No data available in ChromaDB or SQLite.")
                    self.logger.warning("Translation will proceed without few-shot example injection.")
                    self.logger.warning(f"  ChromaDB: {chroma_path}")
                    self.logger.warning(f"  SQLite:   {db_path}")
                    self.logger.warning("=" * 60)
            else:
                self._rag_retriever = None
        return self._rag_retriever

    @property
    def feedback_loop(self):
        """Lazy load feedback loop."""
        if self._feedback_loop is None:
            rag_config = self.config.dict().get('rag', {})
            if rag_config.get('enabled', False):
                from src.data.feedback_loop import FeedbackLoop
                self._feedback_loop = FeedbackLoop(
                    db_path=rag_config.get('feedback_db', 'data/novel_v1_dataset.db'),
                    chroma_path=rag_config.get('feedback_chroma', 'data/chroma_db'),
                    min_score=rag_config.get('feedback_min_score', 3.0),
                    min_myanmar_ratio=rag_config.get('feedback_min_myanmar_ratio', 0.70),
                )
                self.logger.info(f"Feedback Loop initialized: {rag_config.get('feedback_db')}")
            else:
                self._feedback_loop = None
        return self._feedback_loop

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
    def fiction_editor(self):
        """Lazy load fiction editor for literary humanization."""
        if self._fiction_editor is None:
            from src.agents.fiction_editor import FictionEditor
            self._fiction_editor = FictionEditor(
                model=getattr(self.config.models, 'editor', None) or self.config.models.translator,
                config=self.config.dict(),
            )
        return self._fiction_editor

    @property
    def myanmar_syntax_editor(self):
        """Lazy load Myanmar syntax editor (mig-burmese-llm HF model)."""
        if self._myanmar_syntax_editor is None:
            from src.agents.myanmar_syntax_editor import MyanmarSyntaxEditor
            pipeline = self.config.translation_pipeline
            self._myanmar_syntax_editor = MyanmarSyntaxEditor(
                model_path=pipeline.syntax_editor_model,
                device=pipeline.syntax_editor_device,
            )
            self.logger.info("MyanmarSyntaxEditor initialized (HF model)")
        return self._myanmar_syntax_editor

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
                config=self.config.dict(),
                ollama_client=self.ollama_client_checker,
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
        pipeline_mode = getattr(self.config.translation_pipeline, 'mode', 'unknown')
        translator_model = self.config.models.translator
        refiner_model = getattr(self.config.models, 'refiner', None) or \
                        getattr(self.config.models, 'editor', None) or 'N/A'
        checker_model = getattr(self.config.models, 'checker', None) or 'N/A'
        self.logger.info(
            f"Pipeline: {pipeline_mode} | "
            f"Translator: {translator_model} | "
            f"Refiner: {refiner_model} | "
            f"Checker: {checker_model}"
        )
        start_time = time.time()

        # Resolve novel name from filepath if not provided
        if novel_name:
            self._current_novel = novel_name
        else:
            self._current_novel = self._extract_novel_from_path(filepath)

        # Store filepath for use by sibling methods (_translate_chunks, feedback loop)
        self._current_filepath = filepath

        # Bind BEFORE the try: both except handlers reference progress_logger, so if
        # an early step inside the try (e.g. FileHandler.read_text) raises, the
        # handler must not hit UnboundLocalError and mask the real error.
        progress_logger = None

        try:
            # Clear session rules from previous chapter
            try:
                if self._memory_manager:
                    self._memory_manager.clear_session_rules()
            except Exception:
                pass

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
            self._current_chapter = chapter_num

            # Preprocess
            chunks = self._preprocess(text, chapter_label)

            # Initialize progress logger for real-time tracking
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

            # ── Partial completion guard ────────────────────────────────────
            # If timeout or shutdown stopped the pipeline before all chunks
            # were translated, do NOT save partial output. The user must
            # re-run and resume from checkpoints.
            # Count actually-translated chunks: a resume can leave None holes in
            # the list (non-contiguous / rejected checkpoints). Those holes mean
            # the chunk was NOT translated, even though list length may match — so
            # gate on non-None content, never on len() alone (which let a None
            # slip into _postprocess and crash on len(None)).
            completed = sum(1 for c in translated_chunks if c is not None)
            if completed < len(chunks):
                self.logger.error(
                    f"Partial completion: {completed}/{len(chunks)} chunks "
                    f"translated. File NOT saved. Checkpoints available for resumption."
                )
                return {
                    "success": False,
                    "output_path": None,
                    "glossary_updates": [],
                    "errors": [
                        f"Partial completion: {completed}/{len(chunks)} chunks done"
                    ],
                    "metrics": {
                        "partial": True,
                        "completed": completed,
                        "total": len(chunks),
                    },
                    "chapter": Path(filepath).stem,
                }

            # Postprocess
            result_text = self._postprocess(translated_chunks)

            # Deterministic glossary enforcement — replace any source term that
            # leaked verbatim into the Myanmar output with its approved target.
            # Safe (Latin-script leakage only) and independent of model compliance.
            try:
                from src.utils.glossary_enforcer import enforce_glossary, enforce_variants
                terms = self.memory_manager.get_all_terms()
                result_text, n_enforced = enforce_glossary(result_text, text, terms)
                if n_enforced:
                    self.logger.info(
                        f"Glossary enforcement: replaced {n_enforced} leaked "
                        f"source-term occurrence(s) with canonical target(s)"
                    )
                # Normalise known Myanmar variant spellings to canonical (e.g.
                # ပိုင်ရှောင်ချီ → ပိုင်ရှောင်ချန်း) so names are identical everywhere.
                variants = self.memory_manager.get_variant_map()
                result_text, n_var = enforce_variants(result_text, variants)
                if n_var:
                    self.logger.info(
                        f"Variant normalisation: snapped {n_var} variant spelling(s) "
                        f"to canonical glossary target(s)"
                    )
            except Exception as e:
                self.logger.warning(f"Glossary enforcement skipped (non-fatal): {e}")

            # Stage 6: QA Validation — final quality gate on assembled chapter
            # Runs after postprocessing so it checks the full, clean output
            qa_result = None
            try:
                if self.config.translation_pipeline.mode in ('full', 'lite', 'two_stage'):
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

            # ── QA result gate ─────────────────────────────────────────────────
            # If QA validation reports non-ratio failures (e.g., content loss,
            # chapter title mismatch, markdown issues), block save with feedback.
            if qa_result and not qa_result.get("passed"):
                non_ratio_issues = [
                    i for i in qa_result.get("issues", [])
                    if not i.lower().startswith("myanmar ratio")
                ]
                if non_ratio_issues:
                    self.logger.error(
                        f"QA gate FAILED: {len(non_ratio_issues)} structural issue(s) found. "
                        f"File NOT saved: {non_ratio_issues[:3]}"
                    )
                    return {
                        "success": False,
                        "output_path": None,
                        "glossary_updates": [],
                        "errors": [
                            f"QA gate: {len(non_ratio_issues)} issue(s) — {non_ratio_issues[0]}"
                        ],
                        "metrics": {"qa_issues": non_ratio_issues},
                        "chapter": Path(filepath).stem,
                    }

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
            }, source_text=text)

            # Auto-review: generate quality report after saving
            try:
                self._auto_review(str(output_path), result_text, source_text=text)
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

            # Log term usage: track which glossary terms appeared in this chapter
            try:
                if self.memory_manager and result_text:
                    usage_logged = self.memory_manager.log_term_usage_for_chapter(
                        chapter_num=chapter_num or 0,
                        translated_text=result_text
                    )
                    if usage_logged > 0:
                        self.logger.debug(f"Term usage logged: {usage_logged} terms used in chapter {chapter_num or 0}")
            except Exception as e:
                self.logger.warning(f"Term usage logging failed (non-fatal): {e}")

            # Update context memory with chapter data — ensures context flows forward
            # to the next chapter translation (active characters, events, summary)
            try:
                if self.memory_manager and chapter_num:
                    self.memory_manager.update_chapter_context(
                        chapter_num=chapter_num,
                        translated_text=result_text,
                        source_text=text,
                    )
                    self.logger.info(
                        f"Context memory updated for chapter {chapter_num}: "
                        f"characters/events/summary saved for next chapter"
                    )
                elif not chapter_num:
                    self.logger.warning("Context update skipped: chapter_num is 0 or None")
            except Exception as e:
                self.logger.warning(f"Context memory update failed for chapter {chapter_num}: {e}")

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

            # Log to model registry
            try:
                from src.utils.model_registry import log_run
                overall_mm = self._calc_myanmar_ratio(result_text)
                log_run(
                    model_name=self.config.models.translator,
                    novel=self._current_novel or "unknown",
                    chapter=chapter_num or 0,
                    avg_quality_score=avg_score,
                    avg_myanmar_ratio=overall_mm,
                    total_chunks=len(chunk_metrics),
                    pipeline_mode=getattr(self.config.translation_pipeline, 'mode', 'unknown'),
                    duration_seconds=duration,
                    chunk_metrics=chunk_metrics,
                )
            except Exception as e:
                self.logger.debug(f"Model registry update failed (non-fatal): {e}")

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

        except KeyboardInterrupt:
            duration = time.time() - start_time
            self.logger.warning(f"Translation interrupted by user after {duration:.0f}s. Cleaning up and unloading models...")
            if progress_logger:
                try:
                    progress_logger.finalize(success=False)
                except Exception:
                    pass
            return {
                "success": False,
                "output_path": None,
                "glossary_updates": [],
                "errors": ["Translation interrupted by user"],
                "metrics": {},
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
        
        Also checks the en/ subdirectory (data/input/{novel}/en/).
        
        Args:
            novel_dir: Novel directory path
            
        Returns:
            Sorted list of unique chapter numbers
        """
        import re

        chapters: set = set()
        search_dirs = [novel_dir]
        en_dir = novel_dir / "en"
        if en_dir.is_dir():
            search_dirs.append(en_dir)

        for d in search_dirs:
            for f in d.glob("*.md"):
                if f.stem.isdigit():
                    chapters.add(int(f.stem))
                    continue
                m = re.search(r'(?:chapter[\s_-]*)?(\d{3,4})$', f.stem)
                if m:
                    chapters.add(int(m.group(1)))

        return sorted(chapters)

    @staticmethod
    def _find_chapter_file(novel: str, chapter: int, target_dir: Optional[str] = None) -> Optional[Path]:
        """Find a chapter file using multiple naming conventions.
        
        Args:
            novel: Novel name
            chapter: Chapter number
            target_dir: If set, only search this subdirectory (e.g. "en" or "mm").
                        If None, search en/ → mm/ → novel root.
            
        Returns:
            Path to chapter file, or None if not found
        """
        base_dir = Path(INPUT_DIR) / novel
        if not base_dir.is_dir():
            # Check common typo: data/intput/ instead of data/input/
            typo_dir = Path("data/intput") / novel
            if typo_dir.is_dir():
                base_dir = typo_dir
            else:
                return None

        if target_dir:
            search_dirs = [base_dir / target_dir]
        else:
            # Check en/ subdirectory first, then mm/, then novel root
            search_dirs = [base_dir / "en", base_dir / "mm", base_dir]

        for novel_dir in search_dirs:
            if not novel_dir.is_dir():
                continue
            patterns = [
                novel_dir / f"{novel}_chapter_{chapter:04d}.md",
                novel_dir / f"{novel}_chapter_{chapter:03d}.md",
                novel_dir / f"{chapter:03d}.md",
                novel_dir / f"{chapter:04d}.md",
                novel_dir / f"{novel}_{chapter:03d}.md",
                novel_dir / f"{novel}_{chapter:04d}.md",
            ]
            for p in patterns:
                if p.exists():
                    return p

            # Fallback: glob for any file containing "chapter_{chapter}" 
            # (handles mismatched novel name prefix, e.g. dir=a-will-eternal1 but file=a-will-eternal_chapter_001.md)
            for padded in (f"{chapter:04d}", f"{chapter:03d}", f"{chapter}"):
                matches = sorted(novel_dir.glob(f"*chapter_{padded}.md"))
                if matches:
                    return matches[0]

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

            # Check en/ subdirectory first (preferred layout)
            en_dir = novel_dir / "en"
            if en_dir.is_dir():
                novel_dir = en_dir

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
          1. Query Ollama /api/show for model's num_ctx (fallback to config default)
          2. optimal = model_num_ctx * 0.35 (35% of model context window)
          3. Cap by config max (chunk_size or 2500)
          4. If source is short enough for single chunk: optimal = source_tokens
          5. Clamp: max(600, min(optimal, 2500))

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
            if hasattr(client, 'get_model_info'):
                info = client.get_model_info()
                if info and 'num_ctx' in info:
                    model_ctx = info['num_ctx']
                    self.logger.debug(f"Queried Ollama model info: num_ctx={model_ctx}")
            if not model_ctx:
                # Fallback: use config or default
                model_ctx = getattr(self.config.models, 'num_ctx', 4096)
                if not model_ctx:
                    model_ctx = 4096
        except Exception as e:
            self.logger.debug(f"Failed to query Ollama model info: {e}. Using config default.")
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
                optimal = source_tokens  # single chunk: exact fit

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
        consecutive_failures = 0
        quality_window: list[float] = []

        # Clean up old-format flat checkpoints (pre-per-chapter directory format)
        if self._current_novel:
            old_dir = Path("data/working") / self._current_novel
            if old_dir.exists():
                for old_cp in old_dir.glob("ch*_checkpoint.txt"):
                    try:
                        old_cp.unlink(missing_ok=True)
                    except OSError:
                        pass
                try:
                    old_dir.rmdir()
                except OSError:
                    pass

        # Try to resume from checkpoints (2.1: chunk-level resume)
        last_completed = -1
        if self._current_novel and self._current_chapter is not None:
            checkpoint_dir = Path("data/working") / self._current_novel / f"chapter_{self._current_chapter:04d}"
            if checkpoint_dir.exists():
                existing = sorted(checkpoint_dir.glob("ch*_checkpoint.txt"))
                valid_checkpoints = []
                for cp in existing:
                    m = re.match(r'ch(\d+)_checkpoint\.txt', cp.name)
                    if m:
                        idx = int(m.group(1)) - 1
                        if 0 <= idx < len(chunks):
                            valid_checkpoints.append((idx, cp))
                if valid_checkpoints:
                    resume = True  # default: auto-resume in non-interactive mode
                    if sys.stdin.isatty():
                        try:
                            answer = input(
                                f"\nCheckpoints found for chapter {self._current_chapter} "
                                f"({len(valid_checkpoints)}/{len(chunks)} chunks done). "
                                f"Resume? [Y/n]: "
                            ).strip().lower()
                            resume = answer in ("", "y", "yes")
                        except (EOFError, OSError):
                            self.logger.info("Non-interactive input — auto-resuming")
                            resume = True
                    else:
                        self.logger.info(
                            f"Checkpoints found for chapter {self._current_chapter} "
                            f"({len(valid_checkpoints)}/{len(chunks)} chunks done). Auto-resuming."
                        )
                    if resume:
                        for idx, cp in valid_checkpoints:
                            try:
                                text = cp.read_text(encoding="utf-8")
                            except OSError:
                                self.logger.warning(f"Corrupted checkpoint {cp.name}, skipping")
                                continue
                            while len(translated) <= idx:
                                translated.append(None)
                            # Validate resumed checkpoint — reject stale (English/non-Myanmar) content
                            from src.utils.postprocessor import myanmar_char_ratio
                            mm_ratio = myanmar_char_ratio(text)
                            if mm_ratio < 0.70:
                                self.logger.warning(
                                    f"Rejecting stale checkpoint for chunk {idx+1}: "
                                    f"{mm_ratio:.1%} Myanmar ratio. Re-translating."
                                )
                                translated[idx] = None
                                cp.unlink(missing_ok=True)
                                continue
                            translated[idx] = text
                            last_completed = idx
                            self.logger.info(f"Resumed checkpoint: chunk {idx+1}/{len(chunks)} ({mm_ratio:.0%} Myanmar)")
                    else:
                        self.logger.info("User opted to start fresh — deleting checkpoints")
                        for _, cp in valid_checkpoints:
                            cp.unlink(missing_ok=True)
                        # Remove empty directory
                        try:
                            checkpoint_dir.rmdir()
                        except OSError:
                            pass

                # Build rolling context from last completed chunk
                if last_completed >= 0 and translated[last_completed]:
                    rolling_context = get_rolling_context(translated[last_completed], max_context_tokens=400)

        for i, chunk in enumerate(chunks):
            # Skip already-checkpointed chunks
            if i <= last_completed:
                if i < len(translated) and translated[i] is not None:
                    continue
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

            translator_model = self.config.models.translator
            self.logger.info(f"Step 2/7: Translating chunk {i+1}/{total}... "
                           f"[model={translator_model}, {len(chunk)} chars, "
                           f"est {est_chunk} tokens, ctx: {len(rolling_context)} chars]")

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
            if self.config.translation_pipeline.mode in ('full', 'lite', 'two_stage'):
                self.logger.info(f"Step 3/7: Refining chunk {i+1}/{total}...")
                refiner_model = getattr(self.config.models, 'refiner', None) or \
                                getattr(self.config.models, 'editor', None) or \
                                self.config.models.translator
                self.logger.info(f"  Refiner model: {refiner_model}")
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

            # Stage 4: Quality Check (includes paragraph coverage when source is available)
            self.logger.info(f"Step 5/7: Checking quality for chunk {i+1}/{total}...")
            quality_result = self.myanmar_checker.check_quality(translated_chunk, source_text=chunk)
            quality_score = quality_result.get("score", 0)
            quality_passed = quality_result.get("passed", False)
            quality_issues = len(quality_result.get("issues", []))

            # Calculate Myanmar ratio for display
            mm_ratio = self._calc_myanmar_ratio(translated_chunk)

            # CRITICAL: Zero Myanmar ratio = model not outputting Myanmar at all
            # Abort immediately to save API costs on remaining chunks
            if mm_ratio < 0.01:
                self.logger.critical(
                    f"CRITICAL: Chunk {i+1}/{total} has 0% Myanmar ratio. "
                    f"Model is not outputting Myanmar. Aborting pipeline."
                )
                chunk_metrics.append({
                    "chunk": i + 1,
                    "quality_score": quality_score,
                    "quality_passed": quality_passed,
                    "myanmar_ratio": mm_ratio,
                    "issues": quality_issues + 1,
                    "zero_myanmar_abort": True,
                })
                self._shutdown_requested = True
                break

            self._report({
                "type": "chunk_quality",
                "chunk_index": i + 1,
                "total_chunks": total,
                "score": quality_score,
                "passed": quality_passed,
                "issue_count": quality_issues,
                "myanmar_ratio": mm_ratio,
            })

            # Adaptive feedback: inject correction rules from low-scoring chunks
            if quality_score < 80 and quality_issues > 0 and self._memory_manager:
                rules_added = 0
                for issue in quality_result.get("issues", []):
                    if "Archaic" in issue or "archaic" in issue:
                        self._memory_manager.add_session_rule(
                            "avoid_archaic",
                            "Use modern Myanmar words. Avoid archaic terms like သင်သည်/ဤ/ထို. Use မင်း/ဒီ/အဲဒီ instead."
                        )
                        rules_added += 1
                    elif "Repeated" in issue or "repetition" in issue.lower():
                        self._memory_manager.add_session_rule(
                            "avoid_repetition",
                            "Vary word choice in this chunk. Do not repeat the same word 3+ times in close succession."
                        )
                        rules_added += 1
                    elif "particle" in issue.lower():
                        self._memory_manager.add_session_rule(
                            "diversify_particles",
                            "Use diverse Myanmar particles. Avoid overusing သည်/ကို/မှာ in the same paragraph."
                        )
                        rules_added += 1
                    elif "flow" in issue.lower() or "sentence" in issue.lower():
                        self._memory_manager.add_session_rule(
                            "improve_flow",
                            "Vary sentence structure. Mix short and long sentences for better narrative flow."
                        )
                        rules_added += 1
                if rules_added:
                    self.logger.info(
                        f"Adaptive feedback: {rules_added} correction rule(s) added "
                        f"from chunk {i+1} quality issues (score={quality_score})"
                    )

            # Save rejected chunks for future training data
            is_rejected = quality_score < 70 or mm_ratio < 0.7
            if is_rejected:
                consecutive_failures += 1
                try:
                    from src.utils.file_handler import FileHandler
                    safe_novel = re.sub(r'[^a-zA-Z0-9_-]', '_', self._current_novel or "unknown")
                    rejected_dir = Path("data/training/rejected") / safe_novel
                    rejected_dir.mkdir(parents=True, exist_ok=True)
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    FileHandler.write_text(
                        str(rejected_dir / f"chunk_{i+1:03d}_{ts}_source.txt"), chunk
                    )
                    FileHandler.write_text(
                        str(rejected_dir / f"chunk_{i+1:03d}_{ts}_output.txt"), translated_chunk
                    )
                    FileHandler.write_text(
                        str(rejected_dir / f"chunk_{i+1:03d}_{ts}_reason.txt"),
                        f"quality={quality_score}\nmm_ratio={mm_ratio:.2f}"
                    )
                    self.logger.info(
                        f"Rejected chunk {i+1} saved to {rejected_dir} "
                        f"(quality={quality_score}, mm_ratio={mm_ratio:.2f})"
                    )
                except Exception as e:
                    self.logger.warning(f"Failed to save rejected chunk {i+1}: {e}")
            else:
                consecutive_failures = 0

            # ── Early-termination: abort if chunks are clearly failing ─────────
            # Prevents wasting API calls on remaining chunks when quality is bad.
            # Two triggers: 3 consecutive failures OR running avg < 50 after 5+ chunks.
            # For short chapters (<5 chunks), only consecutive-failures triggers;
            # downstream quality gates (overall Myanmar ratio < 70%) still block save.
            quality_window.append(float(quality_score))
            if len(quality_window) > 10:
                quality_window.pop(0)

            abort = False
            if consecutive_failures >= 3:
                self.logger.error(
                    f"EARLY ABORT: {consecutive_failures} consecutive chunks failed quality "
                    f"(latest: score={quality_score}, mm_ratio={mm_ratio:.2f}). "
                    f"Stopping pipeline to save API costs."
                )
                abort = True
            elif len(quality_window) >= 5 and sum(quality_window) / len(quality_window) < 50:
                avg = sum(quality_window) / len(quality_window)
                self.logger.error(
                    f"EARLY ABORT: running quality avg {avg:.0f} < 50 "
                    f"after {len(quality_window)} chunks. "
                    f"Stopping pipeline to save API costs."
                )
                abort = True

            if abort:
                self._shutdown_requested = True
                break

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

            # Stage 5a: Model Collapse Detection
            collapse_issues = self.checker.check_model_collapse(translated_chunk)
            if collapse_issues:
                self.logger.warning(f"Model collapse detected: {collapse_issues}")
                # If collapse is severe, trigger re-translation
                if any('self-annotation' in ci or 'Vietnamese' in ci for ci in collapse_issues):
                    self.logger.warning(f"Severe model collapse in chunk {i+1} — marking for retry")
                    quality_score = 0
                    quality_passed = False
            self._report({
                "type": "chunk_collapse_check",
                "chunk_index": i + 1,
                "total_chunks": total,
                "collapse_issues": collapse_issues,
            })

            # Stage 5b: Fiction Editor — literary humanization (if enabled)
            use_fe = getattr(self.config.translation_pipeline, 'use_fiction_editor', False)
            if use_fe:
                self.logger.info(f"Step 5b/7: Humanizing chunk {i+1}/{total} via FictionEditor...")
                scene_type = self._detect_scene_type(translated_chunk)
                tone_map = {
                    "confrontation": "dramatic",
                    "dialogue": "humanize",
                    "action": "action",
                    "narration": "literary",
                }
                tone = tone_map.get(scene_type, "humanize")
                t_fe = time.time()
                try:
                    translated_chunk = self.fiction_editor.rewrite(translated_chunk, tone=tone)
                except Exception as e:
                    self.logger.warning(f"FictionEditor failed for chunk {i+1}: {e} — using original")
                self._report({
                    "type": "chunk_humanized",
                    "chunk_index": i + 1,
                    "total_chunks": total,
                    "tone": tone,
                    "duration": time.time() - t_fe,
                })

            # Stage 5c: Myanmar Syntax Editor — check/fix Myanmar grammar (if enabled)
            use_se = self.config.translation_pipeline.use_syntax_editor
            if use_se:
                self.logger.info(f"Step 5c/7: Checking Myanmar syntax for chunk {i+1}/{total}...")
                t_se = time.time()
                try:
                    translated_chunk = self.myanmar_syntax_editor.check_and_fix(translated_chunk)
                except Exception as e:
                    self.logger.warning(f"MyanmarSyntaxEditor failed for chunk {i+1}: {e} — using original")
                self._report({
                    "type": "chunk_syntax_edited",
                    "chunk_index": i + 1,
                    "total_chunks": total,
                    "duration": time.time() - t_se,
                })

            total_issues = quality_issues + cons_count
            chunk_duration = time.time() - chunk_t0
            self._report({
                "type": "chunk_complete",
                "chunk_index": i + 1,
                "total_chunks": total,
                "duration": chunk_duration,
            })

            # Always preserve translated output BEFORE timeout check, so partial
            # progress is never lost even if a chunk is slow (report.md 2.4).
            # CRITICAL: when resuming, `translated` may already hold None
            # placeholders at this index (non-contiguous checkpoints, or a stale
            # checkpoint that was rejected). Re-translating such a hole must FILL
            # the existing slot in place — appending would leave the None mid-list
            # and push this chunk out of order, crashing _postprocess (ERR: object
            # of type 'NoneType' has no len()).
            if i < len(translated):
                translated[i] = translated_chunk
            else:
                translated.append(translated_chunk)

            # Save checkpoint immediately for resumability (report.md 2.1)
            # CRITICAL: Only save checkpoint if chunk passed quality gate.
            # Rejected chunks (0% Myanmar, low quality) MUST NOT be checkpointed,
            # otherwise the resume system sees "all chunks done" and skips
            # re-translating the failed chunks (ERR-073).
            if not is_rejected:
                try:
                    if self._current_novel and self._current_chapter is not None:
                        from src.utils.file_handler import FileHandler
                        checkpoint_dir = Path("data/working") / self._current_novel / f"chapter_{self._current_chapter:04d}"
                        checkpoint_dir.mkdir(parents=True, exist_ok=True)
                        checkpoint_path = checkpoint_dir / f"ch{i+1:03d}_checkpoint.txt"
                        FileHandler.write_text(str(checkpoint_path), translated_chunk)
                except Exception as e:
                    self.logger.debug(f"Checkpoint write failed (non-fatal): {e}")

            # Log per-chunk progress if logger is provided
            if progress_logger:
                try:
                    progress_logger.log_chunk(
                        chunk_index=i,
                        chunk_text=translated_chunk,
                        source_text=chunk,
                    )
                except Exception as e:
                    self.logger.debug(f"Per-chunk progress log failed (non-fatal): {e}")

            # Per-chunk timeout guard: if a single chunk exceeds 30 min,
            # log an error and abort. Progress is already saved via checkpoint.
            # Increased from 900s→1800s because FictionEditor can take ~7.5 min
            # per call, and combined with translator+refiner a single chunk
            # can take ~20 min. 1800s gives enough headroom for 18+ chunk chapters.
            # Per report.md 2.4: no longer passes untranslated source text.
            # Use real metrics — do NOT fabricate myanmar_ratio=0.0 (that falsely
            # triggers quality gate rejection on valid output).
            if chunk_duration > 1800:
                self.logger.error(
                    f"⚠ Chunk {i+1}/{total} exceeded 30-min timeout ({chunk_duration:.0f}s). "
                    f"Progress saved via checkpoints. Aborting to prevent garbage output."
                )
                chunk_metrics.append({
                    "chunk": i + 1,
                    "quality_score": quality_score,
                    "quality_passed": quality_passed,
                    "myanmar_ratio": mm_ratio,
                    "issues": total_issues,
                    "timed_out": True,
                })
                self._shutdown_requested = True
                break

            chunk_metrics.append({
                "chunk": i + 1,
                "quality_score": quality_score,
                "quality_passed": quality_passed,
                "myanmar_ratio": mm_ratio,
                "issues": total_issues,
            })

            # Feedback Loop: ingest high-quality pairs back to database
            if self.feedback_loop is not None:
                try:
                    source_path = getattr(self, '_current_filepath', None)
                    feedback_result = self.feedback_loop.rate_and_ingest(
                        en_text=chunk,
                        my_text=translated_chunk,
                        novel_slug=self._current_novel,
                        chapter_num=None,
                        source_file=source_path,
                    )
                    if feedback_result.get("ingested"):
                        self.logger.info(
                            f"Feedback: pair ingested (score={feedback_result['score']:.2f}, "
                            f"my_ratio={feedback_result['myanmar_ratio']:.2f})"
                        )
                except Exception as e:
                    self.logger.debug(f"Feedback loop failed (non-fatal): {e}")

            self.logger.info(
                f"✓ Chunk {i+1}/{total} complete in {chunk_duration:.0f}s. "
                f"Quality: {quality_score}, Ratio: {mm_ratio:.1%}, Issues: {total_issues}"
            )

            # Write orchestration checkpoint to session_memory.json (report.md §6)
            try:
                from src.utils.file_handler import FileHandler
                session_cp = Path(".agent") / "session_memory.json"
                if session_cp.exists():
                    cp_data = FileHandler.read_json(str(session_cp)) or {}
                else:
                    cp_data = {}
                cp_data["last_checkpoint"] = {
                    "chapter": getattr(self, '_current_chapter', None),
                    "chunk_index": i + 1,
                    "total_chunks": total,
                    "stage": "translate",
                    "timestamp": datetime.now().isoformat(),
                    "quality_score": quality_score,
                    "myanmar_ratio": mm_ratio,
                }
                FileHandler.write_json(str(session_cp), cp_data)
            except Exception as e:
                self.logger.debug(f"Session checkpoint write failed (non-fatal): {e}")

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
        text = processor.clean(text, chapter=self._current_chapter or 0)

        # Normalize character names to glossary-approved forms
        try:
            from src.utils.postprocessor import normalize_character_names
            all_terms = self.memory_manager.get_all_terms()
            text = normalize_character_names(text, all_terms)
        except Exception as e:
            self.logger.debug(f"Character name normalization skipped: {e}")

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
            Uses rapidfuzz for 10-100x speed over difflib.SequenceMatcher."""
            from rapidfuzz import fuzz
            if not p1 or not p2:
                return 0.0
            return fuzz.ratio(p1, p2) / 100.0

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

    @staticmethod
    def _detect_scene_type(text: str) -> str:
        """Detect scene type from text content for dynamic prompt injection.
        
        Analyzes text to determine the dominant scene type:
        - 'confrontation': Heated dialogue with accusations, threats
        - 'dialogue': Character conversations
        - 'action': Combat, movement, physical events
        - 'narration': Description, exposition, internal thoughts
        
        Returns scene type string for use in build_linguistic_context().
        """
        # Count dialogue lines (quotes)
        dialogue_lines = len([line for line in text.split('\n')
                              if line.strip().startswith(('"', '"', '"'))])
        
        # Count action indicators
        action_keywords = ['strike', 'attack', 'fight', 'kill', 'sword', 'slash',
                          'ထိုး', 'တိုက်', 'သတ်', 'ခုတ်', 'ပစ်']
        action_count = sum(1 for kw in action_keywords if kw.lower() in text.lower())
        
        # Count confrontation indicators (accusations, threats, anger)
        confrontation_keywords = ['you', 'your', 'die', 'kill', 'hate', 'revenge',
                                 'နင်', 'သေ', 'သတ်', 'မုန်း', 'လက်စား']
        confrontation_count = sum(1 for kw in confrontation_keywords if kw.lower() in text.lower())
        
        # Count exclamation marks (emotional intensity)
        
        total_lines = len([line for line in text.split('\n') if line.strip()])
        dialogue_ratio = dialogue_lines / total_lines if total_lines > 0 else 0
        
        # Decision logic
        if confrontation_count >= 3 and dialogue_ratio > 0.3:
            return 'confrontation'
        elif dialogue_ratio > 0.5:
            return 'dialogue'
        elif action_count >= 3:
            return 'action'
        else:
            return 'narration'

    def _validate_translation(self, source_text: str, translated_text: str, chapter_num: int) -> dict:
        """Validate translation quality before saving.
        
        Checks:
        - Content completeness (paragraph/dialogue count)
        - Ordinal number correctness
        - Latin script leakage
        - Particle repetition overuse
        
        Returns validation report dict.
        """
        from src.utils.postprocessor import (
            check_content_completeness,
            check_ordinal_numbers,
            check_latin_script,
            check_particle_repetition,
            check_sentence_completion,
            detect_ngram_repetition,
            check_source_aligned_ordinals,
        )

        report = {
            'chapter': chapter_num,
            'pass': True,
            'issues': [],
            'warnings': [],
        }

        # Check content completeness
        completeness = check_content_completeness(source_text, translated_text)
        if not completeness['pass']:
            report['pass'] = False
            report['issues'].append(
                f"Content loss: {completeness['missing_paragraphs']} paragraphs missing "
                f"({completeness['paragraph_ratio']:.0%} coverage), "
                f"{completeness['missing_dialogues']} dialogues missing"
            )
        elif completeness['missing_paragraphs'] > 0:
            report['warnings'].append(
                f"Minor content loss: {completeness['missing_paragraphs']} paragraphs "
                f"({completeness['paragraph_ratio']:.0%} coverage)"
            )

        # Check ordinal numbers (legacy: translated-text-only check)
        ordinal_issues = check_ordinal_numbers(translated_text)
        if ordinal_issues:
            report['pass'] = False
            for issue in ordinal_issues:
                report['issues'].append(
                    f"Wrong ordinal at line {issue['line']}: "
                    f"'{issue['found']}' should be '{issue['expected']}' ({issue['meaning']})"
                )

        # Check source-aligned ordinal numbers (4.2: compare source vs translation)
        aligned_ordinal_issues = check_source_aligned_ordinals(source_text, translated_text)
        if aligned_ordinal_issues:
            report['pass'] = False
            for issue in aligned_ordinal_issues[:5]:
                report['issues'].append(
                    f"Ordinal mismatch: {issue['meaning']}"
                )

        # Check Latin script leakage
        latin_issues = check_latin_script(translated_text)
        if latin_issues:
            latin_texts = [i['text'] for i in latin_issues[:5]]
            extra = f"and {len(latin_issues) - 5} more" if len(latin_issues) > 5 else ""
            report['warnings'].append(
                f"Latin script found: {', '.join(latin_texts)}"
                + (f" ({extra})" if extra else "")
            )

        # Check particle repetition
        particle_issues = check_particle_repetition(translated_text)
        if particle_issues:
            for issue in particle_issues[:3]:
                report['warnings'].append(
                    f"Particle overuse in paragraph {issue['paragraph']}: "
                    f"'{issue['particle']}' appears {issue['count']} times "
                    f"(max {issue['max_allowed']})"
                )

        # Check sentence completion (4.3: lines ending mid-sentence)
        sentence_issues = check_sentence_completion(translated_text)
        if sentence_issues:
            report['pass'] = False
            for issue in sentence_issues[:5]:
                report['issues'].append(
                    f"Incomplete sentence at line {issue['line']}: '{issue['text']}'"
                )

        # Check n-gram repetition (4.1: garbled repetition passes ratio gate)
        ngram_result = detect_ngram_repetition(translated_text)
        if ngram_result['has_repetition']:
            ngram_detail = ', '.join(
                f"'{g['ngram']}' ×{g['count']}"
                for g in ngram_result['repeated_ngrams'][:3]
            )
            report['issues'].append(
                f"Repetition detected: {ngram_detail}"
            )

        return report

    def _save_output(self, input_path: str, text: str, extra_meta: Optional[Dict[str, Any]] = None, source_text: str = "") -> Path:
        """Save translated output and update per-novel cumulative meta.json.
        
        Args:
            input_path: Original input file path
            text: Translated text
            extra_meta: Additional metadata to save
            
        Returns:
            Path to output file
        """
        input_path = Path(input_path)

        # Determine output path (strip lang/ subdir like en/ or zh/)
        if str(input_path).startswith(INPUT_DIR):
            relative = input_path.relative_to(INPUT_DIR)
            # Strip language subdirectory (en/, zh/) from output path
            parts = list(relative.parts)
            if len(parts) >= 2 and parts[1] in ("en", "zh", "mm"):
                parts.pop(1)
            relative = Path(*parts)
        else:
            relative = Path(input_path.name)
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

        # --- Run translation validation before saving ---
        if source_text:
            validation = self._validate_translation(source_text, text, chapter_num or 0)
            if validation['issues']:
                for issue in validation['issues']:
                    self.logger.warning(f"Chapter {chapter_num} validation issue: {issue}")
            if validation['warnings']:
                for warning in validation['warnings']:
                    self.logger.info(f"Chapter {chapter_num} validation warning: {warning}")
            
            # Add validation results to extra_meta
            if extra_meta is None:
                extra_meta = {}
            extra_meta['validation_pass'] = validation['pass']
            extra_meta['validation_issues'] = validation['issues']
            extra_meta['validation_warnings'] = validation['warnings']

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
            refiner_model = getattr(self.config.models, 'refiner', None) or \
                            getattr(self.config.models, 'editor', None) or 'N/A'
            chapter_entry = {
                "chapter": chapter_num,
                "translated_at": datetime.now().isoformat(),
                "source": str(input_path),
                "pipeline": self.config.translation_pipeline.mode,
                "model": self.config.models.translator,
                "refiner_model": refiner_model,
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

    def _auto_review(self, output_path: str, translated_text: str = "", source_text: str = "") -> None:
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
                source_text=source_text,
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

        # Unload HF model (mig-burmese-llm) to free RAM
        if self._myanmar_syntax_editor:
            try:
                self._myanmar_syntax_editor.unload()
                self.logger.info("HF model (mig-burmese-llm) unloaded")
            except Exception as e:
                self.logger.error(f"Error unloading HF model: {e}")

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
