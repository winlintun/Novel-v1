#!/usr/bin/env python3
"""Interactive terminal launcher for the novel translation pipeline.

Instead of typing long `python -m src.main --novel ... --chapter ...` commands by
hand, run this and pick from menus. A top-level menu exposes the main functions:

    1. Translate chapters
    2. Generate glossary (from source, from EN<->MM pairs, or init 1-5)
    3. Approve / promote glossary terms
    4. Show quality stats
    5. Review / view a translated file
    6. Change Ollama model (lists installed models, auto-tunes settings)
    7. Launch the web UI

Each action discovers novels in ``data/input/`` and the chapters that actually
exist, assembles the matching `python -m src.main ...` command, shows it, and
runs it for you. Use --dry-run to see the command without executing.

When translating, the pipeline-mode menu is model-aware: it reads the model you
pick (or the configured default) and recommends the best mode for it, warning on
models known to fail Myanmar output (e.g. qwen, sailor2). single_stage is the
recommended mode for every model — the refine/reflect stages drop 41-91% of
content — so guidance mainly surfaces per-model caveats.

Usage:
    python scripts/translate.py
    python scripts/translate.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

INPUT_DIR = "data/input"
OUTPUT_DIR = "data/output"
DEFAULT_CONFIG = "config/settings.yaml"
DEFAULT_OLLAMA_URL = "http://localhost:11434"
HTTP_TIMEOUT = 10  # seconds — NO HANGING REQUESTS

MODES = [
    ("single_stage  (1-stage, RECOMMENDED)", "single_stage"),
    ("lite          (3-stage: Translate -> Refine -> Quality)", "lite"),
    ("fast          (2-stage: Translate -> Quality)", "fast"),
    ("full          (6-stage, may drop content)", "full"),
]

# Per-model guidance for the translate menu. Keyed by a case-insensitive
# substring of the model name (longest match wins). Reflects CLAUDE.md and
# config/settings.yaml: single_stage is the best mode for EVERY model because
# the refine/reflect stages drop 41-91% of content — so the recommendation is
# really about WARNING on models known to fail Myanmar output, and noting the
# quirks of reasoning models. `mode` is the recommended --mode value.
MODEL_GUIDANCE: list[tuple[str, dict]] = [
    ("padauk-gemma",  {"mode": "single_stage",
                       "note": "Recommended Myanmar model - best quality in single_stage."}),
    ("gemma4-e4b",    {"mode": "single_stage",
                       "note": "Good EN->MM model; single_stage recommended."}),
    ("gemma-4-e4b",   {"mode": "single_stage",
                       "note": "Good EN->MM model; single_stage recommended."}),
    ("deepseek-r1",   {"mode": "single_stage",
                       "note": "Reasoning model - translate directly (<think> is stripped). "
                               "Qwen base may leak Chinese; verify output, prefer padauk-gemma."}),
    ("qwq",           {"mode": "single_stage",
                       "note": "Reasoning model - translate directly (<think> is stripped)."}),
    ("qwen",          {"mode": "single_stage",
                       "note": "WARNING: qwen often outputs Chinese/Japanese for Myanmar "
                               "(CLAUDE.md). Prefer padauk-gemma:q8_0."}),
    ("sailor2",       {"mode": "single_stage",
                       "note": "WARNING: sailor2 tends to output English (low Myanmar ratio). "
                               "Prefer padauk-gemma:q8_0."}),
    ("seallm",        {"mode": "single_stage",
                       "note": "SEA-language model; usable, but padauk-gemma is the proven choice."}),
    ("translategemma", {"mode": "single_stage",
                         "note": "Translation model; single_stage recommended."}),
]
# Used for any model not listed above.
DEFAULT_GUIDANCE = {"mode": "single_stage",
                    "note": "single_stage is recommended for all models "
                            "(refine/reflect stages can drop content)."}

# Model-specific tuning profiles. When changing a model, num_ctx, temperature
# AND timeout are auto-adjusted together. Matched by case-insensitive substring.
MODEL_PROFILES: list[tuple[str, dict]] = [
    ("padauk-gemma", {"num_ctx": 8192,  "temperature": 0.2,  "timeout": 300}),
    ("gemma4-e4b",   {"num_ctx": 8192,  "temperature": 0.25, "timeout": 300}),
    ("gemma-4-e4b",  {"num_ctx": 8192,  "temperature": 0.25, "timeout": 300}),
    ("deepseek-r1",  {"num_ctx": 16384, "temperature": 0.6,  "timeout": 1800}),
    ("qwq",          {"num_ctx": 16384, "temperature": 0.3,  "timeout": 1800}),
    ("qwen",         {"num_ctx": 16384, "temperature": 0.3,  "timeout": 600}),
    ("sailor2-20b",  {"num_ctx": 16384, "temperature": 0.2,  "timeout": 1800}),
    ("sailor2",      {"num_ctx": 8192,  "temperature": 0.2,  "timeout": 600}),
    ("seallm",       {"num_ctx": 8192,  "temperature": 0.2,  "timeout": 300}),
    ("llamax3",      {"num_ctx": 8192,  "temperature": 0.3,  "timeout": 600}),
    ("translategemma", {"num_ctx": 8192, "temperature": 0.3, "timeout": 600}),
]
DEFAULT_PROFILE = {"num_ctx": 16384, "temperature": 0.3, "timeout": 600}

# Roles that can be changed in settings.yaml
MODEL_ROLES = ["translator", "refiner", "checker", "editor"]

CHAPTER_RE = re.compile(r"chapter[_-]?0*(\d+)", re.IGNORECASE)


def model_guidance(model: str) -> dict:
    """Return {mode, note} guidance for a model name (longest-prefix match)."""
    name = (model or "").lower()
    best: tuple[str, dict] | None = None
    for prefix, g in MODEL_GUIDANCE:
        if prefix in name and (best is None or len(prefix) > len(best[0])):
            best = (prefix, g)
    return best[1] if best else DEFAULT_GUIDANCE


def model_profile(model: str) -> dict:
    """Return the recommended {num_ctx, temperature, timeout} for a model name."""
    name = (model or "").lower()
    best: tuple[str, dict] | None = None
    for prefix, prof in MODEL_PROFILES:
        if prefix in name and (best is None or len(prefix) > len(best[0])):
            best = (prefix, prof)
    return dict(best[1]) if best else dict(DEFAULT_PROFILE)


def configured_translator(config_path: Path) -> str:
    """Best-effort read of models.translator from settings.yaml ('' if unknown)."""
    try:
        import yaml
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return str(((data.get("models") or {}).get("translator") or "")).strip()
    except Exception:
        return ""


def fetch_installed_models(base_url: str) -> list[str]:
    """Return sorted model names installed in Ollama, or [] on any failure."""
    url = base_url.rstrip("/") + "/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=HTTP_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError):
        return []
    models = [m.get("name", "") for m in data.get("models", []) if m.get("name")]
    return sorted(models)


# Set by main() so action handlers know whether to actually run commands.
DRY_RUN = False


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


# ── YAML helpers (for model changing) ──────────────────────────────────────

def _find_block(lines: list[str], name: str) -> tuple[int, int]:
    """Return [start, end) line indices of a top-level `name:` block body."""
    start = None
    for i, line in enumerate(lines):
        if re.match(rf"^{re.escape(name)}:\s*(#.*)?$", line):
            start = i + 1
            break
    if start is None:
        raise KeyError(f"`{name}:` block not found in config")
    end = len(lines)
    for i in range(start, len(lines)):
        if lines[i] and not lines[i][0].isspace() and not lines[i].startswith("#"):
            end = i
            break
    return start, end


def _set_scalar(lines: list[str], block: str, key: str, value: object) -> str | None:
    """Replace a direct scalar `key` inside a top-level block. Returns old value."""
    start, end = _find_block(lines, block)
    for i in range(start, end):
        m = re.match(rf"^(  )({re.escape(key)}):[ \t]*(\S+)(.*)$", lines[i])
        if m:
            indent, k, old, trailing = m.groups()
            comment = ""
            hash_idx = trailing.find("#")
            if hash_idx != -1:
                comment = "  " + trailing[hash_idx:].strip()
            lines[i] = f"{indent}{k}: {value}{comment}\n"
            return old
    return None


def _set_model_section_temp(lines: list[str], model: str, temp: object) -> bool:
    """Set temperature of a `models.<section>` mapping whose name == model."""
    start, end = _find_block(lines, "models")
    model_lower = (model or "").lower()
    i = start
    while i < end:
        if re.match(r"^  \w+:\s*$", lines[i]):
            sec_start = i + 1
            sec_end = end
            for j in range(sec_start, end):
                if re.match(r"^  \w+:", lines[j]) or (lines[j] and not lines[j][0].isspace()):
                    sec_end = j
                    break
            name_val = None
            temp_idx = None
            for j in range(sec_start, sec_end):
                mn = re.match(r"^    name:\s*(\S+)", lines[j])
                if mn:
                    name_val = mn.group(1).lower()
                if re.match(r"^    temperature:", lines[j]):
                    temp_idx = j
            if name_val == model_lower and temp_idx is not None:
                mt = re.match(r"^(    )(temperature):[ \t]*(\S+)(.*)$", lines[temp_idx])
                if mt:
                    indent, k, _old, trailing = mt.groups()
                    comment = ""
                    hash_idx = trailing.find("#")
                    if hash_idx != -1:
                        comment = "  " + trailing[hash_idx:].strip()
                    lines[temp_idx] = f"{indent}{k}: {temp}{comment}\n"
                    return True
            i = sec_end
            continue
        i += 1
    return False


def _apply_model_tuning(lines: list[str], model: str) -> dict[str, tuple[str, object]]:
    """Sync num_ctx + temperature + timeout to the chosen model's profile."""
    prof = model_profile(model)
    changes: dict[str, tuple[str, object]] = {}

    old_ctx = _set_scalar(lines, "models", "num_ctx", prof["num_ctx"])
    if old_ctx is not None and str(old_ctx) != str(prof["num_ctx"]):
        changes["num_ctx"] = (old_ctx, prof["num_ctx"])

    old_temp = _set_scalar(lines, "processing", "temperature", prof["temperature"])
    if old_temp is not None and str(old_temp) != str(prof["temperature"]):
        changes["temperature"] = (old_temp, prof["temperature"])

    old_to = _set_scalar(lines, "models", "timeout", prof["timeout"])
    if old_to is not None and str(old_to) != str(prof["timeout"]):
        changes["timeout"] = (old_to, prof["timeout"])
    _set_scalar(lines, "processing", "request_timeout", prof["timeout"])

    chunk_timeout = max(1800, 2 * int(prof["timeout"]))
    old_ct = _set_scalar(lines, "processing", "chunk_timeout", chunk_timeout)
    if old_ct is not None and str(old_ct) != str(chunk_timeout):
        changes["chunk_timeout"] = (old_ct, chunk_timeout)

    try:
        _set_model_section_temp(lines, model, prof["temperature"])
    except Exception:
        pass

    return changes


