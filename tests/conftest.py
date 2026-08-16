"""Shared test fixtures + import path setup for the translation pipeline."""

from __future__ import annotations

from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).parent
FIXTURES = TESTS_DIR / "fixtures"


@pytest.fixture
def glossary_path() -> Path:
    return FIXTURES / "glossary-minimal.json"


@pytest.fixture
def chapter_path() -> Path:
    return FIXTURES / "chapter-en-0001.md"


@pytest.fixture
def human_path() -> Path:
    return FIXTURES / "chapter-human-0001.md"


@pytest.fixture
def context_sample() -> dict:
    import json

    return json.loads((FIXTURES / "context-sample.json").read_text(encoding="utf-8"))


@pytest.fixture
def glossary(glossary_path):
    from src.pipeline.glossary import Glossary

    return Glossary(glossary_path)


@pytest.fixture
def config_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "config"


@pytest.fixture
def rules_engine(config_dir):
    from src.pipeline.rules import RulesEngine

    return RulesEngine.load(config_dir / "rules.json")


class MockOllama:
    """Scriptable fake client: caller supplies a mapping call->response."""

    def __init__(self, model="mock", temperature=0.2):
        self.model = model
        self.temperature = temperature
        self.calls: list[dict] = []
        self.responses: list[str] = []
        self._i = 0
        self.ping_result = True
        self.models_result = ["mock"]

    def generate(self, prompt, system="", temperature=None, num_predict=None):
        self.calls.append(
            {"prompt": prompt, "system": system, "temperature": temperature, "num_predict": num_predict}
        )
        if not self.responses:
            return ""
        resp = self.responses[self._i % len(self.responses)]
        self._i += 1
        return resp

    def ping(self):
        return self.ping_result

    def models(self):
        return self.models_result


@pytest.fixture
def mock_ollama() -> MockOllama:
    return MockOllama()