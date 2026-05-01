#!/usr/bin/env python3
"""
CLI output formatters for the novel translation pipeline.

Provides formatted output functions for displaying:
- Translation headers and configuration
- Pipeline step status
- Progress boxes and panels
- Error messages
"""

from typing import List, Tuple, Union, Optional
import sys

from src.config.models import AppConfig


def print_box(title: str, content: List[Union[str, Tuple[str, str]]], width: int = 60) -> None:
    """Print a formatted box with title and content.
    
    Args:
        title: Box title (centered)
        content: List of strings or (label, value) tuples
        width: Box width in characters
    """
    print("╔" + "═" * (width - 2) + "╗")
    print("║" + title.center(width - 2) + "║")
    print("╠" + "═" * (width - 2) + "╣")
    
    for line in content:
        if isinstance(line, tuple):
            # (label, value) pair
            label, value = line
            text = f"  {label}: {value}"
        else:
            text = f"  {line}"
        
        # Truncate if too long
        if len(text) > width - 2:
            text = text[:width - 5] + "..."
        
        print("║" + text.ljust(width - 2) + "║")
    
    print("╚" + "═" * (width - 2) + "╝")


def print_pipeline_status(step: str, status: str, details: str = "") -> None:
    """Print a pipeline step status.
    
    Args:
        step: Step name
        status: Step status (pending, running, complete, error, skip)
        details: Additional details
    """
    icons = {
        "pending": "⏳",
        "running": "🔄",
        "complete": "✅",
        "error": "❌",
        "skip": "⏭️"
    }
    icon = icons.get(status, "•")
    status_text = status.upper()
    
    if details:
        print(f"  {icon} {step:<25} [{status_text}] {details}")
    else:
        print(f"  {icon} {step:<25} [{status_text}]")


def print_translation_header(config: AppConfig, novel: Optional[str] = None) -> None:
    """Print rich formatted translation header with all settings.
    
    Args:
        config: Application configuration
        novel: Novel name (optional)
    """
    print("\n" + "=" * 70)
    print("  📚 NOVEL TRANSLATION PIPELINE")
    print("=" * 70)
    
    if novel:
        print(f"\n  Novel: {novel}")
    
    # Config Info
    print("\n📋 CONFIGURATION")
    print("-" * 70)
    print(f"  Provider:        {config.models.provider.upper()}")
    print(f"  Translator:      {config.models.translator}")
    print(f"  Editor:          {config.models.editor}")
    print(f"  Pipeline Mode:   {config.translation_pipeline.mode.upper()}")
    
    # Processing settings
    print("\n⚙️  PROCESSING SETTINGS")
    print("-" * 70)
    print(f"  Chunk Size:      {config.processing.chunk_size} chars")
    print(f"  Chunk Overlap:   {config.processing.chunk_overlap} chars")
    print(f"  Temperature:     {config.processing.temperature}")
    print(f"  Repeat Penalty:  {config.processing.repeat_penalty}")
    print(f"  Max Retries:     {config.processing.max_retries}")


