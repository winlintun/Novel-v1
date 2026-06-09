#!/usr/bin/env python3
"""
Import universal glossary blueprint JSON into the SQLite database.

Maps the blueprint format (source_term, target_term, aliases, category,
priority, novel_count, novel_appearances) into DB glossary_terms records
with scope='global' and novel_id='novel_global_xianxia'.

Usage:
    python scripts/import_universal_glossary.py
    python scripts/import_universal_glossary.py --db-path custom/path.db
    python scripts/import_universal_glossary.py --blueprint custom/path.json
    python scripts/import_universal_glossary.py --dry-run
"""

import json
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.connection import DatabaseConnection
from src.db.schema import SchemaManager
from src.db.repositories.glossary_repo import GlossaryRepository, GLOBAL_NOVEL_ID
from src.db.repositories.novel_repo import NovelRepository

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

CATEGORY_MAP = {
    "character": "character",
    "location": "location",
    "organization": "organization",
    "item_artifact": "item_artifact",
    "power_level": "power_level",
    "cultivation_concept": "cultivation_concept",
    "event": "event",
    "technique": "technique",
    "title_honorific": "title_honorific",
}

STATUS_MAP = {
    "draft": "pending",
    "candidate": "pending",
    "reviewed": "pending",
    "approved": "approved",
    "verified": "approved",
}


def priority_to_confidence(priority: int) -> float:
    if priority >= 9:
        return 0.95
    elif priority >= 7:
        return 0.85
    elif priority >= 5:
        return 0.70
    elif priority >= 3:
        return 0.50
    return 0.30


def import_glossary_blueprint(
    db_path: str = "data/novel_translation.db",
    blueprint_path: str = "data/universal_glossary_blueprint.json",
    dry_run: bool = False,
) -> dict:
    db = DatabaseConnection(db_path)
    schema = SchemaManager(db)
    schema.create_all()

    novel_repo = NovelRepository(db)
    repo = GlossaryRepository(db)

    if not novel_repo.exists(GLOBAL_NOVEL_ID):
        if dry_run:
            logger.info(f"[DRY RUN] Would create global novel: {GLOBAL_NOVEL_ID}")
        else:
            novel_repo.create(GLOBAL_NOVEL_ID, "Global Xianxia Terms", "universal")
            logger.info(f"Created global novel entry: {GLOBAL_NOVEL_ID}")

    blueprint_path = Path(blueprint_path)
    if not blueprint_path.exists():
        logger.error(f"Blueprint file not found: {blueprint_path}")
        return {"error": f"File not found: {blueprint_path}"}

    with open(blueprint_path, encoding="utf-8-sig") as f:
        data = json.load(f)

    metadata = data.get("metadata", {})
    terms_data = data.get("terms", [])
    logger.info(f"Loaded blueprint: {metadata.get('description', 'unknown')}")
    logger.info(f"Total terms in blueprint: {len(terms_data)}")

    existing = repo.get_global_terms(status=None, limit=9999)
    existing_sources = {(t["source_term"].lower(), t.get("target_term", "")) for t in existing}
    existing_by_source = {}
    for t in existing:
        existing_by_source[t["source_term"].lower()] = t

    added = 0
    skipped_existing = 0
    skipped_placeholder = 0
    variants_added = 0

    for term in terms_data:
        source = term.get("source_term", "").strip()
        target = term.get("target_term", "").strip()
        category_raw = term.get("category", "general")
        category = CATEGORY_MAP.get(category_raw, "general")
        priority = term.get("priority", 5)
        status_raw = term.get("status", "draft")
        status = STATUS_MAP.get(status_raw, "pending")
        aliases_en = term.get("aliases_en", []) or []
        aliases_cn = term.get("aliases_cn", []) or []
        novel_appearances = term.get("novel_appearances", {})
        total_occurrences = term.get("total_occurrences", 0)

        if not source:
            skipped_placeholder += 1
            continue

        source_lower = source.lower()
        if source_lower in existing_by_source:
            skipped_existing += 1
            continue

        confidence = priority_to_confidence(priority)
        if total_occurrences > 100:
            confidence = min(0.98, confidence + 0.10)
        elif total_occurrences > 50:
            confidence = min(0.95, confidence + 0.05)

        notes = term.get("notes", "")
        context_condition = None
        if notes and "placeholder" not in notes.lower():
            context_condition = notes

        if dry_run:
            logger.info(f"[DRY RUN] Would add: {source} -> {target} ({category}, conf={confidence:.2f})")
            if aliases_en or aliases_cn:
                all_aliases = aliases_en + aliases_cn
                logger.info(f"  variants: {all_aliases}")
            added += 1
            continue

        try:
            result = repo.add_term(
                novel_id=GLOBAL_NOVEL_ID,
                source_term=source,
                target_term=target,
                category=category,
                status=status if status != "draft" else "pending",
                enforcement_level="hard",
                context_condition=context_condition,
                confidence=confidence,
                scope="global",
            )

            if result:
                added += 1

                for alias in aliases_en + aliases_cn:
                    alias = alias.strip()
                    if alias and alias != source:
                        try:
                            repo.add_variant(result["id"], alias, match_type="exact")
                            variants_added += 1
                        except Exception as e:
                            logger.debug(f"Failed to add variant '{alias}': {e}")

        except Exception as e:
            logger.warning(f"Failed to add term '{source}': {e}")
            skipped_existing += 1

    db.close()

    summary = {
        "added": added,
        "skipped_existing": skipped_existing,
        "skipped_placeholder": skipped_placeholder,
        "variants_added": variants_added,
        "dry_run": dry_run,
    }

    return summary


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Import universal glossary blueprint into DB")
    parser.add_argument("--db-path", default="data/novel_translation.db", help="Database path")
    parser.add_argument("--blueprint", default="data/universal_glossary_blueprint.json", help="Blueprint JSON path")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no DB writes")

    args = parser.parse_args()

    logger.info(f"Importing universal glossary from {args.blueprint}")
    if args.dry_run:
        logger.info("*** DRY RUN MODE - No changes will be made ***")

    summary = import_glossary_blueprint(
        db_path=args.db_path,
        blueprint_path=args.blueprint,
        dry_run=args.dry_run,
    )

    print(f"\n{'='*50}")
    print(f"  Universal Glossary Import — Complete")
    print(f"{'='*50}")
    print(f"  Added:              {summary.get('added', 0)}")
    print(f"  Skipped (existing): {summary.get('skipped_existing', 0)}")
    print(f"  Skipped (empty):    {summary.get('skipped_placeholder', 0)}")
    print(f"  Variants added:     {summary.get('variants_added', 0)}")
    if summary.get("dry_run"):
        print(f"  *** DRY RUN - No changes committed ***")
    print(f"{'='*50}")
