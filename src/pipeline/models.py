"""SPEC.md §3 data models + §4 state machine.

Everything here is plain dataclasses so it serializes to / from JSON for
resume-safe metadata and context buffers.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class State(str, Enum):
    IDLE = "IDLE"
    CHUNKING = "CHUNKING"
    TRANSLATING = "TRANSLATING"
    VERIFYING = "VERIFYING"
    REVISE = "REVISE"
    RETRY = "RETRY"
    AUDITING = "AUDITING"
    APPROVED = "APPROVED"
    NEEDS_HUMAN = "NEEDS_HUMAN"
    FAILED = "FAILED"


class ChunkStatus(str, Enum):
    PENDING = "pending"
    TRANSLATED = "translated"
    VERIFIED = "verified"
    FAILED = "failed"


class IssueSeverity(str, Enum):
    CRITICAL = "critical"
    FATAL = "fatal"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class IssueCategory(str, Enum):
    GLOSSARY = "glossary"
    VOICE = "voice"
    FORMAT = "format"
    COHERENCE = "coherence"
    REGISTER = "register"


@dataclass
class Issue:
    severity: str
    category: str
    rule_id: str = ""
    location: Dict[str, Any] = field(default_factory=dict)
    message: str = ""
    suggestion: str = ""
    auto_fixed: bool = False

    @property
    def blocks_approval(self) -> bool:
        return self.severity in (
            IssueSeverity.CRITICAL,
            IssueSeverity.FATAL,
            IssueSeverity.ERROR,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "severity": self.severity,
            "category": self.category,
            "rule_id": self.rule_id,
            "location": self.location,
            "message": self.message,
            "suggestion": self.suggestion,
            "auto_fixed": self.auto_fixed,
        }


@dataclass
class Chunk:
    id: str
    chapter_id: str
    scene_id: str
    sequence: int
    type: str = "mixed"
    paragraphs: List[str] = field(default_factory=list)
    overlap_paras: List[str] = field(default_factory=list)
    translated_text: str = ""
    speakers: List[str] = field(default_factory=list)
    status: str = ChunkStatus.PENDING.value
    tokens_in: int = 0
    tokens_out: int = 0

    @property
    def source_text(self) -> str:
        return "\n\n".join(self.paragraphs)

    @property
    def preceding_overlap(self) -> str:
        return "\n\n".join(self.overlap_paras)

    @property
    def body_paragraphs(self) -> List[str]:
        return self.paragraphs[len(self.overlap_paras):]

    def translated_paragraphs(self) -> List[str]:
        """Split the translated block back into paragraphs."""
        if not self.translated_text:
            return []
        return [p.strip() for p in self.translated_text.split("\n\n") if p.strip()]

    def body_translated_paragraphs(self) -> List[str]:
        paras = self.translated_paragraphs()
        overlap_n = len(self.overlap_paras)
        return paras[overlap_n:] if overlap_n and len(paras) >= overlap_n else paras

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "chapter_id": self.chapter_id,
            "scene_id": self.scene_id,
            "sequence": self.sequence,
            "type": self.type,
            "paragraphs": self.paragraphs,
            "overlap_paras": self.overlap_paras,
            "translated_text": self.translated_text,
            "speakers": self.speakers,
            "status": self.status,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
        }


@dataclass
class GlossaryEntry:
    term: str
    translation: str
    original_name: str = ""
    category: str = ""
    gender: str = "neutral"
    formality: str = "mixed"
    locked: bool = True
    aliases: List[str] = field(default_factory=list)
    pronoun: str = ""
    particles: List[str] = field(default_factory=list)
    my_variants: List[str] = field(default_factory=list)
    first_appearance_chapter: int = 1
    notes: str = ""

    @property
    def en(self) -> str:
        return self.term

    @property
    def my(self) -> str:
        return self.translation


@dataclass
class FewShotPair:
    id: str
    category: str = "mixed"
    source: str = ""
    translation: str = ""
    context_note: str = ""


@dataclass
class ContextBuffer:
    chapter_id: str = ""
    scene_id: str = ""
    preceding_summary: str = ""
    preceding_chunks: List[Dict[str, Any]] = field(default_factory=list)
    active_speakers: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    max_preceding_chunks: int = 2
    max_summary_tokens: int = 150

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chapter_id": self.chapter_id,
            "scene_id": self.scene_id,
            "preceding_summary": self.preceding_summary,
            "preceding_chunks": self.preceding_chunks,
            "active_speakers": self.active_speakers,
            "max_preceding_chunks": self.max_preceding_chunks,
            "max_summary_tokens": self.max_summary_tokens,
        }


@dataclass
class AuditReport:
    grade: str = "F"
    scores: Dict[str, int] = field(default_factory=lambda: {"flow": 0, "voice_consistency": 0, "terminology": 0, "literary_quality": 0})
    weighted_total: float = 0.0
    verdict: str = "needs_human_review"
    suggestions: List[str] = field(default_factory=list)
    comparison: Dict[str, Any] = field(default_factory=dict)
    audited_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "grade": self.grade,
            "scores": self.scores,
            "weighted_total": self.weighted_total,
            "verdict": self.verdict,
            "suggestions": self.suggestions,
            "comparison": self.comparison,
            "audited_at": self.audited_at,
        }


@dataclass
class TranslationUnit:
    chapter_id: str = ""
    source_file: str = ""
    output_file: str = ""
    model: str = ""
    temperature: float = 0.2
    glossary_version: str = ""
    style_guide_version: str = ""
    prompt_version: str = ""
    chunks: List[Chunk] = field(default_factory=list)
    started_at: str = ""
    completed_at: str = ""
    state: str = State.IDLE.value
    final_grade: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "unit_id": str(uuid.uuid4()),
            "chapter_id": self.chapter_id,
            "source_file": self.source_file,
            "output_file": self.output_file,
            "model": self.model,
            "temperature": self.temperature,
            "glossary_version": self.glossary_version,
            "style_guide_version": self.style_guide_version,
            "prompt_version": self.prompt_version,
            "chunks": [c.to_dict() for c in self.chunks],
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "state": self.state,
            "final_grade": self.final_grade,
        }