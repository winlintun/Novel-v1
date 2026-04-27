#!/usr/bin/env python3
"""
Core module for the novel translation pipeline.

Provides core functionality including:
- Dependency injection container
- Protocol definitions
- Base classes
"""

from src.core.container import Container, create_container

__all__ = [
    "Container",
    "create_container",
]
