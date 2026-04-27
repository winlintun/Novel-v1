#!/usr/bin/env python3
"""
Auto-clean launcher for novel translation
Clears Python cache before running to ensure fresh code execution
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Clean cache first (unless --no-clean is passed)
if '--no-clean' not in sys.argv:
    from src.utils.cache_cleaner import clean_cache_with_report
    clean_cache_with_report()
    # Remove --no-clean from args if it was there (not needed anymore)
    sys.argv = [arg for arg in sys.argv if arg != '--no-clean']
else:
    # Just remove the flag
    sys.argv = [arg for arg in sys.argv if arg != '--no-clean']

# Now run the main module
from src.main import main

if __name__ == "__main__":
    sys.exit(main())
