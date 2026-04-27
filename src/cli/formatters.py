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
    else:
        stages = [
            ("1. Preprocessing", "pending", "Chunking input text"),
            ("2. Translation", "pending", f"Using {config.models.translator}"),
            ("3. Refinement", "pending", "Literary quality edit" if not skip_refinement else "SKIPPED"),
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
