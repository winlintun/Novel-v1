#!/usr/bin/env python3
"""
Diagnostic script to check translation configuration
Run this to verify your setup is correct

Usage: python diagnose.py
"""

import sys
import os
import json
from pathlib import Path
sys.path.insert(0, '.')

from src.db.connection import DatabaseConnection
from src.db.repositories.glossary_repo import GlossaryRepository


def print_section(title):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


def check_result(name, passed, details=""):
    icon = "✅" if passed else "❌"
    print(f"{icon} {name}")
    if details:
        print(f"   {details}")


def get_novel_dirs(base_path="data/output"):
    """Get list of novel directories from data/output"""
    novels = []
    if os.path.isdir(base_path):
        for d in os.listdir(base_path):
            novel_path = os.path.join(base_path, d)
            if os.path.isdir(novel_path):
                # Skip non-novel directories like 'default', 'report', etc.
                if d not in ('default', 'report'):
                    novels.append(d)
    return novels


print(f"\n{'='*70}")
print(f"  🔍 NOVEL TRANSLATION SETUP DIAGNOSTIC")
print(f"{'='*70}")

# Check 1: Config file
print_section("CONFIGURATION CHECK")
try:
    from src.config import load_config
    config = load_config()
    check_result("Config loaded", True, "config/settings.yaml")
    print(f"  Translator: {config.models.translator}")
    print(f"  Editor: {config.models.editor}")
    print(f"  Checker: {config.models.checker}")
    print(f"  Pipeline mode: {config.translation_pipeline.mode}")
    print(f"  Source language: {config.project.source_language}")
except Exception as e:
    check_result("Config loaded", False, str(e))

# Check 2: Memory Manager (Dual-Layer System)
print_section("MEMORY SYSTEM CHECK")
try:
    from src.memory.memory_manager import MemoryManager
    
    # Check for novels and their memory files
    novels = get_novel_dirs()
    print(f"  Found {len(novels)} novel(s) in data/output/")
    
    if not novels:
        print("  No novels found. Run translation to create memory files.")
    
    for novel in novels:
        print(f"\n  📖 Novel: {novel}")
        
        mm = MemoryManager(novel_name=novel)
        
        try:
            global_terms = mm.get_global_terms()
            check_result(f"  Universal (global DB)", True, f"{len(global_terms)} terms")
        except Exception as e:
            check_result(f"  Universal (global DB)", False, str(e))
        
        novel_id = f"novel_{novel.replace('-', '_').replace(' ', '_')}"
        try:
            repo = GlossaryRepository(DatabaseConnection("data/novel_translation.db"))
            terms = repo.get_terms_by_novel(novel_id, include_global=False, limit=9999)
            approved = sum(1 for t in terms if t["status"] == "approved")
            pending = sum(1 for t in terms if t["status"] == "pending")
            check_result(f"  Glossary (DB)", True, f"{len(terms)} terms ({approved} approved, {pending} pending)")
        except Exception as e:
            check_result(f"  Glossary (DB)", False, str(e))
        
        # Check meta.json (single file per novel)
        novel_meta = f"data/output/{novel}/{novel}.mm.meta.json"
        if os.path.exists(novel_meta):
            try:
                with open(novel_meta, 'r', encoding='utf-8-sig') as f:
                    meta_data = json.load(f)
                total_ch = meta_data.get('total_chapters', 0)
                check_result(f"  Meta.json", True, f"{total_ch} chapters tracked")
            except Exception as e:
                check_result(f"  Meta.json", False, str(e))
        else:
            check_result(f"  Meta.json", False, "Not found (run --rebuild-meta)")
        
        # Count translated chapters
        output_dir = f"data/output/{novel}"
        if os.path.isdir(output_dir):
            chapter_files = [f for f in os.listdir(output_dir) if f.endswith('.mm.md')]
            check_result(f"  Chapters", True, f"{len(chapter_files)} translated")

except Exception as e:
    check_result("Memory Manager", False, str(e))

# Check 3: File Handler
print_section("FILE HANDLER CHECK")
try:
    from src.utils.file_handler import FileHandler
    test_path = "logs/diagnose_test.txt"
    FileHandler.write_text(test_path, "Test content မြန်မာဘာသာ")
    content = FileHandler.read_text(test_path)
    os.remove(test_path)
    check_result("FileHandler", True, "UTF-8 read/write OK")
