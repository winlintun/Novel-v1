import streamlit as st
import os
from pathlib import Path
import pandas as pd
import json

st.set_page_config(page_title="Progress | အောက်ငါးပြင်အကျယ်", page_icon="📊", layout="wide")

st.title("📊 Translation Progress & History | ပြန်လည်အောက်ငါး သမိုင်းမှတ်တမ်း")

col_f1, col_f2, col_f3 = st.columns(3)

with col_f1:
    st.metric("Total Chapters", "--")
with col_f2:
    st.metric("Translated", "--")
with col_f3:
    st.metric("Failed", "--")

st.divider()

st.subheader("Chapter List | အခန်းစာရင်း")

input_dir = Path("data/input")
output_dir = Path("data/output")

novels = []
if input_dir.exists():
    novels = [d for d in input_dir.iterdir() if d.is_dir()]

if not novels:
    st.info("No novels found in data/input/")
    st.stop()

selected_novel = st.selectbox("Select Novel", [d.name for d in novels])

if selected_novel:
    novel_input = input_dir / selected_novel
    novel_output = output_dir / selected_novel
    
    chapters = sorted(list(novel_input.glob("*.md")))
    
    chapter_data = []
    for ch in chapters:
        ch_name = ch.stem
        status = "Untranslated"
        word_count = 0
        time_taken = "--"
        
        if novel_output.exists():
            out_files = list(novel_output.glob(f"{ch.stem}*.md"))
            if out_files:
                status = "Translated"
                try:
                    with open(out_files[0], 'r', encoding='utf-8-sig') as f:
                        content = f.read()
                        word_count = len(content)
                except:
                    pass
        
        chapter_data.append({
            "Chapter": ch_name,
            "Status": status,
            "Words": word_count,
            "Time": time_taken
        })
    
    df = pd.DataFrame(chapter_data)
    
    filter_status = st.selectbox("Filter by Status", ["All", "Translated", "Untranslated", "Failed"], horizontal=True)
    if filter_status != "All":
        df = df[df["Status"] == filter_status]
    
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    col_resume = st.columns([1, 1])
    with col_resume[0]:
        if st.button("🔄 Resume Failed"):
            failed = [row["Chapter"] for row in chapter_data if row["Status"] == "Failed"]
            if failed:
                st.session_state.resume_from = failed[0]
                st.success(f"Resume from {failed[0]}")
            else:
                st.info("No failed chapters.")

st.divider()

st.subheader("📋 Detailed Logs | အသေးစိတ် မှတ်တမ်းများ")

log_dir = Path("logs/progress")
if not log_dir.exists():
    st.info("No logs found. Start translation first.")
    st.stop()

log_files = sorted(list(log_dir.glob("*.md")), key=os.path.getmtime, reverse=True)

if not log_files:
    st.info("No log files found.")
    st.stop()

selected_log = st.selectbox("Select Log File", [f.name for f in log_files], horizontal=True)

if selected_log:
    log_path = log_dir / selected_log
    
    col_log_v, col_log_d = st.columns([1, 1])
    with col_log_v:
        with st.expander("📄 View Log Content", expanded=True):
            with open(log_path, 'r', encoding='utf-8') as f:
                content = f.read()
            st.markdown(content)
    
    with col_log_d:
        with st.expander("📊 Log Statistics"):
            lines = content.split('\n')
            errors = sum(1 for l in lines if 'ERROR' in l)
            warnings = sum(1 for l in lines if 'WARNING' in l)
            
            col_s1, col_s2, col_s3 = st.columns(3)
            with col_s1:
                st.metric("Total Lines", len(lines))
            with col_s2:
                st.metric("Errors", errors)
            with col_s3:
                st.metric("Warnings", warnings)

st.divider()

with st.expander("📥 Download Logs", expanded=False):
    col_dl1, col_dl2 = st.columns(2)
    
    with col_dl1:
        st.download_button("📥 Download All Logs (ZIP)", b"", file_name="logs.zip", mime="application/zip")
    
    with col_dl2:
        if st.button("🗑️ Clear Old Logs"):
            st.warning("Feature not implemented yet.")

if st.button("🔄 Refresh"):
    st.rerun()