#!/usr/bin/env python3
"""
Flask Web UI for the novel translation pipeline.
Replaces Streamlit with a traditional Flask-based web interface.
"""

import os
import sys
import json
import yaml
import logging
from pathlib import Path
from datetime import datetime

from flask import Flask, render_template, request, jsonify, flash
from flask import send_from_directory

# Add project root to path
project_root = str(Path(__file__).parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import pipeline components (optional - for future use)
try:
    pass  # from src.config.loader import load_config
except ImportError as e:
    logging.warning(f"Could not import pipeline components: {e}")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'novel-translation-secret-key-2024')

# Configuration
app.config['UPLOAD_FOLDER'] = 'data/input'
app.config['OUTPUT_FOLDER'] = 'data/output'
app.config['GLOSSARY_PATH'] = 'data/glossary.json'
app.config['CONFIG_PATH'] = 'config/settings.yaml'


# ─────────────────────────────────────────────────────────────
# Helper Functions
# ─────────────────────────────────────────────────────────────

# Model recommendations based on AGENTS.md
MODEL_RECOMMENDATIONS = {
    # Myanmar translation models (EN→MM or CN→MM)
    "padauk-gemma:q8_0": {
        "temp": 0.2,
        "use_case": "EN→MM, CN→MM",
        "description": "Best Myanmar output (recommended)",
        "category": "myanmar"
    },
    "padauk-gemma:q4_0": {
        "temp": 0.2,
        "use_case": "EN→MM, CN→MM",
        "description": "Smaller version of padauk-gemma",
        "category": "myanmar"
    },
    "sailor2-20b:latest": {
        "temp": 0.35,
        "use_case": "EN→MM, CN→MM",
        "description": "Best Myanmar model - 20B parameters",
        "category": "myanmar"
    },
    "sailor2:8b": {
        "temp": 0.3,
        "use_case": "EN→MM, CN→MM",
        "description": "Smaller sailor model - 8B parameters",
        "category": "myanmar"
    },
    "burmese-gpt:7b": {
        "temp": 0.25,
        "use_case": "EN→MM, CN→MM",
        "description": "Burmese GPT - 7B parameters",
        "category": "myanmar"
    },
    "yxchia/seallms-v3-7b:Q4_K_M": {
        "temp": 0.25,
        "use_case": "EN→MM, CN→MM",
        "description": "SEAL LMS v3 - Myanmar language model",
        "category": "myanmar"
    },
    "translategemma:12b": {
        "temp": 0.3,
        "use_case": "EN→MM, CN→MM",
        "description": "TranslateGemma - 12B translation model",
        "category": "myanmar"
    },
    # CN→EN pivot models (Stage 1 only)
    "qwen2.5:14b": {
        "temp": 0.45,
        "use_case": "CN→EN (pivot Stage 1 only)",
        "description": "CN→EN pivot - NOT for Myanmar output",
        "category": "pivot"
    },
    "qwen2.5:7b": {
        "temp": 0.45,
        "use_case": "CN→EN (pivot Stage 1 only)",
        "description": "CN→EN pivot - NOT for Myanmar output",
        "category": "pivot"
    },
    "qwen2.5:7b-instruct": {
        "temp": 0.45,
        "use_case": "CN→EN (pivot Stage 1 only)",
        "description": "CN→EN pivot - NOT for Myanmar output",
        "category": "pivot"
    },
    "alibayram/hunyuan:7b": {
        "temp": 0.45,
        "use_case": "CN→EN (pivot Stage 1 only)",
        "description": "Good Chinese comprehension for CN→EN",
        "category": "pivot"
    },
    "qwen:7b": {
        "temp": 0.45,
        "use_case": "CN→EN (pivot Stage 1 only)",
        "description": "Outputs English only - validation only",
        "category": "pivot"
    },
    # Other models (not tested for Myanmar)
    "gemma:7b": {
        "temp": 0.3,
        "use_case": "General",
        "description": "Google Gemma - not tested for Myanmar",
        "category": "other"
    },
    "aya:8b": {
        "temp": 0.3,
        "use_case": "General",
        "description": "Cohere Aya - multilingual, not tested for Myanmar",
        "category": "other"
    },
    "kimi-k2.6:cloud": {
        "temp": 0.4,
        "use_case": "CN→EN (experimental)",
        "description": "Kimi Cloud - experimental CN support",
        "category": "pivot"
    },
}