except Exception as e:
    check_result("FileHandler", False, str(e))

# Check 4: Ollama Connection
print_section("OLLAMA CONNECTION CHECK")
try:
    import ollama
    models = ollama.list()
    check_result("Ollama", True, f"Connected, {len(models.models)} models available")
    print("  Available models:")
    for m in models.models[:5]:
        print(f"    - {m.model}")
except Exception as e:
    check_result("Ollama", False, str(e))

# Check 5: Data Directories
print_section("DATA DIRECTORIES CHECK")
dirs_to_check = ["data/input", "data/output", "data", "logs", "config"]
for d in dirs_to_check:
    exists = os.path.isdir(d)
    check_result(d, exists, "exists" if exists else "NOT FOUND")

# Check 6: Python Cache
print_section("PYTHON CACHE CHECK")
cache_count = 0
for root, dirs, files in os.walk('.'):
    if '__pycache__' in dirs:
        cache_count += 1
    check_result("__pycache__ dirs", cache_count == 0, f"Found {cache_count} (run 'python -m src.main --clean' to clear)" if cache_count > 0 else "Clean")

# Check 7: Glossary System (Database-Only)
print_section("GLOSSARY SYSTEM CHECK")

# Check global terms in database
try:
    repo = GlossaryRepository(DatabaseConnection("data/novel_translation.db"))
    global_terms = repo.get_global_terms(limit=9999)
    approved = sum(1 for t in global_terms if t["status"] == "approved")
    pending = sum(1 for t in global_terms if t["status"] == "pending")
    check_result("  Global terms (DB)", True, f"{len(global_terms)} total ({approved} approved, {pending} pending)")
except Exception as e:
    check_result("  Global terms (DB)", False, str(e))

# Check DB file exists
db_path = "data/novel_translation.db"
if os.path.exists(db_path):
    size_mb = os.path.getsize(db_path) / (1024 * 1024)
    check_result(f"  novel_translation.db", True, f"{size_mb:.1f} MB")
else:
    check_result(f"  novel_translation.db", False, "Not found")

# Check per-novel glossary files
print("\n  Per-novel files:")
novels = get_novel_dirs()
if novels:
    for novel in novels:
        print(f"\n  📖 {novel}:")
        
        try:
            repo = GlossaryRepository(DatabaseConnection("data/novel_translation.db"))
            nid = f"novel_{novel.replace('-', '_').replace(' ', '_')}"
            terms = repo.get_terms_by_novel(nid, include_global=False, limit=9999)
            approved = sum(1 for t in terms if t["status"] == "approved")
            pending = sum(1 for t in terms if t["status"] == "pending")
            check_result(f"    Glossary (DB)", True, f"{len(terms)} terms ({approved} approved, {pending} pending)")
        except Exception as e:
            check_result(f"    Glossary (DB)", False, str(e))
else:
    print("  No novels found in data/output/")

# Check 8: Agents Available
print_section("AGENTS CHECK")
agents_to_check = [
    ("src/agents/translator.py", "Translator"),
    ("src/agents/refiner.py", "Refiner"),
    ("src/agents/checker.py", "Checker"),
    ("src/agents/qa_tester.py", "QA Tester"),
    ("src/agents/context_updater.py", "Context Updater"),
    ("src/agents/preprocessor.py", "Preprocessor"),
    ("src/agents/reflection_agent.py", "Reflection"),
    ("src/agents/myanmar_quality_checker.py", "Myanmar QC"),
]

for filepath, name in agents_to_check:
    exists = os.path.exists(filepath)
    check_result(name, exists, filepath)

# Check 9: Test file exists
print_section("TEST FILES CHECK")
test_files = ["test_novel_v1.py", "clean_run.bat", "clean_run.sh"]
for f in test_files:
    exists = os.path.exists(f)
    check_result(f, exists, "exists" if exists else "NOT FOUND")

# Summary
print_section("DIAGNOSTIC COMPLETE")
print("""
If any check failed, review the output above.
Common fixes:
  - Missing config: Check config/settings.yaml exists
  - Ollama error: Ensure Ollama is running (ollama serve)
  - Import errors: Run 'python -m src.main --clean' and retry
  - Glossary missing: Run --generate-glossary --novel <name>
  - Meta missing: Run --rebuild-meta --novel <name>
   
For help: python -m src.main --help
""")