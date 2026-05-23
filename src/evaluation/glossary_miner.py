#!/usr/bin/env python3
"""
Universal Glossary Miner: Mines EN→MM term pairs from 6 novels.
Extracts proper nouns from EN files, cross-references with MM files,
and writes to universal_glossary_blueprint.json.

Strategy:
1. Scan each novel's EN files for capitalized multi-word entities (names, places)
2. Scan each novel's MM files for recurring Myanmar sequences
3. Cross-reference using aligned dataset pairs (co-occurrence)
4. Merge across novels (terms appearing in 3+ novels = high confidence)
5. Write to blueprint
"""

import os
import re
import sys
import json
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime
from typing import List, Tuple, Dict, Optional
import math

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

BLUEPRINT_PATH = project_root / "data" / "universal_glossary_blueprint.json"
DATASET_DIR = project_root.parent.parent / "DownloadNovel" / "CreateNovelDataSet"

NOVELS = [
    "a-will-eternal",
    "outside-of-time",
    "eternal-sacred-king",
    "renegade-immortal",
    "daoist-master-of-qing-xuan",
    "we-agreed-on-experiencing-life-so-why-did-you-immortals-become-real",
]

NOVEL_DISPLAY_NAMES = {
    "a-will-eternal": "A Will Eternal",
    "outside-of-time": "Outside of Time",
    "eternal-sacred-king": "Eternal Sacred King",
    "renegade-immortal": "Renegade Immortal",
    "daoist-master-of-qing-xuan": "Daoist Master of Qing Xuan",
    "we-agreed-on-experiencing-life-so-why-did-you-immortals-become-real": "We Agreed on Experiencing Life",
}

# Stop words — common English words that appear capitalized at sentence start
EN_STOP_WORDS = {
    'The', 'A', 'An', 'And', 'But', 'Or', 'For', 'Not', 'In', 'On', 'At',
    'To', 'With', 'By', 'From', 'Of', 'As', 'Was', 'Were', 'Had', 'Has',
    'Have', 'He', 'She', 'It', 'They', 'We', 'You', 'I', 'His', 'Her',
    'Its', 'Their', 'That', 'This', 'These', 'Those', 'There', 'Here',
    'When', 'Where', 'Why', 'How', 'What', 'Which', 'Who', 'Whom',
    'All', 'Some', 'Any', 'None', 'Every', 'Each', 'Both', 'No', 'Yes',
    'Then', 'Now', 'Just', 'Only', 'Even', 'Still', 'Already', 'Also',
    'So', 'But', 'If', 'Because', 'Since', 'While', 'After', 'Before',
    'Until', 'Yet', 'Though', 'Although', 'Suddenly', 'Gradually',
    'However', 'Moreover', 'Furthermore', 'Nevertheless', 'Meanwhile',
    'Therefore', 'Thus', 'Hence', 'Indeed', 'Perhaps', 'Maybe',
    'Chapter', 'Volume', 'Book', 'Part', 'Section',
    'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine', 'Ten',
}

# Novel titles to filter out
NOVEL_TITLES = {
    'a-will-eternal': {'A Will Eternal'},
    'outside-of-time': {'Outside Of Time', 'Outside Of'},
    'eternal-sacred-king': {'Eternal Sacred King'},
    'renegade-immortal': {'Renegade Immortal'},
    'daoist-master-of-qing-xuan': {'Daoist Master Of Qing Xuan', 'Dao Of The Bizarre Immortal',
                                     'The Bizarre Immortal', 'Bizarre Immortal'},
    'we-agreed-on-experiencing-life-so-why-did-you-immortals-become-real': {
        'We Agreed On Experiencing Life', 'Agreed On Experiencing Life',
        'So Why Did You Immortals Become Real', 'So Why Did You',
        'Immortals Become Real', 'We Agreed On Experiencing',
    },
}

MYANMAR_STOP_WORDS = {
    'တစ်ခု', 'တစ်ယောက်', 'အခါ', 'သူတို့', 'တစ်ဦး', 'အဲဒီ',
    'ကျွန်တော်', 'တစ်ချိန်', 'တစ်ခါ', 'ဒီအတွက်', 'အချိန်',
    'တစ်စုံ', 'ဘယ်သူ', 'ဘယ်လို', 'ဒါပေမယ့်', 'သူတို့ရဲ့',
    'ဘာဖြစ်', 'အဲဒီမှာ', 'အဲဒါ', 'ဘယ်လောက်', 'ဒီလို',
    'ဒါဟာ', 'ဒါကြောင့်', 'အဲဒီအခါ', 'သို့သော်', 'ထို့ကြောင့်',
    'အလွန်', 'သူသည်', 'ဒါပေမဲ့', 'ထိုအခါ', 'တစ်ခုမှာ',
    'ထို့နောက်', 'ထို့ပြင်', 'ထိုအချိန်', 'ထိုနေရာ',
    'ရုတ်တရက်', 'တဖြည်းဖြည်း', 'ထို့ကြောင့်',
    'ထို့အတူ', 'သို့ပေမည့်', 'သို့သော်လည်း',
    'ကံကောင်းထောက်မစွာ', 'နောက်ဆုံး', 'ချက်ချင်း',
    'မကြာမီ', 'တစ်ချက်', 'နောက်တစ်ခေါက်', 'ပထမဆုံး',
}


