"""JSON-backed sliding context buffer (SPEC §9, R-CTX-*).

- keeps the last 2 chunks verbatim, older content folded into a summary
- flushes on scene change
- tracks ``active_speakers`` pronoun continuity for the Verifier/Translator
- survives crashes (file-backed) and archives when a chapter completes
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

from .models import Chunk
from .prompt_builder import render_context

DEFAULT_MAX_CHUNKS = 2
DEFAULT_MAX_SUMMARY_TOKENS = 150


class ContextBuffer:
    def __init__(self, path: Optional[Path] = None):
        self.path = path
        self.data: Dict[str, Any] = {
            "chapter_id": "",
            "scene_id": "",
            "preceding_summary": "",
            "preceding_chunks": [],
            "active_speakers": {},
            "max_preceding_chunks": DEFAULT_MAX_CHUNKS,
            "max_summary_tokens": DEFAULT_MAX_SUMMARY_TOKENS,
        }
        if path is not None and path.is_file():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    self.data.update({k: v for k, v in loaded.items() if k in self.data})
            except (json.JSONDecodeError, OSError):
                pass

    def _save(self) -> None:
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8"
            )

    # -- accessors --------------------------------------------------------- #
    def get(self, key: str, default=None):
        return self.data.get(key, default)

    def snapshot(self) -> Dict[str, Any]:
        return dict(self.data)

    def render(self) -> str:
        return render_context(self.data)

    # -- mutations --------------------------------------------------------- #
    def start_scene(
        self,
        chapter_id: str,
        scene_id: str,
        *,
        flush: bool = False,
        summary: str = "",
    ) -> None:
        if flush or self.data["scene_id"] != scene_id:
            self.data["scene_id"] = scene_id
            if flush:
                self.data["preceding_chunks"] = []
                self.data["preceding_summary"] = summary or ""
        if not self.data["chapter_id"]:
            self.data["chapter_id"] = chapter_id
        self._save()

    def append_chunk(
        self,
        chunk: Chunk,
        *,
        emotional_tone: str = "",
        max_tokens: Optional[int] = None,
    ) -> None:
        if not chunk.translated_text:
            return
        cap = max_tokens or int(self.data.get("max_summary_tokens", DEFAULT_MAX_SUMMARY_TOKENS))
        record = {
            "chunk_id": chunk.id,
            "translated_text": chunk.translated_text,
            "speakers": chunk.speakers,
            "emotional_tone": emotional_tone or "",
        }
        chunks = self.data["preceding_chunks"]
        # Fold the oldest chunk into the running summary if we exceed the cap.
        max_chunks = int(self.data.get("max_preceding_chunks", DEFAULT_MAX_CHUNKS))
        while len(chunks) >= max_chunks and chunks:
            oldest = chunks.pop(0)
            if oldest.get("translated_text"):
                suffix = oldest["translated_text"][: max(max_tokens or cap * 3, 10)]
                new_summary = self.data["preceding_summary"]
                if new_summary:
                    new_summary += " | " + suffix
                else:
                    new_summary = suffix
                # keep summary under its own token budget
                self.data["preceding_summary"] = new_summary[: max_chunks * (cap * 3 + 30)]
        chunks.append(record)
        self._save()

    def update_active_speakers(
        self, speakers: Dict[str, Dict[str, Any]]
    ) -> None:
        merged = dict(self.data.get("active_speakers", {}))
        for name, info in speakers.items():
            if not name:
                continue
            prev = merged.get(name, {})
            merged[name] = {**prev, **info}
        self.data["active_speakers"] = merged
        self._save()

    def archive(self, archive_dir: Path, chapter_id: str) -> None:
        archive_dir = Path(archive_dir)
        archive_dir.mkdir(parents=True, exist_ok=True)
        out = archive_dir / f"{chapter_id}.json"
        out.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        self.reset()

    def reset(self) -> None:
        self.data = {
            "chapter_id": "",
            "scene_id": "",
            "preceding_summary": "",
            "preceding_chunks": [],
            "active_speakers": {},
            "max_preceding_chunks": self.data.get("max_preceding_chunks", DEFAULT_MAX_CHUNKS),
            "max_summary_tokens": self.data.get("max_summary_tokens", DEFAULT_MAX_SUMMARY_TOKENS),
        }
        self._save()