import streamlit as st
import os
import subprocess
from pathlib import Path
from ui.components.sidebar import render_sidebar

st.set_page_config(page_title="Translate Novel", page_icon="📝", layout="wide")

selected_novel, model_option = render_sidebar()

st.title("📝 Translate Novel")

if selected_novel == "No novels found":
    st.warning("Please add novel folders to data/input/")
    st.stop()

st.info(f"**Current Novel:** {selected_novel}")

col1, col2 = st.columns(2)

with col1:
    st.subheader("⚙️ Translation Options")
    lang = st.radio("Source Language", ["Chinese", "English"], index=0)
    mode = st.radio("Translation Mode", ["Single Stage", "Two Stage (Pivot)"], index=0)
    
    start_ch = st.number_input("Start Chapter", min_value=1, value=1)
    end_ch = st.number_input("End Chapter (0 for all)", min_value=0, value=0)
    
    skip_refine = st.checkbox("Skip Refinement (Faster)", value=False)
    
    if st.button("🚀 Start Translation", type="primary"):
        st.session_state.running = True
        # Construct command
        cmd = ["python3", "-m", "src.main", "--novel", selected_novel]
        if end_ch == 0:
            cmd.append("--all")
        else:
            cmd.extend(["--chapter", str(start_ch)]) # Simplified for now
            
        if skip_refine:
            cmd.append("--skip-refinement")
            
        if lang == "English":
            cmd.extend(["--lang", "en"])
        else:
            cmd.extend(["--lang", "zh"])
            
        st.write(f"Running command: `{' '.join(cmd)}`")
        st.success("Translation process started in background. Check Progress page.")
        # In a real app, we'd run this as a background process
        # subprocess.Popen(cmd)

with col2:
    st.subheader("👁️ Preview")
    novel_dir = Path("data/input") / selected_novel
    if novel_dir.exists():
        files = sorted(list(novel_dir.glob("*.md")))
        if files:
            selected_file = st.selectbox("Select Chapter to Preview", [f.name for f in files])
            with open(novel_dir / selected_file, 'r', encoding='utf-8-sig') as f:
                content = f.read()[:2000]
            st.text_area("Source Content", content, height=400)
        else:
            st.write("No markdown files found in novel directory.")