def _set_role_model(lines: list[str], role: str, model: str) -> bool:
    """Replace the value for `role` in the models block. Returns True if changed."""
    start, end = _find_block(lines, "models")
    for i in range(start, end):
        m = re.match(rf"^(\s+)({re.escape(role)}):\s*(\S+)(.*)$", lines[i])
        if m:
            indent, key, _old, trailing = m.groups()
            comment = ""
            hash_idx = trailing.find("#")
            if hash_idx != -1:
                comment = "  " + trailing[hash_idx:].strip()
            lines[i] = f"{indent}{key}: {model}{comment}\n"
            return True
    return False


def _read_current_models(lines: list[str]) -> dict[str, str]:
    start, end = _find_block(lines, "models")
    current: dict[str, str] = {}
    for i in range(start, end):
        m = re.match(r"^(\s+)(\w+):\s*(\S+)", lines[i])
        if m and m.group(2) in MODEL_ROLES:
            current[m.group(2)] = m.group(3)
    return current


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


def pick_mode(recommended: str) -> str | None:
    """Pipeline-mode menu that marks the recommended mode; Enter selects it."""
    print("\nSelect a pipeline mode  (Enter = recommended, q = back):")
    rec_idx = None
    for i, (label, val) in enumerate(MODES, 1):
        mark = "   <-- recommended for this model" if val == recommended else ""
        if val == recommended:
            rec_idx = i - 1
        print(f"  {i:>2}. {label}{mark}")
    raw = input("> ").strip().lower()
    if raw in ("q", "quit", "exit", "b", "back"):
        return None
    if raw == "":
        return MODES[rec_idx][1] if rec_idx is not None else None
    if raw.isdigit() and 1 <= int(raw) <= len(MODES):
        return MODES[int(raw) - 1][1]
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

    # Ask for the model first so the mode recommendation can be model-aware.
    model = input("\nModel override (blank = use config default): ").strip()
    effective = model or configured_translator(_repo_root() / DEFAULT_CONFIG)
    guidance = model_guidance(effective)
    if effective:
        print(f"\nModel:      {effective}")
    else:
        print("\nModel:      (config default - could not read settings.yaml)")
    print(f"Guidance:   {guidance['note']}")
    print(f"Best mode:  {guidance['mode']}")

    mode = pick_mode(guidance["mode"])
    if mode is None:
        return 0

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


