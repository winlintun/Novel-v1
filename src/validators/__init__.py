"""Validator registry for the Dataset Alignment Pipeline."""

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class ValidatorContext:
    novel: str
    chapter_ids: list[int] = field(default_factory=list)


@runtime_checkable
class Validator(Protocol):
    name: str
    def run(self, ctx: ValidatorContext) -> int: ...


_REGISTRY: dict[str, type] = {}


def register(cls):
    _REGISTRY[cls.name] = cls
    return cls


def run_all(ctx: ValidatorContext, names: list[str]) -> dict[str, int]:
    import logging
    counts: dict[str, int] = {}
    for name in names:
        cls = _REGISTRY.get(name)
        if cls is None:
            counts[name] = 0
            continue
        try:
            counts[name] = cls().run(ctx)
        except Exception as e:
            logging.getLogger(__name__).exception(f"Validator {name} failed: {e}")
            counts[name] = 0
    return counts


from . import structural
from . import content
from . import linguistic
from . import metadata
from . import noise
from . import quality
