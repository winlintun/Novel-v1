#!/usr/bin/env python3
import streamlit as st
import os
from pathlib import Path

st.set_page_config(
    page_title="Novel-v1 Dashboard",
    page_icon="🏠",
    layout="wide"
)

st.title("📖 Novel Translation Dashboard | ဝတ္ထုဘာသာပြန် ဒက်ရှ်ဘုတ်")
st.markdown("---")

col1, col2 = st.columns(2)

with col1:
    st.subheader("🚀 Project Summary | စီမံကိန်း အကျဉ်းချုပ်")
    st.info("""
    This project is an advanced, AI-powered **Chinese-to-Myanmar (Burmese) novel translation system**.
    It specializes in Wuxia/Xianxia novels using a multi-stage agent pipeline.
    
    ဤစီမံကိန်းသည် AI နည်းပညာသုံး အဆင့်မြင့် **တရုတ်-မြန်မာ ဝတ္ထုဘာသာပြန် စနစ်** ဖြစ်ပါသည်။
    Wuxia/Xianxia ဝတ္ထုများကို အဓိကထား၍ အဆင့်ဆင့် ဘာသာပြန်ဆိုပေးပါသည်။
    """)
    
    st.markdown("### 📊 Status | အခြေအနေ")
    st.write(f"**Input Novels (မူရင်းဝတ္ထုများ):** {len([d for d in os.listdir('data/input') if os.path.isdir(os.path.join('data/input', d))]) if os.path.exists('data/input') else 0}")
    st.write(f"**Output Chapters (ဘာသာပြန်ပြီးသော အခန်းများ):** {len(list(Path('data/output').rglob('*.md'))) if os.path.exists('data/output') else 0}")

with col2:
    st.subheader("📝 Recent Logs | လတ်တလော မှတ်တမ်းများ")
    log_dir = "logs/progress"
    if os.path.exists(log_dir):
        log_files = sorted(Path(log_dir).glob("*.md"), key=os.path.getmtime, reverse=True)[:3]
        for log_file in log_files:
            with st.expander(f"📄 {log_file.name}"):
                with open(log_file, 'r', encoding='utf-8') as f:
                    content = f.read()[:500]
                st.text(content)
    else:
        st.info("No logs found. | မှတ်တမ်းများ မရှိသေးပါ။")

st.divider()
st.markdown("### 🔗 Quick Links | အမြန်လင့်ခ်များ")
if st.button("Go to Translate | ဘာသာပြန်ရန် သွားမည်"):
    st.switch_page("pages/2_Translate.py")