def extract_en_entities(filepath: Path) -> List[str]:
    """Extract capitalized multi-word entities from an EN file."""
    text = filepath.read_text(encoding='utf-8-sig')
    # Strip markdown headers (# ...) to avoid title bleeding into content
    text = re.sub(r'^#+\s+.*$', '', text, flags=re.MULTILINE)
    # Normalize newlines
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    entities = set()
    
    # Split into paragraphs first to avoid cross-paragraph capture
    paragraphs = [p for p in text.split('\n\n') if p.strip()]
    
    patterns = [
        r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b',
    ]
    
    for para in paragraphs:
        for pat in patterns:
            for m in re.finditer(pat, para):
                entity = m.group(1).strip()
                words = entity.split()
                
                # Skip if any word is a stop word AND it's the ONLY word of that type
                if len(words) == 2 and words[0] in EN_STOP_WORDS:
                    continue
                if all(w in EN_STOP_WORDS for w in words):
                    continue
                
                # Skip single-word captures
                if len(words) == 1:
                    continue
                
                # Skip dialogue attributions
                if words[-1].lower() in {'said', 'asked', 'replied', 'whispered', 'shouted', 'yelled',
                                           'murmured', 'growled', 'snapped', 'commanded'}:
                    continue
                    
                entities.add(entity)
    
    # Pattern 2: Single capitalized word that appears with title/status
    # "Lord", "Elder", "Daoist", "Sovereign"
    lines = text.split('\n')
    for line in lines:
        stripped = line.strip()
        # Look for "Title Name" or "Name of Place" patterns
        # E.g., "Elder Wang", "Mount Tai", "City of Dawn"
        title_name = re.findall(
            r'(?:Lord|Elder|Daoist|Sovereign|Ancestor|Saint|Emperor|King|Queen|Prince|Princess'
            r'|Master|Patriarch|Grandmaster|Sage|Deity|God|Immortal|Fairy|Madam|Lady|Sir'
            r'|Mount|River|Lake|Sea|City|Town|Village|Realm|Domain|Palace|Temple|Peak|Valley)'
            r'\s+([A-Z][a-z]+)',
            stripped
        )
        for name in title_name:
            if name not in EN_STOP_WORDS and len(name) > 1:
                entities.add(f"{name}")
    
    return list(entities)


def extract_mm_candidates(filepath: Path) -> List[str]:
    """Extract potential proper name candidates from MM text."""
    text = filepath.read_text(encoding='utf-8-sig')
    candidates = set()
    
    # Myanmar proper names tend to be 2-6 syllable sequences before particles
    # Pattern: Myanmar sequence followed by သည်/က/မှာ/ကို/၏ (common name positions)
    NAME_PATTERN = re.compile(
        r'([\u1000-\u109F]{2,12})\s*(?:သည်|က|မှာ|ကို|၏|၌|\s+ပြော|\s+ဟု)'
    )
    
    for m in NAME_PATTERN.finditer(text):
        name = m.group(1).strip()
        if name in MYANMAR_STOP_WORDS:
            continue
        if len(name) < 2 or len(name) > 12:
            continue
        candidates.add(name)
    
    return list(candidates)


