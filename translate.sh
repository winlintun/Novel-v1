#!/bin/bash
#
# translate.sh - One-click translation with auto cache cleaning for Linux/Mac
# Usage: ./translate.sh --input path/to/file.md
#        ./translate.sh --novel "novel_name" --chapter 1
#

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# If no arguments provided, show help
if [ $# -eq 0 ]; then
    echo "======================================================================"
    echo "  📚 Novel Translation - One-Click Launcher (Linux/Mac)"
    echo "======================================================================"
    echo ""
    echo "Usage:"
    echo "  ./translate.sh --input path/to/file.md"
    echo "  ./translate.sh --novel \"novel_name\" --chapter 1"
    echo "  ./translate.sh --novel \"novel_name\" --all"
    echo ""
    echo "This launcher automatically clears Python cache before each run"
    echo "to ensure you're always running the latest code."
    echo ""
    echo "For more options: python3 -m src.main --help"
    echo ""
    read -p "Press Enter to continue..."
    exit 0
fi

# Make run.sh executable if it isn't
if [ ! -x "$SCRIPT_DIR/run.sh" ]; then
    chmod +x "$SCRIPT_DIR/run.sh"
fi

# Call the main run.sh with all arguments
exec "$SCRIPT_DIR/run.sh" "$@"