def get_available_models() -> list:
    """Get list of available Ollama models with recommendations"""
    import subprocess
    
    available = []
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')[1:]  # Skip header
            for line in lines:
                if line.strip():
                    parts = line.split()
                    if parts:
                        model_name = parts[0]
                        # Check if we have recommendations for this model
                        if model_name in MODEL_RECOMMENDATIONS:
                            rec = MODEL_RECOMMENDATIONS[model_name]
                            available.append({
                                'name': model_name,
                                'temp': rec['temp'],
                                'use_case': rec['use_case'],
                                'description': rec['description'],
                                'category': rec['category']
                            })
                        else:
                            # Unknown model - add with default
                            available.append({
                                'name': model_name,
                                'temp': 0.3,
                                'use_case': "Unknown",
                                'description': "Not tested for translation",
                                'category': 'other'
                            })
    except Exception as e:
        logger.warning(f"Failed to get Ollama models: {e}")
    
    # Always add recommended models even if not installed (user can install)
    for model_name, rec in MODEL_RECOMMENDATIONS.items():
        if not any(m['name'] == model_name for m in available):
            available.append({
                'name': model_name,
                'temp': rec['temp'],
                'use_case': rec['use_case'],
                'description': rec['description'],
                'category': rec['category'],
                'installed': False  # Not installed
            })
    
    # Sort: installed first, then by category (myanmar, pivot, other)
    category_order = {'myanmar': 0, 'pivot': 1, 'other': 2}
    available.sort(key=lambda x: (x.get('installed', True), category_order.get(x.get('category', 3), 3)))
    
    return available

def get_config() -> dict:
    """Load configuration from settings.yaml"""
    config_path = Path(app.config['CONFIG_PATH'])
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning(f"Failed to load config: {e}")
    return {}


def get_novels() -> list:
    """Get list of available novels from input directory"""
    input_dir = Path(app.config['UPLOAD_FOLDER'])
    novels = []
    if input_dir.exists():
        for novel_dir in input_dir.iterdir():
            if novel_dir.is_dir():
                chapters = list(novel_dir.glob("*.md"))
                novels.append({
                    'name': novel_dir.name,
                    'chapter_count': len(chapters),
                    'path': str(novel_dir)
                })
    return novels


def get_translated_chapters(novel_name: str) -> list:
    """Get list of translated chapters for a novel"""
    output_dir = Path(app.config['OUTPUT_FOLDER']) / novel_name
    translated = []
    if output_dir.exists():
        for f in output_dir.glob("*.mm.md"):
            translated.append(f.name)
    return translated


def get_glossary() -> dict:
    """Load glossary data"""
    glossary_path = Path(app.config['GLOSSARY_PATH'])
    if glossary_path.exists():
        try:
            with open(glossary_path, 'r', encoding='utf-8-sig') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load glossary: {e}")
    return {'terms': [], 'total_terms': 0}


