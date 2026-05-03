#!/usr/bin/env python3
"""
Diagnostic script to check translation configuration
Run this to verify your setup is correct

Usage: python diagnose.py
"""

import sys
import os
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

# Check 2: Memory Manager
print_section("MEMORY SYSTEM CHECK")
try:
    from src.memory.memory_manager import MemoryManager
    mm = MemoryManager(
        glossary_path="data/glossary.json",
        context_path="data/context_memory.json"
    )
    glossary = mm.get_glossary_for_prompt(limit=5)
    check_result("MemoryManager", True, f"Glossary loaded: {len(glossary.get('terms', []))} terms")
except Exception as e:
    check_result("MemoryManager", False, str(e))

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

# Check 7: Glossary Files
print_section("GLOSSARY FILES CHECK")
import json

glossary_files = [
    ("data/glossary.json", "Approved terms"),
    ("data/glossary_pending.json", "Pending terms"),
    ("data/context_memory.json", "Context memory")
]

for filepath, desc in glossary_files:
    try:
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            check_result(f"{filepath}", True, f"{desc} - OK")
        else:
            check_result(f"{filepath}", False, "File not found")
    except json.JSONDecodeError:
        check_result(f"{filepath}", False, "Invalid JSON")
    except Exception as e:
        check_result(f"{filepath}", False, str(e))

# Check 8: Agents Available
print_section("AGENTS CHECK")
agents_to_check = [
    ("src/agents/translator.py", "Translator"),
    ("src/agents/refiner.py", "Refiner"),
    ("src/agents/checker.py", "Checker"),
    ("src/agents/qa_tester.py", "QA Tester"),
    ("src/agents/context_updater.py", "Context Updater"),
    ("src/agents/preprocessor.py", "Preprocessor"),
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
  
For help: python -m src.main --help
""")