def action_change_model(_input_dir: Path) -> int:
    """Change the Ollama model for a pipeline role (from change_model.py)."""
    config_path = _repo_root() / DEFAULT_CONFIG
    if not config_path.exists():
        print(f"[error] config not found: {config_path}", file=sys.stderr)
        return 1

    lines = config_path.read_text(encoding="utf-8").splitlines(keepends=True)
    try:
        current = _read_current_models(lines)
    except KeyError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    installed = fetch_installed_models(DEFAULT_OLLAMA_URL)

    # Show current state
    print("\nCurrent model mapping (config/settings.yaml):")
    for role in MODEL_ROLES:
        print(f"  {role:<11} {current.get(role, '(unset)')}")
    if installed:
        print("\nInstalled Ollama models:")
        for i, name in enumerate(installed, 1):
            print(f"  {i:>2}. {name}")
    else:
        print("\n(No Ollama models found — is Ollama running?)")

    # Pick role
    print("\nPick a role to change (number or q to go back):")
    for i, role in enumerate(MODEL_ROLES, 1):
        print(f"  {i}. {role}")
    sel = input("> ").strip().lower()
    if sel in ("q", "quit", "exit", ""):
        return 0
    if not (sel.isdigit() and 1 <= int(sel) <= len(MODEL_ROLES)):
        print("  Invalid selection.")
        return 0
    role = MODEL_ROLES[int(sel) - 1]

    # Pick model
    print(f"\nSelect a model for '{role}' (number or type a name):")
    for i, name in enumerate(installed, 1):
        mark = " (current)" if name == current.get(role) else ""
        print(f"  {i:>2}. {name}{mark}")
    raw = input("> ").strip()
    if not raw:
        return 0
    if raw.isdigit():
        idx = int(raw) - 1
        if 0 <= idx < len(installed):
            model = installed[idx]
        else:
            print("  Invalid number.")
            return 0
    else:
        model = raw

    if installed and model not in installed:
        ans = input(f"  '{model}' is not installed. Use anyway? [y/N] ").strip().lower()
        if ans != "y":
            return 0

    # Apply changes
    if _set_role_model(lines, role, model):
        tuning_changes = _apply_model_tuning(lines, model)
        config_path.write_text("".join(lines), encoding="utf-8")
        print(f"\n  [OK] {role} -> {model}")
        if tuning_changes:
            for field, (old, new) in tuning_changes.items():
                print(f"       {field}: {old} -> {new}")
        else:
            prof = model_profile(model)
            print(f"       settings already match {model}'s profile")
        print(f"  Saved to {config_path}")
    else:
        print(f"  [error] could not find '{role}' in models block")

    return 0


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
    ("Change Ollama model", action_change_model),
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
