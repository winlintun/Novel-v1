"""
Terminology Feedback Loop
===========================
Reads detected terminology violations from the Dataset Alignment Project's
alignment.db and creates session rules / pending glossary entries in the
translation pipeline's MemoryManager.

This closes the detection→correction gap: violations caught by validators
are fed back into the translation pipeline as corrections.

Usage:
    feedback = TerminologyFeedback(
        alignment_db="/path/to/dataset_alignment/data/alignment.db",
        memory_manager=memory_manager_instance,
    )
    corrections = feedback.process_terminology_issues()
"""

import logging
import sqlite3
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Minimum occurrence threshold: only flag terms that are wrong this many times
MIN_OCCURRENCES = 3


class TerminologyFeedback:

    def __init__(
        self,
        alignment_db: str = "",
        memory_manager=None,
        novel_name: Optional[str] = None,
    ):
        self.alignment_db = alignment_db
        self.memory = memory_manager
        self.novel_name = novel_name

    def process_terminology_issues(self) -> dict:
        """Read terminology issues from alignment.db and create corrections.

        Returns:
            dict with counts: session_rules_created, pending_terms_added, errors
        """
        result = {
            "session_rules_created": 0,
            "pending_terms_added": 0,
            "errors": [],
        }

        if not self.alignment_db or not Path(self.alignment_db).exists():
            logger.warning(f"Alignment DB not found: {self.alignment_db}")
            return result

        conn = None
        try:
            conn = sqlite3.connect(self.alignment_db)
            conn.row_factory = sqlite3.Row

            # Query: find all terminology issues grouped by chapter
            # The alignment.db stores issues per sentence
            issues = conn.execute(
                """SELECT i.id, i.chapter_id, i.sentence_id, i.message, i.category,
                          c.novel, c.chapter_no
                   FROM issues i
                   JOIN chapters c ON i.chapter_id = c.id
                   WHERE i.category LIKE 'quality.terminology%'
                      OR i.category = 'content.terminology'
                   ORDER BY c.chapter_no"""
            ).fetchall()

            if not issues:
                logger.info("No terminology issues found in alignment DB")
                return result

            # Group by pattern: extract the source term that was violated
            # Messages look like: "Term 'Fang Yuan' should use 'ဖန်ယွမ်' but found 'Fang Yuan'"
            violation_groups = {}
            for issue in issues:
                novel = issue["novel"]
                if self.novel_name and self.novel_name not in novel:
                    continue
                msg = issue["message"]
                # Extract source term from message
                term = self._extract_term_from_message(msg)
                if term:
                    violation_groups.setdefault(term, []).append(issue)

            # Process grouped violations
            for term, term_issues in violation_groups.items():
                if len(term_issues) < MIN_OCCURRENCES:
                    continue

                # Extract the correct Myanmar translation from the latest issue message
                correct_target = self._extract_correct_target(term_issues[-1]["message"])
                if not correct_target:
                    continue

                # 1. Create a session rule (immediate correction for current translation)
                if self.memory and hasattr(self.memory, 'add_session_rule'):
                    self.memory.add_session_rule(term, correct_target)
                    result["session_rules_created"] += 1
                    logger.info(f"Session rule: {term} -> {correct_target}")

                # 2. Add as pending glossary term
                if self.memory and hasattr(self.memory, 'add_pending_term'):
                    added = self.memory.add_pending_term(
                        source=term,
                        target=correct_target,
                        category="terminology_correction",
                        chapter=term_issues[-1]["chapter_no"],
                    )
                    if added:
                        result["pending_terms_added"] += 1

            logger.info(
                f"Terminology feedback: {result['session_rules_created']} rules, "
                f"{result['pending_terms_added']} pending terms"
            )

        except Exception as e:
            logger.error(f"Terminology feedback failed: {e}")
            result["errors"].append(str(e))

        finally:
            if conn:
                conn.close()

        return result

    @staticmethod
    def _extract_term_from_message(message: str) -> Optional[str]:
        """Extract the source term from a terminology violation message.

        Patterns:
          "Term 'Fang Yuan' should use 'ဖန်ယွမ်' but found 'Fang Yuan'"
          "Glossary violation: 'Fang Yuan' expected 'ဖန်ယွမ်' got 'Fang Yuan'"
        """
        for quote_char in ["'", '"', "`"]:
            # Try: should use 'X' pattern
            idx = message.find(f"should use {quote_char}")
            if idx > 0:
                before = message[:idx].strip()
                for qc in ["'", '"', "`"]:
                    start = before.rfind(qc)
                    if start >= 0:
                        after = before[start + 1:]
                        term_end = after.find(qc)
                        if term_end > 0:
                            return after[:term_end].strip()
            # Try: Glossary violation: 'X' expected pattern
            idx = message.find(f"expected {quote_char}")
            if idx > 0:
                before = message[:idx].strip()
                gl_idx = before.rfind(f"{quote_char}")
                if gl_idx >= 0:
                    after = before[gl_idx + 1:]
                    term_end = after.find(quote_char)
                    if term_end > 0:
                        term = after[:term_end].strip()
                        if term:
                            return term
        return None

    @staticmethod
    def _extract_correct_target(message: str) -> Optional[str]:
        """Extract the correct Myanmar translation from a violation message.

        Pattern: "should use 'ဖန်ယွမ်'" or "expected 'ဖန်ယွမ်'"
        """
        for quote_char in ["'", '"', "`"]:
            patterns = [
                f"should use {quote_char}",
                f"expected {quote_char}",
            ]
            for pat in patterns:
                idx = message.find(pat)
                if idx >= 0:
                    after = message[idx + len(pat):]
                    term_end = after.find(quote_char)
                    if term_end > 0:
                        target = after[:term_end].strip()
                        if target:
                            return target
        return None
