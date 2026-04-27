import streamlit as st
import json
import os
import pandas as pd
from src.utils.file_handler import FileHandler
from src.memory.memory_manager import MemoryManager

st.set_page_config(page_title="Glossary Editor | ဝေါဟာရ တည်းဖြတ်သူ", page_icon="📚", layout="wide")

st.title("📚 Glossary Editor | ဝေါဟာရ တည်းဖြတ်သူ")

tab1, tab2 = st.tabs(["✅ Approved Glossary (အတည်ပြုပြီး)", "⏳ Pending Terms (စောင့်ဆိုင်းဆဲ)"])

def load_glossary(path):
    if os.path.exists(path):
        return FileHandler.read_json(path)
    return None

# Initialize MemoryManager
mm = MemoryManager()

with tab1:
    st.header("Approved Glossary | အတည်ပြုပြီး ဝေါဟာရများ")
    glossary_data = load_glossary("data/glossary.json")
    if glossary_data and "terms" in glossary_data:
        terms = glossary_data["terms"]
        df = pd.DataFrame(terms)
        st.dataframe(df, use_container_width=True)
        
        st.subheader("Add New Term | ဝေါဟာရအသစ်ထည့်ရန်")
        with st.form("add_term_form"):
            col1, col2, col3 = st.columns(3)
            with col1:
                source = st.text_input("Source (CN/EN) | မူရင်း")
            with col2:
                target = st.text_input("Target (MM) | ဘာသာပြန်")
            with col3:
                category = st.selectbox("Category | အမျိုးအစား", ["character", "place", "item", "level"])
            
            if st.form_submit_button("➕ Add Term | ထည့်သွင်းမည်"):
                if source and target:
                    # Logic to add term via MemoryManager
                    mm.add_term(source, target, category)
                    st.success(f"Term '{source}' added successfully! | '{source}' ကို ထည့်သွင်းပြီးပါပြီ။")
                    st.rerun()
                else:
                    st.error("Source and Target are required. | မူရင်းနှင့် ဘာသာပြန် လိုအပ်ပါသည်။")
    else:
        st.info("No approved glossary found.")

with tab2:
    st.header("Pending Terms | စောင့်ဆိုင်းဆဲ ဝေါဟာရများ")
    pending_data = load_glossary("data/glossary_pending.json")
    if pending_data and "pending_terms" in pending_data:
        pending_terms = pending_data["pending_terms"]
        df_pending = pd.DataFrame(pending_terms)
        st.dataframe(df_pending, use_container_width=True)
        
        if st.button("🔄 Generate New Terms | ဝေါဟာရသစ်များ ထုတ်ယူမည်"):
            st.info("This would trigger GlossaryGenerator agent. | ဤအင်္ဂါရပ်သည် GlossaryGenerator ကို အသုံးပြုပါမည်။")
    else:
        st.info("No pending terms found.")

