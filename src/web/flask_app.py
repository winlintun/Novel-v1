#!/usr/bin/env python3
"""
Flask Web UI for the novel translation pipeline.
Replaces Streamlit with a traditional Flask-based web interface.
"""

import os
import sys
import json
import yaml
import time
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


def save_config(config: dict) -> bool:
    """Persist settings.yaml through the shared file handler."""
    try:
        from src.utils.file_handler import FileHandler
        FileHandler.write_text(
            app.config['CONFIG_PATH'],
            yaml.safe_dump(config, allow_unicode=True, sort_keys=False),
        )
        return True
    except Exception as e:
        logger.error(f"Failed to save config: {e}")
        return False


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
    """Load glossary data from SQLite database"""
    try:
        from src.db.connection import DatabaseConnection
        from src.db.repositories.glossary_repo import GlossaryRepository
        
        db = DatabaseConnection('data/novel_translation.db')
        glossary_repo = GlossaryRepository(db)
        
        # Get all terms from database (all novels)
        all_terms = []
        
        # Get approved terms (limit=1000 to get all)
        approved = glossary_repo.get_terms_by_novel('novel_wayfarer', status='approved', limit=1000)
        for t in approved:
            all_terms.append({
                'source': t['source_term'],
                'target': t['target_term'],
                'category': t['category'],
                'verified': True,
                'status': 'approved',
                'confidence': t.get('confidence', 0.0),
                'usage_count': t.get('usage_count', 0)
            })
        
        # Get pending terms (limit=1000 to get all)
        pending = glossary_repo.get_terms_by_novel('novel_wayfarer', status='pending', limit=1000)
        for t in pending:
            all_terms.append({
                'source': t['source_term'],
                'target': t['target_term'],
                'category': t['category'],
                'verified': False,
                'status': 'pending',
                'confidence': t.get('confidence', 0.0),
                'usage_count': t.get('usage_count', 0)
            })
        
        return {
            'terms': all_terms,
            'total_terms': len(all_terms),
            'approved_count': len(approved),
            'pending_count': len(pending)
        }
    except Exception as e:
        logger.warning(f"Failed to load glossary from database: {e}")
        # Fallback to JSON if database fails
        glossary_path = Path(app.config['GLOSSARY_PATH'])
        if glossary_path.exists():
            try:
                with open(glossary_path, 'r', encoding='utf-8-sig') as f:
                    return json.load(f)
            except Exception:
                pass
        return {'terms': [], 'total_terms': 0}


