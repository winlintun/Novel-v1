#!/usr/bin/env python3
"""Flask launcher with logging support."""

import sys
import os
from pathlib import Path
from datetime import datetime

from src.web.launcher import launch_flask_ui


def launch_ui():
    """Launch the Flask UI and append a server entry to the log."""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    # Log file: logs/web_server.log
    log_file = log_dir / "web_server.log"

    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"\n{'='*60}\n")
        f.write(f"Flask Web Server Started: {datetime.now().isoformat()}\n")
        f.write(f"Project Root: {Path(__file__).parent.parent}\n")
        f.write(f"Log File: {log_file}\n")
        f.write(f"{'='*60}\n\n")

    print("🚀 Launching Novel-v1 Flask Web UI...")
    print(f"📋 Server logs: {log_file}")
    print("🌐 Local URL: http://localhost:5000")
    print(f"⏹️  Press Ctrl+C to stop\n")

    try:
        return launch_flask_ui()
    except Exception as e:
        print(f"✗ Error launching Flask UI: {e}")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"\n[ERROR] {datetime.now().isoformat()}: {e}\n")
        return 1


if __name__ == "__main__":
    sys.exit(launch_ui())
