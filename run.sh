#!/bin/bash
#
# Auto-clean and run translation for Linux/Mac
# This script clears Python cache before running to ensure fresh code
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

echo "======================================================================"
echo "  🚀 Starting Translation"
echo "======================================================================"
echo ""

# Run the Python launcher with all arguments passed through
python3 "$SCRIPT_DIR/run.py" "$@"

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
