"""Scene-based chunker (SPEC.md §2.2, RULES.md R-STRUCT-01/02/03).

- scene breaks (``---``, a heading, or blank-page-like separators) force a new
  chunk and become the first paragraph of it (TDD TEST-CHUNK-001)
- consecutive dialogue lines stay together up to ``max_consecutive_dialogue``
  (R-STRUCT-03, TEST-CHUNK-002)
- overlap: the last ``overlap_paragraphs`` of chunk[i] are prepended to the
  source of chunk[i+1] (TEST-CHUNK-003)
- min/max paragraph bounds are respected (TEST-CHUNK-004)
- chunk type: ``dialogue-heavy`` >0.6, ``narration-heavy`` <0.2, else ``mixed``
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .models import Chunk

# Burmese quotes are U+201C/U+201D; the source also uses ASCII quotes.
_DIALOGUE_OPENERS = ('"', "\u201c", "\u2018", "\u300c")
_SCENE_BREAKS = ("---", "***", "<hr>", "\u00ad\u00ad\u00ad")


class ChunkerConfig:
    def __init__(self, data: Optional[Dict] = None):
        data = data or {}
        params = data.get("parameters", {})
        self.max_paragraphs = int(params.get("max_paragraphs_per_chunk", 5))
        self.min_paragraphs = int(params.get("min_paragraphs_per_chunk", 2))
        self.overlap = int(params.get("overlap_paragraphs", 1))
        dia = data.get("dialogue_preservation", {}) or {}
        self.max_consecutive_dialogue = int(dia.get("max_consecutive_dialogue", 6))
        ratio = data.get("chunk_types", {}) or {}
        self.dialogue_heavy_ratio = self._ratio(ratio.get("dialogue-heavy", {}).get("dialogue_ratio", "> 0.6"))
        self.narration_heavy_ratio = self._ratio(ratio.get("narration-heavy", {}).get("dialogue_ratio", "< 0.2"))

    @staticmethod
    def _ratio(spec: str) -> Tuple[str, float]:
        spec = str(spec).strip().replace(" ", "")
        for op in (">=", ">", "<", "<="):
            if spec.startswith(op):
                return op, float(spec[len(op):])
        return ">", float(spec)

    def _above(self, op: str, val: float, compare: float) -> bool:
        if op == ">=":
            return compare >= val
        if op == ">":
            return compare > val
        if op == "<=":
            return compare <= val
        return compare < val

    def classify(self, paragraphs: List[str]) -> str:
        n = len(paragraphs)
        d = sum(1 for p in paragraphs if is_dialogue_para(p))
        ratio = d / n if n else 0.0
        op, val = self.dialogue_heavy_ratio
        if self._above(op, val, ratio):
            return "dialogue-heavy"
        op, val = self.narration_heavy_ratio
        if self._above(op, val, ratio):
            return "narration-heavy"
        return "mixed"

    @classmethod
    def load(cls, path: Optional[Path | str] = None) -> "ChunkerConfig":
        if not path:
            return cls()
        p = Path(path)
        if not p.is_file():
            return cls()
        return cls(json.loads(p.read_text(encoding="utf-8")))


def is_dialogue_para(paragraph: str) -> bool:
    return paragraph.lstrip().startswith(_DIALOGUE_OPENERS)


def is_scene_break(paragraph: str) -> bool:
    stripped = paragraph.strip()
    if stripped in _SCENE_BREAKS or paragraph == "\n\n\n":
        return True
    if stripped.startswith(("# ", "## ", "### ")):
        return True
    return False


_SPEAKER_RE = re.compile(
    r"(?P<name>[A-Z][A-Za-z\u00C0-\u024F .'\-]{0,40}?)\s+"
    r"(?:said|says|asked|replied|answered|hissed|shouted|murmured|called|hollered|told|whispered)\b",
    re.IGNORECASE,
)


def identify_speakers(text: str, glossary_speakers: Optional[List[str]] = None) -> List[str]:
    """Best-effort speaker extraction from dialogue tags + glossary names."""
    names = set()
    for m in _SPEAKER_RE.finditer(text or ""):
        name = m.group("name").strip()
        if name and re.search(r"[A-Za-z]", name):
            names.add(name)
    if glossary_speakers:
        for s in glossary_speakers:
            if s and s in text:
                names.add(s)
    return sorted(names)


def _group_paragraphs(
    paragraphs: List[str], cfg: ChunkerConfig
) -> List[List[str]]:
    """Greedy grouping: scene breaks start a new group; dialogue blocks kept."""
    groups: List[List[str]] = []
    cur: List[str] = []
    n = len(paragraphs)

    def flush() -> None:
        nonlocal cur
        if cur:
            groups.append(cur)
            cur = []

    for i, p in enumerate(paragraphs):
        if is_scene_break(p):
            flush()
            cur = [p]
            continue
        cur.append(p)
        if len(cur) >= cfg.max_paragraphs:
            nxt = paragraphs[i + 1] if i + 1 < n else None
            if nxt is not None and is_dialogue_para(nxt) and not is_scene_break(nxt):
                # try to keep the dialogue run together (subject to the cap)
                dialogue_in_cur = sum(1 for q in cur if is_dialogue_para(q))
                if dialogue_in_cur < cfg.max_consecutive_dialogue:
                    continue
            flush()
    flush()
    return groups


def build_chunks(
    chapter_id: str,
    paragraphs: List[str],
    cfg: ChunkerConfig,
) -> List[Chunk]:
    """Turn source paragraphs into overlap-injected Chunk objects."""
    groups = _group_paragraphs(paragraphs, cfg)
    scene = 0
    chunks: List[Chunk] = []
    for gi, group in enumerate(groups):
        if group and is_scene_break(group[0]):
            scene += 1
        overlap_paras: List[str] = []
        if cfg.overlap and gi and groups[gi - 1]:
            overlap_paras = groups[gi - 1][-cfg.overlap:]
        source_paras = overlap_paras + group
        seq = len(chunks)
        chunk = Chunk(
            id=f"{chapter_id}_sc{scene:02d}_ck{seq:02d}",
            chapter_id=chapter_id,
            scene_id=f"sc{scene:02d}",
            sequence=seq,
            type=cfg.classify(group),
            paragraphs=source_paras,
            overlap_paras=overlap_paras,
            speakers=identify_speakers("\n\n".join(group)),
            status="pending",
        )
        chunks.append(chunk)
    return chunks