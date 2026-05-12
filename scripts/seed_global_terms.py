#!/usr/bin/env python3
"""
Seed global xianxia/cultivation terms into the database.

These terms are available to ALL novels automatically.
Run once after creating the database:
    python scripts/seed_global_terms.py

Global terms use scope='global' and novel_id='novel_global_xianxia'.
They are automatically included in every novel's glossary prompt.
"""

import sys
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.connection import DatabaseConnection
from src.db.schema import SchemaManager
from src.db.repositories.glossary_repo import GlossaryRepository, GLOBAL_NOVEL_ID

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Global xianxia terms — common cultivation world vocabulary
# Format: (source_term, target_term, category)
GLOBAL_TERMS = [
    # ── Cultivation Energy ──
    ("qi", "ချီ", "energy", "hard"),
    ("Qi", "ချီ", "energy", "hard"),
    ("spiritual energy", "ဝိညာဉ်စွမ်းအင်", "energy", "hard"),
    ("spiritual sense", "ဝိညာဉ်အာရုံ", "energy", "hard"),
    ("spiritual power", "ဝိညာဉ်စွမ်းအား", "energy", "hard"),
    ("true qi", "စစ်မှန်သောချီ", "energy", "hard"),
    ("heavenly qi", "ကောင်းကင်ချီ", "energy", "hard"),
    ("earthly qi", "မြေပြင်ချီ", "energy", "hard"),
    ("demonic qi", "နတ်ဆိုးချီ", "energy", "hard"),
    ("killing intent", "သတ်ဖြတ်လိုစိတ်", "energy", "hard"),
    ("aura", "ထွန်းလင်းတောက်ပမှု", "energy", "hard"),
    ("pressure", "ဖိအား", "energy", "hard"),
    ("spiritual pressure", "ဝိညာဉ်ဖိအား", "energy", "hard"),

    # ── Cultivation Concepts ──
    ("dao", "တရား", "cultivation_concept", "hard"),
    ("Dao", "တရား", "cultivation_concept", "hard"),
    ("Heavenly Dao", "ကောင်းကင်တရား", "cultivation_concept", "hard"),
    ("heavenly dao", "ကောင်းကင်တရား", "cultivation_concept", "hard"),
    ("meridian", "မယ်ရီဒီယန်", "cultivation_concept", "hard"),
    ("meridians", "မယ်ရီဒီယန်များ", "cultivation_concept", "hard"),
    ("dantian", "ဒန်တီယန်", "cultivation_concept", "hard"),
    ("cultivation", "တရားအားထုတ်ခြင်း", "cultivation_concept", "hard"),
    ("cultivator", "တရားအားထုတ်သူ", "cultivation_concept", "hard"),
    ("cultivation base", "တရားအားထုတ်မှုအခြေခံ", "cultivation_concept", "hard"),
    ("breakthrough", "အတားအဆီးကျော်လွန်ခြင်း", "cultivation_concept", "hard"),
    ("bottleneck", "ပုလင်းပိတ်ဆို့မှု", "cultivation_concept", "hard"),
    ("tribulation", "ဆိုးကျိုးသက်ရောက်မှု", "cultivation_concept", "hard"),
    ("heavenly tribulation", "ကောင်းကင်ဆိုးကျိုး", "cultivation_concept", "hard"),
    ("enlightenment", "ဉာဏ်အလင်းရခြင်း", "cultivation_concept", "hard"),
    ("comprehension", "နားလည်သဘောပေါက်ခြင်း", "cultivation_concept", "hard"),
    ("realm", "ဘုံ", "cultivation_concept", "hard"),
    ("stage", "အဆင့်", "cultivation_concept", "hard"),
    ("level", "အဆင့်", "cultivation_concept", "hard"),
    ("foundation", "အုတ်မြစ်", "cultivation_concept", "hard"),
    ("core", "ဗဟိုချက်", "cultivation_concept", "hard"),
    ("nascent soul", "မွေးကင်းစဝိညာဉ်", "cultivation_concept", "hard"),
    ("soul formation", "ဝိညာဉ်ဖွဲ့စည်းခြင်း", "cultivation_concept", "hard"),
    ("immortal", "နတ်ဘုရား", "cultivation_concept", "hard"),
    ("ascension", "နတ်ဘုရားဖြစ်ခြင်း", "cultivation_concept", "hard"),
    ("reincarnation", "ပြန်လည်မွေးဖွားခြင်း", "cultivation_concept", "hard"),
    ("karma", "ကံကြမ္မာ", "cultivation_concept", "hard"),
    ("fate", "ကြမ္မာ", "cultivation_concept", "hard"),
    ("heavenly will", "ကောင်းကင်ဆန္ဒ", "cultivation_concept", "hard"),
    ("laws of heaven", "ကောင်းကင်ဥပဒေသများ", "cultivation_concept", "hard"),

    # ── Common Cultivation Realms (generic) ──
    ("Qi Condensation", "ချီစုပေါင်းဘုံ", "power_level", "hard"),
    ("Foundation Establishment", "အုတ်မြစ်တည်ဆောက်ဘုံ", "power_level", "hard"),
    ("Core Formation", "ဗဟိုချက်ဖွဲ့စည်းဘုံ", "power_level", "hard"),
    ("Golden Core", "ရွှေဗဟိုချက်ဘုံ", "power_level", "hard"),
    ("Nascent Soul", "မွေးကင်းစဝိညာဉ်ဘုံ", "power_level", "hard"),
    ("Soul Formation", "ဝိညာဉ်ဖွဲ့စည်းဘုံ", "power_level", "hard"),
    ("Spirit Severing", "ဝိညာဉ်ဖြတ်တောက်ဘုံ", "power_level", "hard"),
    ("Dao Seeking", "တရားရှာဖွေဘုံ", "power_level", "hard"),
    ("Immortal Ascension", "နတ်ဘုရားဖြစ်ဘုံ", "power_level", "hard"),

    # ── Common Items ──
    ("spirit stone", "ဝိညာဉ်ကျောက်", "item_artifact", "hard"),
    ("spirit stones", "ဝိညာဉ်ကျောက်များ", "item_artifact", "hard"),
    ("pill", "ဆေးလုံး", "item_artifact", "hard"),
    ("pills", "ဆေးလုံးများ", "item_artifact", "hard"),
    ("elixir", "ဆေးရည်", "item_artifact", "hard"),
    ("treasure", "ရတနာ", "item_artifact", "hard"),
    ("magic treasure", "မာဂျစ်ရတနာ", "item_artifact", "hard"),
    ("flying sword", "ပျံသန်းသောဓား", "item_artifact", "hard"),
    ("storage ring", "သိုလှောင်ရေးလက်စွပ်", "item_artifact", "hard"),
    ("storage bag", "သိုလှောင်ရေးအိတ်", "item_artifact", "hard"),
    ("formation flag", "ဖွဲ့စည်းပုံအလံ", "item_artifact", "hard"),
    ("talisman", "တလစ်စမန်", "item_artifact", "hard"),
    ("scroll", "စာလိပ်", "item_artifact", "hard"),
    ("cauldron", "အိုးကြီး", "item_artifact", "hard"),
    ("furnace", "မီးဖို", "item_artifact", "hard"),
    ("artifact", "ရှေးဟောင်းပစ္စည်း", "item_artifact", "hard"),

    # ── Common Organizations ──
    ("sect", "ဂိုဏ်း", "organization", "hard"),
    ("clan", "မျိုးနွယ်စု", "organization", "hard"),
    ("family", "မိသားစု", "organization", "hard"),
    ("pavilion", "ပိဋကတ်", "organization", "hard"),
    ("hall", "ခန်းမ", "organization", "hard"),
    ("tower", "တာဝါ", "organization", "hard"),
    ("valley", "ချိုင့်ဝှမ်း", "organization", "hard"),
    ("mountain", "တောင်", "organization", "hard"),
    ("empire", "အင်ပါယာ", "organization", "hard"),
    ("dynasty", "မင်းဆက်", "organization", "hard"),
    ("kingdom", "နိုင်ငံ", "organization", "hard"),

    # ── Common Titles ──
    ("elder", "သက်ကြီး", "title_honorific", "hard"),
    ("ancestor", "ဘบรรိုး", "title_honorific", "hard"),
    ("patriarch", "မျိုးနွယ်ခေါင်းဆောင်", "title_honorific", "hard"),
    ("master", "ဆရာ", "title_honorific", "hard"),
    ("disciple", "တပည့်", "title_honorific", "hard"),
    ("inner disciple", "အတွင်းတပည့်", "title_honorific", "hard"),
    ("outer disciple", "အပြင်တပည့်", "title_honorific", "hard"),
    ("core disciple", "ဗဟိုတပည့်", "title_honorific", "hard"),
    ("senior brother", "အစ်ကိုကြီး", "title_honorific", "hard"),
    ("junior brother", "ညီငယ်", "title_honorific", "hard"),
    ("senior sister", "အစ်မကြီး", "title_honorific", "hard"),
    ("junior sister", "ညီမငယ်", "title_honorific", "hard"),
    ("young master", "လူငယ်သခင်", "title_honorific", "hard"),
    ("young miss", "မိန်းကလေးသခင်မ", "title_honorific", "hard"),
    ("sect leader", "ဂိုဏ်းခေါင်းဆောင်", "title_honorific", "hard"),
    ("hall master", "ခန်းမဆရာ", "title_honorific", "hard"),
    ("peerless", "အတုမရှိ", "title_honorific", "hard"),
    ("Venerable", "ပူဇော်ထိုက်သူ", "title_honorific", "hard"),
    ("Venerable One", "ပူဇော်ထိုက်သူ", "title_honorific", "hard"),
    ("Expert", "ကျွမ်းကျင်သူ", "title_honorific", "hard"),
    ("Senior", "အကြီးအကဲ", "title_honorific", "hard"),
    ("Junior", "အငယ်အကဲ", "title_honorific", "hard"),

    # ── Common Techniques ──
    ("technique", "နည်းစနစ်", "technique", "hard"),
    ("martial art", "သိုင်းပညာ", "technique", "hard"),
    ("sword art", "ဓားပညာ", "technique", "hard"),
    ("movement technique", "ရွေ့လျားမှုနည်းစနစ်", "technique", "hard"),
    ("body refinement", "ခန္ဓာကိုယ်သန့်စင်ခြင်း", "technique", "hard"),
    ("cultivation technique", "တရားအားထုတ်နည်းစနစ်", "technique", "hard"),
    ("secret technique", "လျှို့ဝှက်နည်းစနစ်", "technique", "hard"),
    ("divine ability", "နတ်စွမ်းရည်", "technique", "hard"),
    ("spell", "မန္တန်", "technique", "hard"),
    ("array", "အခင်းအကျင်း", "technique", "hard"),
    ("formation", "ဖွဲ့စည်းပုံ", "technique", "hard"),

    # ── Common Places ──
    ("heaven", "ကောင်းကင်", "location", "hard"),
    ("earth", "မြေပြင်", "location", "hard"),
    ("mortal realm", "သေတ္တာဘုံ", "location", "hard"),
    ("immortal realm", "နတ်ဘုရားဘုံ", "location", "hard"),
    ("demon realm", "နတ်ဆိုးဘုံ", "location", "hard"),
    ("spirit realm", "ဝိညာဉ်ဘုံ", "location", "hard"),
    ("void", "ဟောင်းဟာ", "location", "hard"),
    ("secret realm", "လျှို့ဝှက်ဘုံ", "location", "hard"),
    ("ancient battlefield", "ရှေးဟောင်းစစ်မြေပြင်", "location", "hard"),
    ("ruins", "အပျက်အစီး", "location", "hard"),
    ("cave", "ဂူ", "location", "hard"),
    ("cave abode", "ဂူနေရာ", "location", "hard"),
    ("market", "ဈေး", "location", "hard"),
    ("auction", "လေလံ", "location", "hard"),
    ("city", "မြို့", "location", "hard"),
    ("village", "ကျေးရွာ", "location", "hard"),

    # ── Common Creatures ──
    ("demon beast", "နတ်ဆိုးတိရစ္ဆာန်", "creature", "hard"),
    ("spirit beast", "ဝိညာဉ်တိရစ္ဆာန်", "creature", "hard"),
    ("magical beast", "မာဂျစ်တိရစ္ဆာန်", "creature", "hard"),
    ("monster", "သတ္တဝါ", "creature", "hard"),
    ("divine beast", "နတ်သတ္တဝါ", "creature", "hard"),
    ("ancient beast", "ရှေးဟောင်းသတ္တဝါ", "creature", "hard"),
    ("dragon", "နဂါး", "creature", "hard"),
    ("phoenix", "ဖီးနစ်", "creature", "hard"),
    ("demon", "နတ်ဆိုး", "creature", "hard"),
    ("devil", "မာရ်နတ်", "creature", "hard"),
    ("immortal", "နတ်ဘုရား", "creature", "hard"),
    ("ghost", "ပြေတ", "creature", "hard"),
    ("spirit", "ဝိညာဉ်", "creature", "hard"),

    # ── Common Concepts ──
    ("life and death", "အသက်နှင့်သေဆုံးခြင်း", "cultivation_concept", "hard"),
    ("yin and yang", "ယင်နှင့်ယန်", "cultivation_concept", "hard"),
    ("five elements", "ဒြပ်စင်ငါးပါး", "cultivation_concept", "hard"),
    ("heaven and earth", "ကောင်းကင်နှင့်မြေပြင်", "cultivation_concept", "hard"),
    ("world", "ကမ္ဘာ", "cultivation_concept", "hard"),
    ("universe", "စကြဝဠာ", "cultivation_concept", "hard"),
    ("chaos", "ထရမ်းကားမှု", "cultivation_concept", "hard"),
    ("origin", "မူလအစ", "cultivation_concept", "hard"),
    ("essence", "အနှစ်သာရ", "cultivation_concept", "hard"),
    ("bloodline", "သွေးမျိုးရိုး", "cultivation_concept", "hard"),
    ("inheritance", "အမွေဆက်ခံခြင်း", "cultivation_concept", "hard"),
    ("legacy", "အမွေအနှစ်", "cultivation_concept", "hard"),
    ("fortune", "ကံကောင်းခြင်း", "cultivation_concept", "hard"),
    ("opportunity", "အခွင့်အရေး", "cultivation_concept", "hard"),
    ("danger", "အန္တရာယ်", "cultivation_concept", "hard"),
    ("life", "အသက်", "cultivation_concept", "hard"),
    ("death", "သေဆုံးခြင်း", "cultivation_concept", "hard"),
]


