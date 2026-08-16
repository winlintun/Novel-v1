#!/usr/bin/env python3
"""CLI entry point for the Myanmar novel translation pipeline (SPEC.md).

Examples:
    python main.py --novel my_house_of_horrors --chapter 1
    python main.py --novel my_house_of_horrors --chapter 1 --chapter-to 5 \
        --glossary config/my_house_of_horrors/glossary_my_house_of_horrors.json \
        --pairs en_mm_human_pair/i-have-a-haunted-house.json
    python main.py --src tests/fixtures/chapter-en-0001.md --glossary tests/fixtures/glossary-minimal.json --dry-run 2
    python main.py --chapter 3 --no-analyze --roles config/roles.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from src.pipeline.ollama_client import OllamaClient
from src.pipeline.orchestrator import Orchestrator, PipelineConfig, PipelineError

DEFAULT_NOVEL = "my_house_of_horrors"
DEFAULT_MODEL = "padauk-gemma:q8_0"


def default_src(novel: str, chapter: int) -> Path:
    return Path("books") / novel / f"chapter-{chapter:04d}.md"


def default_glossary(novel: str) -> Path:
    return (
        Path("config") / novel / f"glossary_{novel}.json"
    )


def _load_roles(path: Optional[str]) -> dict:
    if not path:
        return {}
    p = Path(path)
    if not p.is_file():
        print(f"WARNING: --roles file not found: {p}", file=sys.stderr)
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"WARNING: invalid --roles JSON: {exc}", file=sys.stderr)
        return {}
    return data.get("roles", {}) if isinstance(data, dict) else {}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Translate English web-novel chapters into literary Burmese (local Ollama)."
    )
    p.add_argument("--novel", default=DEFAULT_NOVEL, help="novel slug under books/<novel>/")
    p.add_argument("--src", help="explicit source chapter .md (overrides --novel/--chapter)")
    p.add_argument("--chapter", type=int, default=1, help="chapter number")
    p.add_argument("--chapter-to", type=int, help="last chapter number (inclusive), enables range run")
    p.add_argument("--out", default="output", help="output root dir")
    p.add_argument("--config", default="config", help="config dir with chunking_rules.json, rules.json, style_guide.json")
    p.add_argument("--model", default=os.getenv("OLLAMA_MODEL", DEFAULT_MODEL))
    p.add_argument("--temperature", type=float, default=0.2)
    p.add_argument("--glossary", help="glossary JSON path (per-novel default auto)"
                                      "config/<novel>/glossary_<novel>.json")
    p.add_argument("--pairs", help="human EN<->MY few-shot pairs JSON")
    p.add_argument("--human-ref", help="human-translated reference .md for auditor comparison")
    p.add_argument("--compare-with-human", action="store_true", help="auditor compares output to --human-ref")
    p.add_argument("--no-two-pass", dest="two_pass", action="store_false", help="draft only, skip polish")
    p.add_argument("--no-auto-fix", dest="auto_fix", action="store_false")
    p.add_argument("--no-audit", dest="skip_audit", action="store_true", help="skip auditor")
    p.add_argument("--myanmar-numbers", action="store_true", help="convert digits to Myanmar numerals")
    p.add_argument("--dry-run", type=int, metavar="N", default=0,
                   help="print assembled prompts for the first N chunks without calling Ollama")
    p.add_argument("--limit", type=int, default=0, help="translate at most N chunks (0 = all)")
    p.add_argument("--max-revise", type=int, default=3, help="verify/revise attempts per chunk")
    p.add_argument("--force", action="store_true", help="re-translate even if the chapter is already committed")
    p.add_argument("--analyze", dest="analyze", action="store_true", default=True,
                   help="run MP1 analyze/tag (speakers, tone, type) per chunk (default)")
    p.add_argument("--no-analyze", dest="analyze", action="store_false",
                   help="skip MP1 analysis; use regex speaker detection only")
    p.add_argument("--roles", help="role->model assignment JSON (default config/roles.json)")
    p.add_argument("--prompts", default="prompts", help="micro-prompt templates dir (default: prompts)")
    p.add_argument("--no-monitor", dest="monitor", action="store_false", default=True,
                   help="disable per-chunk fleet metrics collection (fleet.db + fleet-report.json)")
    p.add_argument("--golden", action="store_true",
                   help="run the golden test suite against the configured model and exit")
    p.add_argument("--golden-baseline", default="config/golden_baseline.json",
                   help="golden baseline JSON (default: config/golden_baseline.json)")
    p.add_argument("--golden-save", action="store_true",
                   help="write the current model output as the golden baseline")
    return p


def make_pipeline_logger(log_path: Path):
    """Pipeline log to ``logs/pipeline.log`` (mirrors every message to stdout)."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        handle = open(log_path, "a", encoding="utf-8")
    except OSError:
        handle = None

    def log(msg: str) -> None:
        try:
            print(msg, flush=True)
        except (UnicodeEncodeError, OSError):
            pass
        if handle is not None:
            try:
                handle.write(msg + "\n")
                handle.flush()
            except OSError:
                pass

    return log


