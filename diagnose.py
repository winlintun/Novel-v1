#!/usr/bin/env python3
"""
Diagnostic script to check translation configuration
Run this to verify your setup is correct
"""

import sys
sys.path.insert(0, '.')

print("=" * 70)
print("🔍 TRANSLATION SETUP DIAGNOSTIC")
print("=" * 70)

# Check 1: Config file models
print("\n📋 Checking config/settings.yaml...")
from src.config import load_config
config = load_config()

print(f"  Translator model: {config.models.translator}")
print(f"  Editor model: {config.models.editor}")
print(f"  Refiner model: {config.models.refiner}")
print(f"  Pipeline mode: {config.translation_pipeline.mode}")
print(f"  Source language: {config.project.source_language}")

if config.models.translator == "qwen:7b":
    print("  ⚠️  WARNING: Config still using qwen:7b - should be padauk-gemma:q8_0")
else:
    print(f"  ✅ Config looks good (using {config.models.translator})")

# Check 2: Auto-detection logic
print("\n🔍 Checking auto-detection code...")
try:
    from src.cli.commands import _resolve_workflow, _apply_workflow_config
    import inspect
    source = inspect.getsource(_apply_workflow_config)
    if "padauk-gemma" in source:
        print("  ✅ Auto-detection code found with padauk-gemma model")
    else:
        print("  ⚠️  WARNING: Auto-detection code doesn't have padauk-gemma")
except Exception as e:
    print(f"  ❌ ERROR: {e}")

# Check 3: Test with actual file
print("\n📄 Testing with reverend-insanity_0002.md...")
try:
    from src.utils.file_handler import FileHandler
    from src.agents.preprocessor import Preprocessor
    import argparse
    
    text = FileHandler.read_text('data/input/reverend-insanity/reverend-insanity_0002.md')
    preprocessor = Preprocessor()
    detected_lang = preprocessor.detect_language(text)
    
    print(f"  Detected language: {detected_lang}")
    
    # Simulate workflow resolution
    args = argparse.Namespace(
        input_file='data/input/reverend-insanity/reverend-insanity_0002.md',
        workflow=None,
        lang=None
    )
    
    workflow = _resolve_workflow(args)
    print(f"  Resolved workflow: {workflow}")
    
    if workflow:
        import logging
        logging.basicConfig(level=logging.INFO, format='%(message)s')
        logger = logging.getLogger()
        
        test_config = load_config()
        new_config = _apply_workflow_config(test_config, workflow, logger)
        
        print(f"  After workflow applied:")
        print(f"    Translator: {new_config.models.translator}")
        print(f"    Editor: {new_config.models.editor}")
        
        if new_config.models.translator == "padauk-gemma:q8_0":
            print("  ✅ Workflow correctly selects padauk-gemma:q8_0")
        else:
            print(f"  ⚠️  WARNING: Workflow selected {new_config.models.translator}")
    
except Exception as e:
    print(f"  ❌ ERROR: {e}")
    import traceback
    traceback.print_exc()

# Check 4: Python cache
print("\n🐍 Checking Python cache...")
import os
cache_dirs = []
for root, dirs, files in os.walk('.'):
    if '__pycache__' in dirs:
        cache_dirs.append(os.path.join(root, '__pycache__'))

if cache_dirs:
    print(f"  Found {len(cache_dirs)} __pycache__ directories")
    print("  Run this to clear: find . -type d -name '__pycache__' -exec rm -rf {} +")
else:
    print("  ✅ No Python cache found")

print("\n" + "=" * 70)
print("✅ Diagnostic complete")
print("=" * 70)
print("\nIf you see 'qwen:7b' anywhere above, your code is outdated.")
print("Try clearing Python cache: find . -type d -name '__pycache__' -exec rm -rf {} +")
