#!/usr/bin/env python3
"""
Web UI for Chinese-to-Burmese Novel Translation Project.

This Flask-SocketIO application provides a live web interface for:
- Monitoring translation progress
- Viewing streaming Burmese tokens in real-time
- Managing the novel translation queue
- Displaying readability check badges
- Controlling translation (Stop button for graceful shutdown)

Usage:
    python web_ui.py
    
The server starts on the port specified in config/config.json (default: 5000).
"""

import os
import sys
import json
import logging
import webbrowser
import threading
import time
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template_string, jsonify, request, Response
from flask_socketio import SocketIO, emit

# Setup logging
LOG_DIR = Path("working_data/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Create logger (web_ui runs as separate process, so basicConfig works)
logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(LOG_DIR / "web_ui.log", encoding='utf-8')
        ]
    )

# Flask app and SocketIO setup
app = Flask(__name__)
app.config['SECRET_KEY'] = 'novel-translation-secret-key'
socketio = SocketIO(app, cors_allowed_origins="*")

# Global state
translation_state = {
    'active': False,
    'current_novel': None,
    'current_chunk': 0,
    'total_chunks': 0,
    'percentage': 0,
    'eta': None,
    'cancel_requested': False,
    'novels_queue': [],
    'streaming_text': '',
    'readability_results': {}
}


def load_config():
    """Load configuration from config.json."""
    try:
        config_path = Path("config/config.json")
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error("Config file not found: config/config.json")
        return {'web_ui_port': 5000, 'auto_open_browser': True}
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        return {'web_ui_port': 5000, 'auto_open_browser': True}


def scan_novels():
    """Scan input_novels/ and check translation status for each."""
    try:
        input_dir = Path("input_novels")
        translated_dir = Path("translated_novels")
        checkpoint_dir = Path("working_data/checkpoints")
        
        novels = []
        
        if not input_dir.exists():
            logger.warning("input_novels/ directory not found")
            return novels
        
        for txt_file in sorted(input_dir.glob("*.txt")):
            novel_name = txt_file.stem
            
            # Check if already translated
            output_file = translated_dir / f"{novel_name}_burmese.md"
            checkpoint_file = checkpoint_dir / f"{novel_name}.json"
            
            status = 'new'
            progress = 0
            
            if output_file.exists():
                # Check if checkpoint shows completed
                if checkpoint_file.exists():
                    try:
                        with open(checkpoint_file, 'r', encoding='utf-8') as f:
                            checkpoint = json.load(f)
                            if checkpoint.get('status') == 'completed':
                                status = 'done'
                            else:
                                status = 'resuming'
                                progress = checkpoint.get('current_chunk', 0)
                    except Exception as e:
                        logger.error(f"Error reading checkpoint for {novel_name}: {e}")
                        status = 'new'
                else:
                    status = 'done'
            elif checkpoint_file.exists():
                try:
                    with open(checkpoint_file, 'r', encoding='utf-8') as f:
                        checkpoint = json.load(f)
                        if checkpoint.get('status') == 'completed':
                            status = 'done'
                        else:
                            status = 'resuming'
                            progress = checkpoint.get('current_chunk', 0)
                except Exception as e:
                    logger.error(f"Error reading checkpoint for {novel_name}: {e}")
            
            novels.append({
                'name': novel_name,
                'file': str(txt_file),
                'status': status,
                'progress': progress
            })
        
        return novels
        
    except Exception as e:
        logger.error(f"Error scanning novels: {e}")
        return []


