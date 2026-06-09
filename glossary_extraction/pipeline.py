"""Main glossary extraction pipeline — coordinates all stages."""

import logging
import time
from pathlib import Path
from typing import Optional

from glossary_extraction.config import PipelineConfig
from glossary_extraction.db import ExtractionDB
from glossary_extraction.alignment import SentenceAligner, read_chapter_file
from glossary_extraction.candidates import CandidateExtractor
from glossary_extraction.scoring import rank_candidates
from glossary_extraction.llm import verify_candidate

logger = logging.getLogger(__name__)


def run_pipeline(cfg: PipelineConfig) -> dict:
    start_time = time.time()
    summary = {
        "novel_id": cfg.novel_id,
        "chapters_processed": 0,
        "pairs_aligned": 0,
        "candidates_raw": 0,
        "candidates_after_dedup": 0,
        "candidates_scored": 0,
        "llm_verified": 0,
        "terms_inserted": 0,
        "duration_seconds": 0,
        "errors": [],
    }

    if not cfg.en_dir or not cfg.my_dir:
        return {**summary, "error": "en_dir and my_dir are required"}

    if not cfg.novel_id:
        return {**summary, "error": "novel_id is required"}

    en_path = Path(cfg.en_dir)
    my_path = Path(cfg.my_dir)

    if not en_path.exists():
        return {**summary, "error": f"en_dir not found: {en_path}"}
    if not my_path.exists():
        return {**summary, "error": f"my_dir not found: {my_path}"}

    db = ExtractionDB(cfg.db_path)
    db.ensure_novel(cfg.novel_id, cfg.novel_id)

    sentence_aligner = SentenceAligner(threshold=cfg.min_alignment_score)
    candidate_extractor = CandidateExtractor(
        min_occurrences=cfg.min_occurrences,
        min_length=cfg.min_term_length,
    )

    ollama_client = None
    if cfg.use_llm_verify:
        try:
            from src.utils.ollama_client import OllamaClient
            llm_model = getattr(cfg, 'llm_model', 'qwen2.5:14b')
            llm_timeout = getattr(cfg, 'llm_timeout', 120)
            llm_retries = getattr(cfg, 'llm_max_retries', 2)
            ollama_client = OllamaClient(model=llm_model, timeout=llm_timeout, max_retries=llm_retries)
        except Exception as e:
            logger.warning(f"Failed to create OllamaClient (LLM verify disabled): {e}")
            cfg.use_llm_verify = False

    aggregated: dict[str, dict] = {}
    existing_sources: set[str] = set()

    try:
        existing_terms = db.glossary_repo.get_terms_by_novel(cfg.novel_id, limit=9999)
        for t in existing_terms:
            existing_sources.add(t["source_term"].lower())
        existing_global = db.glossary_repo.get_global_terms(limit=9999)
        for t in existing_global:
            existing_sources.add(t["source_term"].lower())
    except Exception as e:
        logger.warning(f"Failed to load existing terms: {e}")

    aligned_chapters = sentence_aligner.align_directory(
        en_dir=str(en_path),
        my_dir=str(my_path),
        chapter_regex=cfg.chapter_regex,
        limit=cfg.limit_chapters,
    )

    summary["chapters_processed"] = len(aligned_chapters)

    for chapter_num, aligned_pairs in aligned_chapters:
        summary["pairs_aligned"] += len(aligned_pairs)

        candidates = candidate_extractor.extract_candidates(aligned_pairs)
        summary["candidates_raw"] += len(candidates)

        for c in candidates:
            source = c["source_term"]
            if source.lower() in existing_sources:
                continue
            if source not in aggregated:
                aggregated[source] = c
            else:
                aggregated[source]["frequency"] += c["frequency"]
                existing_contexts = aggregated[source].get("contexts", [])
                new_contexts = c.get("contexts", [])
                combined = existing_contexts + new_contexts
                aggregated[source]["contexts"] = combined[:3]

    all_candidates = list(aggregated.values())
    all_candidates.sort(key=lambda c: c["frequency"], reverse=True)
    all_candidates = all_candidates[:cfg.candidate_max]
    summary["candidates_after_dedup"] = len(all_candidates)

    scored = rank_candidates(all_candidates, max_results=cfg.candidate_max)
    summary["candidates_scored"] = len(scored)

    for candidate in scored:
        if cfg.use_llm_verify and ollama_client:
            candidate = verify_candidate(candidate, ollama_client=ollama_client)

        source_term = candidate["source_term"]
        target_term = candidate.get("target_term") or candidate.get("llm_target") or f"【?{source_term}?】"
        category = candidate.get("category", "general")
        confidence = candidate.get("confidence", 0.5)
        is_valid = candidate.get("llm_verified", True)

        if not is_valid:
            continue

        summary["llm_verified"] += 1

        if cfg.dry_run:
            logger.info(f"[DRY RUN] Would insert: {source_term} -> {target_term} ({category}, conf={confidence:.2f})")
            continue

        try:
            existing = db.glossary_repo.get_term_by_source(cfg.novel_id, source_term)
            if existing:
                logger.debug(f"Skipping existing term: {source_term}")
                continue

            term_id = db.add_pending_term(
                novel_id=cfg.novel_id,
                source_term=source_term,
                target_term=target_term,
                category=category,
                confidence=confidence,
                source="auto_extract_alignment",
            )
            if term_id:
                summary["terms_inserted"] += 1
                logger.info(f"  [{summary['terms_inserted']}] Added: {source_term} -> {target_term}")
            else:
                logger.debug(f"Already exists (race): {source_term}")

        except Exception as e:
            summary["errors"].append(f"Failed to insert '{source_term}': {e}")
            logger.warning(f"Failed to insert term '{source_term}': {e}")

    db.close()

    summary["duration_seconds"] = round(time.time() - start_time, 2)

    return summary
