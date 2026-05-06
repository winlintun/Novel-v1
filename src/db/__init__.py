"""
SQLite database backend for novel translation project.
Replaces JSON-based glossary/context storage with relational schema.
"""

from src.db.connection import DatabaseConnection
from src.db.schema import SchemaManager
from src.db.migrator import JsonToSqlMigrator

__all__ = ["DatabaseConnection", "SchemaManager", "JsonToSqlMigrator"]
