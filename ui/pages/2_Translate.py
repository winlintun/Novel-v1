import streamlit as st
import os
import subprocess
import time
from pathlib import Path
from ui.components.sidebar import render_sidebar

st.set_page_config(page_title="Translate | ဘာသာပြန်", page_icon="📝", layout="wide")

settings = render_sidebar()

if settings["novel"] == "No novels found":
    st.warning("Please add novel folders to data/input/ | ကျေးဇူးပြု၍ data/input/ တွင် ဝတ္ထုဖိုင်တွဲများ ထည့်သွင်းပါ။")
    st.stop()

st.header(f"📚 {settings['novel']} | {settings['lang_source']} → Myanmar")

col_nav1, col_nav2 = st.columns([1, 3])
with col_nav1:
    st.metric("Current Chapter", f"{settings['start_ch']}")
with col_nav2:
    if st.button("⏹️ Stop Translation"):
        st.warning("Stop signal sent. | ရပ်တ်ဆိုင်းပါပါသည်။")
        st.session_state.running = False

st.divider()

col_src, col_tgt = st.columns(2)

with col_src:
    st.subheader("📄 Original Text | မူရင်း")
    novel_dir = Path("data/input") / settings["novel"]
    if novel_dir.exists():
        files = sorted(list(novel_dir.glob("*.md")))
        if files:
            selected_file = st.selectbox("Select Chapter", [f.name for f in files], key="src_select")
            if selected_file:
                with open(novel_dir / selected_file, 'r', encoding='utf-8-sig') as f:
                    src_content = f.read()
                st.text_area("Source", src_content, height=500, key="src_area", disabled=True)
    else:
        st.info("No source files found.")

with col_tgt:
    st.subheader("🇲🇲 Myanmar Translation")
    
    output_dir = Path("data/output") / settings["novel"]
    out_files = []
    if output_dir.exists():
        out_files = sorted(list(output_dir.glob("*.md")))
    
    selected_out = st.selectbox("Select Output Chapter", [f.name for f in out_files] if out_files else ["-- None --"], key="out_select")
    
    if selected_out and selected_out != "-- None --":
        with open(output_dir / selected_out, 'r', encoding='utf-8-sig') as f:
            tgt_content = f.read()
    else:
        tgt_content = ""
    
    # Highlight glossary terms (per need_fix.md 3.3)
    highlight_terms = st.checkbox("🔍 Highlight Glossary Terms", value=False)
    if highlight_terms:
        glossary_path = Path("data/glossary.json")
        if glossary_path.exists():
            import json
            with open(glossary_path, 'r', encoding='utf-8-sig') as f:
                g_data = json.load(f)
            terms = g_data.get("terms", [])
            highlighted = tgt_content
            for term in terms[:20]:
                target = term.get('target', '')
                if target and target in tgt_content:
                    highlighted = highlighted.replace(target, f"**{target}**")
            if highlighted != tgt_content:
                st.markdown("### 📚 Highlighted Terms")
                st.markdown(highlighted, unsafe_allow_html=True)
            else:
                st.info("No glossary terms found in this chapter.")
        else:
            st.info("No glossary found.")
    
    edited = st.text_area("Translation", tgt_content, height=500, key="tgt_area")
    
    col_save, col_add = st.columns(2)
    with col_save:
        if st.button("💾 Save Edit"):
            if selected_out and selected_out != "-- None --" and edited != tgt_content:
                with open(output_dir / selected_out, 'w', encoding='utf-8-sig') as f:
                    f.write(edited)
                st.success("Saved! | သိမ်းပါပါသည်။")
    with col_add:
        add_glossary = st.button("📚 Add to Glossary", use_container_width=True)

st.divider()

st.subheader("📊 Progress Tracking")

col_prog1, col_prog2, col_prog3 = st.columns([3, 1, 1])

with col_prog1:
    progress_bar = st.progress(0, text="Ready to translate")
with col_prog2:
    pct = st.metric("Progress", "0%")
with col_prog3:
    eta = st.metric("ETA", "--")

st.info("Status: Ready | အသင်းသင်း အသုံးရန် အသင့်ပါ။")

st.subheader("🔄 Translation Stages")
col_stage1, col_stage2, col_stage3, col_stage4 = st.columns(4)

with col_stage1:
    st.markdown("""
    <div style="text-align:center; padding:10px; background:#1f2937; border-radius:8px;">
    <span style="font-size:24px;">⚙️</span><br>
    <strong>Preprocess</strong>
    </div>
    """, unsafe_allow_html=True)
    
with col_stage2:
    st.markdown("""
    <div style="text-align:center; padding:10px; background:#1f2937; border-radius:8px;">
    <span style="font-size:24px;">🌐</span><br>
    <strong>Translate</strong>
    </div>
    """, unsafe_allow_html=True)
    
with col_stage3:
    st.markdown("""
    <div style="text-align:center; padding:10px; background:#1f2937; border-radius:8px;">
    <span style="font-size:24px;">🔍</span><br>
    <strong>Refine</strong>
    </div>
    """, unsafe_allow_html=True)
    
with col_stage4:
    st.markdown("""
    <div style="text-align:center; padding:10px; background:#1f2937; border-radius:8px;">
    <span style="font-size:24px;">✅</span><br>
    <strong>Checker</strong>
    </div>
    """, unsafe_allow_html=True)

st.divider()

with st.expander("📋 Live Translation Logs", expanded=True):
    auto_refresh = st.toggle("Auto Refresh", value=True)
    log_level = st.selectbox("Log Level", ["All", "Info", "Warning", "Error"], horizontal=True)
    
    log_dir = Path("logs/progress")
    if log_dir.exists():
        log_files = sorted(list(log_dir.glob("*.md")), key=os.path.getmtime, reverse=True)[:1]
        if log_files:
            with open(log_files[0], 'r', encoding='utf-8') as f:
                log_content = f.read()
            
            st.text_area("Logs", log_content, height=300, key="log_view")
            
            col_log1, col_log2 = st.columns(2)
            with col_log1:
                if st.button("🔄 Refresh Logs"):
                    st.rerun()
            with col_log2:
                st.download_button("📥 Download Logs", log_content, file_name="translation.log", mime="text/markdown")
        else:
            st.info("No logs yet.")
    else:
        st.info("No logs directory found.")

st.divider()

if settings["translate_btn"]:
    cmd = ["python3", "-m", "src.main", "--novel", settings["novel"]]
    
    if settings["end_ch"] == 0:
        cmd.extend(["--all", "--start", str(settings["start_ch"])])
    else:
        if settings["start_ch"] == settings["end_ch"]:
            cmd.extend(["--chapter", str(settings["start_ch"])])
        else:
            cmd.extend(["--all", "--start", str(settings["start_ch"])])
    
    if settings["fast_mode"]:
        cmd.append("--skip-refinement")
    
    if settings["lang_source"] == "English":
        cmd.extend(["--lang", "en"])
    else:
        cmd.extend(["--lang", "zh"])
    
    st.write(f"Running: `{' '.join(cmd)}`")
    
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        st.session_state.running = True
        st.session_state.pid = process.pid
        st.success(f"Translation started (PID: {process.pid})")
    except Exception as e:
        st.error(f"Failed to start: {e}")