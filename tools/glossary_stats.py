#!/usr/bin/env python3
"""
Quick glossary statistics from the database.

Usage:
    python tools/glossary_stats.py
    python tools/glossary_stats.py --novel novel_wayfarer
    python tools/glossary_stats.py --json
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.connection import DatabaseConnection
from src.db.repositories.glossary_repo import GlossaryRepository


def print_stats(novel_id: str = "", as_json: bool = False, db_path: str = "data/novel_translation.db") -> dict:
    db = DatabaseConnection(db_path)
    repo = GlossaryRepository(db)

    all_novels = {}
    try:
        from src.db.repositories.novel_repo import NovelRepository
        novel_repo = NovelRepository(db)
        for n in novel_repo.get_all():
            all_novels[n["id"]] = n["name"]
    except Exception:
        pass

    results = {}

    if novel_id:
        novel_ids = [novel_id]
    else:
        novel_ids = list(all_novels.keys())
        if "novel_global_xianxia" not in novel_ids:
            novel_ids.append("novel_global_xianxia")

    for nid in novel_ids:
        try:
            terms = repo.get_terms_by_novel(nid, limit=9999)
            total = len(terms)
            approved = sum(1 for t in terms if t["status"] == "approved")
            pending = sum(1 for t in terms if t["status"] == "pending")
            rejected = sum(1 for t in terms if t["status"] == "rejected")

            cats: dict[str, int] = {}
            for t in terms:
                c = t.get("category", "general")
                cats[c] = cats.get(c, 0) + 1

            name = all_novels.get(nid, nid)
            results[nid] = {
                "name": name,
                "total": total,
                "approved": approved,
                "pending": pending,
                "rejected": rejected,
                "categories": dict(sorted(cats.items(), key=lambda x: -x[1])),
            }
        except Exception as e:
            results[nid] = {"error": str(e)}

    db.close()

    if as_json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        for nid, stats in results.items():
            if "error" in stats:
                print(f"  {nid}: ERROR - {stats['error']}")
                continue
            print(f"\n{'='*50}")
            print(f"  {stats['name']} ({nid})")
            print(f"{'='*50}")
            print(f"  Total:     {stats['total']}")
            print(f"  Approved:  {stats['approved']}")
            print(f"  Pending:   {stats['pending']}")
            print(f"  Rejected:  {stats['rejected']}")
            if stats["categories"]:
                print(f"\n  Categories:")
                for cat, count in stats["categories"].items():
                    bar = "█" * min(count, 40)
                    print(f"    {cat:25s}: {count:4d}  {bar}")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Glossary statistics from database")
    parser.add_argument("--novel", default="", help="Novel ID (default: all novels)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--db-path", default="data/novel_translation.db", help="Database path")

    args = parser.parse_args()
    print_stats(novel_id=args.novel, as_json=args.json, db_path=args.db_path)
