#!/usr/bin/env python3
"""
Streamlit launcher with logging support.
Logs all output to logs/web_server.log
"""

import sys
import os
import subprocess
from pathlib import Path
from datetime import datetime

def launch_streamlit():
    """Launch Streamlit with logging to file."""
    
    # Ensure logs directory exists
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Log file path
    log_file = log_dir / "web_server.log"
    
    # Get the project root
    project_root = Path(__file__).parent.parent
    ui_script = project_root / "ui" / "streamlit_app.py"
    
    if not ui_script.exists():
        print(f"✗ Error: UI script not found at {ui_script}")
        return 1
    
    # Write startup info to log
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"\n{'='*60}\n")
        f.write(f"Streamlit Web Server Started: {datetime.now().isoformat()}\n")
        f.write(f"Project Root: {project_root}\n")
        f.write(f"UI Script: {ui_script}\n")
        f.write(f"Log File: {log_file}\n")
        f.write(f"{'='*60}\n\n")
    
    print(f"🚀 Launching Novel-v1 Web UI...")
    print(f"📋 Server logs: {log_file}")
    print(f"🌐 Local URL: http://localhost:8501")
    print(f"⏹️  Press Ctrl+C to stop\n")
    
    try:
        # Open log file for appending
        with open(log_file, "a", encoding="utf-8") as log_f:
            # Launch streamlit with output redirected to log file
            process = subprocess.Popen(
                [
                    sys.executable, "-m", "streamlit", "run", str(ui_script),
                    "--server.port=8501",
                    "--server.address=localhost",
                    "--browser.gatherUsageStats=false",
                    "--logger.level=info"
                ],
                cwd=project_root,
                stdout=log_f,
                stderr=subprocess.STDOUT,
                bufsize=1,
                universal_newlines=True
            )
            
            # Wait for process
            try:
                process.wait()
            except KeyboardInterrupt:
                print("\n⏹️  Stopping Web UI...")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                
                # Log shutdown
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(f"\n{'='*60}\n")
                    f.write(f"Streamlit Web Server Stopped: {datetime.now().isoformat()}\n")
                    f.write(f"{'='*60}\n\n")
                
                print("✅ Web UI stopped.")
                return 0
                
    except FileNotFoundError:
        print("✗ Error: Streamlit not found. Please install it:")
        print("   pip install streamlit")
        return 1
    except Exception as e:
        print(f"✗ Error launching Web UI: {e}")
        # Log error
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"\n[ERROR] {datetime.now().isoformat()}: {e}\n")
        return 1

if __name__ == "__main__":
    sys.exit(launch_streamlit())
