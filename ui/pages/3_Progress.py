import streamlit as st
import os
from pathlib import Path
import time

st.set_page_config(page_title="Progress & Logs", page_icon="📊", layout="wide")

st.title("📊 Translation Progress & Logs")

log_dir = Path("logs/progress")
if not log_dir.exists():
    st.info("No logs found. Start a translation first.")
    st.stop()

log_files = sorted(list(log_dir.glob("*.md")), key=os.path.getmtime, reverse=True)

if not log_files:
    st.info("No log files found.")
    st.stop()

selected_log = st.selectbox("Select Log File", [f.name for f in log_files])

if selected_log:
    log_path = log_dir / selected_log
    
    with st.expander("📄 View Log Content", expanded=True):
        # Read file with auto-refresh simulation if it's the latest one
        with open(log_path, 'r', encoding='utf-8') as f:
            content = f.read()
        st.markdown(content)
        
    if st.button("🔄 Refresh"):
        st.rerun()
