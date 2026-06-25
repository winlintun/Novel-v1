"""Canonical novel slug/id/path resolution.

Single source of truth for converting a novel's folder name (which may contain
spaces, capitals, or mixed casing) into:

  * a filesystem-safe slug          (e.g. `daoist-master-of-qing-xuan`)
  * a DB `novel_id` string          (e.g. `novel_daoist_master_of_qing_xuan`)
  * the input directory that actually holds the novel's chapters

Previously three divergent functions (`memory_manager._make_novel_id`,
`version_manager._get_or_create_novel`, `flask_app._slug_to_novel_id`) plus the
raw folder name itself produced four different keys for the same novel —
breaking glossary reattachment and writing output paths with spaces. This module
unifies them.

All functions are idempotent, Windows-safe, ASCII-output, and contain no
``\\b`` regex.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

__all__ = [
    "slugify_novel",
    "novel_id_from_slug",
    "novel_id_from_name",
    "slug_from_novel_id",
    "resolve_novel_input_dir",
    "is_canonical_novel_dir",
]

_NON_ALNUM = re.compile(r"[^a-z0-9]+", re.IGNORECASE)
_DASH_COLLAPSE = re.compile(r"-{2,}")


def slugify_novel(name: str) -> str:
    """Convert a novel folder/name to a canonical, filesystem-safe slug.

    Rules: lowercase; any run of non-alphanumeric chars (spaces, underscores,
    punctuation) -> single ``-``; collapse repeated ``-``; strip edges. Empty
    input falls back to ``"unknown"`` so we never return an empty path
    component. Underscores are treated as separators (not preserved) so the
    slug-style on-disk dir is always hyphen-delimited.

    Examples:
        >>> slugify_novel("Daoist Master of Qing Xuan")
        'daoist-master-of-qing-xuan'
        >>> slugify_novel("a-will-eternal1")
        'a-will-eternal1'
        >>> slugify_novel("Foo -- Bar__ Baz")
        'foo-bar-baz'
    """
    if not name:
        return "unknown"
    slug = _NON_ALNUM.sub("-", name.strip().lower())
    slug = _DASH_COLLAPSE.sub("-", slug).strip("-")
    return slug or "unknown"


def novel_id_from_slug(slug: str) -> str:
    """Build the DB ``novel_id`` for an already-slugified novel slug.

    The DB convention (set by MemoryManager) is ``novel_<slug>`` with hyphens
    turned to underscores so the body is a valid Python identifier suffix.
    """
    if not slug:
        return "novel_unknown"
    body = slug.replace("-", "_")
    return f"novel_{body}"


def novel_id_from_name(name: str) -> str:
    """One-shot: novel folder name -> canonical DB ``novel_id``."""
    return novel_id_from_slug(slugify_novel(name))


def slug_from_novel_id(novel_id: str) -> str:
    """Reverse of `novel_id_from_slug` (best-effort, for display only)."""
    if novel_id.startswith("novel_"):
        return novel_id[len("novel_"):].replace("_", "-")
    return novel_id


def resolve_novel_input_dir(root: Path, name: str) -> Optional[Path]:
    """Find the on-disk input directory for a novel given by `name`.

    Tries, in order:
      1. `root / name`               (exact folder, preserves spaces/caps)
      2. `root / slugify_novel(name)` (slugified folder)
      3. Scan `root` for ANY subdirectory whose own slug matches the slug of
         `name` (so the raw folder "Daoist Master of Qing Xuan" is found even
         when the user/caller passes the slug "daoist-master-of-qing-xuan")

    Returns the first existing directory, else ``None``. This lets users keep
    either naming convention (raw "Daoist Master of Qing Xuan" or slug
    `daoist-master-of-qing-xuan`) while the code resolves both identically.
    """
    if not name:
        return None
    root_path = Path(root)
    requested_slug = slugify_novel(name)
    # Order matters: exact (preserves the caller's intent) -> slug -> scan.
    candidates = [root_path / name, root_path / requested_slug]
    seen: set[str] = set()
    for cand in candidates:
        key = str(cand)
        if key in seen:
            continue
        seen.add(key)
        if cand.is_dir():
            return cand
    # Fallback: case-insensitive slug match against every subfolder.
    if root_path.is_dir():
        for child in root_path.iterdir():
            if not child.is_dir() or child.name.startswith("."):
                continue
            if slugify_novel(child.name) == requested_slug:
                return child
    return None


def is_canonical_novel_dir(entry_name: str) -> bool:
    """True for real novel folders; False for dotfolders like ``.versions``.

    Used by output-dir scanners so they never treat an infrastructure
    directory (e.g. `data/output/.versions/`) as a novel.
    """
    return bool(entry_name) and not entry_name.startswith(".")