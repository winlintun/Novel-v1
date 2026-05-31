#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# clean_run.sh — Project cleanup script
# Removes: test artifacts, Python caches, old logs, dead files, temp data
# Preserves: current translation logs, databases, glossaries, output files
# ──────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Novel Translation Project — Cleanup ==="
echo ""

# ── 1. Python cache files ───────────────────────────────────────────────────
echo "[1/8] Removing Python cache files..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete
find . -type f -name "*.pyo" -delete
find . -type f -name "*.pyd" -delete
echo "  OK"

# ── 2. Pytest cache + coverage ──────────────────────────────────────────────
echo "[2/8] Removing test artifacts..."
rm -rf .pytest_cache/
rm -rf htmlcov/
rm -f coverage.xml
rm -f .coverage
echo "  OK"

# ── 3. Old logs (keep current session logs) ─────────────────────────────────
echo "[3/8] Cleaning old logs (preserving current translation logs)..."
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
echo "[4/8] Removing working/temp data..."
rm -rf data/working/ 2>/dev/null || true
rm -rf logs/temp/ 2>/dev/null || true
rm -f data/training/rating_progress.json 2>/dev/null || true
echo "  OK"

# ── 5. Dead config files ────────────────────────────────────────────────────
echo "[5/8] Removing unused config files..."
rm -f config/settings.sailor2.yaml 2>/dev/null || true
rm -f config/settings.translategemma.yaml 2>/dev/null || true
rm -f config/settings.qwen2.5.yaml 2>/dev/null || true
rm -f config/error_recovery.yaml 2>/dev/null || true
echo "  OK"

# ── 6. Dead source packages ─────────────────────────────────────────────────
echo "[6/8] Removing dead source files..."
rm -rf src/database/ 2>/dev/null || true           # Old DB package (replaced by src/db/)
rm -f src/agents/prompt_patch.py 2>/dev/null || true  # Deprecated compat shim
rm -rf src/core/ 2>/dev/null || true                # Unused DI container
rm -rf src/types/ 2>/dev/null || true               # Unused TypedDict definitions
rm -f src/utils/ram_monitor.py 2>/dev/null || true
rm -f src/utils/performance_logger.py 2>/dev/null || true
rm -f src/utils/glossary_suggestor.py 2>/dev/null || true
rm -f src/utils/glossary_matcher.py 2>/dev/null || true
rm -f src/evaluation/glossary_miner.py 2>/dev/null || true  # Dead file within live dir
echo "  OK"

# ── 7. Dead agent files ─────────────────────────────────────────────────────
echo "[7/8] Removing dead agent files..."
rm -f src/agents/fast_translator.py 2>/dev/null || true
rm -f src/agents/fast_refiner.py 2>/dev/null || true
rm -f src/agents/pivot_translator.py 2>/dev/null || true
rm -f src/agents/glossary_sync.py 2>/dev/null || true
echo "  OK"

# ── 8. Dead data files ──────────────────────────────────────────────────────
echo "[8/8] Removing dead data files..."
rm -f src/data/ingest_rag_export.py 2>/dev/null || true
echo "  OK"

# ── 9. Dead test files (imports dead source code) ───────────────────────────
echo "[9/9] Removing dead test files..."
for f in \
    test_fast_translator.py \
    test_fast_refiner.py \
    test_pivot_translator.py \
    test_pivot_stage2_guard.py \
    test_glossary_sync.py \
    test_glossary_suggestor.py \
    test_performance_logger.py \
    test_ram_monitor.py \
    test_container.py \
    test_regression.py \
    test_prompt_patch.py \
; do
    rm -f "tests/$f" 2>/dev/null || true
done
echo "  OK"

echo ""
echo "=== Cleanup complete. ==="
echo ""
echo "Remaining tests: $(ls tests/test_*.py 2>/dev/null | wc -l)"
echo "To run: pytest tests/ -v"
