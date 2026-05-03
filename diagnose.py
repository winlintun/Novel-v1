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
    check_result("Config loaded", True, f"config/settings.yaml")
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
    
    for novel in novels:
        print(f"\n  📖 Novel: {novel}")
        
        # Create MemoryManager to test dual-layer loading
        mm = MemoryManager(novel_name=novel)
        
        # Check universal glossary (shared)
        universal_terms = len(mm.universal_glossary.get('terms', []))
        universal_pending = len(mm.universal_pending.get('pending_terms', []))
        check_result(f"  Universal Glossary", True, f"{universal_terms} terms")
        if universal_pending > 0:
            check_result(f"  Universal Pending", True, f"{universal_pending} pending")
        
        # Novel-specific glossary (new structure: data/output/{novel}/glossary/)
        novel_glossary = f"data/output/{novel}/glossary/glossary.json"
        novel_context = f"data/output/{novel}/glossary/context_memory.json"
        novel_pending = f"data/output/{novel}/glossary/glossary_pending.json"
        
        # Check glossary
        if os.path.exists(novel_glossary):
            try:
                with open(novel_glossary, 'r', encoding='utf-8-sig') as f:
                    glossary_data = json.load(f)
                term_count = len(glossary_data.get('terms', []))
                verified_count = sum(1 for t in glossary_data.get('terms', []) if t.get('verified', False))
                check_result(f"  Per-novel Glossary", True, f"{term_count} terms ({verified_count} verified)")
            except Exception as e:
                check_result(f"  Per-novel Glossary", False, str(e))
        else:
            check_result(f"  Per-novel Glossary", False, "Not found")
        
        # Check glossary
        if os.path.exists(novel_glossary):
            try:
                with open(novel_glossary, 'r', encoding='utf-8-sig') as f:
                    glossary_data = json.load(f)
                term_count = len(glossary_data.get('terms', []))
                verified_count = sum(1 for t in glossary_data.get('terms', []) if t.get('verified', False))
                check_result(f"  Glossary", True, f"{term_count} terms ({verified_count} verified)")
            except Exception as e:
                check_result(f"  Glossary", False, str(e))
        else:
            check_result(f"  Glossary", False, "Not found")
        
        # Check pending
        if os.path.exists(novel_pending):
            try:
                with open(novel_pending, 'r', encoding='utf-8-sig') as f:
                    pending_data = json.load(f)
                pending_count = len(pending_data.get('pending_terms', []))
                check_result(f"  Pending Terms", True, f"{pending_count} pending")
            except Exception as e:
                check_result(f"  Pending Terms", False, str(e))
        else:
            check_result(f"  Pending Terms", False, "Not found")
        
        # Check context
        if os.path.exists(novel_context):
            try:
                with open(novel_context, 'r', encoding='utf-8-sig') as f:
                    context_data = json.load(f)
                current_ch = context_data.get('current_chapter', 0)
                check_result(f"  Context", True, f"Current chapter: {current_ch}")
            except Exception as e:
                check_result(f"  Context", False, str(e))
        else:
            check_result(f"  Context", False, "Not found")
        
        # Check meta.json (single file per novel)
        novel_meta = f"data/output/{novel}/{novel}.mm.meta.json"
        if os.path.exists(novel_meta):
            try:
                with open(novel_meta, 'r', encoding='utf-8') as f:
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
check_result("__pycache__ dirs", cache_count == 0, f"Found {cache_count} (run clean_cache.sh to clear)" if cache_count > 0 else "Clean")

# Check 7: Glossary Files (Enhanced)
print_section("GLOSSARY FILES CHECK")

# Check universal (shared) glossary files
universal_files = [
    ("data/universal_glossary_blueprint.json", "Universal approved terms"),
    ("data/universal_glossary_pending_blueprint.json", "Universal pending terms"),
    ("data/universal_context_memory_blueprint.json", "Universal context"),
]

print("  Universal (shared) files:")
for filepath, desc in universal_files:
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8-sig') as f:
                data = json.load(f)
            if 'terms' in data:
                check_result(f"  {filepath}", True, f"{len(data['terms'])} terms")
            elif 'pending_terms' in data:
                check_result(f"  {filepath}", True, f"{len(data['pending_terms'])} pending")
            elif 'dynamic_character_states' in data:
                check_result(f"  {filepath}", True, "OK")
            else:
                check_result(f"  {filepath}", True, "OK")
        except Exception as e:
            check_result(f"  {filepath}", False, str(e))
    else:
        check_result(f"  {filepath}", False, "Not found (blueprint template)")

# Check per-novel glossary files
print("\n  Per-novel files:")
novels = get_novel_dirs()
if novels:
    for novel in novels:
        print(f"\n  📖 {novel}:")
        
        # Glossary
        gl_path = f"data/output/{novel}/glossary/glossary.json"
        if os.path.exists(gl_path):
            try:
                with open(gl_path, 'r', encoding='utf-8-sig') as f:
                    data = json.load(f)
                count = len(data.get('terms', []))
                check_result(f"    glossary.json", True, f"{count} terms")
            except Exception as e:
                check_result(f"    glossary.json", False, str(e))
        else:
            check_result(f"    glossary.json", False, "Not found")
        
        # Pending
        pend_path = f"data/output/{novel}/glossary/glossary_pending.json"
        if os.path.exists(pend_path):
            try:
                with open(pend_path, 'r', encoding='utf-8-sig') as f:
                    data = json.load(f)
                count = len(data.get('pending_terms', []))
                check_result(f"    glossary_pending.json", True, f"{count} pending")
            except Exception as e:
                check_result(f"    glossary_pending.json", False, str(e))
        else:
            check_result(f"    glossary_pending.json", False, "Not found")
        
        # Context
        ctx_path = f"data/output/{novel}/glossary/context_memory.json"
        if os.path.exists(ctx_path):
            try:
                with open(ctx_path, 'r', encoding='utf-8-sig') as f:
                    data = json.load(f)
                ch = data.get('current_chapter', 0)
                check_result(f"    context_memory.json", True, f"ch {ch}")
            except Exception as e:
                check_result(f"    context_memory.json", False, str(e))
        else:
            check_result(f"    context_memory.json", False, "Not found")
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
test_files = ["test_novel_v1.py", "run.sh", "clean_cache.sh"]
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
  - Import errors: Run clean_cache.sh and retry
  - Glossary missing: Run --generate-glossary --novel <name>
  - Meta missing: Run --rebuild-meta --novel <name>
  
For help: python -m src.main --help
""")