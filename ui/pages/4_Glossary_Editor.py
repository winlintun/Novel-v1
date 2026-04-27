import streamlit as st
import json
import os
import pandas as pd
from src.utils.file_handler import FileHandler

st.set_page_config(page_title="Glossary Editor", page_icon="📚", layout="wide")

st.title("📚 Glossary Editor")

tab1, tab2 = st.tabs(["✅ Approved Glossary", "⏳ Pending Terms"])

def load_glossary(path):
    if os.path.exists(path):
        return FileHandler.read_json(path)
    return None

with tab1:
    st.header("Approved Glossary")
    glossary_data = load_glossary("data/glossary.json")
    if glossary_data and "terms" in glossary_data:
        terms = glossary_data["terms"]
        df = pd.DataFrame(terms)
        st.dataframe(df, use_container_width=True)
        
        st.subheader("Add New Term")
        with st.form("add_term_form"):
            col1, col2, col3 = st.columns(3)
            with col1:
                source = st.text_input("Source (CN/EN)")
            with col2:
                target = st.text_input("Target (MM)")
            with col3:
                category = st.selectbox("Category", ["character", "place", "item", "level"])
            
            if st.form_submit_button("➕ Add Term"):
                if source and target:
                    # Logic to add term via MemoryManager or FileHandler
                    st.success(f"Term '{source}' added!")
                else:
                    st.error("Source and Target are required.")
    else:
        st.info("No approved glossary found.")

with tab2:
    st.header("Pending Terms")
    pending_data = load_glossary("data/glossary_pending.json")
    if pending_data and "pending_terms" in pending_data:
        pending_terms = pending_data["pending_terms"]
        df_pending = pd.DataFrame(pending_terms)
        st.dataframe(df_pending, use_container_width=True)
        
        if st.button("🔄 Generate New Terms"):
            st.info("This would trigger GlossaryGenerator agent.")
    else:
        st.info("No pending terms found.")
