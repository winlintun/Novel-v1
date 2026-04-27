#!/usr/bin/env python3
"""
Web module for the novel translation pipeline.

Provides web UI functionality including:
- Streamlit UI launcher
- Web request handlers
"""

from src.web.launcher import launch_web_ui

__all__ = ["launch_web_ui"]
