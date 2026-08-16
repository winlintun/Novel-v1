"""Markdown chapter I/O: YAML frontmatter + heading + blank-separated paragraphs.

SPEC.md §5 defines the source/output markdown shapes.  We only *need* these
three structural pieces; a tiny key/value frontmatter parser keeps us
dependency-free (no PyYAML).
"""
from __future__ import annotations

import re
from typing import Dict, List, Tuple

FRONT_RE = re.compile(r"^(---\s*\r?\n)(.*?)(^---\s*(?:\r?\n|$))", re.DOTALL | re.MULTILINE)
HEADING_RE = re.compile(r"^#\s+.+$", re.MULTILINE)


def parse_frontmatter(text: str) -> Dict[str, str]:
    """Return frontmatter as an ordered dict of key -> value strings."""
    m = FRONT_RE.match(text)
    if not m:
        return {}
    fm: Dict[str, str] = {}
    for line in m.group(2).splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        fm[key.strip()] = value.strip().strip('"\'')
    return fm


def split_frontmatter(text: str) -> Tuple[str, str]:
    """Split ``(raw_frontmatter_block, body)``. Body keeps heading + content."""
    m = FRONT_RE.match(text)
    if not m:
        return "", text
    return m.group(0), text[m.end():]


def parse_body(body: str) -> Tuple[str, List[str]]:
    """Return ``(heading_line, body_paragraphs)`` from the post-frontmatter body."""
    body = body.strip("\n")
    heading = ""
    m = HEADING_RE.match(body)
    if m:
        heading = m.group(0)
        body = body[m.end():]
    paras = [p.strip() for p in body.split("\n\n") if p.strip()]
    return heading, paras


def parse_chapter(text: str) -> Tuple[Dict[str, str], str, str, List[str]]:
    """Full parse: ``(frontmatter_dict, raw_frontmatter, heading, paragraphs)``."""
    raw_fm, body = split_frontmatter(text)
    fm = parse_frontmatter(raw_fm)
    heading, paras = parse_body(body)
    return fm, raw_fm, heading, paras


def render_frontmatter(fm: Dict[str, str]) -> str:
    lines = ["---"]
    for key, value in fm.items():
        if value is None:
            continue
        if isinstance(value, bool):
            value = "true" if value else "false"
        lines.append(f'{key}: "{str(value)}"')
    lines.append("---")
    return "\n".join(lines)


def build_output(frontmatter: Dict[str, str], heading: str, paragraphs: List[str]) -> str:
    """Assemble a translated chapter (frontmatter + heading + paragraphs)."""
    blocks: List[str] = [render_frontmatter(frontmatter), ""]
    if heading:
        blocks.append("# " + heading.lstrip("# ").strip())
        blocks.append("")
    for p in paragraphs:
        if not p.strip():
            continue
        blocks.append(p.strip())
        blocks.append("")
    return "\n".join(blocks).strip() + "\n"


def paragraph_count(text: str) -> int:
    """Count non-empty paragraphs (split on blank lines)."""
    return len([p for p in text.split("\n\n") if p.strip()])


def hash_version(text: str, length: int = 12) -> str:
    """Short content hash used for glossary/style/prompt version fields."""
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]