def seed_global_terms(db_path: str = "data/novel_translation.db") -> dict:
    """Seed global xianxia terms into the database.
    
    Returns:
        Summary dict with counts
    """
    db = DatabaseConnection(db_path)
    schema = SchemaManager(db)
    schema.create_all()
    
    repo = GlossaryRepository(db)
    
    # Ensure global novel exists
    from src.db.repositories.novel_repo import NovelRepository
    novel_repo = NovelRepository(db)
    if not novel_repo.exists(GLOBAL_NOVEL_ID):
        novel_repo.create(GLOBAL_NOVEL_ID, "Global Xianxia Terms", "universal")
        logger.info(f"Created global novel entry: {GLOBAL_NOVEL_ID}")
    
    # Count existing global terms
    existing = repo.get_global_terms()
    existing_sources = {t["source_term"] for t in existing}
    
    added = 0
    skipped = 0
    
    for entry in GLOBAL_TERMS:
        if len(entry) == 4:
            source, target, category, enforcement = entry
        elif len(entry) == 3:
            source, target, category = entry
            enforcement = "hard"
        else:
            # Skip malformed entries (like string-only placeholders)
            skipped += 1
            continue
        
        if source in existing_sources:
            skipped += 1
            continue
        
        try:
            repo.add_global_term(
                source_term=source,
                target_term=target,
                category=category,
                status="approved",
                enforcement_level=enforcement,
                confidence=0.95,
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
        "total_global": len(existing_sources) + added,
    }
    
    return summary


if __name__ == "__main__":
    db_path = "data/novel_translation.db"
    
    logger.info(f"Seeding global xianxia terms into {db_path}...")
    summary = seed_global_terms(db_path)
    
    print(f"\n{'='*50}")
    print(f"  Global Xianxia Terms — Seed Complete")
    print(f"{'='*50}")
    print(f"  Added:          {summary['added']}")
    print(f"  Skipped (dup):  {summary['skipped']}")
    print(f"  Total global:   {summary['total_global']}")
    print(f"{'='*50}")
