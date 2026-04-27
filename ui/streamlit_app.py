#!/usr/bin/env python3
import streamlit as st
import os
from pathlib import Path
import pandas as pd
from datetime import datetime

st.set_page_config(
    page_title="Novel-v1 Dashboard",
    page_icon="🏠",
    layout="wide"
)

st.title("🏠 Novel-v1 Dashboard | ပါဝင်းမှု အလုံးစုံ")

st.markdown("---")

col_h1, col_h2 = st.columns([2, 1])

with col_h1:
    st.subheader("📊 Project Overview | စီမံကိန်း အကျဉ်းချုပ်")
    
    input_dir = Path("data/input")
    output_dir = Path("data/output")
    glossary_path = Path("data/glossary.json")
    
    total_novels = 0
    total_chapters = 0
    translated = 0
    
    if input_dir.exists():
        novels = [d for d in input_dir.iterdir() if d.is_dir()]
        total_novels = len(novels)
        
        for novel in novels:
            chapters = list(novel.glob("*.md"))
            total_chapters += len(chapters)
            
            out_novel = output_dir / novel.name
            if out_novel.exists():
                translated += len(list(out_novel.glob("*.md")))
    
    glossary_terms = 0
    if glossary_path.exists():
        import json
        with open(glossary_path, 'r', encoding='utf-8') as f:
            g_data = json.load(f)
            glossary_terms = len(g_data.get("terms", []))
    
    col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
    
    with col_stat1:
        st.metric("Novels", total_novels)
    with col_stat2:
        st.metric("Chapters", total_chapters)
    with col_stat3:
        st.metric("Translated", translated)
    with col_stat4:
        st.metric("Glossary Terms", glossary_terms)
    
    if total_chapters > 0:
        progress_pct = int((translated / total_chapters) * 100)
        st.progress(progress_pct, text=f"Overall Progress: {progress_pct}%")
    
    st.info(f"""
    **Novel Translation System**
    ဤစီမံကိန်းသည် AI နည်းပညာသုံး အဆင့်မြင့် **တရုတ်-မြန်မာ ဝတ္ထုဘာသာပြန် စနစ်** ဖြစ်ပါသည်။
    
    ပါဝင်းမှု လက်ရှိ အခြေအနေ:
    - {total_novels} ဝတ္ထု({total_novels} novels)
    - {total_chapters} အခန်း({total_chapters} chapters)
    - {translated} ဘာသာပြန်ပြီး({translated} translated)
    - {glossary_terms} အဘိဓာန်စာလုံး({glossary_terms} terms)
    """)
    
    st.subheader("⚡ Quick Actions | အမြန်လင့်ခ်များ")
    
    col_qa1, col_qa2, col_qa3 = st.columns(3)
    
    with col_qa1:
        if st.button("🚀 Continue Translation | ဘာသာပြန်ဆိုရန် ဆက်လုပ်မည်", use_container_width=True):
            st.switch_page("pages/2_Translate.py")
    
    with col_qa2:
        if st.button("📚 Manage Glossary | အဘိဓာန် ထိန်းချုပ်ရန်", use_container_width=True):
            st.switch_page("pages/4_Glossary_Editor.py")
    
    with col_qa3:
        if st.button("📊 View Progress | အောက်ငါးပြင်အကျယ်", use_container_width=True):
            st.switch_page("pages/3_Progress.py")

with col_h2:
    st.subheader("📝 Recent Activity | လတ်တလော လုပ်ဆောင်မှုများ")
    
    log_dir = Path("logs/progress")
    if log_dir.exists():
        log_files = sorted(Path(log_dir).glob("*.md"), key=os.path.getmtime, reverse=True)[:5]
        
        if log_files:
            for log_file in log_files:
                with st.expander(f"📄 {log_file.name}"):
                    with open(log_file, 'r', encoding='utf-8') as f:
                        content = f.read()[:300]
                    st.text(content)
        else:
            st.info("No recent logs.")
    else:
        st.info("No logs found.")

st.divider()

st.subheader("📈 Translation Stats | စာရင်းအားပြမ်းဆွဲမှုများ")

stats_file = Path("data/stats.json")
if stats_file.exists():
    import json
    with open(stats_file, 'r', encoding='utf-8') as f:
        stats = json.load(f)
    
    if stats:
        chart_data = []
        for date, count in stats.items():
            chart_data.append({"Date": date, "Translated": count})
        
        if chart_data:
            df = pd.DataFrame(chart_data)
            st.line_chart(df.set_index("Date"))
    else:
        st.info("No stats available yet.")
else:
    st.info("No stats available. Start translating to see charts.")

st.divider()

col_link1, col_link2, col_link3, col_link4 = st.columns(4)

with col_link1:
    st.link_button("⚙️ Settings | ပြင်ဆင်ရန်", "/page/5_Settings")
with col_link2:
    st.link_button("📝 Translate | ဘာသာပြန်", "/page/2_Translate")
with col_link3:
    st.link_button("📚 Glossary | အဘိဓာန်", "/page/4_Glossary_Editor")
with col_link4:
    st.link_button("📊 Progress | အောက်ငါး", "/page/3_Progress")

st.markdown("---")
st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Novel-v1 Translation System")