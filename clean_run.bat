@echo off
REM ──────────────────────────────────────────────────────────────────────────────
REM clean_run.bat — Project cleanup script (Windows)
REM Removes: test artifacts, Python caches, old logs, dead files, temp data
REM Preserves: current translation logs, databases, glossaries, output files
REM ──────────────────────────────────────────────────────────────────────────────
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo === Novel Translation Project — Cleanup ===
echo.

REM ── 1. Python cache files ───────────────────────────────────────────────────
echo [1/9] Removing Python cache files...
for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d" 2>nul
del /s /q *.pyc 2>nul
del /s /q *.pyo 2>nul
echo   OK

REM ── 2. Pytest cache + coverage ──────────────────────────────────────────────
echo [2/9] Removing test artifacts...
if exist .pytest_cache\ rd /s /q .pytest_cache\ 2>nul
if exist htmlcov\ rd /s /q htmlcov\ 2>nul
if exist coverage.xml del coverage.xml 2>nul
if exist .coverage del .coverage 2>nul
echo   OK

REM ── 3. Old logs (keep last 3 report files) ─────────────────────────────────
echo [3/9] Cleaning old logs (preserving current translation logs)...
if exist logs\report\ (
    for /f "skip=3" %%f in ('dir /b /o-d logs\report\*.md 2^>nul') do del "logs\report\%%f" 2>nul
)
if exist logs\performance\ rd /s /q logs\performance\ 2>nul
if exist logs\*.tmp del /q logs\*.tmp 2>nul
if exist logs\report\benchmark_*.json del /q logs\report\benchmark_*.json 2>nul
echo   OK

REM ── 4. Working / temp data ──────────────────────────────────────────────────
echo [4/9] Removing working/temp data...
if exist data\working\ rd /s /q data\working\ 2>nul
if exist logs\temp\ rd /s /q logs\temp\ 2>nul
if exist data\training\rating_progress.json del data\training\rating_progress.json 2>nul
echo   OK

REM ── 5. Dead config files ────────────────────────────────────────────────────
echo [5/9] Removing unused config files...
if exist config\settings.sailor2.yaml del config\settings.sailor2.yaml 2>nul
if exist config\settings.translategemma.yaml del config\settings.translategemma.yaml 2>nul
if exist config\settings.qwen2.5.yaml del config\settings.qwen2.5.yaml 2>nul
if exist config\error_recovery.yaml del config\error_recovery.yaml 2>nul
echo   OK

REM ── 6. Dead source packages ─────────────────────────────────────────────────
echo [6/9] Removing dead source files...
if exist src\database\ rd /s /q src\database\ 2>nul
if exist src\agents\prompt_patch.py del src\agents\prompt_patch.py 2>nul
if exist src\core\ rd /s /q src\core\ 2>nul
if exist src\types\ rd /s /q src\types\ 2>nul
if exist src\utils\ram_monitor.py del src\utils\ram_monitor.py 2>nul
if exist src\utils\performance_logger.py del src\utils\performance_logger.py 2>nul
if exist src\utils\glossary_suggestor.py del src\utils\glossary_suggestor.py 2>nul
if exist src\utils\glossary_matcher.py del src\utils\glossary_matcher.py 2>nul
if exist src\evaluation\glossary_miner.py del src\evaluation\glossary_miner.py 2>nul
echo   OK

REM ── 7. Dead agent files ─────────────────────────────────────────────────────
echo [7/9] Removing dead agent files...
if exist src\agents\fast_translator.py del src\agents\fast_translator.py 2>nul
if exist src\agents\fast_refiner.py del src\agents\fast_refiner.py 2>nul
if exist src\agents\pivot_translator.py del src\agents\pivot_translator.py 2>nul
if exist src\agents\glossary_sync.py del src\agents\glossary_sync.py 2>nul
echo   OK

REM ── 8. Dead data files ──────────────────────────────────────────────────────
echo [8/9] Removing dead data files...
if exist src\data\ingest_rag_export.py del src\data\ingest_rag_export.py 2>nul
echo   OK

REM ── 9. Dead test files (imports dead source code) ───────────────────────────
echo [9/9] Removing dead test files...
if exist tests\test_fast_translator.py del tests\test_fast_translator.py 2>nul
if exist tests\test_fast_refiner.py del tests\test_fast_refiner.py 2>nul
if exist tests\test_pivot_translator.py del tests\test_pivot_translator.py 2>nul
if exist tests\test_pivot_stage2_guard.py del tests\test_pivot_stage2_guard.py 2>nul
if exist tests\test_glossary_sync.py del tests\test_glossary_sync.py 2>nul
if exist tests\test_glossary_suggestor.py del tests\test_glossary_suggestor.py 2>nul
if exist tests\test_performance_logger.py del tests\test_performance_logger.py 2>nul
if exist tests\test_ram_monitor.py del tests\test_ram_monitor.py 2>nul
if exist tests\test_container.py del tests\test_container.py 2>nul
if exist tests\test_regression.py del tests\test_regression.py 2>nul
if exist tests\test_prompt_patch.py del tests\test_prompt_patch.py 2>nul
echo   OK

echo.
echo === Cleanup complete. ===
echo.
set count=0
for %%f in (tests\test_*.py) do set /a count+=1
echo Remaining tests: %count%
echo To run: python -m pytest tests/ -v
