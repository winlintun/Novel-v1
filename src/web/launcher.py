#!/usr/bin/env python3
"""Flask web UI launcher for the novel translation pipeline."""

import argparse
import os
import sys
import logging
from pathlib import Path
from typing import Optional

# Constants
LOG_DIR = "logs"
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
    
    # Get port from args or env var or use default
    port = 5000
    if args and hasattr(args, 'port') and args.port:
        port = args.port
    elif os.environ.get("NOVEL_TRANSLATE_PORT"):
        port = int(os.environ.get("NOVEL_TRANSLATE_PORT", 5000))
    
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
def launch_web_ui(args: Optional[argparse.Namespace] = None) -> int:
    """Main entry point for the Flask web UI.
    
    Args:
        args: Command line arguments (optional)
        
    Returns:
        Exit code from web UI process
    """
    # Keep honoring the existing env var used by src.main, but only Flask is supported.
    _ = os.environ.get("NOVEL_TRANSLATE_UI", "")
    return launch_flask_ui(args)


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser for web UI launcher."""
    parser = argparse.ArgumentParser(
        description="Launch Novel Translation Web UI",
        formatter_class=argparse.RawDescriptionHelpFormatter
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
        help='Config file path'
    )
    return parser


if __name__ == '__main__':
    parser = create_parser()
    args = parser.parse_args()
    sys.exit(launch_web_ui(args))
