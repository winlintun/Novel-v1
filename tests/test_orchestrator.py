"""End-to-end orchestration tests with a scriptable fake Ollama."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from src.pipeline.orchestrator import Orchestrator, PipelineConfig

AUDIT_JSON = (
    '{"grade":"B","scores":{"flow":80,"voice_consistency":80,"terminology":100,'
    '"literary_quality":80},"weighted_total":84.0,"verdict":"pass","suggestions":[]}'
)


class ScriptedClient:
    """Mimics OllamaClient.generate; synthesizes per-paragraph Burmese from the prompt."""

    def __init__(self, glossary_index, *, two_pass=False, audit=True):
        self.model = "mock"
        self.temperature = 0.2
        self.glossary_index = glossary_index
        self.two_pass = two_pass
        self.audit = audit
        self.calls: list[dict] = []

    def generate(self, prompt, system="", temperature=None, num_predict=None, **kwargs):
        self.calls.append(prompt)
        if self.audit and prompt.strip().startswith("Audit the following"):
            return AUDIT_JSON
        source = self._extract_source(prompt)
        if source is None:
            # polish pass without source marker -> pass the draft through
            draft = self._extract_draft(prompt)
            return draft if draft else "ဒုတိယစာ ဖြစ်သည်။"
        return self._translate(source)

    # -- builders ---------------------------------------------------------- #
    def _extract_source(self, prompt: str):
        m = re.search(r'SOURCE TEXT:\n"""\n(.*?)\n"""', prompt, re.DOTALL)
        return m.group(1) if m else None

    def _extract_draft(self, prompt: str):
        m = re.search(r'DRAFT TEXT:\n"""\n(.*?)\n"""', prompt, re.DOTALL)
        return m.group(1) if m else None

    def _translate(self, source: str) -> str:
        paras = [p for p in source.split("\n\n")]
        out = [self._translate_para(p) for p in paras]
        return "\n\n".join(out)

    def _translate_para(self, para: str) -> str:
        if para.strip() in ("---", "***", ""):
            return para.strip() or "…"
        hits = []
        for e in self.glossary_index:
            if any(a and a in para for a in (e.get("aliases") or [e.get("en", "")])):
                hits.append(e["my"])
        if hits:
            return "".join(hits) + " က အကြောင်းအရာတစ်ခု ဖြစ်လာလေသည်။"
        return "ဤအကြောင်းအရာသည် မြန်မာလို ဘာသာပြန်ထားသော စာကြောင်း ဖြစ်လေသည်။"

    def ping(self) -> bool:
        return True

    def models(self):
        return ["mock"]


@pytest.fixture
def orch(tmp_path, chapter_path, glossary_path, config_dir):
    from src.pipeline.glossary import Glossary

    glossary = Glossary(glossary_path)
    client = ScriptedClient(glossary.index)
    config = PipelineConfig(
        config_dir=config_dir,
        output_dir=tmp_path / "out",
        skip_audit=False,
        two_pass=False,
        force=False,
    )
    return Orchestrator(config, client, log=lambda msg: None), glossary_path, chapter_path


def test_e2e_translate_write_output(tmp_path, chapter_path, glossary_path, config_dir):
    """Full run: chunks translated, verified, audited, files committed."""
    from src.pipeline.glossary import Glossary

    glossary = Glossary(glossary_path)
    client = ScriptedClient(glossary.index)
    config = PipelineConfig(config_dir=config_dir, output_dir=tmp_path / "out",
                            two_pass=False, skip_audit=False)
    orch = Orchestrator(config, client, log=lambda msg: None)

    summary = orch.run_chapter(chapter_path, novel="test", glossary_path=glossary_path)

    assert summary["state"] == "APPROVED"
    assert summary["chunks_total"] > 0
    assert summary["chunks_verified"] == summary["chunks_total"]
    assert summary["chunks_failed"] == 0
    assert summary["audit_grade"] in ("A", "B+", "B")

    out_dir = tmp_path / "out" / "test"
    md = out_dir / "chapter-my-0001.md"
    assert md.is_file()
    text = md.read_text(encoding="utf-8")
    assert "Chen Ge" not in text or "ချန်ဂီ" in text
    assert "သရဲစံအိမ်" in text  # canonical glossary term
    # SPEC §5.2 / NEW_TODO §5.15: pipeline metadata in the frontmatter
    assert "grade:" in text and "glossary_version:" in text
    assert "prompt_version:" in text and "translated_by:" in text
    assert (out_dir / "metadata.json").is_file()
    meta = json.loads((out_dir / "metadata.json").read_text(encoding="utf-8"))
    assert "prompt_version" in meta
    assert (out_dir / "audit-report.json").is_file()
    assert (out_dir / "archive" / "context").is_dir()
    # NEW_TODO §3A: fleet metrics collected when monitoring is enabled
    assert (out_dir / "fleet.db").is_file()
    assert (out_dir / "fleet-report.json").is_file()
    fleet = json.loads((out_dir / "fleet-report.json").read_text(encoding="utf-8"))
    assert "window" in fleet and "alerts" in fleet and "stop_the_line" in fleet


def test_e2e_resume_skips_done_chapter(tmp_path, chapter_path, glossary_path, config_dir):
    from src.pipeline.glossary import Glossary

    glossary = Glossary(glossary_path)
    client = ScriptedClient(glossary.index)
    config = PipelineConfig(config_dir=config_dir, output_dir=tmp_path / "out",
                            two_pass=False, skip_audit=True)
    orch = Orchestrator(config, client, log=lambda msg: None)

    first = orch.run_chapter(chapter_path, novel="test", glossary_path=glossary_path)
    assert first["state"] == "APPROVED"
    assert len(client.calls) > 0

    calls_before = len(client.calls)
    second = orch.run_chapter(chapter_path, novel="test", glossary_path=glossary_path)
    assert second["state"] == "SKIPPED"
    assert len(client.calls) == calls_before


def test_e2e_force_retranslates(tmp_path, chapter_path, glossary_path, config_dir):
    from src.pipeline.glossary import Glossary

    glossary = Glossary(glossary_path)
    client = ScriptedClient(glossary.index)
    config = PipelineConfig(config_dir=config_dir, output_dir=tmp_path / "out",
                            two_pass=False, skip_audit=True)
    orch = Orchestrator(config, client, log=lambda msg: None)
    orchid2 = Orchestrator(PipelineConfig(config_dir=config_dir, output_dir=tmp_path / "out",
                                          two_pass=False, skip_audit=True, force=True),
                           client, log=lambda msg: None)

    orch.run_chapter(chapter_path, novel="test", glossary_path=glossary_path)
    calls_before = len(client.calls)
    second = orchid2.run_chapter(chapter_path, novel="test", glossary_path=glossary_path)
    assert second["state"] == "APPROVED"
    assert len(client.calls) > calls_before


def test_e2e_audit_failure_leads_needs_human(tmp_path, chapter_path, glossary_path, config_dir):
    from src.pipeline.glossary import Glossary

    glossary = Glossary(glossary_path)

    class FailAuditClient(ScriptedClient):
        audit_response = (
            '{"grade":"D","scores":{"flow":40,"voice_consistency":40,'
            '"terminology":50,"literary_quality":50},"weighted_total":45.0,'
            '"verdict":"fail","suggestions":[]}'
        )

        def generate(self, prompt, system="", temperature=None, num_predict=None, **kwargs):
            self.calls.append(prompt)
            if prompt.strip().startswith("Audit the following"):
                return self.audit_response
            source = re.search(r'SOURCE TEXT:\n"""\n(.*?)\n"""', prompt, re.DOTALL)
            if source is None:
                return "ဒုတိယစာ ဖြစ်သည်။"
            return self._translate(source.group(1))

    client = FailAuditClient(glossary.index)
    config = PipelineConfig(config_dir=config_dir, output_dir=tmp_path / "out",
                            two_pass=False)
    orch = Orchestrator(config, client, log=lambda msg: None)
    summary = orch.run_chapter(chapter_path, novel="test", glossary_path=glossary_path)
    assert summary["state"] == "NEEDS_HUMAN"
    assert summary["audit_grade"] == "D"


def test_e2e_partial_chunk_failure_still_commits(tmp_path, chapter_path, glossary_path, config_dir):
    """If some chunks fail verification, the run still commits what translated."""
    from src.pipeline.glossary import Glossary

    glossary = Glossary(glossary_path)
    client = ScriptedClient(glossary.index)

    # First chunk's draft + every fix-mode retranslate returns broken latin text,
# so the chunk ultimately fails verification (R-FORBID-03 + R-GLOSS-01).
    real_generate = client.generate
    broken = "Broken english fragment ဒီစာကို ဘာသာပြန်ဖို့ မလိုပါ။"
    state = {"broken_done": False}

    def flaky_generate(prompt, system="", temperature=None, num_predict=None, **kwargs):
        is_src = client._extract_source(prompt) is not None
        is_fix = "FIX MODE" in prompt
        if is_src and (not state["broken_done"] or is_fix):
            if is_src and not is_fix:
                state["broken_done"] = True
            return broken
        return real_generate(prompt, system=system, temperature=temperature)

    client.generate = flaky_generate
    config = PipelineConfig(config_dir=config_dir, output_dir=tmp_path / "out",
                            two_pass=False, skip_audit=True)
    orch = Orchestrator(config, client, log=lambda msg: None)
    summary = orch.run_chapter(chapter_path, novel="test", glossary_path=glossary_path)

    # Output still written; failed chunks reported.
    assert (tmp_path / "out" / "test" / "chapter-my-0001.md").is_file()
    assert summary["chunks_failed"] >= 1 and summary["chunks_verified"] >= 0


def test_e2e_script_gate_blocks_foreign_script(tmp_path, chapter_path, glossary_path, config_dir):
    """todo.md §2.1: a leak on the assembled body forces NEEDS_HUMAN.

    Patching the gate is deterministic: even with a clean per-chunk run, an
    assembly-level failure must block APPROVE and never write the polluted MD.
    """
    import src.pipeline.orchestrator as orch_mod
    from src.pipeline.glossary import Glossary

    glossary = Glossary(glossary_path)
    client = ScriptedClient(glossary.index)
    config = PipelineConfig(config_dir=config_dir, output_dir=tmp_path / "out",
                            two_pass=False, skip_audit=True)

    real_gate = orch_mod.assembly_script_gate
    orch_mod.assembly_script_gate = lambda text, loanword_allowlist=None: (False, "ทดสอบ foreign leak")
    try:
        orch = Orchestrator(config, client, log=lambda msg: None)
        summary = orch.run_chapter(chapter_path, novel="test", glossary_path=glossary_path)
    finally:
        orch_mod.assembly_script_gate = real_gate

    assert summary["state"] == "NEEDS_HUMAN"
    md = tmp_path / "out" / "test" / "chapter-my-0001.md"
    assert not md.is_file()
    meta = json.loads((tmp_path / "out" / "test" / "metadata.json").read_text(encoding="utf-8"))
    assert meta["state"] == "NEEDS_HUMAN"
    assert "leak" in meta.get("assembly", {}).get("script_gate", "")