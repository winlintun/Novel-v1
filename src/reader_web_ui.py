#!/usr/bin/env python3
"""
Reader Web UI - Flask application for reading translated novels
Integrated with new project structure

Usage:
    python -m src.reader_web_ui
    python -m src.reader_web_ui --port 8080
"""

import os
import sys
import json
import re
import argparse
from flask import Flask, render_template, request, jsonify, send_from_directory
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.file_handler import FileHandler

app = Flask(__name__)

# Default paths (can be overridden by config)
BOOKS_DIR = Path("books")
OUTPUT_DIR = Path("data/output")
PROGRESS_FILE = Path("working_data/progress.json")
CONFIG_PATH = Path("config/settings.yaml")

# Security: Valid filename/book_id pattern
SAFE_NAME_PATTERN = re.compile(r'^[\w\-_.]+$')


def load_config():
    """Load configuration from YAML."""
    try:
        return FileHandler.read_yaml(str(CONFIG_PATH))
    except Exception:
        return {
            "paths": {
                "output_dir": "data/output",
                "books_dir": "books"
            },
            "web_ui": {
                "port": 5000,
                "host": "127.0.0.1"
            }
        }


def get_books_dir():
    """Get books directory from config or default."""
    config = load_config()
    books_dir = config.get("paths", {}).get("books_dir", "books")
    return Path(books_dir)


def get_output_dir():
    """Get output directory from config or default."""
    config = load_config()
    output_dir = config.get("paths", {}).get("output_dir", "data/output")
    return Path(output_dir)


def is_safe_path_name(name):
    """Validate path name to prevent path traversal attacks."""
    if not name or not isinstance(name, str):
        return False
    
    # Block path traversal attempts
    if '..' in name or '/' in name or '\\' in name:
        return False
    
    # Block control characters and null bytes
    if any(ord(c) < 32 for c in name) or '\x00' in name:
        return False
    
    # Must match safe pattern
    if not SAFE_NAME_PATTERN.match(name):
        return False
    
    # Must not start or end with spaces
    if name != name.strip():
        return False
    
    return True


def ensure_dirs():
    """Ensure necessary directories exist."""
    books_dir = get_books_dir()
    output_dir = get_output_dir()
    
    books_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)


def load_progress():
    """Load reading progress from file."""
    if PROGRESS_FILE.exists():
        try:
            with open(PROGRESS_FILE, 'r', encoding='utf-8-sig') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_progress(progress):
    """Save reading progress to file."""
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(progress, f, indent=2, ensure_ascii=False)


def discover_books():
    """Discover all available books in output directory."""
    books = []
    books_dir = get_books_dir()
    output_dir = get_output_dir()
    
    # Check both books/ and data/output/ directories
    search_dirs = [books_dir, output_dir]
    
    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
            
        for book_path in search_dir.iterdir():
            if not book_path.is_dir():
                continue
            
            book_id = book_path.name
            
            # Skip if already added
            if any(b['id'] == book_id for b in books):
                continue
            
            # Look for metadata
            metadata_path = book_path / "metadata.json"
            chapters_dir = book_path / "chapters"
            
            if metadata_path.exists():
                try:
                    with open(metadata_path, 'r', encoding='utf-8-sig') as f:
                        metadata = json.load(f)
                except Exception:
                    metadata = {}
            else:
                metadata = {}
            
            # Count chapters
            chapter_count = 0
            if chapters_dir.exists():
                chapter_count = len(list(chapters_dir.glob("*_mm.md")))
            
            books.append({
                "id": book_id,
                "title": metadata.get("title", book_id),
                "author": metadata.get("author", "Unknown"),
                "chapter_count": chapter_count or metadata.get("chapter_count", 0),
                "path": str(book_path)
            })
    
    return sorted(books, key=lambda x: x['title'])


def get_chapters_for_book(book_id):
    """Get list of chapters for a book."""
    books_dir = get_books_dir()
    output_dir = get_output_dir()
    
    # Search in both directories
    for base_dir in [books_dir, output_dir]:
        book_path = base_dir / book_id
        if not book_path.exists():
            continue
        
        chapters_dir = book_path / "chapters"
        if not chapters_dir.exists():
            continue
        
        chapters = []
        for chapter_file in sorted(chapters_dir.glob("*_mm.md")):
            # Extract chapter number from filename
            match = re.search(r'_(\d+)_mm\.md$', chapter_file.name)
            if match:
                chapter_num = int(match.group(1))
            else:
                chapter_num = 0
            
            # Read first line for title
            try:
                with open(chapter_file, 'r', encoding='utf-8-sig') as f:
                    first_line = f.readline().strip()
                    if first_line.startswith('#'):
                        title = first_line.lstrip('#').strip()
                    else:
                        title = f"Chapter {chapter_num}"
            except Exception:
                title = f"Chapter {chapter_num}"
            
            chapters.append({
                "number": chapter_num,
                "filename": chapter_file.name,
                "title": title,
                "path": str(chapter_file)
            })
        
        return sorted(chapters, key=lambda x: x['number'])
    
    return []


@app.route('/')
def index():
    """Book library view."""
    ensure_dirs()
    books = discover_books()
    progress = load_progress()
    
    # Add progress info to books
    for book in books:
        book_progress = progress.get(book['id'], {})
        book['last_chapter'] = book_progress.get('chapter_number', 0)
        book['last_chapter_title'] = book_progress.get('chapter_title', 'Not started')
    
    return render_template('index.html', books=books)


