#!/usr/bin/env python3
"""
Seed global xianxia/cultivation terms into the database.

These terms are available to ALL novels automatically (scope='global',
novel_id='novel_global_xianxia'). MemoryManager also auto-seeds them on startup
when the global set is empty, so running this by hand is usually unnecessary —
it remains as an explicit one-shot / re-seed entry point.

    python scripts/seed_global_terms.py

The seed data and logic now live in src/db/global_terms_seed.py (single source
of truth); this file is a thin CLI wrapper over it.
"""

import sys
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.global_terms_seed import seed_global_terms

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


if __name__ == "__main__":
    db_path = "data/novel_translation.db"

    logger.info(f"Seeding global xianxia terms into {db_path}...")
    summary = seed_global_terms(db_path)

    print(f"\n{'='*50}")
    print("  Global Xianxia Terms — Seed Complete")
    print(f"{'='*50}")
    print(f"  Added:          {summary['added']}")
    print(f"  Skipped (dup):  {summary['skipped']}")
    print(f"  Total global:   {summary['total_global']}")
    print(f"{'='*50}")