def save_glossary(glossary: dict) -> bool:
    """Save glossary data"""
    glossary_path = Path(app.config['GLOSSARY_PATH'])
    try:
        glossary_path.parent.mkdir(parents=True, exist_ok=True)
        with open(glossary_path, 'w', encoding='utf-8') as f:
            json.dump(glossary, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Failed to save glossary: {e}")
        return False


def get_recent_logs() -> list:
    """Get recent log files"""
    log_dir = Path("logs/progress")
    logs = []
    if log_dir.exists():
        for log_file in sorted(log_dir.glob("*.md"), key=lambda x: x.stat().st_mtime, reverse=True)[:5]:
            try:
                with open(log_file, 'r', encoding='utf-8-sig') as f:
                    logs.append({
                        'name': log_file.name,
                        'content': f.read()[:500]
                    })
            except Exception:
                pass
    return logs


# ─────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────

@app.route('/')
def index():
    """Dashboard/Home page"""
    novels = get_novels()
    glossary = get_glossary()
    
    total_novels = len(novels)
    total_chapters = sum(n['chapter_count'] for n in novels)
    translated = 0
    
    for novel in novels:
        translated += len(get_translated_chapters(novel['name']))
    
    progress_pct = int((translated / total_chapters) * 100) if total_chapters > 0 else 0
    
    return render_template('dashboard.html',
                         novels=novels,
                         total_novels=total_novels,
                         total_chapters=total_chapters,
                         translated=translated,
                         glossary_terms=len(glossary.get('terms', [])),
                         progress_pct=progress_pct,
                         recent_logs=get_recent_logs())


@app.route('/translate', methods=['GET', 'POST'])
def translate():
    """Translation page"""
    novels = get_novels()
    models = get_available_models()
    config = get_config()
    
    selected_novel = request.args.get('novel', '')
    start_chapter = int(request.args.get('chapter', 1))
    translate_all = request.args.get('all', 'false') == 'true'
    
    # Get available chapters for selected novel
    available_chapters = []
    if selected_novel:
        novel_dir = Path(app.config['UPLOAD_FOLDER']) / selected_novel
        if novel_dir.exists():
            chapters = sorted(novel_dir.glob("*.md"))
            for ch in chapters:
                chapter_num = int(ch.stem.split('_')[-1] or ch.stem)
                available_chapters.append(chapter_num)
    
    # Get translated chapters
    translated_chapters = get_translated_chapters(selected_novel) if selected_novel else []
    
    # Handle translation start
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'start_translation':
            novel = request.form.get('novel')
            chapter = int(request.form.get('chapter', 1))
            model = request.form.get('model')
            temperature = float(request.form.get('temperature', 0.2))
            mode = request.form.get('mode', 'single_stage')
            
            # Update config
            if config:
                if 'models' not in config:
                    config['models'] = {}
                config['models']['translator'] = model
                config['models']['editor'] = model
                if 'processing' not in config:
                    config['processing'] = {}
                config['processing']['temperature'] = temperature
                
                # Save updated config
                try:
                    with open(app.config['CONFIG_PATH'], 'w') as f:
                        yaml.dump(config, f)
                except Exception as e:
                    logger.error(f"Failed to save config: {e}")
            
            # Start translation in background
            import subprocess
            cmd = [sys.executable, '-m', 'src.main', '--novel', novel, '--chapter', str(chapter)]
            if mode == 'all':
                cmd.append('--all')
            
            try:
                subprocess.Popen(cmd, cwd=project_root)
                flash(f'Translation started for {novel} chapter {chapter}', 'success')
            except Exception as e:
                flash(f'Failed to start translation: {e}', 'error')
    
    return render_template('translate.html',
                         novels=novels,
                         models=models,
                         selected_novel=selected_novel,
                         start_chapter=start_chapter,
                         translate_all=translate_all,
                         available_chapters=available_chapters,
                         translated_chapters=translated_chapters,
                         current_model=config.get('models', {}).get('translator', 'padauk-gemma:q8_0'),
                         current_temp=config.get('processing', {}).get('temperature', 0.2))


@app.route('/progress')
def progress():
    """Progress monitoring page"""
    novels = get_novels()
    novel_stats = []
    
    for novel in novels:
        translated = get_translated_chapters(novel['name'])
        total = novel['chapter_count']
        pct = int((len(translated) / total) * 100) if total > 0 else 0
        
        novel_stats.append({
            'name': novel['name'],
            'total': total,
            'translated': len(translated),
            'percentage': pct,
            'chapters': sorted(translated)
        })
    
    return render_template('progress.html', novel_stats=novel_stats)


@app.route('/glossary', methods=['GET', 'POST'])
def glossary():
    """Glossary management page"""
    glossary = get_glossary()
    terms = glossary.get('terms', [])
    
    # Handle term operations
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add_term':
            source = request.form.get('source', '').strip()
            target = request.form.get('target', '').strip()
            category = request.form.get('category', 'general')
            
            if source and target:
                new_term = {
                    'source': source,
                    'target': target,
                    'category': category,
                    'verified': True,
                    'added_at': datetime.now().isoformat()
                }
                terms.append(new_term)
                glossary['terms'] = terms
                glossary['total_terms'] = len(terms)
                save_glossary(glossary)
                flash(f'Term "{source}" added successfully', 'success')
        
        elif action == 'delete_term':
            source = request.form.get('source', '')
            terms = [t for t in terms if t.get('source') != source]
            glossary['terms'] = terms
            glossary['total_terms'] = len(terms)
            save_glossary(glossary)
            flash(f'Term "{source}" deleted', 'success')
        
        elif action == 'verify_term':
            source = request.form.get('source', '')
            for term in terms:
                if term.get('source') == source:
                    term['verified'] = True
            glossary['terms'] = terms
            save_glossary(glossary)
            flash(f'Term "{source}" verified', 'success')
    
    # Filter by category
    category_filter = request.args.get('category', 'all')
    if category_filter != 'all':
        terms = [t for t in terms if t.get('category') == category_filter]
    
    categories = list(set(t.get('category', 'general') for t in get_glossary().get('terms', [])))
    
    return render_template('glossary.html',
                         terms=terms,
                         categories=categories,
                         category_filter=category_filter,
                         total_terms=len(terms))


@app.route('/settings', methods=['GET', 'POST'])
def settings():
    """Settings page"""
    config = get_config()
    models = get_available_models()
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'save_model':
            model = request.form.get('model')
            if 'models' not in config:
                config['models'] = {}
            config['models']['translator'] = model
            config['models']['editor'] = model
            
            with open(app.config['CONFIG_PATH'], 'w') as f:
                yaml.dump(config, f)
            flash('Model settings saved', 'success')
        
        elif action == 'save_processing':
            temperature = float(request.form.get('temperature', 0.2))
            max_tokens = int(request.form.get('max_tokens', 2048))
            repeat_penalty = float(request.form.get('repeat_penalty', 1.15))
            
            if 'processing' not in config:
                config['processing'] = {}
            config['processing']['temperature'] = temperature
            config['processing']['max_tokens'] = max_tokens
            config['processing']['repeat_penalty'] = repeat_penalty
            
            with open(app.config['CONFIG_PATH'], 'w') as f:
                yaml.dump(config, f)
            flash('Processing settings saved', 'success')
    
    return render_template('settings.html',
                         config=config,
                         models=models,
                         current_model=config.get('models', {}).get('translator', 'padauk-gemma:q8_0'),
                         current_temp=config.get('processing', {}).get('temperature', 0.2),
                         current_max_tokens=config.get('processing', {}).get('max_tokens', 2048),
                         current_repeat_penalty=config.get('processing', {}).get('repeat_penalty', 1.15))


@app.route('/reader')
def reader():
    """File reader page"""
    novels = get_novels()
    selected_novel = request.args.get('novel', '')
    
    files = []
    if selected_novel:
        output_dir = Path(app.config['OUTPUT_FOLDER']) / selected_novel
        if output_dir.exists():
            files = sorted(output_dir.glob("*.mm.md"), key=lambda x: x.stat().st_mtime, reverse=True)
    
    selected_file = request.args.get('file', '')
    content = ''
    if selected_file:
        try:
            with open(selected_file, 'r', encoding='utf-8-sig') as f:
                content = f.read()
        except Exception as e:
            content = f"Error reading file: {e}"
    
    return render_template('reader.html',
                         novels=novels,
                         selected_novel=selected_novel,
                         files=files,
                         selected_file=selected_file,
                         content=content)


@app.route('/api/novels')
def api_novels():
    """API endpoint for novels list"""
    return jsonify(get_novels())


@app.route('/api/glossary')
def api_glossary():
    """API endpoint for glossary"""
    return jsonify(get_glossary())


@app.route('/api/translate', methods=['POST'])
def api_translate():
    """API endpoint for translation"""
    data = request.json
    novel = data.get('novel')
    chapter = data.get('chapter')
    # model = data.get('model', 'padauk-gemma:q8_0')  # reserved for future use
    
    import subprocess
    cmd = [sys.executable, '-m', 'src.main', '--novel', novel, '--chapter', str(chapter)]
    
    try:
        subprocess.Popen(cmd, cwd=project_root)
        return jsonify({'status': 'started', 'novel': novel, 'chapter': chapter})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ─────────────────────────────────────────────────────────────
# Static Files
# ─────────────────────────────────────────────────────────────

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)


