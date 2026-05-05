#!/usr/bin/env python3
"""
Web UI launcher for the novel translation pipeline.

Supports both Streamlit and Flask web interfaces.
Default is Flask, use --streamlit flag for Streamlit.
"""

import argparse
import os
import sys
import subprocess
import logging
from pathlib import Path
from typing import Optional

# Constants
LOG_DIR = "logs"
UI_DIR = "ui"


def launch_flask_ui(args: Optional[argparse.Namespace] = None) -> int:
    """Launch the Flask web UI.
    
    Args:
        args: Command line arguments (optional)
        
    Returns:
        Exit code from Flask process
    """
    logger = logging.getLogger(__name__)
    
    # Ensure log directory exists
    os.makedirs(LOG_DIR, exist_ok=True)
    
    # Find the Flask app
    flask_app_path = Path(__file__).parent / "flask_app.py"
    if not flask_app_path.exists():
        print("Error: Could not find Flask app at src/web/flask_app.py", file=sys.stderr)
        return 1
    
    # Get port from args or use default
    port = 5000
    if args and hasattr(args, 'port') and args.port:
        port = args.port
    
    # Get debug mode
    debug = False
    if args and hasattr(args, 'debug') and args.debug:
        debug = True
    
    logger.info(f"Launching Flask web UI on port {port}")
    print("\n" + "=" * 60)
    print("🌐 Launching Novel Translation Web UI (Flask)")
    print("=" * 60)
    print(f"\n  URL: http://localhost:{port}")
    print(f"  Debug: {debug}")
    print(f"  Log: {LOG_DIR}/web_server.log")
    print("\n  Press Ctrl+C to stop the server")
    print("=" * 60 + "\n")
    
    # Launch Flask app
    try:
        from src.web.flask_app import app
        app.run(host='0.0.0.0', port=port, debug=debug)
        return 0
    except ImportError as e:
        print(f"Error: Failed to import Flask app: {e}", file=sys.stderr)
        print("\nMake sure Flask is installed:", file=sys.stderr)
        print("  pip install flask", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n\nShutting down web UI...")
        return 0
    except Exception as e:
        logger.error(f"Failed to launch web UI: {e}")
        print(f"Error: Failed to launch web UI: {e}", file=sys.stderr)
        return 1


def launch_streamlit_ui(args: Optional[argparse.Namespace] = None) -> int:
    """Launch the Streamlit web UI.
    
    Args:
        args: Command line arguments (optional)
        
    Returns:
        Exit code from Streamlit process
    """
    logger = logging.getLogger(__name__)

    # Ensure log directory exists
    os.makedirs(LOG_DIR, exist_ok=True)

    # Find the UI entry point
    ui_entry = _find_ui_entry()
    if not ui_entry:
        print("Error: Could not find Streamlit UI entry point", file=sys.stderr)
        return 1

    # Build command
    cmd = [
        sys.executable, "-m", "streamlit", "run",
        str(ui_entry),
        "--server.port=8501",
        "--server.address=localhost",
        "--browser.gatherUsageStats=false",
    ]

    # Add any additional args
    if args and hasattr(args, 'config') and args.config:
        cmd.extend(["--", "--config", args.config])

    logger.info(f"Launching web UI: {' '.join(cmd)}")
    print("\n" + "=" * 60)
    print("🌐 Launching Novel Translation Web UI (Streamlit)")
    print("=" * 60)
    print("\n  URL: http://localhost:8501")
    print(f"  Log: {LOG_DIR}/web_server.log")
    print("\n  Press Ctrl+C to stop the server")
    print("=" * 60 + "\n")

    # Launch with logging
    log_file = Path(LOG_DIR) / "web_server.log"

    try:
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write(f"Web UI launched at {__import__('datetime').datetime.now().isoformat()}\n")
            f.write(f"Command: {' '.join(cmd)}\n")
            f.write("-" * 60 + "\n\n")
            f.flush()

            process = subprocess.Popen(
                cmd,
                stdout=f,
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )

            try:
                return process.wait()
            except KeyboardInterrupt:
                print("\n\nShutting down web UI...")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                return 0

    except Exception as e:
        logger.error(f"Failed to launch web UI: {e}")
        print(f"Error: Failed to launch web UI: {e}", file=sys.stderr)
        return 1


def _find_ui_entry() -> Optional[Path]:
    """Find the Streamlit UI entry point.
    
    Returns:
        Path to UI entry file or None if not found
    """
    # Check common locations
    possible_paths = [
        Path(UI_DIR) / "streamlit_app.py",
        Path(UI_DIR) / "app.py",
        Path("streamlit_app.py"),
        Path("app.py"),
    ]

    for path in possible_paths:
        if path.exists():
            return path

    # Search for any streamlit app
    ui_dir = Path(UI_DIR)
    if ui_dir.exists():
        for py_file in ui_dir.rglob("*.py"):
            # Check if it imports streamlit
            try:
                content = py_file.read_text(encoding='utf-8')
                if 'import streamlit' in content or 'from streamlit' in content:
                    return py_file
            except Exception:
                continue

    return None


def launch_web_ui(args: Optional[argparse.Namespace] = None) -> int:
    """Main entry point - launches Flask by default, Streamlit with --streamlit flag.
    
    Args:
        args: Command line arguments (optional)
        
    Returns:
        Exit code from web UI process
    """
    # Check if Streamlit is explicitly requested
    if args and hasattr(args, 'streamlit') and args.streamlit:
        return launch_streamlit_ui(args)
    else:
        # Default to Flask
        return launch_flask_ui(args)


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser for web UI launcher."""
    parser = argparse.ArgumentParser(
        description="Launch Novel Translation Web UI",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--streamlit',
        action='store_true',
        help='Use Streamlit instead of Flask'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=5000,
        help='Port for Flask server (default: 5000)'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable Flask debug mode'
    )
    parser.add_argument(
        '--config',
        type=str,
        help='Config file path (Streamlit only)'
    )
    return parser


if __name__ == '__main__':
    parser = create_parser()
    args = parser.parse_args()
    sys.exit(launch_web_ui(args))