#!/bin/bash
#
# clean_cache.sh - Comprehensive cache and temp file cleaner for Linux/Mac
# Cleans: Python cache, test cache, coverage reports, IDE cache, temp files
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "======================================================================"
echo "  🧹 Comprehensive Cache & Junk Cleaner"
echo "======================================================================"
echo ""

# Function to count files
count_files() {
    find . -type f "$1" 2>/dev/null | wc -l
}
count_dirs() {
    find . -type d -name "$1" 2>/dev/null | wc -l
}

# ===================== Python Cache =====================
echo "  [1/9] Python Cache..."
echo "----------------------------------------------------------------------"
PYC_DIRS_BEFORE=$(count_dirs "__pycache__")
PYC_FILES_BEFORE=$(count_files "\( -name '*.pyc' -o -name '*.pyo' -o -name '*.pyd' \)")

find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f \( -name "*.pyc" -o -name "*.pyo" -o -name "*.pyd" \) -delete 2>/dev/null || true

echo "    Removed: $PYC_DIRS_BEFORE __pycache__ dirs, $PYC_FILES_BEFORE .pyc/.pyo files"

# ===================== Test Cache =====================
echo "  [2/9] Test Cache..."
echo "----------------------------------------------------------------------"
TEST_DIRS_BEFORE=$(count_dirs ".pytest_cache")
find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true

HYPOTHESIS_BEFORE=$(count_dirs ".hypothesis")
find . -type d -name ".hypothesis" -exec rm -rf {} + 2>/dev/null || true

echo "    Removed: $TEST_DIRS_BEFORE .pytest_cache dirs, $HYPOTHESIS_BEFORE .hypothesis dirs"

# ===================== Coverage Reports =====================
echo "  [3/9] Coverage Reports..."
echo "----------------------------------------------------------------------"
COV_FILES_BEFORE=$(count_files "-name 'coverage.xml' -o -name '.coverage' -o -name '*.cover'")
find . -type f \( -name "coverage.xml" -o -name ".coverage" -o -name "*.cover" \) -delete 2>/dev/null || true

HTMLCOV_BEFORE=$(count_dirs "htmlcov")
find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true

echo "    Removed: $COV_FILES_BEFORE coverage files, $HTMLCOV_BEFORE htmlcov dirs"

# ===================== Type Checker Cache =====================
echo "  [4/9] Type Checker Cache..."
echo "----------------------------------------------------------------------"
MYPY_BEFORE=$(count_dirs ".mypy_cache")
find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true

DMPY_BEFORE=$(count_dirs ".dmypy.json")
find . -type d -name ".dmypy.json" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "dmypy.json" -delete 2>/dev/null || true

PYRE_BEFORE=$(count_dirs ".pyre")
find . -type d -name ".pyre" -exec rm -rf {} + 2>/dev/null || true

echo "    Removed: $MYPY_BEFORE mypy dirs, $DMPY_BEFORE dmypy dirs, $PYRE_BEFORE pyre dirs"

# ===================== Linter Cache =====================
echo "  [5/9] Linter Cache..."
echo "----------------------------------------------------------------------"
RUFF_BEFORE=$(count_dirs ".ruff_cache")
find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true

FLAKE_BEFORE=$(count_dirs ".flake8")
find . -type d -name ".flake8" -exec rm -rf {} + 2>/dev/null || true

echo "    Removed: $RUFF_BEFORE .ruff_cache dirs, $FLAKE_BEFORE .flake8 dirs"

# ===================== Jupyter =====================
echo "  [6/9] Jupyter Cache..."
echo "----------------------------------------------------------------------"
JUPYTER_BEFORE=$(count_dirs ".ipynb_checkpoints")
find . -type d -name ".ipynb_checkpoints" -exec rm -rf {} + 2>/dev/null || true

echo "    Removed: $JUPYTER_BEFORE .ipynb_checkpoints dirs"

# ===================== IDE Cache =====================
echo "  [7/9] IDE Cache..."
echo "----------------------------------------------------------------------"
find . -type d -name ".vscode" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name ".idea" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.swp" -delete 2>/dev/null || true
find . -type f -name "*.swo" -delete 2>/dev/null || true

echo "    Removed: .vscode/, .idea/, *.swp, *.swo"

# ===================== Temp Files =====================
echo "  [8/9] Temporary Files..."
echo "----------------------------------------------------------------------"
TEMP_FILES_BEFORE=$(count_files "-name '*.tmp' -o -name '*.bak' -o -name '*.orig' -o -name '*.pyjt'")
find . -type f \( -name "*.tmp" -o -name "*.bak" -o -name "*.orig" -o -name "*.pyjt" \) -delete 2>/dev/null || true

echo "    Removed: $TEMP_FILES_BEFORE temp/backup files"

# ===================== Log Files =====================
echo "  [9/9] Old Log Files (keep recent)..."
echo "----------------------------------------------------------------------"

# Keep last 5 translation logs
if [ -d "logs" ]; then
    cd logs
    ls -t translation_*.log 2>/dev/null | tail -n +6 | xargs -r rm -f 2>/dev/null || true
    # Clean old review reports (keep last 10)
    if [ -d "report" ]; then
        cd report
        ls -t *.md 2>/dev/null | tail -n +11 | xargs -r rm -f 2>/dev/null || true
        cd ..
    fi
    cd "$SCRIPT_DIR"
fi

echo "    Kept: 5 most recent translation logs, 10 most recent review reports"

# ===================== Summary =====================
echo ""
echo "======================================================================"
echo "  ✅ Cleanup Complete!"
echo "======================================================================"

PYC_AFTER=$(count_dirs "__pycache__")
echo "  Remaining __pycache__: $PYC_AFTER dirs"

# Check for any remaining .pyc files
REMAINING_PYC=$(find . -type f \( -name "*.pyc" -o -name "*.pyo" \) 2>/dev/null | wc -l)
echo "  Remaining .pyc/.pyo: $REMAINING_PYC files"
echo ""