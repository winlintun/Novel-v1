#!/usr/bin/env python3
"""
Diagnostic script to check translation configuration
Run this to verify your setup is correct

Usage: python diagnose.py
"""

import sys
import os
import json
sys.path.insert(0, '.')

# Windows consoles default to cp1252 and choke on the emoji/Myanmar output
# below. Force UTF-8 so the diagnostic never crashes on its own print calls.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

from src.db.connection import DatabaseConnection  # noqa: E402
from src.db.repositories.glossary_repo import GlossaryRepository  # noqa: E402


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
            # Skip dotfolders (e.g. .versions) and non-novel dirs. These are
            # infrastructure, not novels — treating them as novels previously
            # created a bogus `novel_.versions` row in the glossary DB.
            if d.startswith('.'):
                continue
            novel_path = os.path.join(base_path, d)
            if os.path.isdir(novel_path):
                # Skip non-novel directories like 'default', 'report', etc.
                if d not in ('default', 'report'):
                    novels.append(d)
    return novels


print(f"\n{'='*70}")
print("  🔍 NOVEL TRANSLATION SETUP DIAGNOSTIC")
print(f"{'='*70}")

# Check 1: Config file
print_section("CONFIGURATION CHECK")
try:
    from src.config import load_config
    config = load_config()
    check_result("Config loaded", True, "config/settings.yaml")
    print(f"  Translator: {config.models.translator}")
    print(f"  Editor: {config.models.editor}")
    print(f"  Refiner: {config.models.refiner}")
    print(f"  Checker: {config.models.checker}")
    print(f"  Pipeline mode: {config.translation_pipeline.mode}")
    pipe = config.translation_pipeline
    print(f"  Optional stages: reflection={pipe.use_reflection} "
          f"fiction_editor={pipe.use_fiction_editor} "
          f"syntax_editor={pipe.use_syntax_editor}")
    if pipe.mode == "two_stage":
        print(f"  Two-stage models: {pipe.stage1_model} -> {pipe.stage2_model}")
    print(f"  Source language: {config.project.source_language}")
    print(f"  Target language: {config.project.target_language}")
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
            check_result("  Universal (global DB)", True, f"{len(global_terms)} terms")
        except Exception as e:
            check_result("  Universal (global DB)", False, str(e))
        
        from src.utils.novel_slug import novel_id_from_name, slugify_novel
        novel_id = novel_id_from_name(novel)
        try:
            repo = GlossaryRepository(DatabaseConnection("data/novel_translation.db"))
            terms = repo.get_terms_by_novel(novel_id, include_global=False, limit=9999)
            approved = sum(1 for t in terms if t["status"] == "approved")
            pending = sum(1 for t in terms if t["status"] == "pending")
            check_result("  Glossary (DB)", True, f"{len(terms)} terms ({approved} approved, {pending} pending)")
        except Exception as e:
            check_result("  Glossary (DB)", False, str(e))
        
        # Check meta.json (single file per novel) — output dir is slugified.
        novel_slug = slugify_novel(novel)
        novel_meta = f"data/output/{novel_slug}/{novel_slug}.mm.meta.json"
        if os.path.exists(novel_meta):
            try:
                with open(novel_meta, 'r', encoding='utf-8-sig') as f:
                    meta_data = json.load(f)
                total_ch = meta_data.get('total_chapters', 0)
                check_result("  Meta.json", True, f"{total_ch} chapters tracked")
            except Exception as e:
                check_result("  Meta.json", False, str(e))
        else:
            check_result("  Meta.json", False, "Not found (run --rebuild-meta)")
        
        # Count translated chapters
        output_dir = f"data/output/{novel}"
        if os.path.isdir(output_dir):
            chapter_files = [f for f in os.listdir(output_dir) if f.endswith('.mm.md')]
            check_result("  Chapters", True, f"{len(chapter_files)} translated")

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
    # Don't descend into the virtualenv — its __pycache__ dirs are not ours.
    dirs[:] = [d for d in dirs if d not in ('env', '.venv', 'venv', '.git')]
    if '__pycache__' in dirs:
        cache_count += 1
check_result(
    "__pycache__ dirs",
    cache_count == 0,
    "Clean" if cache_count == 0
    else f"Found {cache_count} (run 'python -m src.main --clean' to clear)",
)

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
    check_result("  novel_translation.db", True, f"{size_mb:.1f} MB")
else:
    check_result("  novel_translation.db", False, "Not found")

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
            check_result("    Glossary (DB)", True, f"{len(terms)} terms ({approved} approved, {pending} pending)")
        except Exception as e:
            check_result("    Glossary (DB)", False, str(e))
else:
    print("  No novels found in data/output/")

# Check 8: RAG System (translation-example retrieval)
print_section("RAG SYSTEM CHECK")
try:
    rag_cfg = config.rag if isinstance(getattr(config, "rag", None), dict) else {}
    enabled = rag_cfg.get("enabled", False)
    check_result("  RAG enabled", enabled,
                 "on" if enabled else "disabled in config")

    if enabled:
        # chromadb is an optional dependency; RAG falls back to SQLite without it
        try:
            import chromadb  # noqa: F401
            check_result("  chromadb installed", True)
        except Exception as e:
            check_result("  chromadb installed", False,
                         f"{e} (RAG falls back to SQLite)")

        chroma_path = rag_cfg.get("chroma_path", "data/chroma")
        check_result("  Chroma store", os.path.isdir(chroma_path),
                     chroma_path if os.path.isdir(chroma_path)
                     else f"{chroma_path} not found (build with alignment pipeline)")

        embed_model = rag_cfg.get("embedding_model", "models/bge-m3")
        check_result("  Embedding model", os.path.isdir(embed_model),
                     embed_model if os.path.isdir(embed_model)
                     else f"{embed_model} not found")

        feedback_db = rag_cfg.get("feedback_db", rag_cfg.get("db_path", ""))
        if feedback_db:
            check_result("  Feedback/dataset DB", os.path.exists(feedback_db),
                         feedback_db if os.path.exists(feedback_db) else "not found")
except Exception as e:
    check_result("  RAG system", False, str(e))

# Check 9: Agents Available
print_section("AGENTS CHECK")
agents_to_check = [
    ("src/agents/translator.py", "Translator"),
    ("src/agents/refiner.py", "Refiner"),
    ("src/agents/fiction_editor.py", "Fiction Editor"),
    ("src/agents/myanmar_syntax_editor.py", "Myanmar Syntax Editor"),
    ("src/agents/checker.py", "Checker"),
    ("src/agents/qa_tester.py", "QA Tester"),
    ("src/agents/context_updater.py", "Context Updater"),
    ("src/agents/preprocessor.py", "Preprocessor"),
    ("src/agents/reflection_agent.py", "Reflection"),
    ("src/agents/glossary_generator.py", "Glossary Generator"),
    ("src/agents/myanmar_quality_checker.py", "Myanmar QC"),
]

for filepath, name in agents_to_check:
    exists = os.path.exists(filepath)
    check_result(name, exists, filepath)

# Check 10: Test suite + helper scripts
print_section("TEST FILES CHECK")
if os.path.isdir("tests"):
    test_modules = [f for f in os.listdir("tests")
                    if f.startswith("test_") and f.endswith(".py")]
    check_result("tests/ suite", bool(test_modules),
                 f"{len(test_modules)} test modules (run with: pytest)")
else:
    check_result("tests/ suite", False, "tests/ directory NOT FOUND")

for f in ("clean_run.bat", "clean_run.sh"):
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
  - RAG store missing: Build it via the dataset alignment pipeline

For help: python -m src.main --help
""")