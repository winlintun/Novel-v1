#!/bin/bash
#
# run.sh - Auto-clean and run translation for Linux/Mac
# Cleans: Python cache, test cache, coverage, linter cache, temp files
# 
# Usage: ./run.sh [arguments]
#        ./run.sh --novel "novel_name" --chapter 1
#        ./run.sh --novel "novel_name" --all
#        ./run.sh --help
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

# Function to count files/dirs
count_files() {
    find . -type f "$1" 2>/dev/null | wc -l
}
count_dirs() {
    find . -type d -name "$1" 2>/dev/null | wc -l
}

# ===================== Step 1: Comprehensive Cache Cleaning =====================
echo "Step 1: Cleaning Python Cache..."
echo "----------------------------------------------------------------------"

# Python cache
BEFORE_PYC_DIRS=$(count_dirs "__pycache__")
BEFORE_PYC_FILES=$(count_files "\( -name '*.pyc' -o -name '*.pyo' -o -name '*.pyd' \)")

find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f \( -name "*.pyc" -o -name "*.pyo" -o -name "*.pyd" \) -delete 2>/dev/null || true

echo "  Python cache: $BEFORE_PYC_DIRS dirs, $BEFORE_PYC_FILES files"

# Test cache
find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name ".hypothesis" -exec rm -rf {} + 2>/dev/null || true

# Coverage
find . -type f \( -name "coverage.xml" -o -name ".coverage" -o -name "*.cover" \) -delete 2>/dev/null || true
find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true

# Type checkers
find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "dmypy.json" -delete 2>/dev/null || true
find . -type d -name ".pyre" -exec rm -rf {} + 2>/dev/null || true

# Linters
find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true

# Jupyter
find . -type d -name ".ipynb_checkpoints" -exec rm -rf {} + 2>/dev/null || true

# IDE
find . -type d -name ".vscode" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name ".idea" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.swp" -delete 2>/dev/null || true
find . -type f -name "*.swo" -delete 2>/dev/null || true

# Temp files
find . -type f \( -name "*.tmp" -o -name "*.bak" -o -name "*.orig" \) -delete 2>/dev/null || true

AFTER_PYC_DIRS=$(count_dirs "__pycache__")
AFTER_PYC_FILES=$(count_files "\( -name '*.pyc' -o -name '*.pyo' \)")

echo "  Remaining: $AFTER_PYC_DIRS dirs, $AFTER_PYC_FILES files"
echo "  ✅ Cache cleaned!"
echo ""

# ===================== Step 2: Clean old log files =====================
echo "Step 2: Cleaning old log files..."
echo "----------------------------------------------------------------------"

LOGS_REMOVED=0

if [ -d "logs" ]; then
    cd logs 2>/dev/null || true
    
    # Keep last 5 translation logs
    ls -t translation_*.log 2>/dev/null | tail -n +6 | while read file; do
        rm -f "$file" 2>/dev/null && LOGS_REMOVED=$((LOGS_REMOVED + 1))
    done
    
    # Clean old review reports - keep last 10
    if [ -d "report" ]; then
        cd report 2>/dev/null || true
        ls -t *.md 2>/dev/null | tail -n +11 | while read file; do
            rm -f "$file" 2>/dev/null && LOGS_REMOVED=$((LOGS_REMOVED + 1))
        done
        cd .. 2>/dev/null || true
    fi
    
    cd "$SCRIPT_DIR" 2>/dev/null || true
fi

echo "  Old log files removed: $LOGS_REMOVED"
echo "  ✅ Logs cleaned (kept: 5 recent translation logs, 10 review reports)"
echo ""

# ===================== Step 3: Show help if no args =====================
if [ $# -eq 0 ]; then
    echo "======================================================================"
    echo "  📚 Novel Translation Pipeline"
    echo "======================================================================"
    echo ""
    echo "Usage:"
    echo "  ./run.sh --novel \"novel_name\" --chapter 1"
    echo "  ./run.sh --novel \"novel_name\" --all"
    echo "  ./run.sh --novel \"novel_name\" --generate-glossary"
    echo ""
    echo "Common Options:"
    echo "  --novel NAME       Translate a novel (use with --chapter or --all)"
    echo "  --chapter NUM      Translate specific chapter"
    echo "  --chapter-range N-M  Translate chapters N to M"
    echo "  --all              Translate all chapters"
    echo "  --generate-glossary  Generate glossary from chapters"
    echo "  --workflow way1    Force EN->MM direct translation"
    echo "  --workflow way2    Force CN->EN->MM pivot translation"
    echo "  --ui               Launch web UI"
    echo ""
    echo "Cache and logs have been cleaned."
    echo "Use one of the commands above to translate."
    echo ""
    echo "For full help: python -m src.main --help"
    echo ""
    exit 0
fi

# ===================== Step 4: Run the translation =====================
echo "======================================================================"
echo "  🚀 Starting Translation"
echo "======================================================================"
echo ""

cd "$SCRIPT_DIR"

# Run the main module
python3 -m src.main "$@"

# Get the exit code
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "======================================================================"
    echo "  ❌ Translation failed with error code $EXIT_CODE"
    echo "======================================================================"
else
    echo ""
    echo "======================================================================"
    echo "  ✅ Translation completed successfully"
    echo "======================================================================"
fi

exit $EXIT_CODE