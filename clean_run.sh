#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# clean_run.sh — Project cleanup script
# Removes: Python caches, test artifacts, old logs, temp/working data
# Preserves: current translation logs, databases, glossaries, output files
# ──────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Novel Translation Project — Cleanup ==="
echo ""

# ── 1. Python cache files ───────────────────────────────────────────────────
# NOTE: scope to project source dirs only. Never recurse into env/.venv/venv —
# those hold installed packages whose compiled extensions (*.pyd/*.so) must not
# be touched. Also never delete *.pyd: those are native C extensions, not cache.
echo "[1/4] Removing Python cache files..."
for d in src tests scripts; do
    [ -d "$d" ] || continue
    find "$d" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find "$d" -type f \( -name "*.pyc" -o -name "*.pyo" \) -delete 2>/dev/null || true
done
rm -rf __pycache__ 2>/dev/null || true
echo "  OK"

# ── 2. Test / lint / coverage artifacts ─────────────────────────────────────
echo "[2/4] Removing test artifacts..."
rm -rf .pytest_cache/
rm -rf .ruff_cache/
rm -rf .mypy_cache/
rm -rf htmlcov/
rm -f coverage.xml
rm -f .coverage
echo "  OK"

# ── 3. Old logs (keep current session logs) ─────────────────────────────────
echo "[3/4] Cleaning old logs (preserving current translation logs)..."
if [ -d "logs" ]; then
    # Keep last 3 report files, delete older ones
    if [ -d "logs/report" ]; then
        ls -t logs/report/*.md 2>/dev/null | tail -n +4 | xargs rm -f 2>/dev/null || true
    fi
    # Delete performance logs (dead utility)
    rm -rf logs/performance/ 2>/dev/null || true
    # Delete temp log files
    rm -f logs/*.tmp 2>/dev/null || true
    # Delete benchmark reports (standalone)
    rm -f logs/report/benchmark_*.json 2>/dev/null || true
fi
echo "  OK"

# ── 4. Working / temp data ──────────────────────────────────────────────────
echo "[4/4] Removing working/temp data..."
rm -rf data/working/ 2>/dev/null || true
rm -rf logs/temp/ 2>/dev/null || true
rm -f data/training/rating_progress.json 2>/dev/null || true
echo "  OK"

echo ""
echo "=== Cleanup complete. ==="
echo ""
echo "Remaining tests: $(ls tests/test_*.py 2>/dev/null | wc -l)"
echo "To run: pytest tests/ -v"