def print_pipeline_stages(config: AppConfig, skip_refinement: bool = False) -> None:
    """Print pipeline stages based on configuration.
    
    Args:
        config: Application configuration
        skip_refinement: Whether refinement is skipped
    """
    print("\n🔄 PIPELINE STAGES")
    print("-" * 70)
    
    mode = config.translation_pipeline.mode
    
    if mode == "full":
        stages = [
            ("1. Preprocessing", "pending", "Chunking input text"),
            ("2. Translation", "pending", f"Using {config.models.translator}"),
            ("3. Refinement", "pending", "Literary quality edit" if not skip_refinement else "SKIPPED"),
            ("4. Reflection", "pending", "Self-correction" if config.translation_pipeline.use_reflection else "DISABLED"),
            ("5. Quality Check", "pending", "Myanmar linguistic validation"),
            ("6. Consistency", "pending", "Glossary verification"),
            ("7. QA Review", "pending", "Final validation"),
        ]
    elif mode == "lite":
        stages = [
            ("1. Preprocessing", "pending", "Chunking input text"),
            ("2. Translation", "pending", f"Using {config.models.translator}"),
            ("3. Refinement", "pending", "Literary quality edit" if not skip_refinement else "SKIPPED"),
            ("4. Quality Check", "pending", "Myanmar linguistic validation"),
        ]
    elif mode == "fast":
        stages = [
            ("1. Preprocessing", "pending", "Chunking input text"),
            ("2. Translation", "pending", f"Using {config.models.translator}"),
            ("3. Quality Check", "pending", "Myanmar linguistic validation"),
        ]
    elif mode == "single_stage":
        stages = [
            ("1. Preprocessing", "pending", "Chunking input text"),
            ("2. Translation", "pending", f"Using {config.models.translator}"),
            ("3. Quality Check", "pending", "Myanmar linguistic validation"),
            ("4. Consistency", "pending", "Glossary verification"),
            ("5. QA Review", "pending", "Final validation"),
        ]
    else:
        stages = [
            ("1. Preprocessing", "pending", "Chunking input text"),
            ("2. Translation", "pending", f"Using {config.models.translator}"),
            ("3. Refinement", "pending", "Literary quality edit" if not skip_refinement else "SKIPPED"),
            ("4. Quality Check", "pending", "Myanmar linguistic validation"),
            ("5. Consistency", "pending", "Glossary verification"),
            ("6. QA Review", "pending", "Final validation"),
        ]
    
    for stage_name, status, details in stages:
        print_pipeline_status(stage_name, status, details)
    
    print("\n" + "=" * 70)
    print()


def print_progress_bar(current: int, total: int, width: int = 50) -> None:
    """Print a progress bar.
    
    Args:
        current: Current progress
        total: Total items
        width: Bar width in characters
    """
    if total == 0:
        return
    
    percent = current / total
    filled = int(width * percent)
    bar = "█" * filled + "░" * (width - filled)
    
    print(f"\r  [{bar}] {current}/{total} ({percent*100:.1f}%)", end="", flush=True)
    
    if current >= total:
        print()  # New line when complete


def print_error(message: str, details: Optional[str] = None) -> None:
    """Print an error message.
    
    Args:
        message: Error message
        details: Additional error details
    """
    print(f"\n❌ ERROR: {message}")
    if details:
        print(f"   Details: {details}")


def print_warning(message: str) -> None:
    """Print a warning message.
    
    Args:
        message: Warning message
    """
    print(f"\n⚠️  WARNING: {message}")


def print_success(message: str) -> None:
    """Print a success message.
    
    Args:
        message: Success message
    """
    print(f"\n✅ {message}")


def print_info(message: str) -> None:
    """Print an info message.
    
    Args:
        message: Info message
    """
    print(f"  ℹ️  {message}")


def print_section_header(title: str) -> None:
    """Print a section header.
    
    Args:
        title: Section title
    """
    print(f"\n{'─' * 70}")
    print(f"  {title}")
    print(f"{'─' * 70}")


def print_auto_detection_result(source_lang: str, workflow: str, models: dict) -> None:
    """Print auto-detection results in a formatted banner.
    
    Args:
        source_lang: Detected source language ('chinese', 'english', or 'unknown')
        workflow: Selected workflow ('way1' or 'way2')
        models: Dictionary of selected models with keys like 'translator', 'editor', etc.
    """
    print("\n" + "=" * 70)
    print("  🔍 AUTO-DETECTION RESULTS")
    print("=" * 70)
    
    # Language emoji
    lang_emoji = {"chinese": "🇨🇳", "english": "🇬🇧", "unknown": "❓"}
    lang_display = source_lang.upper() if source_lang != "unknown" else "UNKNOWN"
    
    print(f"\n  Source Language: {lang_emoji.get(source_lang, '❓')} {lang_display}")
    
    # Workflow info
    if workflow == "way1":
        print(f"  Workflow:        🔄 way1 (EN → MM direct)")
        print(f"  Description:     English to Myanmar direct translation")
    elif workflow == "way2":
        print(f"  Workflow:        🔄 way2 (CN → EN → MM pivot)")
        print(f"  Description:     Chinese to English to Myanmar pivot translation")
    else:
        print(f"  Workflow:        ⚠️  Using config default")
    
     # Model info
    if models:
        print(f"\n  🤖 Auto-Selected Models:")
        for role, model in models.items():
            print(f"     • {role.capitalize():12} {model}")
    
    print("\n" + "=" * 70)
    print()


