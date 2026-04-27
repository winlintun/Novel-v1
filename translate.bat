@echo off
REM translate.bat - One-click translation with auto cache cleaning
REM Usage: translate.bat --input data/input/novel/chapter_001.md
REM        translate.bat --novel "novel_name" --chapter 1

REM If no arguments provided, show help
if "%~1"=="" (
    echo ======================================================================  
    echo  📚 Novel Translation - One-Click Launcher
    echo ======================================================================  
    echo.
    echo Usage:
    echo   translate.bat --input path\to\file.md
    echo   translate.bat --novel "novel_name" --chapter 1
    echo   translate.bat --novel "novel_name" --all
    echo.
    echo This launcher automatically clears Python cache before each run
    echo to ensure you're always running the latest code.
    echo.
    echo For more options: py -m src.main --help
    echo.
    pause
    exit /b 0
)

REM Call the main run.bat with all arguments
call "%~dp0run.bat" %*
