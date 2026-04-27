#!/bin/bash
#
# translate.sh - One-click translation with auto cache cleaning for Linux/Mac
# Usage: ./translate.sh [arguments]
#        ./translate.sh --input path/to/file.md
#        ./translate.sh --novel "novel_name" --chapter 1
#        ./translate.sh (cleans cache and shows help)
#

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Make run.sh executable if it isn't
if [ ! -x "$SCRIPT_DIR/run.sh" ]; then
    chmod +x "$SCRIPT_DIR/run.sh"
fi

# Call the main run.sh with all arguments (including zero arguments)
# This will clean cache even if no arguments provided
exec "$SCRIPT_DIR/run.sh" "$@"
