#!/usr/bin/env python3
"""
Database lock diagnostic and recovery tool.
Helps diagnose and fix SQLite database locking issues.
"""

import sqlite3
import os
import sys
import time
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def check_database_lock(db_path: str = "data/novel_translation.db") -> dict:
    """Check if the database is locked and gather diagnostic info."""
    db_file = Path(db_path)
    results = {
        "db_exists": db_file.exists(),
        "db_path": str(db_file.absolute()),
        "db_size_mb": 0,
        "is_locked": False,
        "can_read": False,
        "can_write": False,
        "wal_mode": False,
        "journal_exists": False,
        "shm_exists": False,
        "connections": [],
        "error": None
    }
    
    if not results["db_exists"]:
        results["error"] = "Database file does not exist"
        return results
    
    # Check file size
    results["db_size_mb"] = round(db_file.stat().st_size / (1024 * 1024), 2)
    
    # Check for WAL files
    wal_file = db_file.parent / f"{db_file.name}-wal"
    shm_file = db_file.parent / f"{db_file.name}-shm"
    journal_file = db_file.parent / f"{db_file.name}-journal"
    
    results["wal_exists"] = wal_file.exists()
    results["shm_exists"] = shm_file.exists()
    results["journal_exists"] = journal_file.exists()
    
    # Try to connect in read-only mode
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=1)
        conn.execute("SELECT 1")
        conn.close()
        results["can_read"] = True
    except sqlite3.OperationalError as e:
        if "database is locked" in str(e).lower():
            results["is_locked"] = True
        results["error"] = str(e)
    except Exception as e:
        results["error"] = str(e)
    
    # Try to connect in read-write mode
    if not results["is_locked"]:
        try:
            conn = sqlite3.connect(db_path, timeout=1)
            conn.execute("SELECT 1")
            conn.close()
            results["can_write"] = True
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e).lower():
                results["is_locked"] = True
                results["can_write"] = False
        except Exception as e:
            results["error"] = str(e)
    
    # Check WAL mode
    if results["can_read"]:
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            cursor = conn.execute("PRAGMA journal_mode")
            mode = cursor.fetchone()[0]
            results["wal_mode"] = (mode == "wal")
            conn.close()
        except Exception as e:
            logger.warning(f"Could not check journal mode: {e}")
    
    # Check for active processes (Linux only)
    try:
        import subprocess
        result = subprocess.run(
            ["lsof", str(db_file)],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            for line in lines[1:]:  # Skip header
                parts = line.split()
                if len(parts) >= 2:
                    results["connections"].append({
                        "command": parts[0],
                        "pid": parts[1]
                    })
    except Exception:
        pass  # lsof not available or other error
    
    return results


def force_close_connections(db_path: str) -> bool:
    """Attempt to force close connections by creating a lock file."""
    logger.info("Attempting to force close connections...")
    logger.warning("Note: This may not work on all systems")
    
    # On Linux, we could try to kill processes
    try:
        import subprocess
        db_file = Path(db_path).absolute()
        result = subprocess.run(
            ["fuser", "-k", str(db_file)],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            logger.info("Killed processes holding database lock")
            time.sleep(1)  # Wait for cleanup
            return True
    except Exception as e:
        logger.error(f"Could not kill processes: {e}")
    
    return False


def recover_database(db_path: str) -> bool:
    """Attempt to recover a locked database."""
    db_file = Path(db_path)
    
    if not db_file.exists():
        logger.error(f"Database not found: {db_path}")
        return False
    
    logger.info(f"Attempting to recover database: {db_path}")
    
    # Backup current database
    backup_path = db_file.parent / f"{db_file.name}.backup.{int(time.time())}"
    logger.info(f"Creating backup: {backup_path}")
    
    import shutil
    try:
        shutil.copy2(db_file, backup_path)
    except Exception as e:
        logger.error(f"Failed to create backup: {e}")
        return False
    
    # Try to recover using SQLite's recovery
    try:
        conn = sqlite3.connect(db_path, timeout=30)
        conn.execute("PRAGMA integrity_check")
        conn.execute("PRAGMA optimize")
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.close()
        logger.info("Database recovery successful")
        return True
    except sqlite3.OperationalError as e:
        logger.error(f"Recovery failed: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during recovery: {e}")
        return False


def main():
    """Main diagnostic function."""
    db_path = sys.argv[1] if len(sys.argv) > 1 else "data/novel_translation.db"
    
    print("=" * 60)
    print("Database Lock Diagnostic Tool")
    print("=" * 60)
    print()
    
    print(f"Checking database: {db_path}")
    print()
    
    results = check_database_lock(db_path)
    
    # Print results
    print("Database Status:")
    print(f"  Exists: {results['db_exists']}")
    print(f"  Path: {results['db_path']}")
    print(f"  Size: {results['db_size_mb']} MB")
    print()
    
    print("Lock Status:")
    print(f"  Is Locked: {results['is_locked']}")
    print(f"  Can Read: {results['can_read']}")
    print(f"  Can Write: {results['can_write']}")
    print()
    
    print("WAL Status:")
    print(f"  WAL Mode: {results['wal_mode']}")
    print(f"  WAL File Exists: {results['wal_exists']}")
    print(f"  SHM File Exists: {results['shm_exists']}")
    print(f"  Journal Exists: {results['journal_exists']}")
    print()
    
    if results['connections']:
        print("Active Connections:")
        for conn in results['connections'][:10]:  # Show first 10
            print(f"  PID {conn['pid']}: {conn['command']}")
        print()
    
    if results['error']:
        print(f"Error: {results['error']}")
        print()
    
    # Recovery options
    if results['is_locked']:
        print("Database is LOCKED!")
        print()
        print("Options:")
        print("1. Wait for other processes to finish")
        print("2. Check for running Python processes: ps aux | grep python")
        print("3. Kill processes using: python scripts/diagnose_db.py --kill")
        print("4. Try recovery: python scripts/diagnose_db.py --recover")
        print()
        
        if "--kill" in sys.argv:
            if force_close_connections(db_path):
                print("Processes killed. Retrying...")
                time.sleep(2)
                results = check_database_lock(db_path)
                if not results['is_locked']:
                    print("✓ Database is now unlocked!")
                else:
                    print("✗ Database is still locked")
        
        elif "--recover" in sys.argv:
            if recover_database(db_path):
                print("✓ Recovery successful!")
            else:
                print("✗ Recovery failed")
    else:
        print("✓ Database is accessible")
    
    print()
    print("=" * 60)


if __name__ == "__main__":
    main()
