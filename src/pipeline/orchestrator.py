"""Orchestrator (SKILL_orchestrator.md, SPEC §2.1/§4/§6).

Coordinates: ingest → chunk → per-chunk translate/postprocess/verify/revise →
audit → commit.  Follows the SPEC state machine and error matrix, is
resume-safe (skip already-committed chapters unless forced) and commits after
every chunk plus on KeyboardInterrupt.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

from . import markdownio, postprocessor
from .assembly import (
    assembly_completeness,
    assembly_script_gate,
    check_naming_consistency,
    dedup_assembled_paras,
    normalize_hygiene,
    translate_loanwords,
)
from .auditor import Auditor
from .chunker import ChunkerConfig, build_chunks
from .context_buffer import ContextBuffer
from .fleet import FleetMonitor
from .glossary import Glossary
from .models import Chunk, FewShotPair, State, TranslationUnit
from .ollama_client import OllamaClient
from .prompt_builder import render_few_shots, select_few_shots
from .quality import quality_score
from .rules import RulesEngine
from .translator import Translator
from .verifier import verify


class PipelineError(RuntimeError):
    pass


class PipelineConfig:
    def __init__(
        self,
        *,
        config_dir: Optional[Path | str] = None,
        output_dir: Optional[Path | str] = None,
        model: str = "padauk-gemma:q8_0",
        temperature: float = 0.2,
        two_pass: bool = True,
        max_ctx: int = 8192,
        max_revise: int = 3,
        skip_audit: bool = False,
        auto_fix: bool = True,
        myanmar_numbers: bool = False,
        dry_run: int = 0,
        limit: int = 0,
        force: bool = False,
        analyze: bool = True,
        roles: Optional[Dict[str, Any]] = None,
        prompts_dir: Optional[Path | str] = None,
        monitor: bool = True,
    ):
        self.config_dir = Path(config_dir) if config_dir else Path("config")
        self.output_dir = Path(output_dir) if output_dir else Path("output")
        self.model = model
        self.temperature = temperature
        self.two_pass = two_pass
        self.max_ctx = max_ctx
        self.max_revise = max_revise
        self.skip_audit = skip_audit
        self.auto_fix = auto_fix
        self.myanmar_numbers = myanmar_numbers
        self.dry_run = dry_run
        self.limit = limit
        self.force = force
        self.analyze = analyze
        self.roles = dict(roles or {})
        self.prompts_dir = Path(prompts_dir) if prompts_dir else Path("prompts")
        self.monitor = monitor


class Orchestrator:
    def __init__(
        self,
        config: PipelineConfig,
        client: OllamaClient,
        *,
        log: Callable[[str], None] = print,
    ):
        self.config = config
        self.client = client
        self.logger = log
        self.chunker = ChunkerConfig.load(config.config_dir / "chunking_rules.json")
        self.rules = RulesEngine.load(config.config_dir / "rules.json")
        self.style_guide = self._load_json(config.config_dir / "style_guide.json")
        self.roles = self._load_roles(config)
        self.prompt_version = self._prompts_hash(config.prompts_dir)
        self.auditor = Auditor(client, roles=self.roles)
        self.translator = Translator(
            client,
            two_pass=config.two_pass,
            temperature=config.temperature,
            max_ctx=config.max_ctx,
            roles=self.roles,
        )
        self.states: List[str] = []

    @staticmethod
    def _load_json(path: Path) -> Dict[str, Any]:
        if path.is_file():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return {}
        return {}

    @classmethod
    def _load_roles(cls, config: PipelineConfig) -> Dict[str, Dict[str, Any]]:
        """Role->model assignment (NEW_TODO §4): ``config/roles.json`` wins over
        an explicit override; missing roles fall back to the base ``--model``."""
        loaded = cls._load_json(config.config_dir / "roles.json").get("roles", {})
        if not isinstance(loaded, dict):
            loaded = {}
        roles: Dict[str, Dict[str, Any]] = {}
        for name, spec in {**loaded, **config.roles}.items():
            if isinstance(spec, dict):
                roles[str(name)] = {
                    "model": spec.get("model"),
                    "temperature": spec.get("temperature"),
                }
        return roles

    @staticmethod
    def _prompts_hash(prompts_dir: Path) -> str:
        """SPEC §7 prompt_version: hash of the ``prompts/`` micro-prompt files."""
        if not prompts_dir.is_dir():
            return ""
        parts = []
        for f in sorted(prompts_dir.glob("*.txt")):
            try:
                parts.append(f.name + ":" + f.read_text(encoding="utf-8"))
            except OSError:
                continue
        if not parts:
            return ""
        return markdownio.hash_version("\n".join(parts))

    def _state(self, state: State, reason: str = "") -> None:
        self.states.append(state.value)
        self.logger(f"[state] {state.value}{' — ' + reason if reason else ''}")

    # ------------------------------------------------------------------ #
    # Few-shot loading (human EN<->MY pairs)
    # ------------------------------------------------------------------ #
    def load_few_shots(self, pairs_path: Optional[Path | str] = None) -> List[FewShotPair]:
        path = Path(pairs_path) if pairs_path else None
        if not path or not path.is_file():
            return []
        raw = json.loads(path.read_text(encoding="utf-8"))
        entries = raw.get("entries", []) if isinstance(raw, dict) else raw
        pairs: List[FewShotPair] = []
        for i, e in enumerate(entries if isinstance(entries, list) else []):
            en = (e.get("en") or "").strip()
            my = (e.get("my_original") or e.get("my") or e.get("translation") or "").strip()
            if not en or not my:
                continue
            category = "dialogue" if any(q in en for q in ('"', "\u201c", "\u2018")) else "mixed"
            pairs.append(FewShotPair(id=f"fs_{i:03d}", category=category, source=en, translation=my))
        return pairs

    # ------------------------------------------------------------------ #
    # Run a single chapter
    # ------------------------------------------------------------------ #
    def run_chapter(
        self,
        source_path: Path | str,
        *,
        novel: str,
        chapter_no: Optional[str] = None,
        glossary_path: Optional[Path | str] = None,
        human_reference_path: Optional[Path | str] = None,
        compare_with_human: bool = False,
        out_dir: Optional[Path | str] = None,
    ) -> Dict[str, Any]:
        src = Path(source_path)
        if not src.is_file():
            raise PipelineError(f"source file not found: {src}")
        text = src.read_text(encoding="utf-8")
        fm, _raw_fm, heading, paras = markdownio.parse_chapter(text)
        if not paras:
            raise PipelineError(f"source has no paragraphs: {src}")

        if chapter_no is None:
            m = re.search(r"(\d+)", src.stem)
            chapter_no = m.group(1) if m else "001"
        chapter_id = f"ch{int(chapter_no):03d}"
        novel_dir = Path(out_dir) if out_dir else self.config.output_dir / novel
        novel_dir.mkdir(parents=True, exist_ok=True)

        output_md = novel_dir / f"chapter-my-{chapter_no}.md"
        if output_md.is_file() and not self.config.force:
            self._state(State.APPROVED, "already committed (resume skip)")
            return self.summary(chapter_id, novel_dir, output_md, skipped=True)

        glossary = Glossary(glossary_path)
        if not glossary.index:
            self.logger("WARNING: empty glossary — terminology checks disabled")
        few_shots = self.load_few_shots(human_reference_path)
        context = ContextBuffer(novel_dir / "context_buffer.json")

        unit = TranslationUnit(
            chapter_id=chapter_id,
            source_file=str(src),
            output_file=str(output_md),
            model=self.client.model,
            temperature=self.config.temperature,
            glossary_version=glossary.version,
            style_guide_version="1.0",
            prompt_version=self.prompt_version,
            started_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
        )

        self._state(State.CHUNKING, f"{len(paras)} paragraphs")
        chunks = build_chunks(chapter_id, paras, self.chunker)
        if self.config.limit:
            chunks = chunks[: self.config.limit]
        unit.chunks = chunks
        self.logger(f"chunks: {len(chunks)}")

        self._state(State.TRANSLATING)
        prev_body_paras: List[str] = []
        dry_shown = 0
        monitor = FleetMonitor(novel_dir / "fleet.db") if self.config.monitor else None
        totals = {"auto_fix": 0, "fallback": 0, "overlap": 0, "latency_ms": 0}
        try:
            for chunk in chunks:
                # scene transition
                if chunk.scene_id:
                    context.start_scene(chapter_id, chunk.scene_id, flush=(chunk.scene_id != context.get("scene_id")))

                # -- MP1: analyze & tag (NOOP when disabled / dry-run) ------ #
                tone = ""
                if self.config.analyze and not self.config.dry_run:
                    meta: Dict[str, Any] = {}
                    try:
                        meta = self.translator.analyze_chunk(
                            chunk, system_prompt=prompt_system(self.style_guide)
                        )
                    except Exception as exc:  # noqa: BLE001 — MP1 is enrichment, never fatal
                        self.logger(f"[analyze-warn] {chunk.id}: {exc} — falling back to regex speakers")
                    speakers = [s for s in (meta.get("speakers") or []) if isinstance(s, str) and s]
                    if speakers:
                        chunk.speakers = speakers
                    ctype = meta.get("type") or meta.get("scene_type")
                    if ctype in ("dialogue-heavy", "narration-heavy", "mixed"):
                        chunk.type = ctype
                    tone = meta.get("emotional_tone") or meta.get("tone") or ""

                glossary_section = glossary.section([chunk.source_text], dynamic=True)
                context_section = context.render()
                few_shot_section = render_few_shots(
                    select_few_shots(few_shots, chunk.type, n=2)
                )
                style_guide_section = self._style_section(chunk.type)

                if self.config.dry_run:
                    if dry_shown < self.config.dry_run:
                        from .prompt_builder import assembled_prompt

                        dry_shown += 1
                        prompt = assembled_prompt(
                            chunk,
                            glossary_section=glossary_section,
                            context_section=context_section,
                            few_shot_section=few_shot_section,
                            max_ctx=self.config.max_ctx,
                        )
                        self.logger(f"\n===== {chunk.id} dry-run prompt =====")
                        self.logger("[SYSTEM]\n" + self.translator.__class__.__name__)
                        self.logger(prompt)
                    continue

                # -- LLM passes ------------------------------------------- #
                expected_overlap = self._expected_overlap(prev_body_paras, chunk)
                t_start = time.monotonic()
                fallback_used = False
                raw, micro = self.translator.translate_chunk(
                    chunk,
                    system_prompt=prompt_system(self.style_guide),
                    glossary_section=glossary_section,
                    context_section=context_section,
                    few_shot_section=few_shot_section,
                    style_guide_section=style_guide_section,
                )
                chunk.tokens_in = len(raw)
                text, auto_fixed = postprocessor.apply_all(
                    raw,
                    index=glossary.index,
                    expected_overlap=expected_overlap,
                    max_auto_fix=self.rules.max_auto_fix,
                    myanmar_numbers=self.config.myanmar_numbers,
                )
                chunk.translated_text = text

                # -- verify / revise loop ---------------------------------- #
                self._state(State.VERIFYING, chunk.id)
                verified = False
                result = None
                for attempt in range(1, self.config.max_revise + 1):
                    result = verify(
                        chunk.source_text,
                        text,
                        glossary.index,
                        context=context.snapshot(),
                        preceding_overlap=expected_overlap,
                        auto_fix_enabled=self.config.auto_fix,
                        max_auto_fix=self.rules.max_auto_fix,
                    )
                    if result.passv:
                        verified = True
                        break
                    fatal_msgs = [
                        i.message for i in result.issues
                        if i.severity in ("critical", "fatal", "error")
                    ]
                    # try fix-mode retranslate for any blocking issue (glossary
                    # violations, untranslated English, register mixing), then fail
                    if fatal_msgs and attempt < self.config.max_revise:
                        self._state(State.REVISE, f"{chunk.id} attempt {attempt}")
                        fallback_used = True
                        raw2, _m = self.translator.translate_chunk(
                            chunk,
                            system_prompt=prompt_system(self.style_guide),
                            glossary_section=glossary_section,
                            context_section=context_section,
                            few_shot_section=few_shot_section,
                            fix_issues=fatal_msgs,
                        )
                        text, auto_fixed = postprocessor.apply_all(
                            raw2,
                            index=glossary.index,
                            expected_overlap=expected_overlap,
                            max_auto_fix=self.rules.max_auto_fix,
                            myanmar_numbers=self.config.myanmar_numbers,
                        )
                        chunk.translated_text = text
                        continue
                    chunk.status = "failed"
                    self.logger(f"[verify-fail] {chunk.id} attempt {attempt}: {[i.message for i in result.issues][:2]}")
                    break

                latency_ms = int((time.monotonic() - t_start) * 1000)
                q = quality_score(chunk.source_text, text, glossary.index)
                overlap_diverged = bool(result and any(i.rule_id == "R-STRUCT-04" for i in result.issues))
                if monitor is not None:
                    monitor.record_chunk(
                        novel,
                        chapter_id,
                        chunk.id,
                        quality_score=q.get("score", None),
                        rejected=not verified,
                        fallback_used=fallback_used,
                        auto_fixed=auto_fixed,
                        overlap_diverged=overlap_diverged,
                        latency_ms=latency_ms,
                    )
                    totals["auto_fix"] += auto_fixed
                    if fallback_used:
                        totals["fallback"] += 1
                    if overlap_diverged:
                        totals["overlap"] += 1
                    totals["latency_ms"] += latency_ms

                if not verified:
                    continue  # chunk failed; keep going, report at the end

                chunk.status = "verified"
                self._state(State.VERIFYING, f"{chunk.id} OK (auto_fixed={auto_fixed})")
                body_paras = chunk.body_translated_paragraphs()
                prev_body_paras = body_paras if body_paras else prev_body_paras

                # -- context buffer update ----------------------------------- #
                context.append_chunk(chunk, emotional_tone=tone)
                speakers = chunk.speakers or glossary.speakers_in(chunk.source_text)
                active = {}
                for name in speakers:
                    entry = next((e for e in glossary.index if e["en"] == name or name in e["aliases"]), None)
                    if entry:
                        active[name] = {"pronoun": entry.get("pronoun") or "", "mood": ""}
                context.update_active_speakers(active)
        except KeyboardInterrupt:
            self.logger("Interrupted; committing partial progress...")
            # No paragraphs: never write a half-translated MD (that would make
            # resume *skip* the chapter).  Persist metadata + context archive only.
            self._commit(context, unit, novel_dir, chapter_no, output_md, fm, heading, [], partial=True)
            raise

        if self.config.dry_run:
            return self.summary(
                chapter_id, novel_dir, output_md,
                dry_run=self.config.dry_run, prompt_count=dry_shown, chunks=chunks,
            )

        # -- assembly + audit + commit -------------------------------------- #
        # Only verified chunks go into the committed MD.  Failed chunks may
        # contain verifier-rejected text (foreign script, untranslated English,
        # duplicate/overlap artifacts) and are never a safe thing to publish;
        # the run is resume-safe and a later --force re-runs the chapter.
        result_paras: List[str] = []
        for chunk in chunks:
            if chunk.status == "verified":
                result_paras.extend(chunk.body_translated_paragraphs())
        chunks_failed_total = sum(1 for c in chunks if c.status == "failed")

        # -- assembly-time gates (todo.md §2/§3) ----------------------------- #
        # The verifier is per-chunk; these run on the fully assembled chapter.
        assembly_notes: Dict[str, Any] = {"dropped_duplicates": [], "naming": []}
        result_paras, dropped = dedup_assembled_paras(result_paras)
        assembly_notes["dropped_duplicates"] = dropped
        if dropped:
            self.logger(f"[assembly] dropped {len(dropped)} near-duplicate paragraph(s)")

        assembled_body = "\n\n".join(result_paras)
        ok_script, script_reason = assembly_script_gate(
            assembled_body, loanword_allowlist=glossary.loanword_allowlist()
        )
        assembly_notes["script_gate"] = script_reason
        if not ok_script:
            self.logger(f"[assembly-gate] FAIL script: {script_reason}")

        ok_complete, complete_reason = assembly_completeness(result_paras, source_paras=paras)
        assembly_notes["completeness"] = complete_reason
        if not ok_complete:
            self.logger(f"[assembly-gate] FAIL completeness: {complete_reason}")

        assembly_notes["naming"] = check_naming_consistency(assembled_body, glossary.index)
        if assembly_notes["naming"]:
            for flag in assembly_notes["naming"]:
                self.logger(f"[assembly-warn] naming drift: {flag}")

        # Hygiene normalizes AFTER the gates so it can never mask a leak.
        if ok_script:
            assembled_body = normalize_hygiene(assembled_body)
            assembled_body = translate_loanwords(assembled_body)
        result_paras = [p for p in assembled_body.split("\n\n") if p.strip()]

        assembly_blocked = (not ok_script) or (not ok_complete)
        out_fm = self._output_frontmatter(
            fm, unit, audited=not self.config.skip_audit,
            verified=(chunks_failed_total == 0 and not assembly_blocked),
        )
        final_md = markdownio.build_output(out_fm, heading, result_paras)

        grade = None
        weighted_total = None
        if assembly_blocked:
            # Hard gate failure: never APPROVE, never write the polluted body.
            final_state = State.NEEDS_HUMAN
            self._state(final_state, f"assembly gate: {script_reason} {complete_reason}".strip())
        elif not self.config.skip_audit:
            self._state(State.AUDITING)
            report = self.auditor.audit(
                markdownio.build_output(fm, heading, paras),
                final_md,
                glossary_index=glossary.index,
                human_reference=(Path(human_reference_path).read_text(encoding="utf-8")
                                 if human_reference_path else ""),
                compare_with_human=compare_with_human,
            )
            grade = report["grade"]
            weighted_total = report.get("weighted_total")
            novel_dir.joinpath("audit-report.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            out_fm["grade"] = grade
            # A chapter with any failed chunk has unverified content, so it can
            # never be APPROVED, regardless of the auditor's verdict (SPEC §4:
            # AUDITING may only follow "all chunks pass verification").
            chunks_failed = sum(1 for c in chunks if c.status == "failed")
            if chunks_failed:
                final_state = State.NEEDS_HUMAN
            elif report["verdict"] == "pass":
                final_state = State.APPROVED
            else:
                final_state = State.NEEDS_HUMAN
            self._state(final_state, f"grade={grade}, verdict={report['verdict']}, chunks_failed={chunks_failed}")
        else:
            # Audit skipped: a chapter with failed chunks still has unverified
            # content and must not be silently marked APPROVED.
            chunks_failed = sum(1 for c in chunks if c.status == "failed")
            final_state = State.APPROVED if chunks_failed == 0 else State.NEEDS_HUMAN

        self._commit(
            context, unit, novel_dir, chapter_no, output_md, out_fm, heading,
            [] if assembly_blocked else result_paras,
            grade=grade, state=final_state.value,
            extra=assembly_notes,
        )
        if monitor is not None:
            monitor.record_chapter(
                novel,
                chapter_id,
                weighted_total=float(weighted_total) if weighted_total is not None else None,
                grade=grade or "",
                chunks_total=sum(1 for c in chunks if c.status in ("verified", "failed")),
                chunks_failed=sum(1 for c in chunks if c.status == "failed"),
                glossary_auto_fix_total=totals["auto_fix"],
                fallback_total=totals["fallback"],
                overlap_diverged_total=totals["overlap"],
                latency_total_ms=totals["latency_ms"],
            )
            novel_dir.joinpath("fleet-report.json").write_text(
                json.dumps(monitor.report(novel), ensure_ascii=False, indent=2), encoding="utf-8"
            )
        return self.summary(
            chapter_id, novel_dir, output_md,
            state=final_state.value, grade=grade, chunks=chunks,
        )

    # ------------------------------------------------------------------ #
    # helpers
    # ------------------------------------------------------------------ #
    def _style_section(self, chunk_type: str) -> str:
        if not self.style_guide:
            return ""
        regs = self.style_guide.get("registers", {})
        if chunk_type == "dialogue-heavy":
            return "Dialogue must use spoken Burmese (တယ်, လား, ပဲ, ကွာ, နော်, ဗျာ). Never mix with literary လေသည်.\n" + json.dumps({k: v for k, v in regs.items() if "dialogue" in k}, ensure_ascii=False)
        if chunk_type == "narration-heavy":
            endings = ", ".join(regs.get("narration", {}).get("preferred_endings", ["လေသည်"]))
            return f"Narration uses literary Burmese endings: {endings}. Forbidden spoken particles in narration."
        return "Mixed chunk: narration literary (လေသည်/ရလေသည်), dialogue spoken (ကွာ/နော်/ဗျာ). Never mix registers in one sentence."

    def _expected_overlap(self, prev_body_paras: List[str], chunk: Chunk) -> str:
        n = len(chunk.overlap_paras)
        if not n or not prev_body_paras:
            return ""
        return "\n\n".join(prev_body_paras[-n:])

    @staticmethod
    def _output_frontmatter(
        fm: Dict[str, str],
        unit: TranslationUnit,
        *,
        grade: str = "pending",
        audited: bool = True,
        verified: bool = True,
    ) -> Dict[str, str]:
        """Output frontmatter with pipeline metadata (SPEC §5.2, NEW_TODO §5.15)."""
        out = dict(fm)
        out["translated_by"] = "ollama-" + (unit.model or "unknown")
        out["verified"] = "true" if verified else "false"
        out["audited"] = "true" if audited else "false"
        out["grade"] = grade or "pending"
        if unit.glossary_version:
            out["glossary_version"] = unit.glossary_version
        if unit.prompt_version:
            out["prompt_version"] = unit.prompt_version
        return out

    def _commit(
        self,
        context: ContextBuffer,
        unit: TranslationUnit,
        novel_dir: Path,
        chapter_no: str,
        output_md: Path,
        fm: Dict[str, str],
        heading: str,
        paragraphs: List[str],
        *,
        grade: Optional[str] = None,
        state: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
        partial: bool = False,
    ) -> None:
        if paragraphs:
            output_md.write_text(markdownio.build_output(fm, heading, paragraphs), encoding="utf-8")
        unit.completed_at = time.strftime("%Y-%m-%dT%H:%M:%S")
        unit.state = state or (State.APPROVED.value if not partial else "PARTIAL")
        unit.final_grade = grade or ""
        meta = unit.to_dict()
        meta["output_paragraphs"] = len(paragraphs)
        if extra:
            meta["assembly"] = extra
        novel_dir.joinpath("metadata.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        archive_dir = novel_dir / "archive" / "context"
        context.archive(archive_dir, unit.chapter_id)
        self.logger(f"committed -> {output_md.name} ({len(paragraphs)} paras)")

    @staticmethod
    def summary(
        chapter_id: str,
        novel_dir: Path,
        output_md: Path,
        *,
        skipped: bool = False,
        dry_run: int = 0,
        prompt_count: int = 0,
        state: str = "",
        grade: Optional[str] = None,
        chunks: Optional[Sequence[Chunk]] = None,
    ) -> Dict[str, Any]:
        failed = sum(1 for c in (chunks or []) if c.status == "failed") if chunks else 0
        verified = sum(1 for c in (chunks or []) if c.status == "verified") if chunks else 0
        return {
            "chapter_id": chapter_id,
            "state": state or ("SKIPPED" if skipped else ("DRY_RUN" if dry_run else State.APPROVED.value)),
            "output_files": [str(output_md)] if output_md.is_file() else [],
            "audit_grade": grade,
            "chunks_total": len(chunks) if chunks else 0,
            "chunks_verified": verified,
            "chunks_failed": failed,
            "dry_run_prompts": prompt_count,
            "output_dir": str(novel_dir),
        }


def prompt_system(style_guide: Dict[str, Any]) -> str:
    from .prompt_builder import TRANSLATOR_SYSTEM

    return TRANSLATOR_SYSTEM