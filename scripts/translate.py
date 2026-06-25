#!/usr/bin/env python3
"""Interactive terminal launcher for the novel translation pipeline.

Instead of typing long `python -m src.main --novel ... --chapter ...` commands by
hand, run this and pick from menus. A top-level menu exposes the main functions:

    1. Translate chapters
    2. Generate glossary (from source, from EN<->MM pairs, or init 1-5)
    3. Approve / promote glossary terms
    4. Show quality stats
    5. Review / view a translated file
    6. Launch the web UI

Each action discovers novels in ``data/input/`` and the chapters that actually
exist, assembles the matching `python -m src.main ...` command, shows it, and
runs it for you. Use --dry-run to see the command without executing.

Usage:
    python scripts/translate.py
    python scripts/translate.py --dry-run
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

INPUT_DIR = "data/input"
OUTPUT_DIR = "data/output"

MODES = [
    ("single_stage  (1-stage, RECOMMENDED)", "single_stage"),
    ("lite          (3-stage: Translate -> Refine -> Quality)", "lite"),
    ("fast          (2-stage: Translate -> Quality)", "fast"),
    ("full          (6-stage, may drop content)", "full"),
]

CHAPTER_RE = re.compile(r"chapter[_-]?0*(\d+)", re.IGNORECASE)

# Set by main() so action handlers know whether to actually run commands.
DRY_RUN = False


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


# ── discovery helpers ───────────────────────────────────────────────────────

def list_novels(input_dir: Path) -> list[str]:
    if not input_dir.is_dir():
        return []
    return sorted(p.name for p in input_dir.iterdir() if p.is_dir() and not p.name.startswith('.'))


def list_chapters(novel_dir: Path) -> list[int]:
    """Sorted chapter numbers found for a novel (checks en/ then the dir)."""
    numbers: set[int] = set()
    for d in (novel_dir / "en", novel_dir):
        if not d.is_dir():
            continue
        for f in d.glob("*.md"):
            m = CHAPTER_RE.search(f.stem)
            if m:
                numbers.add(int(m.group(1)))
        if numbers:
            break
    return sorted(numbers)


# ── prompt helpers ──────────────────────────────────────────────────────────

def pick_from_menu(title: str, options: list[str]) -> int | None:
    """Numbered menu; returns 0-based index or None to cancel."""
    print(f"\n{title}")
    for i, opt in enumerate(options, 1):
        print(f"  {i:>2}. {opt}")
    raw = input("> ").strip().lower()
    if raw in ("", "q", "quit", "exit", "b", "back"):
        return None
    if raw.isdigit() and 1 <= int(raw) <= len(options):
        return int(raw) - 1
    print("  Invalid selection.")
    return None


def pick_novel(input_dir: Path) -> str | None:
    novels = list_novels(input_dir)
    if not novels:
        print(f"[error] No novels found in {input_dir}", file=sys.stderr)
        return None
    idx = pick_from_menu("Select a novel:", novels)
    return novels[idx] if idx is not None else None


def choose_chapters(chapters: list[int], allow_all: bool = True) -> list[str] | None:
    """Return chapter-selection CLI args, or None to cancel."""
    if chapters:
        print(f"\nChapters available: {chapters[0]}-{chapters[-1]} ({len(chapters)} files)")
    else:
        print("\n(No chapter files auto-detected; you can still type a number.)")
    print("Choose what to use:")
    print("   1. A single chapter")
    print("   2. A range of chapters")
    if allow_all:
        print("   3. All chapters")
    sel = input("> ").strip().lower()
    if sel in ("", "q", "quit", "exit", "b", "back"):
        return None

    if sel == "1":
        raw = input("  Chapter number: ").strip()
        if not raw.isdigit():
            print("  Invalid chapter number.")
            return None
        return ["--chapter", raw]
    if sel == "2":
        raw = input("  Range (e.g. 5-15): ").strip()
        if not re.fullmatch(r"\d+-\d+", raw):
            print("  Invalid range. Expected start-end, e.g. 5-15.")
            return None
        start, end = (int(x) for x in raw.split("-"))
        if end < start:
            print("  End chapter must be >= start.")
            return None
        return ["--chapter-range", raw]
    if sel == "3" and allow_all:
        return ["--all"]
    print("  Invalid selection.")
    return None


def choose_range(prompt: str = "Chapter range for glossary (e.g. 1-5): ") -> list[str] | None:
    raw = input(f"  {prompt}").strip()
    if not raw:
        return []  # let the CLI use its own default
    if not re.fullmatch(r"\d+-\d+", raw):
        print("  Invalid range. Expected start-end, e.g. 1-5.")
        return None
    start, end = (int(x) for x in raw.split("-"))
    if end < start:
        print("  End chapter must be >= start.")
        return None
    return ["--chapter-range", raw]


# ── command runner ──────────────────────────────────────────────────────────

def run_cmd(extra_args: list[str], confirm: bool = True) -> int:
    """Assemble and run `python -m src.main <extra_args>` from the repo root."""
    root = _repo_root()
    cmd = [sys.executable, "-m", "src.main", *extra_args]
    print(f"\nCommand:\n  {' '.join(cmd)}")

    if DRY_RUN:
        print("\n[dry-run] Not executing.")
        return 0
    if confirm:
        ans = input("\nRun it now? [Y/n] ").strip().lower()
        if ans not in ("", "y", "yes"):
            print("Cancelled.")
            return 0

    print()
    try:
        return subprocess.run(cmd, cwd=str(root)).returncode
    except KeyboardInterrupt:
        print("\nInterrupted.")
        return 130
    except OSError as exc:
        print(f"[error] Failed to launch: {exc}", file=sys.stderr)
        return 1


# ── actions ─────────────────────────────────────────────────────────────────

def action_translate(input_dir: Path) -> int:
    novel = pick_novel(input_dir)
    if not novel:
        return 0
    chapter_args = choose_chapters(list_chapters(input_dir / novel))
    if chapter_args is None:
        return 0
    idx = pick_from_menu("Select a pipeline mode:", [m[0] for m in MODES])
    if idx is None:
        return 0
    mode = MODES[idx][1]
    model = input("\nModel override (blank = use config default): ").strip()

    args = ["--novel", novel, *chapter_args, "--mode", mode]
    if model:
        args += ["--model", model]
    return run_cmd(args)


def action_glossary(input_dir: Path) -> int:
    novel = pick_novel(input_dir)
    if not novel:
        return 0
    idx = pick_from_menu(
        "Glossary extraction mode:",
        [
            "From source chapters (--generate-glossary)",
            "From EN<->MM translated pairs (--from-mm)",
            "Init: chapters 1-5 then stop for review (--init-glossary)",
        ],
    )
    if idx is None:
        return 0

    if idx == 2:  # init mode: fixed 1-5, no range prompt
        return run_cmd(["--novel", novel, "--init-glossary"])

    range_args = choose_range()
    if range_args is None:
        return 0
    args = ["--novel", novel, "--generate-glossary", *range_args]
    if idx == 1:
        args.append("--from-mm")
    return run_cmd(args)


def action_promote(input_dir: Path) -> int:
    novel = pick_novel(input_dir)
    if not novel:
        return 0
    idx = pick_from_menu(
        "Glossary review action:",
        [
            "Auto-promote high-confidence pending terms (--auto-promote)",
            "Bulk approve ALL pending terms (--approve-glossary)",
        ],
    )
    if idx is None:
        return 0
    flag = "--auto-promote" if idx == 0 else "--approve-glossary"
    return run_cmd(["--novel", novel, flag])


def action_stats(input_dir: Path) -> int:
    novel = pick_novel(input_dir)
    if not novel:
        return 0
    return run_cmd(["--stats", "--novel", novel], confirm=False)


def action_review(input_dir: Path) -> int:
    idx = pick_from_menu(
        "File action:",
        ["View formatted in terminal (--view)", "Review against quality rules (--review)"],
    )
    if idx is None:
        return 0
    flag = "--view" if idx == 0 else "--review"
    path = input("  Path to .mm.md file: ").strip().strip('"')
    if not path:
        print("  No file given.")
        return 0
    if not Path(path).exists():
        print(f"  [warn] file not found: {path}")
    return run_cmd([flag, path], confirm=False)


def action_ui(_input_dir: Path) -> int:
    port = input("  Port [5000]: ").strip() or "5000"
    if not port.isdigit():
        print("  Invalid port.")
        return 0
    return run_cmd(["--ui", "--port", port], confirm=False)


MAIN_MENU = [
    ("Translate chapters", action_translate),
    ("Generate glossary", action_glossary),
    ("Approve / promote glossary terms", action_promote),
    ("Show quality stats", action_stats),
    ("Review / view a translated file", action_review),
    ("Launch web UI", action_ui),
]


def main(argv: list[str] | None = None) -> int:
    global DRY_RUN
    parser = argparse.ArgumentParser(description="Interactive launcher for the translation pipeline.")
    parser.add_argument("--dry-run", action="store_true", help="Print commands but do not run them")
    parser.add_argument("--input-dir", default=INPUT_DIR, help="Where novels live (default: data/input)")
    args = parser.parse_args(argv)
    DRY_RUN = args.dry_run

    input_dir = Path(args.input_dir)
    if not input_dir.is_absolute():
        input_dir = _repo_root() / input_dir

    while True:
        idx = pick_from_menu("=== Novel Translation Launcher ===  (q to quit)",
                             [label for label, _ in MAIN_MENU])
        if idx is None:
            print("Bye.")
            return 0
        try:
            MAIN_MENU[idx][1](input_dir)
        except KeyboardInterrupt:
            print("\n(cancelled, back to menu)")
    # unreachable


if __name__ == "__main__":
    raise SystemExit(main())