@app.route('/api/progress')
def api_progress():
    """API endpoint for real-time translation progress"""
    progress_file = Path("logs/progress_current.json")
    
    if progress_file.exists():
        try:
            with open(progress_file, 'r', encoding='utf-8') as f:
                return jsonify(json.load(f))
        except Exception:
            pass
    
    return jsonify({
        'status': 'idle',
        'message': 'No translation in progress'
    })


@app.route('/api/start-translation', methods=['POST'])
def api_start_translation():
    """Start translation and track progress"""
    data = request.json
    novel = data.get('novel')
    chapter = data.get('chapter')
    model = data.get('model', 'padauk-gemma:q8_0')
    translate_all = data.get('translate_all', False)
    
    # Create progress file
    progress_file = Path("logs/progress_current.json")
    progress_file.parent.mkdir(parents=True, exist_ok=True)
    
    progress_data = {
        'status': 'starting',
        'novel': novel,
        'chapter': chapter,
        'model': model,
        'translate_all': translate_all,
        'started_at': datetime.now().isoformat(),
        'current_chunk': 0,
        'total_chunks': 0,
        'message': f'Starting translation of {novel}...'
    }
    
    with open(progress_file, 'w', encoding='utf-8') as f:
        json.dump(progress_data, f)
    
    # Start translation in background
    import subprocess
    if translate_all:
        cmd = [sys.executable, '-m', 'src.main', '--novel', novel, '--all', '--model', model]
    else:
        cmd = [sys.executable, '-m', 'src.main', '--novel', novel, '--chapter', str(chapter), '--model', model]
    
    subprocess.Popen(cmd, cwd=project_root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    return jsonify({'status': 'started', 'progress': progress_data})


# ─────────────────────────────────────────────────────────────
# Main Entry Point
# ─────────────────────────────────────────────────────────────

def create_app():
    """Create and configure the Flask application"""
    return app


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    
    print("\n" + "=" * 60)
    print("🌐 Novel Translation Web UI (Flask)")
    print("=" * 60)
    print(f"\n  URL: http://localhost:{port}")
    print(f"  Debug: {debug}")
    print("\n  Press Ctrl+C to stop the server")
    print("=" * 60 + "\n")
    
    app.run(host='0.0.0.0', port=port, debug=debug)