"""Preprocessing: normalize → clean → segment sentences."""

import unicodedata
import logging
from dataclasses import dataclass
from typing import Optional

import regex

from src.dataset_alignment.config import get_alignment_config

logger = logging.getLogger(__name__)

try:
    import ftfy
except ImportError:
    ftfy = None
    logger.warning("ftfy not installed — text normalization will be limited")

try:
    import pysbd
    _EN_SEG = pysbd.Segmenter(language="en", clean=False)
except ImportError:
    pysbd = None
    _EN_SEG = None
    logger.warning("pysbd not installed — English sentence segmentation limited")

_ZERO_WIDTH = regex.compile(r"[\u200B-\u200D\uFEFF\u00AD]")
_MULTI_SPACE = regex.compile(r"[ \t]{2,}")
_MULTI_NEWLINE = regex.compile(r"\n{3,}")
_SOFT_HYPHEN = regex.compile(r"(\w)-\n(\w)")
_TITLE_LINE = regex.compile(r"^\s{0,3}#{1,3}\s+(.+?)\s*$", regex.MULTILINE)
_MD_CODE = regex.compile(r"```.*?```", regex.DOTALL)


@dataclass
class CleanResult:
    text: str
    removed: list[tuple[str, str]]


def detect_zawgyi(text: str) -> float:
    """Detect Zawgyi encoding in Myanmar text. Returns probability 0-1."""
    try:
        from myanmartools import ZawgyiDetector
        detector = ZawgyiDetector()
        if text.strip():
            return float(detector.get_zawgyi_probability(text))
    except Exception:
        pass
    return 0.0


def _fix_text(text: str) -> str:
    if ftfy is not None:
        try:
            return ftfy.fix_text(text)
        except Exception:
            pass
    return text


def normalize_text(text: str) -> str:
    """NFC normalize + ftfy + strip zero-width chars + collapse whitespace."""
    text = _fix_text(text)
    text = unicodedata.normalize("NFC", text)
    text = _ZERO_WIDTH.sub("", text)
    text = _SOFT_HYPHEN.sub(r"\1\2", text)
    text = _MULTI_SPACE.sub(" ", text)
    text = _MULTI_NEWLINE.sub("\n\n", text)
    return text.strip()


def clean_text(text: str) -> CleanResult:
    """Remove noise patterns defined in rule.yaml."""
    cfg = get_alignment_config()
    removed: list[tuple[str, str]] = []

    for cat in ("translator_notes", "ads", "formatting_artifacts", "ocr_errors"):
        for pat in cfg.rule("noise_patterns", cat, default=[]) or []:
            for m in regex.finditer(pat, text):
                removed.append((f"noise.{cat}", m.group(0)[:120]))
            text = regex.sub(pat, " ", text)

    text = _MULTI_SPACE.sub(" ", text)
    text = _MULTI_NEWLINE.sub("\n\n", text).strip()
    return CleanResult(text=text, removed=removed)


def segment_sentences(text: str, lang: str) -> list[str]:
    """Split text into sentences for the given language."""
    text = text.strip()
    if not text:
        return []
    if lang == "en":
        if _EN_SEG is not None:
            return [s.strip() for s in _EN_SEG.segment(text) if s.strip()]
        return [s.strip() for s in text.split(". ") if s.strip()]
    if lang in ("my", "mm", "bur"):
        chunks = regex.split(
            r"(?<=[။?!၊])[\s་]*",
            text,
        )
        chunks = [c.strip() for c in chunks if c.strip()]
        chunks = [c for c in chunks if len(c) >= 3]
        return chunks
    return [s.strip() for s in text.split(". ") if s.strip()]


def extract_title_and_body(md_text: str) -> tuple[Optional[str], str]:
    """Extract the first heading as title, rest as body."""
    md_text = _MD_CODE.sub("", md_text)
    m = _TITLE_LINE.search(md_text)
    title = m.group(1).strip() if m else None
    body = md_text
    if m:
        body = md_text[m.end():].lstrip()
    return title, body