# HTML template for the web UI
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Chinese-to-Burmese Novel Translator</title>
    <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        
        header {
            text-align: center;
            color: white;
            margin-bottom: 30px;
        }
        
        h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        
        .subtitle {
            opacity: 0.9;
            font-size: 1.1em;
        }
        
        .grid {
            display: grid;
            grid-template-columns: 1fr 2fr;
            gap: 20px;
        }
        
        @media (max-width: 900px) {
            .grid {
                grid-template-columns: 1fr;
            }
        }
        
        .panel {
            background: white;
            border-radius: 16px;
            padding: 24px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
        }
        
        .panel h2 {
            color: #333;
            margin-bottom: 20px;
            font-size: 1.3em;
            border-bottom: 3px solid #667eea;
            padding-bottom: 10px;
        }
        
        .progress-section {
            margin-bottom: 20px;
        }
        
        .progress-bar-container {
            background: #e0e0e0;
            border-radius: 10px;
            overflow: hidden;
            height: 30px;
            margin: 10px 0;
        }
        
        .progress-bar {
            background: linear-gradient(90deg, #667eea, #764ba2);
            height: 100%;
            width: 0%;
            transition: width 0.3s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
        }
        
        .stats {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
            margin-top: 15px;
        }
        
        .stat-box {
            background: #f5f5f5;
            padding: 12px;
            border-radius: 8px;
            text-align: center;
        }
        
        .stat-label {
            color: #666;
            font-size: 0.85em;
            margin-bottom: 5px;
        }
        
        .stat-value {
            color: #333;
            font-size: 1.4em;
            font-weight: bold;
        }
        
        .streaming-panel {
            background: #1e1e1e;
            border-radius: 12px;
            padding: 20px;
            color: #d4d4d4;
            font-family: 'Noto Sans Myanmar', 'Padauk', monospace;
            min-height: 300px;
            max-height: 500px;
            overflow-y: auto;
            white-space: pre-wrap;
            line-height: 1.8;
            font-size: 1.1em;
        }
        
        .streaming-panel:empty::before {
            content: "Translation will appear here...";
            color: #666;
            font-style: italic;
        }
        
        .queue-list {
            list-style: none;
        }
        
        .queue-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px;
            margin-bottom: 8px;
            background: #f5f5f5;
            border-radius: 8px;
            border-left: 4px solid #ccc;
        }
        
        .queue-item.pending {
            border-left-color: #999;
        }
        
        .queue-item.translating {
            border-left-color: #667eea;
            background: #e8edff;
        }
        
        .queue-item.resuming {
            border-left-color: #f39c12;
            background: #fef5e7;
        }
        
        .queue-item.done {
            border-left-color: #27ae60;
            background: #e8f8f5;
        }
        
        .queue-item.skipped {
            border-left-color: #95a5a6;
            opacity: 0.7;
        }
        
        .novel-name {
            font-weight: 500;
            color: #333;
        }
        
        .status-badge {
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.8em;
            font-weight: 500;
            text-transform: uppercase;
        }
        
        .badge-pending {
            background: #bdc3c7;
            color: white;
        }
        
        .badge-translating {
            background: #667eea;
            color: white;
            animation: pulse 2s infinite;
        }
        
        .badge-resuming {
            background: #f39c12;
            color: white;
        }
        
        .badge-done {
            background: #27ae60;
            color: white;
        }
        
        .badge-skipped {
            background: #95a5a6;
            color: white;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.7; }
        }
        
        .stop-button {
            background: #e74c3c;
            color: white;
            border: none;
            padding: 15px 30px;
            font-size: 1.1em;
            border-radius: 8px;
            cursor: pointer;
            width: 100%;
            margin-top: 15px;
            transition: background 0.2s;
        }
        
        .stop-button:hover {
            background: #c0392b;
        }
        
        .stop-button:disabled {
            background: #95a5a6;
            cursor: not-allowed;
        }
        
        .readability-indicator {
            display: flex;
            gap: 10px;
            margin-top: 15px;
            flex-wrap: wrap;
        }
        
        .readability-badge {
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: 500;
        }
        
        .badge-pass {
            background: #27ae60;
            color: white;
        }
        
        .badge-flagged {
            background: #f39c12;
            color: white;
        }
        
        .badge-checking {
            background: #3498db;
            color: white;
        }
        
        .info-message {
            padding: 12px;
            background: #e8edff;
            border-radius: 8px;
            margin-bottom: 15px;
            color: #667eea;
        }
        
        .error-message {
            padding: 12px;
            background: #fee;
            border-radius: 8px;
            margin-bottom: 15px;
            color: #c0392b;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Chinese-to-Burmese Novel Translator</h1>
            <p class="subtitle">Live Translation Dashboard</p>
        </header>
        
        <div class="grid">
            <div class="left-column">
                <div class="panel">
                    <h2>📊 Translation Progress</h2>
                    <div class="progress-section">
                        <div id="current-novel" class="info-message">No translation active</div>
                        
                        <div class="progress-bar-container">
                            <div id="progress-bar" class="progress-bar">0%</div>
                        </div>
                        
                        <div class="stats">
                            <div class="stat-box">
                                <div class="stat-label">Current Chunk</div>
                                <div id="stat-chunk" class="stat-value">-</div>
                            </div>
                            <div class="stat-box">
                                <div class="stat-label">Total Chunks</div>
                                <div id="stat-total" class="stat-value">-</div>
                            </div>
                            <div class="stat-box">
                                <div class="stat-label">ETA</div>
                                <div id="stat-eta" class="stat-value">-</div>
                            </div>
                            <div class="stat-box">
                                <div class="stat-label">Percentage</div>
                                <div id="stat-percentage" class="stat-value">0%</div>
                            </div>
                        </div>
                        
                        <div class="readability-indicator" id="readability-badges">
                            <span class="readability-badge badge-checking">Readability: Waiting...</span>
                        </div>
                    </div>
                    
                    <button id="stop-button" class="stop-button" disabled>
                        ⏹ Stop Translation
                    </button>
                </div>
                
                <div class="panel">
                    <h2>📚 Novel Queue</h2>
                    <ul id="queue-list" class="queue-list">
                        <li class="queue-item pending">
                            <span class="novel-name">Loading...</span>
                            <span class="status-badge badge-pending">Loading</span>
                        </li>
                    </ul>
                </div>
            </div>
            
            <div class="right-column">
                <div class="panel">
                    <h2>✨ Live Streaming Translation</h2>
                    <div id="streaming-panel" class="streaming-panel"></div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        // Connect to SocketIO server
        const socket = io();
        
        // DOM elements
        const progressBar = document.getElementById('progress-bar');
        const currentNovelDiv = document.getElementById('current-novel');
        const statChunk = document.getElementById('stat-chunk');
        const statTotal = document.getElementById('stat-total');
        const statEta = document.getElementById('stat-eta');
        const statPercentage = document.getElementById('stat-percentage');
        const streamingPanel = document.getElementById('streaming-panel');
        const queueList = document.getElementById('queue-list');
        const stopButton = document.getElementById('stop-button');
        const readabilityBadges = document.getElementById('readability-badges');
        
        // State
        let isTranslating = false;
        
        // Handle translation token
        socket.on('translation_token', (data) => {
            streamingPanel.textContent += data.token;
            streamingPanel.scrollTop = streamingPanel.scrollHeight;
        });
        
        // Handle progress update
        socket.on('progress_update', (data) => {
            const percentage = data.percentage || 0;
            progressBar.style.width = percentage + '%';
            progressBar.textContent = percentage.toFixed(1) + '%';
            
            statChunk.textContent = data.chunk || '-';
            statTotal.textContent = data.total || '-';
            statPercentage.textContent = percentage.toFixed(1) + '%';
            statEta.textContent = data.eta || '-';
            
            if (data.novel) {
                currentNovelDiv.textContent = `Translating: ${data.novel}`;
                isTranslating = true;
                stopButton.disabled = false;
            }
        });
        
        // Handle readability result
        socket.on('readability_result', (data) => {
            const badge = document.createElement('span');
            badge.className = 'readability-badge ' + (data.passed ? 'badge-pass' : 'badge-flagged');
            badge.textContent = `Chunk ${data.chunk}: ${data.passed ? 'PASS' : 'FLAGGED'}`;
            readabilityBadges.appendChild(badge);
            
            // Keep only last 5 badges
            while (readabilityBadges.children.length > 5) {
                readabilityBadges.removeChild(readabilityBadges.firstChild);
            }
        });
        
        // Handle queue update
        socket.on('queue_update', (data) => {
            updateQueue(data.novels);
        });
        
        // Handle chunk complete
        socket.on('chunk_complete', (data) => {
            streamingPanel.textContent += '\n\n--- Chunk ' + data.chunk + ' Complete ---\n\n';
        });
        
        // Handle translation complete
        socket.on('translation_complete', (data) => {
            currentNovelDiv.textContent = 'Translation complete: ' + data.novel;
            progressBar.style.width = '100%';
            progressBar.textContent = '100%';
            statPercentage.textContent = '100%';
            isTranslating = false;
            stopButton.disabled = true;
        });
        
        // Update queue display
        function updateQueue(novels) {
            queueList.innerHTML = '';
            
            novels.forEach(novel => {
                const li = document.createElement('li');
                li.className = 'queue-item ' + novel.status;
                
                const nameSpan = document.createElement('span');
                nameSpan.className = 'novel-name';
                nameSpan.textContent = novel.name;
                
                const badgeSpan = document.createElement('span');
                badgeSpan.className = 'status-badge badge-' + novel.status;
                
                let statusText = novel.status;
                if (novel.status === 'resuming' && novel.progress > 0) {
                    statusText = `resuming (${novel.progress})`;
                }
                badgeSpan.textContent = statusText;
                
                li.appendChild(nameSpan);
                li.appendChild(badgeSpan);
                queueList.appendChild(li);
            });
        }
        
        // Stop button handler
        stopButton.addEventListener('click', async () => {
            if (!isTranslating) return;
            
            if (confirm('Stop translation? Progress will be saved.')) {
                try {
                    const response = await fetch('/stop', { method: 'POST' });
                    const result = await response.json();
                    
                    if (result.success) {
                        currentNovelDiv.textContent = 'Translation stopped. Progress saved.';
                        stopButton.disabled = true;
                    }
                } catch (err) {
                    console.error('Error stopping translation:', err);
                }
            }
        });
        
        // Load initial queue
        async function loadQueue() {
            try {
                const response = await fetch('/api/queue');
                const data = await response.json();
                updateQueue(data.novels);
            } catch (err) {
                console.error('Error loading queue:', err);
            }
        }
        
        // Initial load
        loadQueue();
        
        // Refresh queue every 30 seconds
        setInterval(loadQueue, 30000);
    </script>
</body>
</html>
"""


@app.route('/')
def index():
    """Render the main web UI."""
    return render_template_string(HTML_TEMPLATE)


@app.route('/api/queue')
def get_queue():
    """API endpoint to get current novel queue."""
    try:
        novels = scan_novels()
        return jsonify({'novels': novels})
    except Exception as e:
        logger.error(f"Error getting queue: {e}")
        return jsonify({'novels': [], 'error': str(e)}), 500


@app.route('/stop', methods=['POST'])
def stop_translation():
    """Stop translation gracefully."""
    try:
        translation_state['cancel_requested'] = True
        logger.info("Stop requested via web UI")
        
        # Notify all clients
        socketio.emit('translation_stopped', {
            'message': 'Translation stop requested. Saving checkpoint...'
        })
        
        return jsonify({'success': True, 'message': 'Stop requested'})
    except Exception as e:
        logger.error(f"Error stopping translation: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/status')
def get_status():
    """API endpoint to get current translation status."""
    try:
        return jsonify({
            'active': translation_state['active'],
            'current_novel': translation_state['current_novel'],
            'current_chunk': translation_state['current_chunk'],
            'total_chunks': translation_state['total_chunks'],
            'percentage': translation_state['percentage'],
            'eta': translation_state['eta'],
            'cancel_requested': translation_state['cancel_requested']
        })
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        return jsonify({'error': str(e)}), 500


@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    logger.info(f"Client connected: {request.sid}")
    emit('connected', {'message': 'Connected to translation server'})
    
    # Send current state
    emit('queue_update', {'novels': scan_novels()})


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    logger.info(f"Client disconnected: {request.sid}")


def emit_progress(novel, chunk, total, percentage, eta=None):
    """Emit progress update to all connected clients."""
    try:
        translation_state['current_novel'] = novel
        translation_state['current_chunk'] = chunk
        translation_state['total_chunks'] = total
        translation_state['percentage'] = percentage
        translation_state['eta'] = eta
        
        socketio.emit('progress_update', {
            'novel': novel,
            'chunk': chunk,
            'total': total,
            'percentage': percentage,
            'eta': eta
        })
    except Exception as e:
        logger.error(f"Error emitting progress: {e}")


def emit_token(token, novel):
    """Emit translation token to all connected clients."""
    try:
        socketio.emit('translation_token', {
            'novel': novel,
            'token': token
        })
    except Exception as e:
        logger.error(f"Error emitting token: {e}")


def emit_readability_result(chunk, passed):
    """Emit readability check result."""
    try:
        socketio.emit('readability_result', {
            'chunk': chunk,
            'passed': passed
        })
    except Exception as e:
        logger.error(f"Error emitting readability result: {e}")


def emit_chunk_complete(chunk):
    """Emit chunk completion notification."""
    try:
        socketio.emit('chunk_complete', {
            'chunk': chunk
        })
    except Exception as e:
        logger.error(f"Error emitting chunk complete: {e}")


def emit_translation_complete(novel):
    """Emit translation completion notification."""
    try:
        socketio.emit('translation_complete', {
            'novel': novel
        })
    except Exception as e:
        logger.error(f"Error emitting translation complete: {e}")


def update_queue():
    """Broadcast queue update to all clients."""
    try:
        novels = scan_novels()
        socketio.emit('queue_update', {'novels': novels})
    except Exception as e:
        logger.error(f"Error updating queue: {e}")


def is_cancel_requested():
    """Check if translation cancellation was requested."""
    return translation_state['cancel_requested']


def clear_cancel_request():
    """Clear the cancellation request flag."""
    translation_state['cancel_requested'] = False


def open_browser(port):
    """Open browser after a short delay."""
    try:
        time.sleep(2)
        url = f"http://localhost:{port}"
        logger.info(f"Opening browser at {url}")
        webbrowser.open(url)
    except Exception as e:
        logger.error(f"Error opening browser: {e}")


def main():
    """Main entry point."""
    try:
        config = load_config()
        port = config.get('web_ui_port', 5000)
        auto_open = config.get('auto_open_browser', True)
        
        logger.info(f"Starting Web UI server on port {port}")
        
        # Open browser in background thread if enabled
        if auto_open:
            threading.Thread(target=open_browser, args=(port,), daemon=True).start()
        
        # Run the server
        socketio.run(app, host='0.0.0.0', port=port, debug=False)
        
    except Exception as e:
        logger.error(f"Error starting web UI: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