def scan_novel(novel: str, sample_limit: int = 0) -> Tuple[Counter, Counter, int]:
    """Scan one novel's EN and MM files for term candidates."""
    novel_dir = DATASET_DIR / novel
    en_dir = novel_dir / "en"
    mm_dir = novel_dir / "mm"
    
    en_entities = Counter()
    mm_candidates = Counter()
    chapter_count = 0
    
    if not en_dir.exists() or not mm_dir.exists():
        return en_entities, mm_candidates, 0
    
    en_files = sorted(en_dir.glob("*.md"))
    if sample_limit > 0:
        en_files = en_files[:sample_limit]
    
    for f in en_files:
        # Find corresponding MM file
        chapter_num = re.findall(r'(\d+)', f.stem)
        if not chapter_num:
            continue
        ch = int(chapter_num[-1])
        
        # Try multiple MM naming patterns
        mm_candidates_files = []
        for pat in [
            f"{novel}_myanmar_chapter_{ch:04d}.md",
            f"{novel}_chapter_{ch:04d}.md",
            str(f.name).replace(".md", "_chapter_" + str(ch).zfill(4) + ".md"),
        ]:
            p = mm_dir / pat
            if p.exists():
                mm_candidates_files.append(p)
                break
        else:
            # Fallback: scan by chapter number
            for mf in mm_dir.iterdir():
                nums = re.findall(r'(\d+)', mf.stem)
                if nums and int(nums[-1]) == ch:
                    mm_candidates_files.append(mf)
                    break
        
        if not mm_candidates_files:
            continue
        
        # Extract entities from EN
        entities = extract_en_entities(f)
        for e in entities:
            # Filter out novel titles
            novel_titles = NOVEL_TITLES.get(novel, set())
            # Filter out short terms
            words = e.split()
            if len(words) < 2:
                continue
            if any(len(w) <= 1 for w in words):
                continue
            if e in novel_titles:
                continue
            en_entities[e] += 1
        
        # Extract candidates from MM
        for mf in mm_candidates_files:
            candidates = extract_mm_candidates(mf)
            for c in candidates:
                mm_candidates[c] += 1
        
        chapter_count += 1
    
    return en_entities, mm_candidates, chapter_count


def build_term_id(prefix: str, source_term: str, idx: int) -> str:
    """Build a unique term ID."""
    # Take first 2 chars of each word for compact ID
    short = ''.join(w[:2].lower() for w in source_term.split()[:2] if w)
    return f"{prefix}_{short}_{idx:03d}"


def guess_category(source_term: str) -> str:
    """Guess the category of a term based on context words."""
    term_lower = source_term.lower()
    
    location_keywords = ['continent', 'city', 'town', 'mountain', 'river', 'lake', 'sea',
                         'ocean', 'realm', 'domain', 'land', 'valley', 'peak', 'island',
                         'province', 'region', 'district', 'village', 'kingdom', 'empire',
                         'gate', 'path', 'road', 'temple', 'palace', 'hall', 'pavilion']
    
    character_keywords = ['elder', 'lord', 'master', 'king', 'emperor', 'saint', 'sage',
                          'ancestor', 'patriarch', 'daoist', 'immortal', 'sovereign',
                          'prince', 'princess', 'queen', 'god', 'deity', 'madam', 'lady',
                          'brother', 'sister', 'uncle', 'aunt', 'grandfather', 'grandmother']
    
    technique_keywords = ['technique', 'art', 'skill', 'method', 'cultivation', 'power',
                          'force', 'strike', 'palm', 'fist', 'sword', 'blade', 'saber',
                          'dao', 'sutra', 'scripture', 'manual', 'charm', 'talisman',
                          'formation', 'array', 'seal', 'curse', 'spell', 'incantation']
    
    item_keywords = ['pill', 'elixir', 'treasure', 'artifact', 'weapon', 'robe', 'ring',
                     'pouch', 'bag', 'jade', 'gold', 'silver', 'coin', 'stone', 'crystal']
    
    for kw in location_keywords:
        if kw in term_lower:
            return "location"
    for kw in character_keywords:
        if kw in term_lower:
            return "character"
    for kw in technique_keywords:
        if kw in term_lower:
            return "technique"
    for kw in item_keywords:
        if kw in term_lower:
            return "item_artifact"
    
    return "title_honorific" if any(w[0].isupper() for w in term_lower.split()) else "cultivation_concept"


# Preposition prefixes that create noise when attached to names
NOISE_PREFIXES = {
    'When ', 'After ', 'As ', 'Before ', 'While ', 'During ', 'Without ',
    'Hearing ', 'Seeing ', 'Watching ', 'Finding ', 'Using ',
    'Knowing ', 'Understanding ', 'Remembering ', 'Forgetting ',
}


