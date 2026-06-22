#!/usr/bin/env python3
"""Discover and register Myanmar name-spelling variants from translated output.

The translator often renders a character name *consistently but slightly wrong*
— e.g. ပိုင်ရှောင်ချီ for the canonical ပိုင်ရှောင်ချန်း. Text-aware glossary
injection gets the prefix right; this closes the last syllable deterministically.

For each approved character/title/place term, we scan the novel's translated
output for whitespace tokens that are highly similar to the canonical target
(shared prefix + difflib ratio above threshold) but not identical, and register
them in the ``term_variants`` table. The deterministic glossary enforcer then
snaps every such token to the canonical spelling on the next translation.

Usage:
    python scripts/seed_term_variants.py --novel a-will-eternal            # dry-run
    python scripts/seed_term_variants.py --novel a-will-eternal --apply
    python scripts/seed_term_variants.py --novel a-will-eternal --apply --threshold 0.8
"""

import argparse
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from src.memory.memory_manager import MemoryManager

# Myanmar letters + combining marks only. Excludes punctuation (၊ ။ ၌ …,
# U+104A–U+104F) and digits (U+1040–U+1049) so a trailing comma is never baked
# into a variant (which would strip it on replacement).
_MM_TOKEN = re.compile(r"[က-ဿꧠ-꧿ꩠ-ꩿ]+")
# ONLY character proper nouns. Common nouns (village, heaven, old man) and
# place/title terms routinely appear as canonical+particle (Burmese agglutinates
# postpositions with no space — ကျေးရွာက = ကျေးရွာ + က), which look like variants
# but are valid grammar. Restricting to character names plus the prefix/suffix
# guard below keeps this from stripping particles.
_NAME_CATEGORIES = {"character"}
# Names shorter than this are too risky to substring-replace safely.
_MIN_VARIANT_LEN = 5


def _is_inflection_or_truncation(token: str, canon: str) -> bool:
    """True when one string is a prefix of the other.

    That pattern means the token is the canonical name plus an agglutinated
    particle (ရှောင်ချန်းပါ = ရှောင်ချန်း + ပါ) or a truncation — NOT a misspelling.
    A real spelling variant differs by an *internal* character (ချွန် vs ချန်း).
    """
    return token.startswith(canon) or canon.startswith(token)


def _candidate_tokens(text: str) -> set[str]:
    """Myanmar tokens from output, split on whitespace/punctuation."""
    return {m.group(0) for m in _MM_TOKEN.finditer(text)}


def main() -> int:
    p = argparse.ArgumentParser(description="Seed term_variants from translated output")
    p.add_argument("--novel", required=True)
    p.add_argument("--apply", action="store_true", help="Write variants (default: dry-run)")
    p.add_argument("--threshold", type=float, default=0.78,
                   help="Min difflib ratio to treat a token as a variant (default 0.78)")
    p.add_argument("--output-dir", default="data/output")
    args = p.parse_args()

    mem = MemoryManager(novel_name=args.novel)
    terms = [
        t for t in mem.get_all_terms()
        if t.get("category") in _NAME_CATEGORIES and t.get("target")
    ]
    if not terms:
        print("No proper-noun terms found for novel.")
        return 0

    # Gather candidate tokens from every translated file for this novel.
    out_dir = Path(args.output_dir)
    files = sorted(out_dir.glob(f"{args.novel}*.md")) + sorted(out_dir.glob(f"{args.novel}/*.md"))
    tokens: set[str] = set()
    for f in files:
        try:
            tokens |= _candidate_tokens(f.read_text(encoding="utf-8"))
        except Exception:
            continue
    print(f"Scanned {len(files)} file(s), {len(tokens)} distinct Myanmar tokens.\n")

    # Map each canonical target to existing variants so we don't re-add.
    existing = {(v["variant_text"]) for v in mem.get_variant_map()}

    proposals: list[tuple[str, str, str, float]] = []  # (variant, canonical, source, ratio)
    canon_set = {t["target"] for t in terms}
    for t in terms:
        canon = t["target"].strip()
        src = t["source"]
        if len(canon) < 4:
            continue
        prefix = canon[: max(3, len(canon) // 2)]
        for tok in tokens:
            if tok == canon or tok in canon_set or tok in existing:
                continue
            if len(tok) < _MIN_VARIANT_LEN:
                continue
            # Must share a meaningful prefix with the canonical name.
            if not tok.startswith(canon[:3]) and not canon.startswith(tok[:3]):
                continue
            # Reject canonical+particle / truncation — those are valid grammar,
            # not misspellings. Only keep internal-substitution differences.
            if _is_inflection_or_truncation(tok, canon):
                continue
            ratio = SequenceMatcher(None, tok, canon).ratio()
            if ratio >= args.threshold and abs(len(tok) - len(canon)) <= 4:
                proposals.append((tok, canon, src, ratio))

    # De-dup: keep the best canonical match per variant token.
    best: dict[str, tuple[str, str, float]] = {}
    for tok, canon, src, ratio in proposals:
        if tok not in best or ratio > best[tok][2]:
            best[tok] = (canon, src, ratio)

    if not best:
        print("No variant spellings found above threshold. Output names already match glossary.")
        return 0

    print(f"{'VARIANT (output)':<24} {'→ CANONICAL':<24} {'ratio':>6}  source")
    print("-" * 78)
    for tok, (canon, src, ratio) in sorted(best.items(), key=lambda x: -x[1][2]):
        print(f"{tok:<24} {canon:<24} {ratio:>6.2f}  {src}")

    if not args.apply:
        print(f"\nDry-run: {len(best)} variant(s) would be registered. Re-run with --apply.")
        return 0

    # Persist. Look up the term_id for each canonical target.
    id_by_target = {t["target"]: t["id"] for t in terms}
    written = 0
    for tok, (canon, _src, _ratio) in best.items():
        term_id = id_by_target.get(canon)
        if not term_id:
            continue
        try:
            mem.glossary_repo.add_variant(term_id, tok)
            written += 1
        except Exception as e:
            print(f"  skip {tok!r}: {e}")
    mem.save_memory()
    print(f"\nRegistered {written} variant(s) into term_variants.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
