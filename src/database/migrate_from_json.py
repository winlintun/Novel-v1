# src/database/migrate_from_json.py
"""
Migration script to convert existing JSON glossary files to SQLite database.

Based on sql_blueprint.md migration path:
1. Backup JSON files
2. Import to SQLite
3. Rename originals to .json.bak

Usage:
    python -m src.database.migrate_from_json --novel <slug>
"""

import argparse
import hashlib
import json
import logging
import shutil
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def generate_term_id(novel_slug: str, source_term: str) -> str:
    """Generate term ID: term_<novel>_<hash>"""
    term_hash = hashlib.md5(source_term.encode()).hexdigest()[:8]
    return f"term_{novel_slug}_{term_hash}"


def migrate_glossary(db_manager, novel_slug: str, glossary_path: Path) -> dict:
    """
    Migrate glossary JSON to database.
    
    Args:
        db_manager: DatabaseManager instance
        novel_slug: Novel identifier
        glossary_path: Path to glossary.json
        
    Returns:
        dict: Migration statistics
    """
    stats = {'terms': 0, 'variants': 0, 'errors': 0}
    
    if not glossary_path.exists():
        logger.warning(f"Glossary file not found: {glossary_path}")
        return stats
    
    try:
        with open(glossary_path, 'r', encoding='utf-8-sig') as f:
            data = json.load(f)
        
        terms = data.get('terms', [])
        
        for term in terms:
            try:
                source = term.get('source', '')
                target = term.get('target', '')
                category = term.get('category', 'concept')
                status = term.get('status', 'pending')
                
                if not source or not target:
                    continue
                
                # Generate term ID
                term_id = generate_term_id(novel_slug, source)
                
                # Add term to database
                db_manager.add_glossary_term(
                    term_id=term_id,
                    novel_id=f"novel_{novel_slug}",
                    source_term=source,
                    target_term=target,
                    canonical_form=source,
                    category=category,
                    status=status,
                    enforcement_level='soft',
                )
                
                # Add variants if present
                variants = term.get('variants', [])
                for variant in variants:
                    db_manager.add_term_variant(
                        term_id=term_id,
                        variant_text=variant.get('text', ''),
                        match_type=variant.get('type', 'exact'),
                        case_sensitive=variant.get('case_sensitive', False)
                    )
                    stats['variants'] += 1
                
                stats['terms'] += 1
                
            except Exception as e:
                logger.error(f"Error migrating term: {e}")
                stats['errors'] += 1
        
        logger.info(f"Migration complete: {stats}")
        
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {glossary_path}: {e}")
    except Exception as e:
        logger.error(f"Migration failed: {e}")
    
    return stats


def migrate_context_memory(db_manager, novel_slug: str, context_path: Path) -> dict:
    """
    Migrate context memory JSON to database.
    
    Args:
        db_manager: DatabaseManager instance
        novel_slug: Novel identifier
        context_path: Path to context_memory.json
        
    Returns:
        dict: Migration statistics
    """
    stats = {'snapshots': 0, 'chapters': 0, 'errors': 0}
    
    if not context_path.exists():
        logger.warning(f"Context file not found: {context_path}")
        return stats
    
    try:
        with open(context_path, 'r', encoding='utf-8-sig') as f:
            data = json.load(f)
        
        # Create chapters for discovered content
        chapters_dir = Path('data/input') / novel_slug
        if chapters_dir.exists():
            for md_file in chapters_dir.glob('*.md'):
                try:
                    # Extract chapter number from filename
                    filename = md_file.stem
                    if 'chapter' in filename.lower():
                        # Try to extract number
                        parts = filename.split('_')
                        for part in parts:
                            if part.isdigit():
                                db_manager.create_chapter(
                                    novel_id=f"novel_{novel_slug}",
                                    chapter_num=int(part),
                                    file_path=str(md_file)
                                )
                                stats['chapters'] += 1
                                break
                except Exception as e:
                    logger.error(f"Error processing chapter file {md_file}: {e}")
        
        # Save context snapshot if available
        if data.get('summary') or data.get('active_characters'):
            pass
        
        logger.info(f"Context migration complete: {stats}")
        
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {context_path}: {e}")
    except Exception as e:
        logger.error(f"Context migration failed: {e}")
    
    return stats


def migrate_novel(novel_slug: str, source_language: str = 'chinese') -> dict:
    """
    Migrate all JSON data for a novel to SQLite.
    
    Args:
        novel_slug: Novel identifier
        source_language: Source language (chinese/english/japanese)
        
    Returns:
        dict: Overall migration statistics
    """
    from src.database.db_manager import DatabaseManager
    
    # Create backup folder
    backup_dir = Path(f"backups/glossary_migration_{datetime.now().strftime('%Y%m%d')}")
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize database
    with DatabaseManager() as db:
        # Create novel entry
        db.create_novel(
            novel_id=f"novel_{novel_slug}",
            name=novel_slug,
            source_language=source_language
        )
        
        # Migrate glossary
        glossary_path = Path(f'data/output/{novel_slug}/glossary/glossary.json')
        glossary_stats = migrate_glossary(db, novel_slug, glossary_path)
        
        # Migrate context
        context_path = Path(f'data/output/{novel_slug}/glossary/context_memory.json')
        context_stats = migrate_context_memory(db, novel_slug, context_path)
        
        # Backup and rename originals
        if glossary_path.exists():
            backup_file = backup_dir / f"{novel_slug}_glossary.json"
            shutil.copy2(glossary_path, backup_file)
            glossary_path.rename(glossary_path.with_suffix('.json.bak'))
            logger.info(f"Backed up {glossary_path} to {backup_file}")
        
        if context_path.exists():
            backup_file = backup_dir / f"{novel_slug}_context.json"
            shutil.copy2(context_path, backup_file)
            context_path.rename(context_path.with_suffix('.json.bak'))
            logger.info(f"Backed up {context_path} to {backup_file}")
        
        return {
            'novel': novel_slug,
            'glossary': glossary_stats,
            'context': context_stats,
            'backup_dir': str(backup_dir)
        }


def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(description='Migrate JSON glossary to SQLite database')
    parser.add_argument('--novel', required=True, help='Novel slug to migrate')
    parser.add_argument('--language', default='chinese', choices=['chinese', 'english', 'japanese'],
                       help='Source language')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be migrated without executing')
    
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    if args.dry_run:
        # Just show what files would be migrated
        glossary_path = Path(f'data/output/{args.novel}/glossary/glossary.json')
        context_path = Path(f'data/output/{args.novel}/glossary/context_memory.json')
        
        print(f"Would migrate for novel: {args.novel}")
        print(f"  Glossary: {glossary_path} (exists: {glossary_path.exists()})")
        print(f"  Context:  {context_path} (exists: {context_path.exists()})")
    else:
        result = migrate_novel(args.novel, args.language)
        print("\nMigration complete!")
        print(f"  Terms migrated: {result['glossary']['terms']}")
        print(f"  Variants migrated: {result['glossary']['variants']}")
        print(f"  Chapters processed: {result['context']['chapters']}")
        print(f"  Backup location: {result['backup_dir']}")


if __name__ == '__main__':
    main()