def build_blueprint(all_en_entities: Dict[str, Counter], novel_info: Dict[str, int]) -> dict:
    """Build the universal glossary blueprint from mined entities."""
    
    # Read existing blueprint to preserve structure
    existing = {}
    if BLUEPRINT_PATH.exists():
        try:
            existing = json.loads(BLUEPRINT_PATH.read_text(encoding='utf-8-sig'))
        except:
            existing = {}
    
    blueprint = existing or {
        "metadata": {
            "schema_version": "3.2.1",
            "pipeline_compatible": ["novel_translation_project", "v2.0"],
            "source_language": "Chinese/English",
            "target_language": "Myanmar",
            "last_updated": datetime.now().strftime('%Y-%m-%d'),
            "max_context_size_kb": 48,
            "description": "Universal glossary mined from 6 novels' human translations.",
        },
        "settings": {
            "allowed_categories": [
                "character", "location", "organization", "item_artifact",
                "power_level", "cultivation_concept", "event", "technique", "title_honorific"
            ],
            "translation_rules_valid": ["transliterate", "translate", "fixed", "pattern_match", "context_adapt"],
            "default_pronoun_rules": {
                "to_elder": {"self": "ကျွန်တော်/ကျွန်မ", "target": "ခင်ဗျား/အရှင်", "honorific": "အကြီးအကဲ"},
                "to_peer":  {"self": "ငါ", "target": "မင်း", "honorific": ""},
                "to_enemy": {"self": "ငါ", "target": "နင်", "honorific": "မိစ္ဆာကောင်"}
            },
            "ai_injection_limit": {
                "max_terms_per_prompt": 60,
                "priority_cutoff": 2,
                "fallback_placeholder": "【?term?】",
                "scene_tone_keys": ["formal", "casual", "hostile", "pleading", "intimate"]
            }
        },
        "terms": [],
        "novel_inventory": {},
    }
    
    # Clean: remove noise prefix+name terms (e.g., "When Xu Qing", "After Wang Lin")
    cleaned = {}
    for source_term, novel_counts in all_en_entities.items():
        has_noise_prefix = False
        for prefix in NOISE_PREFIXES:
            if source_term.startswith(prefix):
                has_noise_prefix = True
                # Also add the bare name if it's not already captured
                bare_name = source_term[len(prefix):].strip()
                if bare_name and bare_name not in all_en_entities:
                    # Check if this is a valid entity (not a stop word)
                    if bare_name not in EN_STOP_WORDS and len(bare_name) > 1:
                        # Add with reduced count
                        if bare_name not in cleaned:
                            cleaned[bare_name] = Counter()
                        for novel, count in novel_counts.items():
                            cleaned[bare_name][novel] += count // 2  # half weight
                break
        if not has_noise_prefix:
            cleaned[source_term] = novel_counts
    
    # Also filter out anything that starts with a noise prefix
    cleaned = {k: v for k, v in cleaned.items()
               if not any(k.startswith(p) for p in NOISE_PREFIXES)}
    
    # Build terms from mined entities
    terms = []
    seen_sources = set()
    
    # 1. Global entities appearing in 3+ novels (highest confidence)
    # 2. Novel-specific entities appearing 5+ times within a novel
    for source_term, novel_counts in sorted(
        cleaned.items(),
        key=lambda x: (len(x[1]), sum(x[1].values())),
        reverse=True
    ):
        if source_term in seen_sources:
            continue
        if source_term in EN_STOP_WORDS:
            continue
        
        total_count = sum(novel_counts.values())
        novel_count = len(novel_counts)
        
        # Only include terms with enough evidence
        if total_count < 5:
            continue
        if novel_count < 2 and total_count < 20:
            continue
        # Filter single-word terms unless they are title+name (e.g., "Elder Wang")
        words = source_term.split()
        if len(words) <= 1:
            continue
        if source_term in EN_STOP_WORDS:
            continue
        
        total_count = sum(novel_counts.values())
        novel_count = len(novel_counts)
        
        # Only include terms with enough evidence
        if novel_count < 2 and total_count < 5:
            continue
        if total_count < 3:
            continue
        
        seen_sources.add(source_term)
        category = guess_category(source_term)
        
        # Build novel-specific info
        appearances = {}
        for novel, count in novel_counts.most_common():
            appearances[novel] = {"count": count}
        
        term_id = build_term_id(category[:4], source_term, len(terms) + 1)
        
        term = {
            "id": term_id,
            "source_term": source_term,
            "target_term": "【?" + source_term + "?】",
            "aliases_en": [],
            "aliases_cn": [],
            "category": category,
            "translation_rule": "transliterate",
            "priority": min(10, novel_count + math.ceil(total_count / 10)),
            "status": "draft",
            "usage_frequency": "high" if total_count > 20 else ("medium" if total_count > 8 else "low"),
            "chapter_first_seen": 1,
            "novel_count": novel_count,
            "total_occurrences": total_count,
            "appears_in_novels": list(novel_counts.keys()),
            "novel_appearances": dict(novel_counts.most_common()),
            "description": f"EN term from {novel_count} novel(s), {total_count} occurrences. Category: {category}.",
            "notes": "Auto-mined from human translation dataset. Target translation needs verification.",
        }
        terms.append(term)
    
    # Remove old template placeholder terms (<...>)
    existing_terms = blueprint.get("terms", [])
    if existing_terms:
        old_terms = [t for t in existing_terms if t.get("source_term", "").startswith("<")]
        if old_terms:
            terms = old_terms + terms
    
    # Cap at 500 highest-confidence terms
    terms = terms[:500]
    
    blueprint["terms"] = terms
    blueprint["metadata"]["last_updated"] = datetime.now().strftime('%Y-%m-%d')
    blueprint["novel_inventory"] = novel_info
    
    for novel, count in novel_info.items():
        display = NOVEL_DISPLAY_NAMES.get(novel, novel)
        blueprint.setdefault("novel_details", {})[novel] = {
            "display_name": display,
            "chapters_scanned": count,
            "file_pattern_en": "{novel}_chapter_{NNNN}.md",
            "file_pattern_mm": "{novel}_chapter_{NNNN}.md / {novel}_myanmar_chapter_{NNNN}.md",
        }
    
    return blueprint


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Mine universal glossary from novel dataset")
    parser.add_argument("--sample", type=int, default=0, help="Sample N chapters per novel (for testing)")
    parser.add_argument("--min-novels", type=int, default=2, help="Min novels for a term to be included")
    parser.add_argument("--output", default=str(BLUEPRINT_PATH), help="Output path")
    args = parser.parse_args()
    
    all_en_entities = {}  # source_term -> {novel: count}
    novel_info = {}
    
    print(f"{'='*60}")
    print(f"  Universal Glossary Miner")
    print(f"{'='*60}")
    
    for novel in NOVELS:
        print(f"\n  📖 Scanning {NOVEL_DISPLAY_NAMES.get(novel, novel)}...")
        en_entities, mm_candidates, chapters = scan_novel(novel, args.sample)
        
        novel_info[novel] = chapters
        print(f"     EN chapters: {chapters}")
        print(f"     EN entities found: {len(en_entities)}")
        print(f"     MM candidates found: {len(mm_candidates)}")
        
        # Show top entities
        for entity, count in en_entities.most_common(10):
            print(f"       {entity:<45} ×{count}")
        
        # Merge into global
        for entity, count in en_entities.items():
            if entity not in all_en_entities:
                all_en_entities[entity] = Counter()
            all_en_entities[entity][novel] = count
    
    # Build blueprint
    print(f"\n  🔨 Building glossary blueprint...")
    blueprint = build_blueprint(all_en_entities, novel_info)
    
    total_terms = len(blueprint["terms"])
    template_terms = sum(1 for t in blueprint["terms"] if t.get("source_term", "").startswith("<"))
    mined_terms = total_terms - template_terms
    
    print(f"\n  📊 RESULTS")
    print(f"  {'Total terms':<30} {total_terms}")
    print(f"  {'Mined terms':<30} {mined_terms}")
    print(f"  {'Template placeholders':<30} {template_terms}")
    print(f"  {'Novels contributing':<30} {sum(1 for v in novel_info.values() if v > 0)}/{len(NOVELS)}")
    
    if mined_terms > 0:
        cats = Counter(t["category"] for t in blueprint["terms"] if not t["source_term"].startswith("<"))
        print(f"\n  📂 CATEGORIES")
        for cat, count in cats.most_common():
            print(f"  {cat:<30} {count}")
    
    # Write
    output_path = Path(args.output)
    output_path.write_text(json.dumps(blueprint, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"\n  💾 Glossary saved: {output_path}")
    
    # Also save a summary
    summary_path = output_path.with_name("universal_glossary_summary.json")
    summary = {
        "last_updated": datetime.now().isoformat(),
        "total_terms": total_terms,
        "mined_terms": mined_terms,
        "template_terms": template_terms,
        "novels_scanned": [
            {"name": n, "display": NOVEL_DISPLAY_NAMES.get(n, n), "chapters": novel_info.get(n, 0)}
            for n in NOVELS if novel_info.get(n, 0) > 0
        ],
        "top_terms": [
            {
                "term": t["source_term"],
                "category": t["category"],
                "frequency": t.get("usage_frequency", "unknown"),
                "novels": len(t.get("appears_in_novels", [])),
                "occurrences": t.get("total_occurrences", 0),
            }
            for t in blueprint["terms"][:30]
            if not t["source_term"].startswith("<")
        ]
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"  💾 Summary saved: {summary_path}")
    
    print(f"\n  ✅ Done! Run with --sample 0 to scan ALL chapters.")


if __name__ == "__main__":
    main()
