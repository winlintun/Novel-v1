import streamlit as st
import json
import os
import pandas as pd
import csv
from src.utils.file_handler import FileHandler
from src.memory.memory_manager import MemoryManager

st.set_page_config(page_title="Glossary Editor | ဝေါဟာရ တည်းဖြတ်သူ", page_icon="📚", layout="wide")

st.title("📚 Glossary Editor | ဝေါဟာရ တည်းဖြတ်သူ")

glossary_path = "data/glossary.json"
pending_path = "data/glossary_pending.json"

def load_glossary(path):
    if os.path.exists(path):
        return FileHandler.read_json(path)
    return None

def save_glossary(path, data):
    FileHandler.write_json(path, data)

mm = MemoryManager()

tab1, tab2, tab3 = st.tabs(["✅ Approved (အတည်ပြုပြီး)", "⏳ Pending (စောင့်ဆိုင်းဆဲ)", "📥 Import/Export"])

with tab1:
    st.header("Approved Glossary | အတည်ပြုပြီး ဝေါဟာရများ")
    
    search_term = st.text_input("🔍 Search Terms", placeholder="Search source or target...")
    
    glossary_data = load_glossary(glossary_path)
    
    if glossary_data and "terms" in glossary_data:
        terms = glossary_data["terms"]
        
        if search_term:
            terms = [t for t in terms if search_term.lower() in t.get('source', '').lower() or search_term.lower() in t.get('target', '').lower()]
        
        filter_cat = st.selectbox("Filter by Category", ["All", "character", "place", "item", "level"], horizontal=True)
        if filter_cat != "All":
            terms = [t for t in terms if t.get('category') == filter_cat]
        
        df = pd.DataFrame(terms)
        if not df.empty:
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.caption(f"Total: {len(terms)} terms")
        else:
            st.info("No terms found.")
        
        with st.expander("➕ Add New Term | ဝေါဟာရအသစ်ထည့်ရန်"):
            with st.form("add_term_form"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    source = st.text_input("Source (CN/EN) | မူရင်း", key="src_add")
                with col2:
                    target = st.text_input("Target (MM) | ဘာသာပြန်", key="tgt_add")
                with col3:
                    category = st.selectbox("Category | အမျိုးအစား", ["character", "place", "item", "level"])
                
                notes = st.text_area("Notes | မှတ်ချက်များ")
                
                if st.form_submit_button("➕ Add Term | ထည့်သွင်းမည်", type="primary"):
                    if source and target:
                        conflict = False
                        for t in terms:
                            if t.get('source', '').lower() == source.lower():
                                conflict = True
                                st.error(f"Conflict! '{source}' already exists. | ဤစကားလုံးသည် ရှိပါပါသည်။")
                                break
                        
                        if not conflict:
                            import uuid
                            new_term = {
                                "id": f"term_{len(terms) + 1:03d}",
                                "source": source,
                                "target": target,
                                "category": category,
                                "chapter_first_seen": 1,
                                "verified": True,
                                "notes": notes
                            }
                            terms.append(new_term)
                            glossary_data["terms"] = terms
                            glossary_data["total_terms"] = len(terms)
                            save_glossary(glossary_path, glossary_data)
                            st.success(f"Term '{source}' added! | ထည့်သွင်းပါပါသည်။")
                            st.rerun()
                    else:
                        st.error("Source and Target required. | မူရင်းနှင့် ဘာသာပြန် လိုအပ်ပါသည်။")
        
        with st.expander("✏️ Edit Term | ဝေါဟာရ ပြင်ဆင်ရန်"):
            if terms:
                edit_id = st.selectbox("Select Term to Edit", [f"{t.get('source', '')} → {t.get('target', '')}" for t in terms])
                if edit_id:
                    term_idx = next(i for i, t in enumerate(terms) if f"{t.get('source', '')} → {t.get('target', '')}" == edit_id)
                    term = terms[term_idx]
                    
                    col_e1, col_e2 = st.columns(2)
                    with col_e1:
                        new_source = st.text_input("Source", value=term.get('source', ''), key="edit_src")
                    with col_e2:
                        new_target = st.text_input("Target", value=term.get('target', ''), key="edit_tgt")
                    
                    new_category = st.selectbox("Category", ["character", "place", "item", "level"], index=["character", "place", "item", "level"].index(term.get('category', 'character')))
                    
                    if st.button("💾 Save Changes"):
                        terms[term_idx] = {
                            "id": term.get('id'),
                            "source": new_source,
                            "target": new_target,
                            "category": new_category,
                            "chapter_first_seen": term.get('chapter_first_seen', 1),
                            "verified": term.get('verified', True)
                        }
                        glossary_data["terms"] = terms
                        save_glossary(glossary_path, glossary_data)
                        st.success("Saved! | သိမ်းပါပါသည်။")
                        st.rerun()
                    
                    if st.button("🗑️ Delete Term", type="primary"):
                        deleted = terms.pop(term_idx)
                        glossary_data["terms"] = terms
                        glossary_data["total_terms"] = len(terms)
                        save_glossary(glossary_path, glossary_data)
                        st.success(f"Deleted: {deleted.get('source')}")
                        st.rerun()
    else:
        st.info("No approved glossary yet. Create one first.")

with tab2:
    st.header("Pending Terms | စောင့်ဆိုင်းဆဲ ဝေါဟာရများ")
    
    pending_data = load_glossary(pending_path)
    
    if pending_data and "pending_terms" in pending_data:
        pending = pending_data["pending_terms"]
        
        df_pending = pd.DataFrame(pending)
        if not df_pending.empty:
            st.dataframe(df_pending, use_container_width=True, hide_index=True)
        
        st.subheader("Review Pending | စောင့်ဆိုင်းဆဲများကို စစ်ဆေးရန်")
        
        for i, term in enumerate(pending):
            with st.expander(f"{term.get('source', '')} → {term.get('target', '')} | {term.get('category', '')}"):
                col_p1, col_p2 = st.columns(2)
                with col_p1:
                    st.write(f"**Source:** {term.get('source', '')}")
                with col_p2:
                    st.write(f"**Category:** {term.get('category', '')}")
                
                st.write(f"**Proposed Target:** {term.get('target', '')}")
                st.write(f"**Chapter:** {term.get('extracted_from_chapter', 'N/A'}")
                
                col_ap1, col_ap2 = st.columns(2)
                with col_ap1:
                    if st.button(f"✅ Approve (အတည်ပါ�ပါသည်)", key=f"appr_{i}"):
                        mm.add_term(term.get('source', ''), term.get('target', ''), term.get('category', ''))
                        pending.pop(i)
                        glossary_data = load_glossary(glossary_path)
                        if not glossary_data:
                            glossary_data = {"version": "1.0", "terms": [], "total_terms": 0}
                        
                        import uuid
                        glossary_data["terms"].append({
                            "id": f"term_{len(glossary_data['terms']) + 1:03d}",
                            "source": term.get('source', ''),
                            "target": term.get('target', ''),
                            "category": term.get('category', ''),
                            "chapter_first_seen": term.get('extracted_from_chapter', 1),
                            "verified": True
                        })
                        glossary_data["total_terms"] = len(glossary_data["terms"])
                        save_glossary(glossary_path, glossary_data)
                        save_glossary(pending_path, pending_data)
                        st.success("Approved! | အတည်ပြုပါပါသည်။")
                        st.rerun()
                
                with col_ap2:
                    if st.button(f"❌ Reject (ပယ်ရန်)", key=f"rej_{i}"):
                        pending.pop(i)
                        pending_data["pending_terms"] = pending
                        save_glossary(pending_path, pending_data)
                        st.warning("Rejected. | ပယ်ပါပါသည်။")
                        st.rerun()
    else:
        st.info("No pending terms. They will appear after translation.")
    
    if st.button("🔄 Auto Generate Terms | ဝေါဟာရသစ်များ ထုတ်ယူမည်"):
        st.info("Run translation first to auto-generate terms.")

with tab3:
    st.header("Import/Export | ထုတ်သွင်းရန်/သိမ်းသွင်းရန်")
    
    col_imp, col_exp = st.columns(2)
    
    with col_imp:
        st.subheader("📥 Import")
        import_file = st.file_uploader("Upload CSV or JSON", type=["csv", "json"])
        
        if import_file:
            if st.button("Import Terms"):
                try:
                    if import_file.name.endswith('.csv'):
                        df = pd.read_csv(import_file)
                        st.dataframe(df)
                        st.success(f"Ready to import {len(df)} terms from CSV")
                    else:
                        data = json.load(import_file)
                        st.success(f"Ready to import {len(data.get('terms', data.get('pending_terms', [])))} terms")
                except Exception as e:
                    st.error(f"Failed to import: {e}")
    
    with col_exp:
        st.subheader("📤 Export")
        export_format = st.radio("Format", ["JSON", "CSV"], horizontal=True)
        
        glossary_data = load_glossary(glossary_path)
        
        if glossary_data and export_format == "JSON":
            json_str = json.dumps(glossary_data, ensure_ascii=False, indent=2)
            st.download_button("📥 Download JSON", json_str, file_name="glossary.json", mime="application/json")
        
        elif glossary_data and export_format == "CSV":
            terms = glossary_data.get("terms", [])
            if terms:
                df = pd.DataFrame(terms)
                csv_str = df.to_csv(index=False)
                st.download_button("📥 Download CSV", csv_str, file_name="glossary.csv", mime="text/csv")
        
        pending_data = load_glossary(pending_path)
        if pending_data and export_format == "JSON":
            json_str = json.dumps(pending_data, ensure_ascii=False, indent=2)
            st.download_button("📥 Download Pending JSON", json_str, file_name="pending_terms.json", mime="application/json")