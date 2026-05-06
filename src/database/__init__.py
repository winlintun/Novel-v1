# src/database/__init__.py
"""
Database module for Novel Translation Project.
Implements SQLite schema from sql_blueprint.md.
"""

from src.database.db_manager import DatabaseManager
from src.database.init_db import init_database, get_schema_version

__all__ = ['DatabaseManager', 'init_database', 'get_schema_version']