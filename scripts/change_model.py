#!/usr/bin/env python3
"""Interactive terminal tool to change the Ollama model used for each pipeline role.

Lists the models actually installed in your local Ollama instance, shows the
model currently configured for each role in ``config/settings.yaml``, and lets
you reassign a role to a different model. The YAML file is edited in place with
line-targeted replacements so comments and formatting are preserved.

Usage:
    python -m scripts.change_model                 # interactive
    python scripts/change_model.py                 # interactive
    python scripts/change_model.py --list          # just print current state
    python scripts/change_model.py --set translator=padauk-gemma:q8_0
    python scripts/change_model.py --config config/settings.yaml

Stability: every Ollama call has a timeout and every parse/IO is guarded so the
tool never crashes the way AGENTS.md forbids.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

# Roles that live under the top-level `models:` block and are consumed by the
# pipeline (see src/cli/commands.py, src/pipeline/orchestrator.py).
ROLES = ["translator", "refiner", "checker", "editor"]

DEFAULT_CONFIG = "config/settings.yaml"
DEFAULT_OLLAMA_URL = "http://localhost:11434"
HTTP_TIMEOUT = 10  # seconds -- NO HANGING REQUESTS


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def fetch_installed_models(base_url: str) -> list[str]:
    """Return sorted model names installed in Ollama, or [] on any failure."""
    url = base_url.rstrip("/") + "/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=HTTP_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[warn] Could not reach Ollama at {url}: {exc}", file=sys.stderr)
        return []
    models = [m.get("name", "") for m in data.get("models", []) if m.get("name")]
    return sorted(models)


def find_models_block(lines: list[str]) -> tuple[int, int]:
    """Return [start, end) line indices of the top-level `models:` block body."""
    start = None
    for i, line in enumerate(lines):
        if re.match(r"^models:\s*(#.*)?$", line):
            start = i + 1
            break
    if start is None:
        raise KeyError("`models:` block not found in config")
    end = len(lines)
    for i in range(start, len(lines)):
        # next top-level key (no indentation) ends the block
        if lines[i] and not lines[i][0].isspace() and not lines[i].startswith("#"):
            end = i
            break
    return start, end


def read_current_models(lines: list[str]) -> dict[str, str]:
    start, end = find_models_block(lines)
    current: dict[str, str] = {}
    for i in range(start, end):
        m = re.match(r"^(\s+)(\w+):\s*(\S+)", lines[i])
        if m and m.group(2) in ROLES:
            current[m.group(2)] = m.group(3)
    return current


def set_role_model(lines: list[str], role: str, model: str) -> bool:
    """Replace the value for `role` in the models block. Returns True if changed."""
    start, end = find_models_block(lines)
    for i in range(start, end):
        m = re.match(rf"^(\s+)({re.escape(role)}):\s*(\S+)(.*)$", lines[i])
        if m:
            indent, key, _old, trailing = m.groups()
            # preserve an inline comment if present in the trailing text
            comment = ""
            hash_idx = trailing.find("#")
            if hash_idx != -1:
                comment = "  " + trailing[hash_idx:].strip()
            lines[i] = f"{indent}{key}: {model}{comment}\n"
            return True
    return False


def print_state(current: dict[str, str], installed: list[str]) -> None:
    print("\nCurrent role -> model mapping (config/settings.yaml):")
    for role in ROLES:
        print(f"  {role:<11} {current.get(role, '(unset)')}")
    print("\nInstalled Ollama models:")
    if installed:
        for i, name in enumerate(installed, 1):
            print(f"  {i:>2}. {name}")
    else:
        print("  (none found -- is Ollama running?)")


def prompt_choice(prompt: str, options: list[str]) -> str | None:
    """Prompt the user to pick from options by number. Returns choice or None."""
    raw = input(prompt).strip()
    if not raw:
        return None
    if raw.isdigit():
        idx = int(raw) - 1
        if 0 <= idx < len(options):
            return options[idx]
        print("  Invalid number.")
        return None
    return raw  # allow typing a model name directly


def run_interactive(config_path: Path, base_url: str) -> int:
    lines = config_path.read_text(encoding="utf-8").splitlines(keepends=True)
    try:
        current = read_current_models(lines)
    except KeyError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1
    installed = fetch_installed_models(base_url)

    while True:
        print_state(current, installed)
        print("\nPick a role to change (number), or 'q' to quit:")
        for i, role in enumerate(ROLES, 1):
            print(f"  {i}. {role}")
        sel = input("> ").strip().lower()
        if sel in ("q", "quit", "exit", ""):
            print("No changes saved." if sel == "" else "Bye.")
            return 0
        if not (sel.isdigit() and 1 <= int(sel) <= len(ROLES)):
            print("  Invalid selection.")
            continue
        role = ROLES[int(sel) - 1]

        print(f"\nSelect a model for '{role}' (number or type a name):")
        for i, name in enumerate(installed, 1):
            mark = " (current)" if name == current.get(role) else ""
            print(f"  {i:>2}. {name}{mark}")
        model = prompt_choice("> ", installed)
        if not model:
            continue
        if installed and model not in installed:
            ans = input(f"  '{model}' is not installed. Use anyway? [y/N] ").strip().lower()
            if ans != "y":
                continue

        if set_role_model(lines, role, model):
            config_path.write_text("".join(lines), encoding="utf-8")
            current[role] = model
            print(f"  [OK] {role} -> {model}  (saved to {config_path})")
        else:
            print(f"  [error] could not find '{role}' in models block")
    # unreachable


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Change the Ollama model per pipeline role.")
    parser.add_argument("--config", default=DEFAULT_CONFIG, help="Path to settings.yaml")
    parser.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL, help="Ollama base URL")
    parser.add_argument("--list", action="store_true", help="Print current state and exit")
    parser.add_argument(
        "--set",
        metavar="ROLE=MODEL",
        help="Non-interactively set a role, e.g. --set translator=padauk-gemma:q8_0",
    )
    args = parser.parse_args(argv)

    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = _repo_root() / config_path
    if not config_path.exists():
        print(f"[error] config not found: {config_path}", file=sys.stderr)
        return 1

    lines = config_path.read_text(encoding="utf-8").splitlines(keepends=True)

    if args.set:
        if "=" not in args.set:
            print("[error] --set expects ROLE=MODEL", file=sys.stderr)
            return 1
        role, model = (part.strip() for part in args.set.split("=", 1))
        if role not in ROLES:
            print(f"[error] unknown role '{role}'. Valid: {', '.join(ROLES)}", file=sys.stderr)
            return 1
        if set_role_model(lines, role, model):
            config_path.write_text("".join(lines), encoding="utf-8")
            print(f"[OK] {role} -> {model}  (saved to {config_path})")
            return 0
        print(f"[error] could not find '{role}' in models block", file=sys.stderr)
        return 1

    if args.list:
        try:
            current = read_current_models(lines)
        except KeyError as exc:
            print(f"[error] {exc}", file=sys.stderr)
            return 1
        print_state(current, fetch_installed_models(args.ollama_url))
        return 0

    return run_interactive(config_path, args.ollama_url)


if __name__ == "__main__":
    raise SystemExit(main())
