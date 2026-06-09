"""Sentence alignment between English and Myanmar parallel chapters.

Uses length-ratio and word-count heuristics for cross-script alignment
(English and Myanmar share no common characters, so character-level
similarity is always ~0).
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

SENTENCE_SPLIT_EN = re.compile(r'(?<=[.!?])\s+')
SENTENCE_SPLIT_MM = re.compile(r'(?<=[။၊!?])\s*')


def split_sentences(text: str, language: str = "en") -> list[str]:
    if language == "my":
        raw = SENTENCE_SPLIT_MM.split(text)
    else:
        raw = SENTENCE_SPLIT_EN.split(text)
    return [s.strip() for s in raw if s.strip() and len(s.strip()) > 5]


def read_chapter_file(filepath: str) -> str:
    import codecs
    with codecs.open(filepath, encoding="utf-8-sig") as f:
        return f.read()


class SentenceAligner:
    """Aligns sentences from parallel EN/MM chapter files using length-ratio heuristics.

    Since English and Myanmar scripts share no common characters, cross-script
    alignment uses relative length ratios and word counts rather than character
    sequence matching.
    """

    def __init__(self, threshold: float = 0.3):
        self.threshold = threshold

    @staticmethod
    def _length_ratio(en_text: str, my_text: str) -> float:
        en_words = len(en_text.split())
        my_chars = len(my_text.replace(" ", ""))
        if en_words == 0 or my_chars == 0:
            return 0.0
        ratio = en_words / max(my_chars / 3, 1)
        return 1.0 - abs(1.0 - min(ratio, 3.0) / 3.0)

    def align_chapters(self, en_text: str, my_text: str) -> list[tuple[str, str]]:
        en_sentences = split_sentences(en_text, "en")
        my_sentences = split_sentences(my_text, "my")

        if not en_sentences or not my_sentences:
            return []

        total_en = len(en_sentences)
        total_my = len(my_sentences)
        alignment = []
        en_idx = 0
        my_idx = 0

        while en_idx < total_en and my_idx < total_my:
            en_pos = en_idx / max(total_en - 1, 1)
            my_pos = my_idx / max(total_my - 1, 1)

            en_sent = en_sentences[en_idx]
            my_sent = my_sentences[my_idx]

            pos_ratio = 1.0 - abs(en_pos - my_pos)
            len_score = self._length_ratio(en_sent, my_sent)
            combined = pos_ratio * 0.6 + len_score * 0.4

            if combined > self.threshold:
                alignment.append((en_sent, my_sent))
                en_idx += 1
                my_idx += 1
            elif en_pos < my_pos:
                en_idx += 1
            else:
                my_idx += 1

        return alignment

    def align_directory(
        self,
        en_dir: str,
        my_dir: str,
        chapter_regex: str = r"chapter[_\-\s]*(\d+)",
        limit: int = 0,
    ) -> list[tuple[int, list[tuple[str, str]]]]:
        import os
        from pathlib import Path

        en_path = Path(en_dir)
        my_path = Path(my_dir)
        pattern = re.compile(chapter_regex, re.IGNORECASE)

        chapters = []
        for en_file in sorted(en_path.iterdir()):
            if not en_file.is_file():
                continue
            match = pattern.search(en_file.name)
            if not match:
                continue
            chapter_num = int(match.group(1))
            if limit > 0 and chapter_num > limit:
                continue

            my_file = my_path / en_file.name
            if not my_file.exists():
                candidates = list(my_path.glob(f"*{chapter_num}*"))
                my_file = candidates[0] if candidates else None
            if not my_file:
                continue

            try:
                en_text = read_chapter_file(str(en_file))
                my_text = read_chapter_file(str(my_file))
                aligned_sentences = self.align_chapters(en_text, my_text)
                if aligned_sentences:
                    chapters.append((chapter_num, aligned_sentences))
                    logger.info(f"Aligned chapter {chapter_num}: {len(aligned_sentences)} pairs")
            except Exception as e:
                logger.warning(f"Failed to align chapter {chapter_num}: {e}")

        return chapters
