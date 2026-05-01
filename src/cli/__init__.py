#!/usr/bin/env python3
"""
CLI module for the novel translation pipeline.

Provides command-line interface functionality including:
- Argument parsing
- Output formatting
- Command handlers
"""

from src.cli.parser import (
    create_parser,
    parse_arguments,
    validate_arguments,
    get_chapter_list,
)

from src.cli.formatters import (
    print_box,
    print_pipeline_status,
    print_translation_header,
    print_pipeline_stages,
    print_progress_bar,
    print_error,
    print_warning,
    print_success,
    print_info,
    print_section_header,
)

from src.cli.commands import (
    setup_logging,
    run_translation_pipeline,
    run_glossary_generation,
    run_ui_launch,
    run_test,
    run_view_file,
)

__all__ = [
    # Parser
    "create_parser",
    "parse_arguments",
    "validate_arguments",
    "get_chapter_list",
    # Formatters
    "print_box",
    "print_pipeline_status",
    "print_translation_header",
    "print_pipeline_stages",
    "print_progress_bar",
    "print_error",
    "print_warning",
    "print_success",
    "print_info",
    "print_section_header",
    # Commands
    "setup_logging",
    "run_translation_pipeline",
    "run_glossary_generation",
    "run_ui_launch",
    "run_test",
    "run_view_file",
]
