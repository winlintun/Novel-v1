import os
import json
import re
from flask import Flask, render_template, request, jsonify, send_from_directory
from pathlib import Path

app = Flask(__name__)

# Constants
BOOKS_DIR = Path("books")
PROGRESS_FILE = Path("working_data/progress.json")

# Security: Valid filename/book_id pattern (Unicode word characters, dash, underscore, no spaces)
# Allows: English letters, numbers, Chinese characters, Japanese, etc.
# Blocks: Path separators, parent directory references, control characters
SAFE_NAME_PATTERN = re.compile(r'^[\w\-_.]+$')

def is_safe_path_name(name):
    """Validate path name to prevent path traversal attacks.
    
    Allows Unicode word characters (including Chinese, Japanese, etc.)
    while blocking path traversal attempts.
    """
    if not name or not isinstance(name, str):
        return False
    
    # Block path traversal attempts first
    if '..' in name or '/' in name or '\\' in name:
        return False
    
    # Block control characters and null bytes
    if any(ord(c) < 32 for c in name) or '\x00' in name:
        return False
    
    # Must match safe pattern (Unicode word chars, dash, underscore, dot)
    if not SAFE_NAME_PATTERN.match(name):
        return False
    
    # Must not start or end with spaces
    if name != name.strip():
        return False
    
    return True

def ensure_dirs():
    """Ensure necessary directories exist."""
    BOOKS_DIR.mkdir(parents=True, exist_ok=True)
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)

def load_progress():
    """Load reading progress from file."""
    if PROGRESS_FILE.exists():
        try:
            with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_progress(progress):
    """Save reading progress to file."""
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(progress, f, indent=2)

@app.route('/')
def index():
    """Book library view."""
    ensure_dirs()
    books = []
    progress = load_progress()
    
    for book_path in BOOKS_DIR.iterdir():
        if book_path.is_dir():
            metadata_path = book_path / "metadata.json"
            if metadata_path.exists():
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                    
                book_id = book_path.name
                book_progress = progress.get(book_id, {})
                
                books.append({
                    "id": book_id,
                    "title": metadata.get("title", book_id),
                    "author": metadata.get("author", "Unknown"),
                    "chapter_count": len(metadata.get("chapters", [])),
                    "last_chapter": book_progress.get("chapter_number", 0),
                    "last_chapter_title": book_progress.get("chapter_title", "Not started")
                })
    
    return render_template('index.html', books=books)

@app.route('/book/<book_id>')
def chapters(book_id):
    """Chapter list view."""
    # Security: Validate book_id to prevent path traversal
    if not is_safe_path_name(book_id):
        return "Invalid book ID", 400
    
    metadata_path = BOOKS_DIR / book_id / "metadata.json"
    if not metadata_path.exists():
        return "Book not found", 404
        
    with open(metadata_path, 'r', encoding='utf-8') as f:
        metadata = json.load(f)
    
    # Add book_id to metadata for template use
    metadata['id'] = book_id
    
    # Normalize chapter data - support both 'number' and 'chapter_num' keys
    for chapter in metadata.get("chapters", []):
        if "chapter_num" in chapter and "number" not in chapter:
            chapter["number"] = chapter["chapter_num"]
        elif "number" in chapter and "chapter_num" not in chapter:
            chapter["chapter_num"] = chapter["number"]
        
    progress = load_progress().get(book_id, {})
    
    return render_template('chapters.html', book=metadata, progress=progress)

@app.route('/book/<book_id>/chapter/<int:chapter_num>')
def reader(book_id, chapter_num):
    """Reader view."""
    # Security: Validate book_id to prevent path traversal
    if not is_safe_path_name(book_id):
        return "Invalid book ID", 400
    
    metadata_path = BOOKS_DIR / book_id / "metadata.json"
    if not metadata_path.exists():
        return "Book not found", 404
        
    with open(metadata_path, 'r', encoding='utf-8') as f:
        metadata = json.load(f)
    
    # Normalize chapter data - support both 'file' and 'filename' keys
    for chapter in metadata.get("chapters", []):
        if "file" in chapter and "filename" not in chapter:
            chapter["filename"] = chapter["file"]
        elif "filename" in chapter and "file" not in chapter:
            chapter["file"] = chapter["filename"]
        
        # Also normalize number/chapter_num
        if "chapter_num" in chapter and "number" not in chapter:
            chapter["number"] = chapter["chapter_num"]
        elif "number" in chapter and "chapter_num" not in chapter:
            chapter["chapter_num"] = chapter["number"]
        
    # Find the chapter
    chapter = next((c for c in metadata["chapters"] if c.get("number") == chapter_num or c.get("chapter_num") == chapter_num), None)
    if not chapter:
        return "Chapter not found", 404
        
    # Find next and prev chapters
    prev_chapter = next((c for c in metadata["chapters"] if c.get("number") == chapter_num - 1 or c.get("chapter_num") == chapter_num - 1), None)
    next_chapter = next((c for c in metadata["chapters"] if c.get("number") == chapter_num + 1 or c.get("chapter_num") == chapter_num + 1), None)
    
    return render_template('reader.html', 
                           book_id=book_id, 
                           book_title=metadata["title"],
                           chapter=chapter,
                           prev_chapter=prev_chapter,
                           next_chapter=next_chapter)

@app.route('/api/chapter_content/<book_id>/<filename>')
def get_chapter_content(book_id, filename):
    """Get chapter markdown content."""
    # Security: Validate book_id and filename to prevent path traversal
    if not is_safe_path_name(book_id):
        return "Invalid book ID", 400
    
    # Validate filename (alphanumeric, dash, underscore, dot for .md extension)
    if not filename or not isinstance(filename, str):
        return "Invalid filename", 400
    if '..' in filename or '/' in filename or '\\' in filename:
        return "Invalid filename", 400
    if not filename.endswith('.md'):
        return "Invalid file type", 400
    
    chapter_path = BOOKS_DIR / book_id / "chapters" / filename
    if not chapter_path.exists():
        return "Chapter file not found", 404
        
    with open(chapter_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    return content

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
    
    # Validate chapter_num is a positive integer
    try:
        chapter_num = int(chapter_num) if chapter_num else 0
        if chapter_num < 0:
            chapter_num = 0
    except (TypeError, ValueError):
        chapter_num = 0
    
    # Validate scroll_pos is a non-negative integer
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

if __name__ == '__main__':
    ensure_dirs()
    # Load config for port
    config_path = Path("config/config.json")
    port = 5000
    debug_mode = False  # Security: Never run debug=True in production
    
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                port = config.get("web_ui_port", 5000)
                # Only enable debug if explicitly set in config (not recommended for production)
                debug_mode = config.get("debug_mode", False)
        except Exception:
            pass
    
    print(f"Starting Reader App on http://localhost:{port}")
    # Security: debug=False by default to prevent code execution vulnerabilities
    app.run(debug=debug_mode, host='127.0.0.1', port=port)
