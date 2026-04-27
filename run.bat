@echo off
REM Auto-clean and run translation for Windows
REM This script clears Python cache and old logs before running to ensure fresh code

cls
echo ======================================================================  
echo  🧹 Novel Translation - Auto Cache Cleaner & Launcher
echo ======================================================================  
echo.

REM Check if Python is available
where py >nul 2>&1
if errorlevel 1 (
    echo ❌ ERROR: Python not found!
    echo Please install Python or add it to your PATH
    pause
    exit /b 1
)

echo Step 1: Cleaning Python cache...
echo ----------------------------------------------------------------------

REM Remove all __pycache__ directories
set "DIRS_REMOVED=0"
for /d /r . %%d in (__pycache__) do (
    if exist "%%d" (
        rd /s /q "%%d" 2>nul
        set /a DIRS_REMOVED+=1
    )
)

REM Remove all .pyc and .pyo files
set "FILES_REMOVED=0"
for /r . %%f in (*.pyc) do (
    del /q "%%f" 2>nul
    set /a FILES_REMOVED+=1
)
for /r . %%f in (*.pyo) do (
    del /q "%%f" 2>nul
    set /a FILES_REMOVED+=1
)

echo  Directories removed: %DIRS_REMOVED%
echo  Files removed: %FILES_REMOVED%
echo  ✅ Cache cleaned!
echo.

echo Step 2: Cleaning old log files...
echo ----------------------------------------------------------------------

set "LOGS_REMOVED=0"

REM Keep only the last 5 translation log files (sorted by date)
if exist "logs\translation_*.log" (
    REM Count total translation logs
    for /f %%a in ('dir /b /o-d logs\translation_*.log 2^>nul ^| find /c /v ""') do set "TOTAL_LOGS=%%a"
    
    REM Remove all but the 5 most recent
    if %TOTAL_LOGS% gtr 5 (
        for /f "skip=5 eol=: delims=" %%F in ('dir /b /o-d logs\translation_*.log 2^>nul') do (
            del /q "logs\%%F" 2>nul
            set /a LOGS_REMOVED+=1
        )
    )
)

REM Keep only the last 10 progress log files
if exist "logs\progress\progress_*.md" (
    for /f %%a in ('dir /b /o-d logs\progress\progress_*.md 2^>nul ^| find /c /v ""') do set "TOTAL_PROGRESS=%%a"
    
    if %TOTAL_PROGRESS% gtr 10 (
        for /f "skip=10 eol=: delims=" %%F in ('dir /b /o-d logs\progress\progress_*.md 2^>nul') do (
            del /q "logs\progress\%%F" 2>nul
            set /a LOGS_REMOVED+=1
        )
    )
)

REM Note: web_server.log is preserved (not touched)

echo  Old log files removed: %LOGS_REMOVED%
echo  ✅ Logs cleaned (kept: recent translation logs, web_server.log)
echo.

echo ======================================================================  
echo  🚀 Starting Translation
echo ======================================================================  
echo.

REM Run the actual command with all arguments passed through
py -m src.main --no-clean %*

REM Get the exit code
set "EXIT_CODE=%errorlevel%"

REM Pause if there was an error
if %EXIT_CODE% neq 0 (
    echo.
    echo ======================================================================  
    echo  ❌ Translation failed with error code %EXIT_CODE%
    echo ======================================================================  
    pause
) else (
    echo.
    echo ======================================================================  
    echo  ✅ Translation completed successfully
    echo ======================================================================  
)

exit /b %EXIT_CODE%
