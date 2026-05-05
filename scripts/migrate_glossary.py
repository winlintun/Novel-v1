#!/usr/bin/env python3
"""
Migrate wayfarer glossary from JSON to SQLite database.

This script reads the legacy glossary.json file and imports all terms
into the SQLite database using the GlossaryRepository.
"""

import json
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.db.connection import DatabaseConnection
from src.db.repositories.glossary_repo import GlossaryRepository


def migrate_glossary(novel_id: str = "novel_wayfarer"):
    """Migrate glossary terms from JSON to database."""
    
    # Paths
    glossary_path = project_root / "data" / "output" / "wayfarer" / "glossary" / "glossary.json"
    db_path = project_root / "data" / "novel_translation.db"
    
    print(f"📖 Reading glossary from: {glossary_path}")
    print(f"💾 Target database: {db_path}")
    
    # Read JSON glossary
    with open(glossary_path, 'r', encoding='utf-8-sig') as f:
        data = json.load(f)
    
    terms = data.get('terms', [])
    print(f"📋 Found {len(terms)} terms to migrate")
    
    # Connect to database
    db = DatabaseConnection(str(db_path))
    repo = GlossaryRepository(db)
    
    # Track stats
    stats = {
        'imported': 0,
        'skipped': 0,
        'errors': 0
    }
    
    # Migrate each term
    for i, term in enumerate(terms, 1):
        source = term.get('source', '')
        target = term.get('target', '')
        category = term.get('category', 'general')
        verified = term.get('verified', False)
        auto_approved = term.get('auto_approved', False)
        chapter_first = term.get('chapter_first_seen', 0)
        
        # Map verified status to database status
        if verified:
            status = 'approved'
        elif auto_approved:
            status = 'approved'
        else:
            status = 'pending'
        
        # Set enforcement level based on verification
        enforcement_level = 'hard' if verified else 'soft'
        
        # Set confidence based on verification
        confidence = 0.95 if verified else 0.7
        
        try:
            # Check if term already exists
            existing = repo.get_term_by_source(novel_id, source)
            if existing:
                print(f"  ⚠️  Skipping (exists): {source}")
                stats['skipped'] += 1
                continue
            
            # Add term to database
            result = repo.add_term(
                novel_id=novel_id,
                source_term=source,
                target_term=target,
                category=category,
                status=status,
                enforcement_level=enforcement_level,
                confidence=confidence
            )
            
            if result:
                print(f"  ✅ Imported ({i}/{len(terms)}): {source} → {target}")
                stats['imported'] += 1
            else:
                print(f"  ❌ Failed to import: {source}")
                stats['errors'] += 1
                
        except Exception as e:
            print(f"  ❌ Error importing '{source}': {e}")
            stats['errors'] += 1
    
    # Summary
    print("\n" + "="*60)
    print("📊 MIGRATION SUMMARY")
    print("="*60)
    print(f"  ✅ Imported:  {stats['imported']} terms")
    print(f"  ⚠️  Skipped:  {stats['skipped']} terms (already exist)")
    print(f"  ❌ Errors:    {stats['errors']} terms")
    print(f"  📋 Total:     {len(terms)} terms processed")
    print("="*60)
    
    # Verify by counting terms in database
    db_terms = repo.get_terms_by_novel(novel_id, limit=1000)
    print(f"\n📈 Database now contains {len(db_terms)} terms for novel '{novel_id}'")
    
    return stats


if __name__ == "__main__":
    print("🚀 Starting glossary migration...\n")
    migrate_glossary()
    print("\n✨ Migration complete!")
