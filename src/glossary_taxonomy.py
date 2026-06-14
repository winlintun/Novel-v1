"""Glossary taxonomy — two-tier categories + term relationship types.

The glossary stores a coarse ``category`` (what downstream code groups/reasons
on) plus a fine ``subtype`` (the specific worldbuilding label). This module is
the single source of truth for both, and for the relationship-edge vocabulary
used by the ``term_relationships`` table.

Usage:
    from src.glossary_taxonomy import normalize_category, RELATION_TYPES
    category, subtype = normalize_category("village")   # -> ("place", "village")
    category, subtype = normalize_category("sect master") # -> ("title", "sect_master")
"""

from __future__ import annotations

# ── Coarse category → fine subtypes ──────────────────────────────────────────
# Coarse categories are intentionally few (~12) so consistency-checking and
# prompt-injection code can reason about them. The subtype carries the detail.
CATEGORIES: dict[str, list[str]] = {
    "character": ["person", "spirit", "demon", "god", "clone", "alter_ego"],
    "creature": ["beast", "spirit_beast", "demon_beast", "monster", "mount"],
    "place": [
        # administrative / political divisions
        "empire", "dynasty", "kingdom", "country", "region", "province",
        "prefecture", "district", "township", "city", "town", "village",
        "hamlet", "ward",
        # urban features
        "street", "marketplace",
        # natural geography
        "mountain", "peak", "range", "river", "lake", "sea", "valley",
        "gorge", "forest", "plains", "desert", "wilderness",
        # special / cultivation locales
        "secret_realm", "dungeon", "cave_abode", "sealed_land", "spiritual_vein",
        # structures
        "hall", "pavilion", "tower", "terrace", "gate", "courtyard", "manor",
        "estate", "temple", "shrine", "monastery", "tomb", "ancestral_hall",
    ],
    "organization": ["sect", "clan", "family", "guild", "alliance", "empire_court"],
    "title": [
        # royal / noble / state
        "king", "prince", "princess", "noble", "lord", "official_rank",
        "minister", "general",
        # sect positions
        "sect_master", "peak_master", "elder", "steward", "disciple",
        # family heads
        "family_head", "patriarch", "matriarch",
    ],
    "cultivation": ["realm", "rank", "stage", "spiritual_root", "concept"],
    "technique": ["sword_art", "body_technique", "spell", "skill", "formation"],
    "item": ["weapon", "artifact", "pill", "treasure", "material", "talisman"],
    "food": ["dish", "ingredient", "drink"],
    "currency": ["coin", "spirit_stone", "note"],
    "concept": ["term", "law", "dao", "direction", "event"],
    "general": ["general"],
}

# Fine subtype → coarse category (reverse index).
SUBTYPE_TO_CATEGORY: dict[str, str] = {
    sub: cat for cat, subs in CATEGORIES.items() for sub in subs
}

# Aliases: free-form inputs the LLM / legacy code may emit, mapped to a subtype.
_ALIASES: dict[str, str] = {
    # legacy coarse labels from older prompts
    "location": "city",
    "place": "city",
    "power_level": "realm",
    "cultivation_concept": "concept",
    "cultivation_realm": "realm",
    "item_artifact": "artifact",
    "title_honorific": "official_rank",
    "organization_sect": "sect",
    # natural-language variants
    "secret realm": "secret_realm",
    "cave abode": "cave_abode",
    "cave-abode": "cave_abode",
    "sealed land": "sealed_land",
    "spiritual veins": "spiritual_vein",
    "spiritual vein": "spiritual_vein",
    "ancestral hall": "ancestral_hall",
    "sect master": "sect_master",
    "peak master": "peak_master",
    "family head": "family_head",
    "official ranks": "official_rank",
    "official rank": "official_rank",
    "disciple tiers": "disciple",
    "spiritual root": "spiritual_root",
    "spirit beast": "spirit_beast",
    "demon beast": "demon_beast",
    "relam": "realm",   # common misspelling
    "pains": "plains",  # common misspelling
}

# ── Relationship vocabulary (term_relationships.relation_type) ────────────────
# Directed edges: (src) --relation--> (dst).
RELATION_TYPES: set[str] = {
    "located_in",     # place located_in larger place; character located_in place
    "part_of",        # generic containment (region part_of country)
    "ruled_by",       # kingdom ruled_by king
    "rules",          # king rules kingdom (inverse of ruled_by)
    "capital_of",     # city capital_of kingdom
    "member_of",      # character member_of sect/clan
    "heads",          # patriarch heads clan; sect_master heads sect
    "subordinate_to", # peak_master subordinate_to sect_master
    "master_of",      # character master_of disciple
    "disciple_of",    # character disciple_of master
    "parent_of",
    "child_of",
    "sibling_of",
    "spouse_of",
    "ally_of",
    "enemy_of",
    "owns",           # character owns item
    "wields",         # character wields weapon/technique
    "located_at",     # character located_at place
}

# Inverse edges, so a single extraction can populate both directions.
RELATION_INVERSE: dict[str, str] = {
    "ruled_by": "rules",
    "master_of": "disciple_of",
    "disciple_of": "master_of",
    "parent_of": "child_of",
    "child_of": "parent_of",
    "sibling_of": "sibling_of",
    "spouse_of": "spouse_of",
    "ally_of": "ally_of",
    "enemy_of": "enemy_of",
}


def _slug(value: str) -> str:
    return value.strip().lower().replace("-", " ").replace("_", " ")


def normalize_category(value: str | None) -> tuple[str, str | None]:
    """Map an arbitrary category/subtype string to (coarse_category, subtype).

    Accepts a coarse category ("place"), a fine subtype ("mountain"), a
    natural-language variant ("secret realm"), or a legacy label ("location").
    Unknown values fall back to ("general", <slug>) so nothing is ever lost.
    """
    if not value or not str(value).strip():
        return "general", None

    raw = _slug(str(value))
    key = raw.replace(" ", "_")

    # Exact coarse category
    if key in CATEGORIES:
        return key, None
    # Known fine subtype
    if key in SUBTYPE_TO_CATEGORY:
        return SUBTYPE_TO_CATEGORY[key], key
    # Alias (natural-language or legacy) — try both spaced and underscored forms
    alias = _ALIASES.get(raw) or _ALIASES.get(key)
    if alias:
        return SUBTYPE_TO_CATEGORY.get(alias, "general"), alias

    # Unknown — keep it as a subtype under 'general' rather than dropping it.
    return "general", key


def is_valid_relation(relation_type: str) -> bool:
    """True if relation_type is a recognised edge label."""
    return relation_type in RELATION_TYPES


def all_subtypes() -> list[str]:
    """Flat, sorted list of every fine subtype (for prompts / validation)."""
    return sorted(SUBTYPE_TO_CATEGORY.keys())
