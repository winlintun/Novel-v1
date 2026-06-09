#!/usr/bin/env python3
"""
Glossary Review Flask App — standalone review UI for glossary terms.

All glossary data is read/written directly to the SQLite database.
No JSON files are used.

Run with:
    python -m glossary_app.app

Or:
    flask --app glossary_app.app run
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask
from glossary_app.routes import bp


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(Path(__file__).parent / "templates"),
        static_folder=str(Path(__file__).parent / "static"),
    )
    app.secret_key = "glossary-review-secret-2026"
    app.register_blueprint(bp)
    return app


if __name__ == "__main__":
    app = create_app()
    print("=" * 60)
    print("  Glossary Review App")
    print(f"  Open: http://127.0.0.1:5001")
    print("=" * 60)
    app.run(host="127.0.0.1", port=5001, debug=True)
