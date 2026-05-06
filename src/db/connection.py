"""
SQLite connection manager with WAL mode, foreign keys, and connection pooling.
Improved with retry logic and better concurrency handling.
"""

import sqlite3
import logging
import time
import random
from pathlib import Path
from typing import Optional, Any, Callable
from contextlib import contextmanager
from functools import wraps

logger = logging.getLogger(__name__)


def retry_on_lock(max_retries: int = 5, base_delay: float = 0.1):
    """Decorator to retry database operations on lock errors."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except sqlite3.OperationalError as e:
                    if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                        # Exponential backoff with jitter
                        delay = base_delay * (2 ** attempt) + random.uniform(0, 0.1)
                        logger.warning(f"Database locked, retrying in {delay:.2f}s (attempt {attempt + 1}/{max_retries})")
                        time.sleep(delay)
                    else:
                        raise
            return func(*args, **kwargs)
        return wrapper
    return decorator


class DatabaseConnection:
    """Manages SQLite database connections with safety settings and retry logic."""

    def __init__(self, db_path: str = "data/novel_translation.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection: Optional[sqlite3.Connection] = None
        self._lock = None  # For thread safety if needed

    def connect(self) -> sqlite3.Connection:
        """Create or return existing connection with safety settings."""
        if self._connection is None:
            logger.debug(f"Creating new database connection to {self.db_path}")
            self._connection = sqlite3.connect(
                str(self.db_path),
                timeout=60,  # Increased from 30 to 60 seconds
                check_same_thread=False,
                isolation_level=None,  # Allow autocommit mode for better concurrency
            )
            self._configure_connection(self._connection)
            logger.info(f"Database connected: {self.db_path}")
        return self._connection

    def _configure_connection(self, conn: sqlite3.Connection) -> None:
        """Apply safety and performance settings."""
        # WAL mode allows readers and writers to coexist
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        # Busy timeout - wait up to 60 seconds before failing
        conn.execute("PRAGMA busy_timeout=60000")
        # Synchronous=NORMAL is a good balance between safety and speed with WAL
        conn.execute("PRAGMA synchronous=NORMAL")
        # Cache size - increase for better performance (negative = KB)
        conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
        # Temp store in memory for better performance
        conn.execute("PRAGMA temp_store=MEMORY")
        # mmap_size for faster reads (256MB)
        conn.execute("PRAGMA mmap_size=268435456")
        conn.row_factory = sqlite3.Row

    def close(self) -> None:
        """Close the connection."""
        if self._connection:
            try:
                self._connection.close()
                logger.debug("Database connection closed")
            except sqlite3.Error as e:
                logger.warning(f"Error closing database connection: {e}")
            finally:
                self._connection = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - always close connection."""
        self.close()

    @contextmanager
    def transaction(self):
        """Context manager for atomic transactions with retry logic."""
        conn = self.connect()
        # Begin immediate transaction to acquire write lock early
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield conn
            conn.commit()
            logger.debug("Transaction committed")
        except Exception:
            conn.rollback()
            logger.debug("Transaction rolled back")
            raise

    @contextmanager
    def cursor(self):
        """Context manager for a cursor with auto-close."""
        conn = self.connect()
        cur = conn.cursor()
        try:
            yield cur
        finally:
            cur.close()

    @retry_on_lock(max_retries=5, base_delay=0.1)
    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        """Execute a single statement with retry on lock."""
        with self.cursor() as cur:
            cur.execute(sql, params)
            return cur

    @retry_on_lock(max_retries=5, base_delay=0.1)
    def executemany(self, sql: str, params_list: list[tuple]) -> sqlite3.Cursor:
        """Execute a statement with multiple parameter sets with retry."""
        with self.cursor() as cur:
            cur.executemany(sql, params_list)
            return cur

    @retry_on_lock(max_retries=5, base_delay=0.1)
    def fetchone(self, sql: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        """Execute and fetch one row with retry on lock."""
        with self.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()

    @retry_on_lock(max_retries=5, base_delay=0.1)
    def fetchall(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        """Execute and fetch all rows with retry on lock."""
        with self.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()

    def fetchall_dict(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        """Execute and fetch all rows as dictionaries."""
        rows = self.fetchall(sql, params)
        return [dict(row) for row in rows]

    def row_exists(self, sql: str, params: tuple = ()) -> bool:
        """Check if any row matches the query."""
        result = self.fetchone(sql, params)
        return result is not None

    @property
    def is_open(self) -> bool:
        """Check if connection is open."""
        return self._connection is not None

    def vacuum(self) -> None:
        """Optimize database file size."""
        with self.transaction():
            self.execute("VACUUM")
        logger.info("Database vacuum completed")

    def get_stats(self) -> dict[str, Any]:
        """Get database statistics and settings."""
        conn = self.connect()
        stats = {}
        
        pragmas = [
            'journal_mode',
            'synchronous',
            'cache_size',
            'page_size',
            'busy_timeout',
            'wal_autocheckpoint',
            'freelist_count',
            'page_count'
        ]
        
        for pragma in pragmas:
            try:
                result = conn.execute(f"PRAGMA {pragma}").fetchone()
                stats[pragma] = result[0] if result else None
            except sqlite3.Error as e:
                stats[pragma] = f"Error: {e}"
        
        # Calculate database size
        try:
            page_count = stats.get('page_count', 0) or 0
            page_size = stats.get('page_size', 4096) or 4096
            stats['estimated_size_bytes'] = page_count * page_size
            stats['estimated_size_mb'] = round((page_count * page_size) / (1024 * 1024), 2)
        except Exception as e:
            stats['size_error'] = str(e)
        
        return stats
