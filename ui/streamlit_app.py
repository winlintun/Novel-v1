#!/usr/bin/env python3
"""
Web UI for Novel Translation Project using Streamlit.
Provides user-friendly interface for translating novels.
"""

import streamlit as st
import os
import yaml
from pathlib import Path

st.set_page_config(
    page_title="Novel Translation",
    page_icon="📖",
    layout="wide"
)

st.title("📖 Novel Translation System")
st.markdown("Chinese to Myanmar Wuxia/Xianxia Novel Translator")

# Sidebar - Configuration
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # Model selection
    model_option = st.selectbox(
        "Translation Model",
        ["padauk-gemma:q8_0", "qwen2.5:14b", "qwen:7b"],
        index=0
    )
    
    # Translation mode
    trans_mode = st.radio(
        "Translation Mode",
        ["Single Stage (EN→MM)", "Two Stage (CN→EN→MM)"],
        index=0
    )
    
    # Skip refinement
    skip_refine = st.checkbox("Skip Refinement (Faster)", value=False)
    
    st.divider()
    
    # Novel selection
    input_dir = "data/input"
    if os.path.exists(input_dir):
        novels = [d for d in os.listdir(input_dir) if os.path.isdir(os.path.join(input_dir, d))]
    else:
        novels = []
    
    selected_novel = st.selectbox("Select Novel", novels if novels else ["No novels found"])
    
    # Chapter range
    if novels:
        chapters = list(range(1, 21))  # Default 1-20
        start_ch, end_ch = st.select_slider(
            "Chapter Range",
            options=chapters,
            value=(1, 5)
        )
    
    st.divider()
    
    # Translate button
    if st.button("🚀 Start Translation", type="primary"):
        st.session_state.translating = True

# Main area - Tabs
tab1, tab2, tab3 = st.tabs(["📝 Translate", "📚 Glossary", "📊 Progress"])

with tab1:
    st.header("Translation")
    
    # Show current novel/chapter info
    if selected_novel and selected_novel != "No novels found":
        st.info(f"**Novel:** {selected_novel} | **Chapters:** {start_ch} - {end_ch}")
        st.info(f"**Mode:** {trans_mode} | **Model:** {model_option}")
        
        # Show input file info
        novel_dir = os.path.join(input_dir, selected_novel)
        if os.path.exists(novel_dir):
            chapter_files = [f for f in os.listdir(novel_dir) if f.endswith('.md')]
            st.write(f"Available chapters: {len(chapter_files)}")
            
            # Preview first chapter
            if chapter_files:
                with st.expander("Preview First Chapter"):
                    first_file = sorted(chapter_files)[0]
                    with open(os.path.join(novel_dir, first_file), 'r', encoding='utf-8-sig') as f:
                        content = f.read()[:1000]
                    st.text(content)
    else:
        st.warning("Please add novel files to data/input/ directory")

with tab2:
    st.header("Glossary Management")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Approved Terms")
        if os.path.exists("data/glossary.json"):
            with open("data/glossary.json", 'r', encoding='utf-8-sig') as f:
                import json
                glossary = json.load(f)
                st.write(f"Total terms: {len(glossary.get('terms', []))}")
                st.json(glossary.get('terms', [])[:5])
        else:
            st.info("No glossary yet")
    
    with col2:
        st.subheader("Pending Terms")
        if os.path.exists("data/glossary_pending.json"):
            with open("data/glossary_pending.json", 'r', encoding='utf-8-sig') as f:
                import json
                pending = json.load(f)
                st.write(f"Pending: {len(pending.get('pending_terms', []))}")
                st.json(pending.get('pending_terms', [])[:5])
        else:
            st.info("No pending terms")

with tab3:
    st.header("Progress")
    
    # Show recent translation logs
    log_dir = "logs/progress"
    if os.path.exists(log_dir):
        log_files = sorted(Path(log_dir).glob("*.md"), key=os.path.getmtime, reverse=True)[:5]
        
        for log_file in log_files:
            with st.expander(f"📄 {log_file.name}"):
                with open(log_file, 'r', encoding='utf-8') as f:
                    content = f.read()[:2000]
                st.text(content)
    else:
        st.info("No progress logs yet")

# Status messages
if 'translating' in st.session_state and st.session_state.translating:
    st.success("Translation started! Check logs for progress.")
    st.session_state.translating = False

# Footer
st.divider()
st.markdown("""
---
**Novel Translation Project** | Powered by Ollama + Streamlit
""")