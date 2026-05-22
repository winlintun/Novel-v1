#!/usr/bin/env python3
"""
Seed "Outside of Time" (光阴之外) novel-specific glossary terms into SQLite.

These terms are specific to Er Gen's "Outside of Time" novel.
Run after the global terms seed:
    python scripts/seed_outside_of_time_terms.py

Terms use novel_id='novel_outside_of_time' and scope='novel'.
"""

import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.connection import DatabaseConnection
from src.db.schema import SchemaManager
from src.db.repositories.glossary_repo import GlossaryRepository
from src.db.repositories.novel_repo import NovelRepository

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

NOVEL_ID = "novel_outside_of_time"
NOVEL_NAME = "outside-of-time"

# Format: (source_cn, target_mm, category, enforcement_level)
NOVEL_TERMS = [
    # ── Character Names (CRITICAL — pinyin-based transliteration) ──
    # Format: (source_cn, target_mm, category, enforcement_level, variants)
    ("许青", "ရွှီချင်း", "character", "hard", ["ရှူးချင်း", "ရှူချင်း", "ရှူချင်"]),
    ("紫阙", "ကျစ်လွီဆဲ့", "character", "hard", ["ခရမ်းစိမ်း"]),
    ("紫阙太子", "ကျစ်လွီဆဲ့အိမ်ရှေ့စံ", "character", "hard", []),
    ("杨署", "အမတ်ယောင်", "character", "hard", ["မင်းကြီးယောင်"]),
    ("府主", "ရုံးတော်သခင်", "character", "hard", ["မင်းကြီး"]),
    ("暮沙", "မိုဆာဆော", "character", "hard", ["ဘုံတာအိုမိုဆာ"]),

    # ── Titles ──
    ("副府主", "လက်ထောက်ဒေသအကြီးအကဲ", "title", "hard"),
    ("府主", "ရုံးတော်သခင်", "title", "hard"),
    ("队长", "တပ်မှူး", "title", "soft"),

    # ── Organizations ──
    ("三局", "ရုံးတော်သုံးခု", "organization", "hard"),
    ("执法局", "တရားရေးရုံးတော်", "organization", "hard"),
    ("监察局", "ပြည်ထဲရေးရုံးတော်", "organization", "hard"),
    ("刀楼", "ဓားကိုင်ရုံးတော်", "organization", "hard"),

    # ── Places ──
    ("凤海", "ဖုန်းဟိုင်", "place", "hard"),
    ("凤海小域", "ဖုန်းဟိုင်ဒေသငယ်", "place", "hard"),
    ("南煌", "နန်းဟွမ်", "place", "hard"),
    ("南煌大地", "နန်းဟွမ်ကုန်းမြေ", "place", "hard"),
    ("紫阙帝国", "ကျစ်လွီဆဲ့တိုင်းပြည်", "place", "hard"),

    # ── Cultivation Terms (Outside of Time specific) ──
    ("元婴", "ဝိညာဉ်နတ်သူငယ်", "cultivation_concept", "hard"),
    ("命", "ကမ္မ", "cultivation_concept", "hard"),
    ("命门", "ကမ္မသရဖူ", "cultivation_concept", "hard"),
    ("第九", "နဝမ", "power_level", "hard"),
    ("第十", "ဒသမ", "power_level", "hard"),
    ("第十一", "ဧကာဒသမ", "power_level", "hard"),
    ("证人", "သက်သေ", "term", "hard"),
    ("平民", "သေမျိုး", "term", "hard"),
    ("祭坛", "စင်မြင့်", "place", "soft"),
    ("刀客", "ဓားကိုင်", "term", "soft"),
    ("刀客们", "ဓားကိုင်တွေ", "term", "soft"),
    ("刀", "ဓား", "term", "soft"),

    # ── D132 (convert to Myanmar script) ──
    ("D132", "ဃ၁၃၂", "term", "hard"),

    # ── Common terms in this novel ──
    ("修炼者", "ကျင့်ကြံသူ", "term", "soft"),
    ("凡人", "သေမျိုး", "term", "soft"),
    ("禁网", "တားမြစ်ပိုက်ကွန်", "term", "soft"),
    ("极寒", "အစွန်းရောက်အအေးဒဏ်", "term", "soft"),
    ("战场", "စစ်မြေပြင်", "place", "soft"),
    ("石光", "ကျောက်ရှာအလင်း", "term", "soft"),
    ("彩虹", "သက်တံ့အရောင်", "term", "soft"),
]


def seed_novel_terms(db_path: str = "data/novel_translation.db") -> dict:
    """Seed Outside of Time specific terms into the database."""
    db = DatabaseConnection(db_path)
    schema = SchemaManager(db)
    schema.create_all()

    repo = GlossaryRepository(db)
    novel_repo = NovelRepository(db)

    if not novel_repo.exists(NOVEL_ID):
        novel_repo.create(NOVEL_ID, NOVEL_NAME, "chinese")
        logger.info(f"Created novel entry: {NOVEL_ID}")

    existing = repo.get_terms_by_novel(NOVEL_ID, include_global=False)
    existing_sources = {t["source_term"] for t in existing}

    added = 0
    skipped = 0

    for entry in NOVEL_TERMS:
        if len(entry) == 5:
            source, target, category, enforcement, variants = entry
        elif len(entry) == 4:
            source, target, category, enforcement = entry
            variants = []
        else:
            skipped += 1
            continue

        if source in existing_sources:
            skipped += 1
            continue

        try:
            repo.add_term(
                novel_id=NOVEL_ID,
                source_term=source,
                target_term=target,
                category=category,
                status="approved",
                enforcement_level=enforcement,
                confidence=0.95,
                variants=variants,
            )
            added += 1
            existing_sources.add(source)
        except Exception as e:
            logger.warning(f"Failed to add term '{source}': {e}")
            skipped += 1

    db.close()

    summary = {
        "added": added,
        "skipped": skipped,
        "total_novel": len(existing_sources) + added,
    }
    return summary


if __name__ == "__main__":
    db_path = "data/novel_translation.db"
    logger.info(f"Seeding '{NOVEL_NAME}' terms into {db_path}...")
    summary = seed_novel_terms(db_path)

    print(f"\n{'='*50}")
    print(f"  Outside of Time — Glossary Seed Complete")
    print(f"{'='*50}")
    print(f"  Added:          {summary['added']}")
    print(f"  Skipped (dup):  {summary['skipped']}")
    print(f"  Total novel:    {summary['total_novel']}")
    print(f"{'='*50}")
