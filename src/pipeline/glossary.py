"""Per-novel glossary loading, indexing, filtering and prompt sections.

Handles both the nested ``categories`` layout (current project) and the older
flat ``entries`` layout.  Terms are matched longest-first so ``Haunted House``
never partially matches ``House``.

Scale support (NEW_TODO.md §5): ``load_hierarchy`` merges a global glossary
(base) with a novel-specific one (overrides), and ``PendingGlossary`` gives the
'Detected -> Pending -> Proposed -> Locked -> Immutable' term lifecycle a
persistent queue so new terms discovered by the Verifier can be triaged by a
human instead of being silently injected.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from .markdownio import hash_version


def load_entries(data: Any) -> List[Dict[str, Any]]:
    """Normalize any supported glossary JSON shape into a list of entry dicts."""
    if isinstance(data, dict):
        if isinstance(data.get("categories"), dict):
            out: List[Dict[str, Any]] = []
            for cat in data["categories"].values():
                if isinstance(cat, dict) and isinstance(cat.get("entries"), list):
                    out.extend(cat["entries"])
            return out
        if isinstance(data.get("entries"), list):
            return data["entries"]
        if data.get("term") or data.get("en"):
            return [data]
        return []
    if isinstance(data, list):
        return [e for e in data if isinstance(e, dict)]
    return []


class Glossary:
    """Indexed, longest-first glossary with alias + variant support."""

    def __init__(self, path: Optional[Path | str] = None, entries: Optional[List[Dict[str, Any]]] = None):
        self.path = Path(path) if path is not None and str(path) else None
        self.version = ""
        self.raw_meta: Dict[str, Any] = {}
        self._flat: List[Dict[str, Any]] = []
        if self.path is not None and self.path.is_file():
            text = self.path.read_text(encoding="utf-8")
            self.version = hash_version(text)
            data = json.loads(text)
            if isinstance(data, dict):
                self.raw_meta = {k: v for k, v in data.items() if k != "categories"}
            self._flat = load_entries(data)
        elif entries is not None:
            self._flat = load_entries(entries)
        self.index: List[Dict[str, Any]] = self._build_index(self._flat)

    @staticmethod
    def _build_index(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        idx: List[Dict[str, Any]] = []
        for e in entries:
            en = (e.get("term") or e.get("en") or "").strip()
            my = (e.get("translation") or e.get("my") or "").strip()
            if not en or not my:
                continue
            idx.append(
                {
                    "en": en,
                    "my": my,
                    "zh": (e.get("original_name") or e.get("zh") or "").strip(),
                    "category": e.get("category", ""),
                    "gender": e.get("gender", "neutral"),
                    "formality": e.get("formality", "mixed"),
                    "locked": bool(e.get("locked", True)),
                    "aliases": list(e.get("aliases") or [en]),
                    "pronoun": e.get("pronoun_dialogue", ""),
                    "particles": list(e.get("particles") or []),
                    "my_variants": list(e.get("my_variants") or e.get("variants") or []),
                }
            )
        idx.sort(key=lambda d: len(d["en"]), reverse=True)
        return idx

    # -- matching --------------------------------------------------------- #
    def aliases_for(self, text: str) -> List[str]:
        """Glossary English aliases present in ``text`` (longest first)."""
        found: List[str] = []
        for e in self.index:
            if any(a in text for a in e["aliases"]):
                found.append(e["en"])
        return found

    def entries_for(self, text: str) -> List[Dict[str, Any]]:
        """Entries whose alias appears in ``text``."""
        return [e for e in self.index if any(a in text for a in e["aliases"])]

    def speakers_in(self, text: str) -> List[str]:
        """Character entries appearing in ``text``."""
        return [e["en"] for e in self.entries_for(text) if e.get("category") == "character"]

    def term_set(self) -> set:
        s: set = set()
        for e in self.index:
            s.add(e["en"])
            for a in e["aliases"]:
                s.add(a)
        return s

    # -- loanword allowlist (todo.md §2.1 / new_todo.md §7) ---------------- #
    def loanword_allowlist(self) -> set:
        """Explicit Latin loanwords permitted in output (``raw_meta`` key)."""
        raw = self.raw_meta.get("loanword_allowlist") or []
        if isinstance(raw, list):
            return {str(x).strip() for x in raw if str(x).strip()}
        return set()

    # -- prompt section ----------------------------------------------------- #
    def section(
        self,
        texts: Optional[Sequence[str]] = None,
        dynamic: bool = False,
        max_terms: int = 100,
    ) -> str:
        """Render ``- EN (ZH) = MY`` lines; ``dynamic`` keeps only matched terms."""
        entries = self.index
        if dynamic and texts is not None:
            haystack = " ".join(t or "" for t in texts)
            entries = [e for e in entries if any(a in haystack for a in e["aliases"])]
        entries = entries[:max_terms]
        if not entries:
            return ""
        lines = ["GLOSSARY (CRITICAL - use EXACTLY these spellings):"]
        for e in entries:
            ref = f" ({e['zh']})" if e.get("zh") else ""
            lines.append(f"- {e['en']}{ref} = {e['my']}")
        return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Glossary hierarchy (NEW_TODO.md §5A) + lock lifecycle (§5B)
# --------------------------------------------------------------------------- #
def merge_glossary_files(*paths: Optional[Path | str]) -> List[Dict[str, Any]]:
    """Merge term entries from several glossary JSON files, later files win.

    First file found is treated as the *base* layer (e.g. ``global.json`` that
    applies to every novel); subsequent files override entries with the same
    ``term``/``en`` key (e.g. the novel-specific glossary).  Terms unique to a
    layer are kept from every layer.
    """
    merged: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    for raw in paths:
        if not raw:
            continue
        path = Path(raw)
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        for e in load_entries(data):
            key = str(e.get("term") or e.get("en") or "").strip()
            if not key:
                continue
            if key not in merged:
                order.append(key)
            merged[key] = e
    return [merged[k] for k in order]


class PendingGlossary:
    """Persistent pending-term queue (R-GLOSS-03, NEW_TODO.md §5B).

    Lifecycle: *Detected* (Verifier flags a new proper noun) -> *Pending*
    (this file) -> human curates a Myanmar rendering -> *Locked* (moved into the
    active glossary).  Entries cap at ``max_pending`` so a runaway detector
    cannot grow the queue unbounded between curation sessions.
    """

    def __init__(self, path: Optional[Path | str] = None, max_pending: int = 50):
        self.path = Path(path) if path is not None and str(path) else None
        self.max_pending = int(max_pending)
        self.entries: List[Dict[str, Any]] = []
        if self.path is not None and self.path.is_file():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    self.entries = [e for e in data if isinstance(e, dict)]
            except (json.JSONDecodeError, OSError):
                self.entries = []

    def detected(self, en: str, source_snippet: str = "") -> bool:
        """Add a newly-detected term (no-op if already pending)."""
        en = (en or "").strip()
        if not en:
            return False
        if any(e.get("en") == en for e in self.entries):
            return False
        if len(self.entries) >= self.max_pending:
            return False
        self.entries.append({
            "en": en,
            "state": "pending",
            "source_snippet": (source_snippet or "")[:120],
            "detected_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "my": "",
        })
        self.save()
        return True

    def curate(self, en: str, my: str, *, locked: bool = True) -> Optional[Dict[str, Any]]:
        """Assign a Myanmar rendering, marking the term proposed/locked."""
        for e in self.entries:
            if e.get("en") == en:
                e["my"] = (my or "").strip()
                e["state"] = "locked" if locked else "proposed"
                e["locked_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                self.save()
                return e
        return None

    def proposed(self) -> List[Dict[str, Any]]:
        return [e for e in self.entries if e.get("state") == "proposed"]

    def pending_names(self) -> List[str]:
        return [str(e.get("en")) for e in self.entries]

    def remove(self, en: str) -> bool:
        before = len(self.entries)
        self.entries = [e for e in self.entries if e.get("en") != en]
        changed = len(self.entries) != before
        if changed:
            self.save()
        return changed

    def save(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.entries, ensure_ascii=False, indent=2), encoding="utf-8"
        )