@app.route('/book/<book_id>')
def chapters(book_id):
    """Chapter list view."""
    # Security: Validate book_id
    if not is_safe_path_name(book_id):
        return "Invalid book ID", 400
    
    chapters_list = get_chapters_for_book(book_id)
    
    if not chapters_list:
        return "Book not found or no chapters available", 404
    
    # Build book metadata
    book = {
        'id': book_id,
        'title': book_id.replace('_', ' ').title(),
        'chapters': chapters_list
    }
    
    progress = load_progress().get(book_id, {})
    
    return render_template('chapters.html', book=book, progress=progress)


@app.route('/book/<book_id>/chapter/<int:chapter_num>')
def reader(book_id, chapter_num):
    """Reader view."""
    # Security: Validate book_id
    if not is_safe_path_name(book_id):
        return "Invalid book ID", 400
    
    chapters_list = get_chapters_for_book(book_id)
    
    if not chapters_list:
        return "Book not found", 404
    
    # Find the chapter
    chapter = next((c for c in chapters_list if c['number'] == chapter_num), None)
    if not chapter:
        return "Chapter not found", 404
    
    # Find next and prev chapters
    chapter_numbers = [c['number'] for c in chapters_list]
    prev_chapter = None
    next_chapter = None
    
    if chapter_num > min(chapter_numbers):
        prev_num = max(n for n in chapter_numbers if n < chapter_num)
        prev_chapter = next((c for c in chapters_list if c['number'] == prev_num), None)
    
    if chapter_num < max(chapter_numbers):
        next_num = min(n for n in chapter_numbers if n > chapter_num)
        next_chapter = next((c for c in chapters_list if c['number'] == next_num), None)
    
    return render_template('reader.html',
                           book_id=book_id,
                           book_title=book_id.replace('_', ' ').title(),
                           chapter=chapter,
                           prev_chapter=prev_chapter,
                           next_chapter=next_chapter)


@app.route('/api/chapter_content/<book_id>/<filename>')
def get_chapter_content(book_id, filename):
    """Get chapter markdown content."""
    # Security: Validate book_id and filename
    if not is_safe_path_name(book_id):
        return "Invalid book ID", 400
    
    if not filename or not isinstance(filename, str):
        return "Invalid filename", 400
    if '..' in filename or '/' in filename or '\\' in filename:
        return "Invalid filename", 400
    if not filename.endswith('.md'):
        return "Invalid file type", 400
    
    # Search in both directories
    books_dir = get_books_dir()
    output_dir = get_output_dir()
    
    for base_dir in [books_dir, output_dir]:
        chapter_path = base_dir / book_id / "chapters" / filename
        if chapter_path.exists():
            with open(chapter_path, 'r', encoding='utf-8-sig') as f:
                content = f.read()
            return content
    
    return "Chapter file not found", 404


@app.route('/api/save_progress', methods=['POST'])
def api_save_progress():
    """API to save reading progress."""
    data = request.json
    if not data or not isinstance(data, dict):
        return jsonify({"success": False, "error": "Invalid request data"}), 400
    
    book_id = data.get("book_id")
    chapter_num = data.get("chapter_number")
    chapter_title = data.get("chapter_title")
    scroll_pos = data.get("scroll_position", 0)
    
    # Security: Validate book_id
    if not book_id or not is_safe_path_name(book_id):
        return jsonify({"success": False, "error": "Invalid book_id"}), 400
    
    # Validate chapter_num
    try:
        chapter_num = int(chapter_num) if chapter_num else 0
        if chapter_num < 0:
            chapter_num = 0
    except (TypeError, ValueError):
        chapter_num = 0
    
    # Validate scroll_pos
    try:
        scroll_pos = int(scroll_pos) if scroll_pos else 0
        if scroll_pos < 0:
            scroll_pos = 0
    except (TypeError, ValueError):
        scroll_pos = 0
    
    progress = load_progress()
    progress[book_id] = {
        "chapter_number": chapter_num,
        "chapter_title": chapter_title,
        "scroll_position": scroll_pos,
        "last_read": data.get("last_read")
    }
    save_progress(progress)
    
    return jsonify({"success": True})


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Novel Reader Web UI")
    parser.add_argument("--port", "-p", type=int, help="Port number (default: from config or 5000)")
    parser.add_argument("--host", "-H", help="Host address (default: 127.0.0.1)")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode (not recommended for production)")
    
    args = parser.parse_args()
    
    # Load config
    config = load_config()
    web_ui_config = config.get("web_ui", {})
    
    # Determine settings
    port = args.port or web_ui_config.get("port", 5000)
    host = args.host or web_ui_config.get("host", "127.0.0.1")
    debug = args.debug or web_ui_config.get("debug_mode", False)
    
    # Ensure directories exist
    ensure_dirs()
    
    print("=" * 60)
    print("Novel Reader Web UI")
    print("=" * 60)
    print(f"URL: http://{host}:{port}")
    print(f"Books directory: {get_books_dir()}")
    print(f"Output directory: {get_output_dir()}")
    print("=" * 60)
    print("Press Ctrl+C to stop")
    print()
    
    # Run app
    try:
        app.run(debug=debug, host=host, port=port)
    except KeyboardInterrupt:
        print("\n\nShutting down...")
        sys.exit(0)


if __name__ == '__main__':
    main()