def save_glossary(glossary: dict) -> bool:
    """Save glossary data to SQLite database"""
    try:
        # Note: This function is called when adding terms via the web UI
        # The actual save happens when individual terms are added/updated
        # For now, we'll just return True since the database handles persistence
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
    translation_models = set()  # Track which models were used

    for novel in novels:
        translated_chapters = get_translated_chapters(novel['name'])
        translated += len(translated_chapters)

        # Load meta.json to get model info
        meta_path = Path(app.config['OUTPUT_FOLDER']) / novel['name'] / f"{novel['name']}.mm.meta.json"
        if meta_path.exists():
            try:
                with open(meta_path, 'r', encoding='utf-8-sig') as f:
                    meta = json.load(f)
                for ch_data in meta.get('chapters', {}).values():
                    if isinstance(ch_data, dict) and ch_data.get('model'):
                        translation_models.add(ch_data['model'])
            except Exception:
                pass

    progress_pct = int((translated / total_chapters) * 100) if total_chapters > 0 else 0

    # Get primary model (most recently used, or from config)
    primary_model = None
    if translation_models:
        primary_model = sorted(translation_models)[0]  # Pick first alphabetically
    else:
        config = get_config()
        primary_model = config.get('models', {}).get('translator', 'padauk-gemma:q8_0')

    return render_template('dashboard.html',
                         novels=novels,
                         total_novels=total_novels,
                         total_chapters=total_chapters,
                         translated=translated,
                         glossary_terms=len(glossary.get('terms', [])),
                         progress_pct=progress_pct,
                         recent_logs=get_recent_logs(),
                         translation_model=primary_model)


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
    chapter_list = []  # List of dicts with num and title
    if selected_novel:
        novel_dir = Path(app.config['UPLOAD_FOLDER']) / selected_novel
        if novel_dir.exists():
            chapters = sorted(novel_dir.glob("*.md"))
            for ch in chapters:
                chapter_num = int(ch.stem.split('_')[-1] or ch.stem)
                available_chapters.append(chapter_num)
                # Try to extract title from file or use default
                chapter_title = f"Chapter {chapter_num:03d}"
                try:
                    # Read first few lines to find title
                    content = ch.read_text(encoding='utf-8-sig', errors='ignore')
                    lines = content.strip().split('\n')
                    for line in lines[:5]:
                        line = line.strip()
                        if line.startswith('# '):
                            title = line[2:].strip()
                            if title and not title.startswith('Chapter'):
                                chapter_title = f"{chapter_num:03d}: {title[:40]}"
                            break
                except Exception:
                    pass
                chapter_list.append({'num': chapter_num, 'title': chapter_title})
    
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
                save_config(config)
            
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
                         chapter_list=chapter_list,
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
        
        try:
            from src.db.connection import DatabaseConnection
            from src.db.repositories.glossary_repo import GlossaryRepository
            
            db = DatabaseConnection('data/novel_translation.db')
            glossary_repo = GlossaryRepository(db)
            novel_id = 'novel_wayfarer'
            
            if action == 'add_term':
                source = request.form.get('source', '').strip()
                target = request.form.get('target', '').strip()
                category = request.form.get('category', 'general')
                
                if source and target:
                    glossary_repo.add_term(
                        novel_id=novel_id,
                        source_term=source,
                        target_term=target,
                        category=category,
                        status='approved'
                    )
                    flash(f'Term "{source}" added successfully', 'success')
            
            elif action == 'delete_term':
                source = request.form.get('source', '')
                term = glossary_repo.get_term_by_source(novel_id, source)
                if term:
                    glossary_repo.delete_term(term['id'])
                    flash(f'Term "{source}" deleted', 'success')
            
            elif action == 'verify_term':
                source = request.form.get('source', '')
                term = glossary_repo.get_term_by_source(novel_id, source)
                if term:
                    glossary_repo.update_term(term['id'], status='approved')
                    flash(f'Term "{source}" verified', 'success')
        except Exception as e:
            logger.error(f"Failed to perform glossary action: {e}")
            flash(f'Error: {str(e)}', 'error')
    
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

            if save_config(config):
                flash('Model settings saved', 'success')
            else:
                flash('Failed to save model settings', 'error')
        
        elif action == 'save_processing':
            temperature = float(request.form.get('temperature', 0.2))
            max_tokens = int(request.form.get('max_tokens', 2048))
            repeat_penalty = float(request.form.get('repeat_penalty', 1.15))
            
            if 'processing' not in config:
                config['processing'] = {}
            config['processing']['temperature'] = temperature
            config['processing']['max_tokens'] = max_tokens
            config['processing']['repeat_penalty'] = repeat_penalty

            if save_config(config):
                flash('Processing settings saved', 'success')
            else:
                flash('Failed to save processing settings', 'error')
        
        elif action == 'save_storage':
            storage_backend = request.form.get('storage_backend', 'sqlite')
            db_path = request.form.get('db_path', 'data/novel_translation.db')
            
            if 'storage' not in config:
                config['storage'] = {}
            config['storage']['backend'] = storage_backend
            config['storage']['db_path'] = db_path

            if save_config(config):
                flash(f'Storage settings saved (backend: {storage_backend})', 'success')
            else:
                flash('Failed to save storage settings', 'error')
    
    return render_template('settings.html',
                         config=config,
                         models=models,
                         current_model=config.get('models', {}).get('translator', 'padauk-gemma:q8_0'),
                         current_temp=config.get('processing', {}).get('temperature', 0.2),
                         current_max_tokens=config.get('processing', {}).get('max_tokens', 2048),
                         current_repeat_penalty=config.get('processing', {}).get('repeat_penalty', 1.15),
                         storage_backend=config.get('storage', {}).get('backend', 'sqlite'),
                         db_path=config.get('storage', {}).get('db_path', 'data/novel_translation.db'))


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
    chapter_meta = None

    if selected_file:
        try:
            with open(selected_file, 'r', encoding='utf-8-sig') as f:
                content = f.read()

            # Load chapter metadata from meta.json
            if selected_novel:
                meta_path = Path(app.config['OUTPUT_FOLDER']) / selected_novel / f"{selected_novel}.mm.meta.json"
                if meta_path.exists():
                    try:
                        with open(meta_path, 'r', encoding='utf-8-sig') as f:
                            meta = json.load(f)

                        # Extract chapter number from filename
                        ch_match = re.search(r'chapter[_\-]?(\d+)', Path(selected_file).name)
                        if ch_match:
                            ch_num = ch_match.group(1).lstrip('0') or '1'
                            chapter_meta = meta.get('chapters', {}).get(ch_num, {})
                    except Exception:
                        pass
        except Exception as e:
            content = f"Error reading file: {e}"

    return render_template('reader.html',
                         novels=novels,
                         selected_novel=selected_novel,
                         files=files,
                         selected_file=selected_file,
                         content=content,
                         chapter_meta=chapter_meta)


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
    from datetime import datetime

    progress_file = Path("logs/progress_current.json")

    if progress_file.exists():
        try:
            with open(progress_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            status = data.get('status', 'starting')
            
            # Calculate elapsed time
            started_at = data.get('started_at')
            if started_at:
                try:
                    start_time = datetime.fromisoformat(started_at)
                    elapsed_seconds = int((datetime.now() - start_time).total_seconds())
                    hours = elapsed_seconds // 3600
                    minutes = (elapsed_seconds % 3600) // 60
                    seconds = elapsed_seconds % 60
                    if hours > 0:
                        data['elapsed_time'] = f"{hours}h {minutes}m {seconds}s"
                    elif minutes > 0:
                        data['elapsed_time'] = f"{minutes}m {seconds}s"
                    else:
                        data['elapsed_time'] = f"{seconds}s"
                    data['elapsed_seconds'] = elapsed_seconds
                except:
                    data['elapsed_time'] = "calculating..."

            # If orchestrator already marked it completed/error, trust that
            if status in ('completed', 'error'):
                # Clean up progress file after 2 minutes so next idle poll is clean
                age = time.time() - progress_file.stat().st_mtime
                if age > 120:
                    progress_file.unlink(missing_ok=True)
                return jsonify(data)

            # Still in progress — fall back to file-age heuristic if chunk info missing
            novel = data.get('novel', '')
            if novel and not data.get('current_chunk'):
                output_dir = Path("data/output") / novel
                if output_dir.exists():
                    output_files = sorted(
                        output_dir.glob("*.mm.md"),
                        key=lambda x: x.stat().st_mtime,
                        reverse=True
                    )
                    if output_files:
                        age = time.time() - output_files[0].stat().st_mtime
                        if age > 90:
                            data['status'] = 'completed'
                            data['message'] = 'Translation completed!'

            return jsonify(data)
        except Exception as e:
            logger.warning(f"Progress check error: {e}")
            progress_file.unlink(missing_ok=True)

    return jsonify({
        'status': 'idle',
        'message': 'No translation in progress'
    })


@app.route('/api/start-translation', methods=['POST'])
def api_start_translation():
    """Start translation and track progress"""
    import subprocess
    
    data = request.json
    novel = data.get('novel')
    chapter = data.get('chapter')
    chapter_range = data.get('chapter_range')  # Format: "start-end" (e.g., "1-5")
    model = data.get('model', 'padauk-gemma:q8_0')
    translate_all = data.get('translate_all', False)
    temperature = float(data.get('temperature', 0.2))
    
    # Validate inputs
    if not novel:
        return jsonify({
            'status': 'error',
            'error': 'No novel specified'
        }), 400
    
    # Update and save config
    config = get_config()
    if not config:
        config = {}
    if 'models' not in config:
        config['models'] = {}
    if 'processing' not in config:
        config['processing'] = {}
    config['models']['translator'] = model
    config['models']['editor'] = model
    config['processing']['temperature'] = temperature
    
    logger.info(f"Saving config with model={model}, temperature={temperature}")
    
    if not save_config(config):
        logger.error("Failed to save configuration")
        return jsonify({
            'status': 'error',
            'error': 'Failed to save translation settings'
        }), 500
    
    # Create progress file
    progress_file = Path("logs/progress_current.json")
    try:
        progress_file.parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.error(f"Failed to create progress directory: {e}")
        return jsonify({
            'status': 'error',
            'error': f'Failed to create progress directory: {str(e)}'
        }), 500
    
    progress_data = {
        'status': 'starting',
        'novel': novel,
        'chapter': chapter,
        'chapter_range': chapter_range,
        'model': model,
        'temperature': temperature,
        'translate_all': translate_all,
        'started_at': datetime.now().isoformat(),
        'current_chunk': 0,
        'total_chunks': 0,
        'message': f'Starting translation of {novel}...'
    }
    
    try:
        with open(progress_file, 'w', encoding='utf-8') as f:
            json.dump(progress_data, f)
    except Exception as e:
        logger.error(f"Failed to write progress file: {e}")
        return jsonify({
            'status': 'error',
            'error': f'Failed to write progress file: {str(e)}'
        }), 500
    
    # Start translation in background
    if translate_all:
        cmd = [sys.executable, '-m', 'src.main', '--novel', novel, '--all']
    elif chapter_range:
        cmd = [sys.executable, '-m', 'src.main', '--novel', novel, '--chapter-range', chapter_range]
    else:
        cmd = [sys.executable, '-m', 'src.main', '--novel', novel, '--chapter', str(chapter)]
    
    logger.info(f"Starting translation with command: {' '.join(cmd)}")
    logger.info(f"Working directory: {project_root}")
    
    try:
        # Start the process and capture initial output for error detection
        log_file = Path("logs/translation_webui.log")
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(log_file, 'a', encoding='utf-8') as log:
            log.write(f"\n{'='*60}\n")
            log.write(f"[{datetime.now().isoformat()}] Starting translation\n")
            if chapter_range:
                log.write(f"Novel: {novel}, Range: {chapter_range}, Model: {model}\n")
            else:
                log.write(f"Novel: {novel}, Chapter: {chapter}, Model: {model}\n")
            log.write(f"Command: {' '.join(cmd)}\n")
            log.write(f"Working dir: {project_root}\n")
            log.write(f"{'='*60}\n")
        
        # Start process with output redirected to log file
        with open(log_file, 'a', encoding='utf-8') as log:
            process = subprocess.Popen(
                cmd,
                cwd=project_root,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True  # Detach from parent process
            )
        
        logger.info(f"Translation process started with PID: {process.pid}")
        
        # Check if process started successfully (non-blocking)
        # Give it a moment to fail immediately if there's a config error
        import time
        time.sleep(0.5)
        
        return_code = process.poll()
        if return_code is not None and return_code != 0:
            # Process exited immediately with error
            error_msg = f"Translation process failed to start (exit code: {return_code})"
            logger.error(error_msg)
            
            # Update progress file with error
            progress_data['status'] = 'error'
            progress_data['message'] = error_msg
            with open(progress_file, 'w', encoding='utf-8') as f:
                json.dump(progress_data, f)
            
            return jsonify({
                'status': 'error',
                'error': error_msg,
                'details': 'Check logs/translation_webui.log for details'
            }), 500
        
        return jsonify({
            'status': 'started',
            'progress': progress_data,
            'pid': process.pid
        })
        
    except FileNotFoundError as e:
        logger.error(f"Python executable or module not found: {e}")
        return jsonify({
            'status': 'error',
            'error': f'Failed to start translation: Python or src.main not found. {str(e)}'
        }), 500
    except Exception as e:
        logger.exception("Failed to start translation process")
        return jsonify({
            'status': 'error',
            'error': f'Failed to start translation: {str(e)}'
        }), 500


@app.route('/api/progress/clear', methods=['POST'])
def api_progress_clear():
    """Clear stuck progress"""
    progress_file = Path("logs/progress_current.json")
    if progress_file.exists():
        progress_file.unlink(missing_ok=True)
    return jsonify({'status': 'cleared'})


@app.route('/api/translation/stop', methods=['POST'])
def api_stop_translation():
    """Signal running translation to stop gracefully."""
    try:
        # Create stop flag file
        stop_flag = Path("logs/translation_stop.flag")
        stop_flag.touch(exist_ok=True)
        
        # Update progress file to show stopping status
        progress_file = Path("logs/progress_current.json")
        if progress_file.exists():
            try:
                with open(progress_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                data['status'] = 'stopping'
                data['message'] = 'Stopping translation...'
                with open(progress_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f)
            except Exception:
                pass
        
        return jsonify({
            'status': 'success',
            'message': 'Stop signal sent to translation process'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Failed to send stop signal: {str(e)}'
        }), 500


@app.route('/api/debug/translation-log')
def api_translation_log():
    """Get the last lines of the translation log for debugging"""
    log_file = Path("logs/translation_webui.log")
    if not log_file.exists():
        return jsonify({'exists': False, 'content': 'No log file yet'})
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            # Get last 50 lines
            last_lines = lines[-50:] if len(lines) > 50 else lines
            return jsonify({
                'exists': True,
                'total_lines': len(lines),
                'content': ''.join(last_lines)
            })
    except Exception as e:
        return jsonify({'exists': True, 'error': str(e)}), 500


@app.route('/api/debug/health')
def api_health_check():
    """Health check endpoint to verify system status"""
    import subprocess
    
    checks = {
        'python_version': sys.version,
        'project_root': project_root,
        'input_dir_exists': Path(app.config['UPLOAD_FOLDER']).exists(),
        'output_dir_exists': Path(app.config['OUTPUT_FOLDER']).exists(),
        'logs_dir_exists': Path("logs").exists(),
        'config_exists': Path(app.config['CONFIG_PATH']).exists(),
    }
    
    # Check Ollama status
    try:
        result = subprocess.run(['ollama', 'list'], capture_output=True, text=True, timeout=5)
        checks['ollama_available'] = result.returncode == 0
        if result.returncode == 0:
            checks['ollama_models'] = len(result.stdout.strip().split('\n')) - 1  # minus header
    except Exception as e:
        checks['ollama_available'] = False
        checks['ollama_error'] = str(e)
    
    # Check current config
    try:
        config = get_config()
        checks['current_config'] = {
            'translator_model': config.get('models', {}).get('translator', 'not set'),
            'temperature': config.get('processing', {}).get('temperature', 'not set')
        }
    except Exception as e:
        checks['config_error'] = str(e)
    
    return jsonify(checks)


# ─────────────────────────────────────────────────────────────
# Fiction Editor Routes
# ─────────────────────────────────────────────────────────────

@app.route('/editor')
def editor():
    """Fiction-style editing page"""
    novels = get_novels()
    selected_novel = request.args.get('novel', '')
    selected_file = request.args.get('file', '')

    files = []
    if selected_novel:
        output_dir = Path(app.config['OUTPUT_FOLDER']) / selected_novel
        if output_dir.exists():
            files = sorted(output_dir.glob("*.mm.md"), key=lambda x: x.name)

    paragraphs = []
    raw_content = ''
    if selected_file:
        try:
            with open(selected_file, 'r', encoding='utf-8-sig') as f:
                raw_content = f.read()
            paragraphs = [p for p in raw_content.split('\n\n') if p.strip()]
        except Exception as e:
            flash(f'Error reading file: {e}', 'error')

    return render_template(
        'editor.html',
        novels=novels,
        files=files,
        selected_novel=selected_novel,
        selected_file=selected_file,
        paragraphs=paragraphs,
    )


@app.route('/api/editor/rewrite', methods=['POST'])
def api_editor_rewrite():
    """Rewrite a paragraph with a tone preset or custom instruction."""
    data = request.json or {}
    text = data.get('text', '').strip()
    tone = data.get('tone', 'humanize')
    custom_instruction = data.get('custom_instruction', '')

    if not text:
        return jsonify({'error': 'No text provided'}), 400

    valid_tones = {'humanize', 'dramatic', 'casual', 'literary', 'action', 'romantic', 'custom'}
    if tone not in valid_tones:
        tone = 'humanize'

    try:
        from src.agents.fiction_editor import FictionEditor
        config = get_config()
        editor_agent = FictionEditor(config=config)
        result = editor_agent.rewrite(text, tone=tone, custom_instruction=custom_instruction)
        return jsonify({'result': result, 'tone': tone})
    except Exception as e:
        logger.error(f"Editor rewrite error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/editor/chapter', methods=['GET'])
def api_editor_chapter():
    """Load a chapter file and return its paragraphs."""
    file_path = request.args.get('file', '')
    if not file_path:
        return jsonify({'error': 'No file specified'}), 400

    try:
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            content = f.read()
        paragraphs = [p for p in content.split('\n\n') if p.strip()]
        return jsonify({'paragraphs': paragraphs, 'file': file_path})
    except FileNotFoundError:
        return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/editor/format', methods=['POST'])
def api_editor_format():
    """Format a chapter's text and return the cleaned version with a change report."""
    data = request.json or {}
    file_path = data.get('file', '')
    text = data.get('text', '')
    options = data.get('options', None)

    # Accept either raw text or file path
    if not text and file_path:
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                text = f.read()
        except FileNotFoundError:
            return jsonify({'error': 'File not found'}), 404
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    if not text:
        return jsonify({'error': 'No text or file provided'}), 400

    try:
        from src.utils.formatter import format_chapter
        report = format_chapter(text, options)
        return jsonify(report.as_dict())
    except Exception as e:
        logger.error(f"Format error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/editor/format-save', methods=['POST'])
def api_editor_format_save():
    """Format a file in-place and save it (with backup)."""
    data = request.json or {}
    file_path = data.get('file', '')
    options = data.get('options', None)

    if not file_path:
        return jsonify({'error': 'No file specified'}), 400

    try:
        from src.utils.formatter import format_file
        report = format_file(file_path, backup=True, options=options)
        result = report.as_dict()
        result['file'] = file_path
        return jsonify(result)
    except FileNotFoundError:
        return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        logger.error(f"Format-save error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/editor/format-batch', methods=['POST'])
def api_editor_format_batch():
    """Format all .mm.md files for a novel and return per-file results."""
    data = request.json or {}
    novel = data.get('novel', '')
    options = data.get('options', None)

    if not novel:
        return jsonify({'error': 'No novel specified'}), 400

    output_dir = Path(app.config['OUTPUT_FOLDER']) / novel
    if not output_dir.exists():
        return jsonify({'error': f'No output directory for novel: {novel}'}), 404

    try:
        from src.utils.formatter import format_novel
        results = format_novel(output_dir, backup=True, options=options)
        total_changes = sum(r['total_changes'] for r in results)
        files_changed = sum(1 for r in results if r['changed'])
        return jsonify({
            'novel': novel,
            'files_processed': len(results),
            'files_changed': files_changed,
            'total_changes': total_changes,
            'results': results,
        })
    except Exception as e:
        logger.error(f"Batch format error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/cleanup')
def cleanup():
    """Batch formatting / cleanup page"""
    novels = get_novels()
    selected_novel = request.args.get('novel', '')

    files = []
    if selected_novel:
        output_dir = Path(app.config['OUTPUT_FOLDER']) / selected_novel
        if output_dir.exists():
            files = sorted(output_dir.glob("*.mm.md"), key=lambda x: x.name)

    return render_template(
        'cleanup.html',
        novels=novels,
        selected_novel=selected_novel,
        files=files,
    )


@app.route('/api/editor/save', methods=['POST'])
def api_editor_save():
    """Save edited chapter back to disk."""
    data = request.json or {}
    file_path = data.get('file', '')
    paragraphs = data.get('paragraphs', [])

    if not file_path:
        return jsonify({'error': 'No file specified'}), 400
    if not paragraphs:
        return jsonify({'error': 'No content to save'}), 400

    try:
        content = '\n\n'.join(paragraphs)
        # Write a backup first
        backup_path = Path(file_path).with_suffix('.bak.md')
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                original = f.read()
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(original)
        except Exception:
            pass  # backup is best-effort

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return jsonify({'status': 'saved', 'file': file_path, 'paragraphs': len(paragraphs)})
    except Exception as e:
        logger.error(f"Editor save error: {e}")
        return jsonify({'error': str(e)}), 500


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
