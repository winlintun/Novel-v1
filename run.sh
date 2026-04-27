#!/bin/bash
#
# Auto-clean and run translation for Linux/Mac
# This script clears Python cache and old logs before running to ensure fresh execution
# 
# Usage: ./run.sh [arguments]
#        ./run.sh --input path/to/file.md
#        ./run.sh --novel "novel_name" --chapter 1
#        ./run.sh (no arguments shows help)
#

set -e  # Exit on error

echo "======================================================================"
echo "  🧹 Novel Translation - Auto Cache Cleaner & Launcher"
echo "======================================================================"
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ ERROR: Python 3 not found!"
    echo "Please install Python 3 or add it to your PATH"
    exit 1
fi

# Step 1: Clean Python cache
echo "Step 1: Cleaning Python cache..."
echo "----------------------------------------------------------------------"

# Count before cleaning
DIRS_BEFORE=$(find . -type d -name "__pycache__" 2>/dev/null | wc -l)
FILES_BEFORE=$(find . -type f \( -name "*.pyc" -o -name "*.pyo" \) 2>/dev/null | wc -l)

# Remove all __pycache__ directories
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# Remove all .pyc and .pyo files
find . -type f \( -name "*.pyc" -o -name "*.pyo" \) -delete 2>/dev/null || true

# Count after cleaning
DIRS_AFTER=$(find . -type d -name "__pycache__" 2>/dev/null | wc -l)
FILES_AFTER=$(find . -type f \( -name "*.pyc" -o -name "*.pyo" \) 2>/dev/null | wc -l)

DIRS_REMOVED=$((DIRS_BEFORE - DIRS_AFTER))
FILES_REMOVED=$((FILES_BEFORE - FILES_AFTER))

echo "  Directories removed: $DIRS_REMOVED"
echo "  Files removed: $FILES_REMOVED"
echo "  ✅ Cache cleaned!"
echo ""

# Step 2: Clean old log files (keep last one and server logs)
echo "Step 2: Cleaning old log files..."
echo "----------------------------------------------------------------------"

LOGS_REMOVED=0

# Clean old translation logs - keep only the most recent one
if [ -d "logs" ]; then
    cd logs 2>/dev/null || true
    
    # Simple approach: list files sorted by time, skip first (newest), delete rest
    ls -t translation_*.log 2>/dev/null | tail -n +2 | while read file; do
        rm -f "$file" 2>/dev/null && LOGS_REMOVED=$((LOGS_REMOVED + 1))
    done
    
    # Clean old progress logs - keep last 10
    if [ -d "progress" ]; then
        cd progress 2>/dev/null || true
        ls -t progress_*.md 2>/dev/null | tail -n +11 | while read file; do
            rm -f "$file" 2>/dev/null && LOGS_REMOVED=$((LOGS_REMOVED + 1))
        done
        cd .. 2>/dev/null || true
    fi
    
    cd "$SCRIPT_DIR" 2>/dev/null || true
fi

echo "  Old log files removed: $LOGS_REMOVED"
echo "  ✅ Logs cleaned (kept: most recent translation log, web_server.log)"
echo ""

# Step 3: If no arguments, show help and exit
if [ $# -eq 0 ]; then
    echo "======================================================================"
    echo "  📚 Novel Translation Pipeline"
    echo "======================================================================"
    echo ""
    echo "Usage:"
    echo "  ./run.sh --input path/to/file.md"
    echo "  ./run.sh --novel \"novel_name\" --chapter 1"
    echo "  ./run.sh --novel \"novel_name\" --all"
    echo ""
    echo "Common Options:"
    echo "  --input FILE       Translate a single file"
    echo "  --novel NAME       Translate a novel (use with --chapter or --all)"
    echo "  --chapter NUM      Translate specific chapter"
    echo "  --all              Translate all chapters"
    echo "  --workflow way1    Force EN->MM direct translation"
    echo "  --workflow way2    Force CN->EN->MM pivot translation"
    echo ""
    echo "Cache and logs have been cleaned."
    echo "Use one of the commands above to translate."
    echo ""
    echo "For full help: ./run.sh --help"
    echo ""
    exit 0
fi

# Step 4: Run the translation with all arguments
echo "======================================================================"
echo "  🚀 Starting Translation"
echo "======================================================================"
echo ""

# Run the main module directly (cache already cleaned above)
# Use --no-clean flag to skip redundant cleaning in Python
cd "$SCRIPT_DIR"
python3 -c "
import sys
sys.path.insert(0, '.')
from src.main import main
sys.argv = ['src.main'] + ['--no-clean'] + sys.argv[1:]
sys.exit(main())
" "$@"

# Get the exit code
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "======================================================================"
    echo "  ❌ Translation failed with error code $EXIT_CODE"
    echo "======================================================================"
    read -p "Press Enter to continue..."
else
    echo ""
    echo "======================================================================"
    echo "  ✅ Translation completed successfully"
    echo "======================================================================"
fi

exit $EXIT_CODE
