"""
Omission Auto-Filler
======================
Reads 1:NULL omission records from the Dataset Alignment Project's export
and auto-translates them using the translation pipeline.

Omissions are English sentences with NO Myanmar translation. The dataset
alignment project exports them to omissions.jsonl. This module pipes them
through the Translator agent and stores the filled pairs back.

Usage:
    filler = OmissionFiller(
        omissions_path="/path/to/dataset_alignment/data/omissions.jsonl",
        translator=translator_instance,
        memory_manager=memory_manager_instance,
    )
    result = filler.fill_omissions()
"""

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class OmissionFiller:

    def __init__(
        self,
        omissions_path: str = "",
        translator=None,
        memory_manager=None,
        novel_name: Optional[str] = None,
    ):
        self.omissions_path = omissions_path
        self.translator = translator
        self.memory = memory_manager
        self.novel_name = novel_name

    def fill_omissions(self, max_fill: int = 50) -> dict:
        """Read omission records and auto-translate them.

        Args:
            max_fill: Maximum number of omissions to fill per run (cap for safety)

        Returns:
            dict with counts: filled, skipped, errors
        """
        result = {
            "filled": 0,
            "skipped": 0,
            "errors": 0,
            "filled_pairs": [],
        }

        if not self.omissions_path or not Path(self.omissions_path).exists():
            logger.warning(f"Omissions file not found: {self.omissions_path}")
            return result

        if not self.translator:
            logger.warning("No translator provided — omission filler disabled")
            return result

        try:
            with open(self.omissions_path, "r", encoding="utf-8") as f:
                records = [json.loads(line) for line in f if line.strip()]

            if not records:
                logger.info("No omissions to fill")
                return result

            # Filter by novel name if specified
            if self.novel_name:
                records = [r for r in records if self.novel_name in r.get("novel", "")]
                logger.info(f"Filtered to {len(records)} omissions for novel '{self.novel_name}'")

            # De-duplicate by source text
            seen = set()
            unique_records = []
            for r in records:
                src = r.get("src", "").strip()
                if src and src not in seen:
                    seen.add(src)
                    unique_records.append(r)

            records = unique_records[:max_fill]
            logger.info(f"Filling {len(records)} omissions (capped at {max_fill})")

            for i, record in enumerate(records):
                try:
                    src_text = record.get("src", "").strip()
                    if not src_text:
                        result["skipped"] += 1
                        continue

                    # Translate the omitted sentence
                    translation = self.translator.translate_paragraph(
                        paragraph=src_text,
                        chapter_num=record.get("chapter", 0),
                    )

                    if not translation or len(translation.strip()) < 5:
                        logger.warning(f"Empty translation for omission {i+1}: {src_text[:50]}")
                        result["skipped"] += 1
                        continue

                    # Store the filled pair
                    pair = {
                        "novel": record.get("novel", self.novel_name or "unknown"),
                        "chapter": record.get("chapter", 0),
                        "src": src_text,
                        "tgt": translation,
                    }
                    result["filled_pairs"].append(pair)
                    result["filled"] += 1

                    # Add to pending glossary if names/terms are involved
                    if self.memory and hasattr(self.memory, 'add_pending_term'):
                        self._extract_and_pend_terms(src_text, translation,
                                                      record.get("chapter", 0))

                    logger.debug(f"Filled omission {i+1}/{len(records)}: {src_text[:40]} -> {translation[:40]}")

                except Exception as e:
                    logger.warning(f"Failed to fill omission {i+1}: {e}")
                    result["errors"] += 1

            logger.info(f"Omission filler: {result['filled']} filled, "
                        f"{result['skipped']} skipped, {result['errors']} errors")

        except Exception as e:
            logger.error(f"Omission filler failed: {e}")
            result["errors"] += 1

        return result

    def _extract_and_pend_terms(self, src: str, tgt: str, chapter: int) -> None:
        """Simple term extraction: look for placeholder patterns in translation."""
        import re
        placeholders = re.findall(r'【\?([^?]+)\?】', tgt)
        for term in placeholders:
            if term.strip():
                self.memory.add_pending_term(
                    source=term.strip(),
                    target=f"【?{term.strip()}?】",
                    category="extracted_omission",
                    chapter=chapter,
                )
