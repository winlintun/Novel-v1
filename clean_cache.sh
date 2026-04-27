#!/bin/bash
#
# clean_cache.sh - Standalone cache cleaning script for Linux/Mac
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "======================================================================"
echo "  🧹 Cleaning Python Cache"
echo "======================================================================"
echo ""

# Count before cleaning
DIRS_BEFORE=$(find . -type d -name "__pycache__" 2>/dev/null | wc -l)
FILES_BEFORE=$(find . -type f \( -name "*.pyc" -o -name "*.pyo" \) 2>/dev/null | wc -l)

echo "  Before cleaning:"
echo "    Directories: $DIRS_BEFORE"
echo "    Files: $FILES_BEFORE"
echo ""

# Remove all __pycache__ directories
echo "  Removing __pycache__ directories..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# Remove all .pyc and .pyo files
echo "  Removing .pyc and .pyo files..."
find . -type f \( -name "*.pyc" -o -name "*.pyo" \) -delete 2>/dev/null || true

# Count after cleaning
DIRS_AFTER=$(find . -type d -name "__pycache__" 2>/dev/null | wc -l)
FILES_AFTER=$(find . -type f \( -name "*.pyc" -o -name "*.pyo" \) 2>/dev/null | wc -l)

DIRS_REMOVED=$((DIRS_BEFORE - DIRS_AFTER))
FILES_REMOVED=$((FILES_BEFORE - FILES_AFTER))

echo ""
echo "  After cleaning:"
echo "    Directories: $DIRS_AFTER"
echo "    Files: $FILES_AFTER"
echo ""
echo "  Removed:"
echo "    Directories: $DIRS_REMOVED"
echo "    Files: $FILES_REMOVED"
echo ""
echo "======================================================================"
echo "  ✅ Cache cleaning complete!"
echo "======================================================================"