# ---------------------------------------------------------------------------
#  Live Progress Display — per-chunk translation status
# ---------------------------------------------------------------------------

# ANSI color codes for terminal output
class _Color:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RESET = '\033[0m'


def _color_status(score: float, passed: bool) -> str:
    """Return color-coded score string."""
    if passed and score >= 85:
        return f"{_Color.GREEN}{score:.0f} ✓{_Color.RESET}"
    elif passed:
        return f"{_Color.CYAN}{score:.0f} ✓{_Color.RESET}"
    elif score >= 50:
        return f"{_Color.YELLOW}{score:.0f} ⚠{_Color.RESET}"
    else:
        return f"{_Color.RED}{score:.0f} ✗{_Color.RESET}"


def print_progress_event(event: dict, novel_name: str = "") -> None:
    """Handle a progress event from the pipeline and display it.

    Args:
        event: Progress event dict with 'type' key
        novel_name: Novel name for context (optional)
    """
    etype = event.get("type", "")

    if etype == "preprocess_start":
        char_count = event.get("char_count", 0)
        chapter = event.get("chapter", "")
        print()
        print(f"{_Color.CYAN}{'─' * 70}{_Color.RESET}")
        print(f"  {_Color.BOLD}📄 Input{_Color.RESET}  {chapter}")
        print(f"  {_Color.DIM}Characters:{_Color.RESET} {char_count:,}")

    elif etype == "preprocess_done":
        chunk_count = event.get("chunk_count", 0)
        chunk_size = event.get("chunk_size", 0)
        duration = event.get("duration", 0)
        print(f"  {_Color.DIM}Chunks:{_Color.RESET}     {chunk_count} ({chunk_size} chars each)")
        print(f"  {_Color.DIM}Preprocess:{_Color.RESET} {duration:.2f}s")
        print(f"{_Color.CYAN}{'─' * 70}{_Color.RESET}")

    elif etype == "chunk_start":
        idx = event.get("chunk_index", 0)
        total = event.get("total_chunks", 0)
        chars = event.get("char_count", 0)
        pct = f"[{idx}/{total}]"
        print(f"\n  {_Color.BOLD}{_Color.MAGENTA}🔄 Chunk {pct}{_Color.RESET} ({chars:,} chars)", end="")
        sys.stdout.flush()

    elif etype == "chunk_translated":
        duration = event.get("duration", 0)
        print(f" {_Color.DIM}→ Trans ({duration:.1f}s){_Color.RESET}", end="")
        sys.stdout.flush()

    elif etype == "chunk_refined":
        duration = event.get("duration", 0)
        print(f" {_Color.DIM}→ Refined ({duration:.1f}s){_Color.RESET}", end="")
        sys.stdout.flush()

    elif etype == "chunk_reflected":
        duration = event.get("duration", 0)
        print(f" {_Color.DIM}→ Reflect ({duration:.1f}s){_Color.RESET}", end="")
        sys.stdout.flush()

    elif etype == "chunk_quality":
        score = event.get("score", 0)
        passed = event.get("passed", False)
        issues = event.get("issue_count", 0)
        mm_ratio = event.get("myanmar_ratio")

        status_str = _color_status(score, passed)
        print(f" {_Color.DIM}→ Quality:{_Color.RESET} {status_str}", end="")
        if mm_ratio is not None:
            ratio_color = _Color.GREEN if mm_ratio >= 0.70 else _Color.RED
            print(f" {_Color.DIM}MM:{_Color.RESET} {ratio_color}{mm_ratio:.0%}{_Color.RESET}", end="")
        if issues > 0:
            print(f" {_Color.YELLOW}({issues} issues){_Color.RESET}", end="")
        sys.stdout.flush()

    elif etype == "chunk_consistency":
        issue_count = event.get("issue_count", 0)
        if issue_count > 0:
            print(f" {_Color.DIM}→ Glossary:{_Color.RESET} {_Color.YELLOW}{issue_count} mismatches{_Color.RESET}", end="")
            sys.stdout.flush()

    elif etype == "chunk_complete":
        duration = event.get("duration", 0)
        print(f" {_Color.DIM}[{duration:.1f}s total]{_Color.RESET}")

    elif etype == "chunk_qa":
        score = event.get("score", 0)
        passed = event.get("passed", False)
        issues = event.get("issue_count", 0)
        status_str = _color_status(score, passed)
        print(f" {_Color.DIM}→ QA:{_Color.RESET} {status_str}", end="")
        if issues > 0:
            print(f" {_Color.YELLOW}({issues} issues){_Color.RESET}", end="")
        sys.stdout.flush()

    elif etype == "chunk_error":
        idx = event.get("chunk_index", 0)
        total = event.get("total_chunks", 0)
        error = event.get("error", "")
        print(f"\n  {_Color.RED}❌ Chunk [{idx}/{total}] FAILED:{_Color.RESET} {error[:80]}")

    elif etype == "postprocess":
        dedup = event.get("dedup_removed", 0)
        final_chars = event.get("final_chars", 0)
        if dedup > 0:
            print(f"\n  {_Color.DIM}Postprocess:{_Color.RESET} removed {dedup:,} duplicate char(s), {final_chars:,} chars final")

    elif etype == "save_start":
        path = event.get("output_path", "")
        print(f"\n  {_Color.DIM}💾 Saving to:{_Color.RESET} {path}")

    elif etype == "save_done":
        path = event.get("output_path", "")
        size = event.get("file_size", 0)
        print(f"  {_Color.GREEN}✅ Saved:{_Color.RESET} {path} ({size:,} bytes)")

    elif etype == "summary":
        total_chunks = event.get("total_chunks", 0)
        avg_score = event.get("avg_score", 0)
        total_time = event.get("total_time", 0)
        output_path = event.get("output_path", "")
        file_size = event.get("file_size", 0)
        issues_total = event.get("issues_total", 0)

        score_color = _Color.GREEN if avg_score >= 70 else _Color.YELLOW
        print(f"\n{_Color.CYAN}{'═' * 70}{_Color.RESET}")
        print(f"  {_Color.BOLD}📊 TRANSLATION SUMMARY{_Color.RESET}")
        print(f"{_Color.CYAN}{'─' * 70}{_Color.RESET}")
        print(f"  {_Color.DIM}Chunks:{_Color.RESET}       {total_chunks}")
        print(f"  {_Color.DIM}Avg Quality:{_Color.RESET}  {score_color}{avg_score:.0f}/100{_Color.RESET}")
        print(f"  {_Color.DIM}Total Time:{_Color.RESET}   {total_time:.1f}s")
        if issues_total > 0:
            print(f"  {_Color.DIM}Issues:{_Color.RESET}       {_Color.YELLOW}{issues_total}{_Color.RESET}")
        else:
            print(f"  {_Color.DIM}Issues:{_Color.RESET}       None")
        print(f"  {_Color.DIM}Output:{_Color.RESET}       {output_path} ({file_size:,} bytes)")
        print(f"{_Color.CYAN}{'═' * 70}{_Color.RESET}\n")
