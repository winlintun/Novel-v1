import streamlit as st
import os
import subprocess
from pathlib import Path
from ui.components.sidebar import render_sidebar

st.set_page_config(page_title="Translate Novel | ဝတ္ထု ဘာသာပြန်ဆိုရန်", page_icon="📝", layout="wide")

selected_novel, model_option = render_sidebar()

st.title("📝 Translate Novel | ဝတ္ထု ဘာသာပြန်ဆိုရန်")

if selected_novel == "No novels found":
    st.warning("Please add novel folders to data/input/ | ကျေးဇူးပြု၍ data/input/ တွင် ဝတ္ထုဖိုင်တွဲများ ထည့်သွင်းပါ။")
    st.stop()

st.info(f"**Current Novel (လက်ရှိ ဝတ္ထု):** {selected_novel}")

col1, col2 = st.columns(2)

with col1:
    st.subheader("⚙️ Translation Options | ဘာသာပြန်ဆိုမှု ရွေးချယ်စရာများ")
    lang = st.radio("Source Language | မူရင်းဘာသာစကား", ["Chinese", "English"], index=0)
    mode = st.radio("Translation Mode | ဘာသာပြန်ဆိုမှု ပုံစံ", ["Single Stage", "Two Stage (Pivot)"], index=0)
    
    start_ch = st.number_input("Start Chapter | စတင်မည့် အခန်း", min_value=1, value=1)
    end_ch = st.number_input("End Chapter (0 for all) | အဆုံးသတ်မည့် အခန်း (အားလုံးအတွက် 0)", min_value=0, value=0)
    
    skip_refine = st.checkbox("Skip Refinement (Faster) | ပြန်လည်ပြင်ဆင်မှု ကျော်ရန် (ပိုမြန်သည်)", value=False)
    
    if st.button("🚀 Start Translation | ဘာသာပြန်ဆိုမှု စတင်ရန်", type="primary"):

        st.session_state.running = True
        # Construct command
        cmd = ["python3", "-m", "src.main", "--novel", selected_novel]
        
        if end_ch == 0:
            if start_ch > 1:
                cmd.extend(["--all", "--start", str(start_ch)])
            else:
                cmd.append("--all")
        else:
            if start_ch == end_ch:
                cmd.extend(["--chapter", str(start_ch)])
            else:
                # If range, we use --all --start and need to handle end manually in main.py
                # For now, let's use --start and warn it will continue to the end
                cmd.extend(["--all", "--start", str(start_ch)])
                st.warning(f"Note: Translating from chapter {start_ch} to the end of novel.")
            
        if skip_refine:
            cmd.append("--skip-refinement")
            
        if lang == "English":
            cmd.extend(["--lang", "en"])
        else:
            cmd.extend(["--lang", "zh"])
            
        st.write(f"Running command: `{' '.join(cmd)}`")
        
        try:
            # Run as background process
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            st.success(f"Translation process started (PID: {process.pid}). Check Progress page.")
        except Exception as e:
            st.error(f"Failed to start translation: {e}")

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
