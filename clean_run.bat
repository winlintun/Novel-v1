@echo off
REM ──────────────────────────────────────────────────────────────────────────────
REM clean_run.bat — Project cleanup script (Windows)
REM Removes: Python caches, test artifacts, old logs, temp/working data
REM Preserves: current translation logs, databases, glossaries, output files
REM ──────────────────────────────────────────────────────────────────────────────
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo === Novel Translation Project — Cleanup ===
echo.

REM ── 1. Python cache files ───────────────────────────────────────────────────
REM Scope to project source dirs only. Never recurse into env\.venv\venv — those
REM hold installed packages whose compiled .pyd/.so extensions must not be touched.
echo [1/4] Removing Python cache files...
for %%g in (src tests scripts) do (
    if exist "%%g\" (
        for /d /r "%%g" %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d" 2>nul
        del /s /q "%%g\*.pyc" 2>nul
        del /s /q "%%g\*.pyo" 2>nul
    )
)
if exist __pycache__ rd /s /q __pycache__ 2>nul
echo   OK

REM ── 2. Test / lint / coverage artifacts ─────────────────────────────────────
echo [2/4] Removing test artifacts...
if exist .pytest_cache\ rd /s /q .pytest_cache\ 2>nul
if exist .ruff_cache\ rd /s /q .ruff_cache\ 2>nul
if exist .mypy_cache\ rd /s /q .mypy_cache\ 2>nul
if exist htmlcov\ rd /s /q htmlcov\ 2>nul
if exist coverage.xml del coverage.xml 2>nul
if exist .coverage del .coverage 2>nul
echo   OK

REM ── 3. Old logs (keep last 3 report files) ─────────────────────────────────
echo [3/4] Cleaning old logs (preserving current translation logs)...
if exist logs\report\ (
    for /f "skip=3" %%f in ('dir /b /o-d logs\report\*.md 2^>nul') do del "logs\report\%%f" 2>nul
)
if exist logs\performance\ rd /s /q logs\performance\ 2>nul
if exist logs\*.tmp del /q logs\*.tmp 2>nul
if exist logs\report\benchmark_*.json del /q logs\report\benchmark_*.json 2>nul
echo   OK

REM ── 4. Working / temp data ──────────────────────────────────────────────────
echo [4/4] Removing working/temp data...
if exist data\working\ rd /s /q data\working\ 2>nul
if exist logs\temp\ rd /s /q logs\temp\ 2>nul
if exist data\training\rating_progress.json del data\training\rating_progress.json 2>nul
echo   OK

echo.
echo === Cleanup complete. ===
echo.
set count=0
for %%f in (tests\test_*.py) do set /a count+=1
echo Remaining tests: %count%
echo To run: python -m pytest tests/ -v