def main(argv=None) -> int:
    load_dotenv()
    # Windows consoles default to cp1252; Burmese Unicode breaks ``print`` otherwise.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    args = build_parser().parse_args(argv)

    config = PipelineConfig(
        config_dir=args.config,
        output_dir=args.out,
        model=args.model,
        temperature=args.temperature,
        two_pass=args.two_pass,
        max_revise=args.max_revise,
        skip_audit=args.skip_audit,
        auto_fix=args.auto_fix,
        myanmar_numbers=args.myanmar_numbers,
        dry_run=args.dry_run or 0,
        limit=args.limit,
        force=args.force,
        analyze=args.analyze,
        roles=_load_roles(args.roles),
        prompts_dir=args.prompts,
        monitor=args.monitor,
    )

    if args.golden:
        from src.pipeline.golden import GOLDEN_CHUNKS, review_golden_report, run_golden_suite, save_baseline
        from src.pipeline.ollama_client import OllamaClient as _OC

        golden_client = _OC(model=config.model, temperature=config.temperature)
        report = run_golden_suite(golden_client, config.model, args.golden_baseline,
                                  two_pass=False)
        for c in report["chunks"]:
            print(f"  golden:{c['name']:<18} sim={c['baseline_similarity']:.3f} "
                  f"{'DRIFT' if c.get('drifted') else 'ok'}")
        print(review_golden_report(report))
        if args.golden_save:
            save_baseline(args.golden_baseline, config.model,
                          {c["name"]: c["output"] for c in report["chunks"] if not c.get("error")})
            print(f"baseline saved -> {args.golden_baseline}")
        golden_client.unload()
        return 1 if report["drift_count"] else 0

    chapters = list(range(args.chapter, (args.chapter_to or args.chapter) + 1))
    srcs = {
        ch: (Path(args.src) if args.src else default_src(args.novel, ch))
        for ch in chapters
    }
    missing = [str(s) for s in srcs.values() if not s.is_file()]
    if missing:
        print(f"ERROR: source chapter file(s) not found: {missing}", file=sys.stderr)
        return 2

    glossary = args.glossary
    if not glossary:
        default = default_glossary(args.novel)
        if default.is_file():
            glossary = str(default)

    client = OllamaClient(model=config.model, temperature=config.temperature)
    orch = Orchestrator(config, client, log=make_pipeline_logger(Path("logs") / "pipeline.log"))
    pair_path = args.pairs

    overall = 0
    for ch in chapters:
        src = srcs[ch]
        print(f"\n=== chapter {ch}: {src.name} ===", flush=True)
        try:
            summary = orch.run_chapter(
                src,
                novel=args.novel,
                chapter_no=str(ch),
                glossary_path=glossary,
                human_reference_path=args.human_ref,
                compare_with_human=args.compare_with_human,
            )
        except (PipelineError, KeyboardInterrupt) as exc:
            print(f"chapter {ch} interrupted: {exc}", file=sys.stderr)
            return 130
        print(
            f"chapter {ch}: state={summary['state']} "
            f"chunks={summary['chunks_total']} verified={summary['chunks_verified']} "
            f"failed={summary['chunks_failed']} grade={summary.get('audit_grade','-')} "
            f"files={summary['output_files']}"
        )
        if summary["state"] not in ("APPROVED", "SKIPPED", "DRY_RUN"):
            overall = 1
    client.unload()
    return overall


if __name__ == "__main__":
    raise SystemExit(main())