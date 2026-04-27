import streamlit as st
import os
from pathlib import Path

def render_sidebar():
    with st.sidebar:
        st.header("🏯 Novel-v1 | ဝတ္ထုဘာသာပြန်")

        input_dir = "data/input"
        if os.path.exists(input_dir):
            novels = [d for d in os.listdir(input_dir) if os.path.isdir(os.path.join(input_dir, d))]
        else:
            novels = []
        
        novel = st.selectbox("📚 ဝတ္ထုအမည်", novels if novels else ["No novels found"])
        
        st.markdown(f"**Source → Target:** Chinese → Myanmar")
        
        st.divider()
        
        with st.expander("📖 အခန်းရွေးချယ်ရန်", expanded=True):
            scope = st.radio("Translation Scope", ["Single Chapter", "Range", "All Remaining"])
            
            if scope == "Single Chapter":
                start_ch = st.number_input("Start Chapter", min_value=1, value=1, key="start_ch_single")
                end_ch = start_ch
            elif scope == "Range":
                col_c1, col_c2 = st.columns(2)
                with col_c1:
                    start_ch = st.number_input("From Chapter", min_value=1, value=1, key="start_ch_range")
                with col_c2:
                    end_ch = st.number_input("To Chapter", min_value=1, value=start_ch, key="end_ch_range")
            else:
                start_ch = st.number_input("Start from Chapter", min_value=1, value=1, key="start_ch_all")
                end_ch = 0
            
            st.markdown("**Quick Buttons:**")
            col_q1, col_q2, col_q3 = st.columns(3)
            with col_q1:
                if st.button("Next 5", use_container_width=True):
                    st.session_state.quick_range = (start_ch, start_ch + 4)
            with col_q2:
                if st.button("Next 10", use_container_width=True):
                    st.session_state.quick_range = (start_ch, start_ch + 9)
            with col_q3:
                if st.button("All Untranslated", use_container_width=True):
                    st.session_state.quick_range = (start_ch, 0)
            
            resume_failed = st.checkbox("Resume from last failed chapter", value=False)
        
        st.divider()
        
        with st.expander("⚙️ Translation Settings", expanded=True):
            model = st.selectbox("🤖 Model", ["qwen2.5:14b", "padauk-gemma:q8_0", "qwen:7b"], index=0)
            
            lang_source = st.radio("🌐 Source Language", ["Chinese", "English"])
            
            col_q1, col_q2 = st.columns(2)
            with col_q1:
                two_stage = st.checkbox("Two-stage Translation", value=True)
            with col_q2:
                use_glossary = st.checkbox("Use Glossary", value=True)
            
            col_s1, col_s2 = st.columns(2)
            with col_s1:
                fast_mode = st.checkbox("Fast Mode", value=False)
            with col_s2:
                enable_reflection = st.checkbox("Enable Reflection", value=False)
        
        st.divider()
        
        with st.expander("🔧 Model Settings (Advanced)"):
            api_key = st.text_input("API Key", type="password", placeholder="••••••••")
            context_window = st.selectbox("Context Window", ["4K", "8K", "16K", "32K"], index=1)
            temperature = st.slider("Temperature", 0.0, 2.0, 0.3)
            max_tokens = st.number_input("Max Output Tokens", min_value=256, value=4096, step=256)
            top_p = st.slider("Top P", 0.0, 1.0, 0.95)
            freq_penalty = st.slider("Frequency Penalty", 0.0, 2.0, 1.1)
            pres_penalty = st.slider("Presence Penalty", 0.0, 2.0, 0.0)
            
            if st.button("🔄 Reset to Defaults"):
                st.rerun()
        
        st.divider()
        
        with st.expander("⚡ Translation Behavior"):
            batch_size = st.number_input("Batch Size", min_value=1, value=5)
            retry_on_fail = st.checkbox("Retry on Failure", value=True)
            max_retries = st.number_input("Max Retries", min_value=1, value=3)
            delay_retry = st.number_input("Delay Between Retries (sec)", min_value=1, value=2)
            
            fallback = st.selectbox("Fallback Strategy", ["Skip & Log", "Use Simpler Model", "Notify & Pause"])
            concurrent_workers = st.number_input("Concurrent Workers", min_value=1, value=1)
            
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                preserve_formatting = st.checkbox("Preserve Formatting", value=True)
            with col_f2:
                term_separation = st.checkbox("Term Separation", value=True)
        
        st.divider()
        
        with st.expander("📚 Glossary Settings"):
            enable_glossary = st.checkbox("Enable Glossary for Translation", value=True)
            
            priority = st.radio("Glossary Priority", ["Strict", "Flexible"])
            
            col_n1, col_n2 = st.columns(2)
            with col_n1:
                new_term_notify = st.checkbox("New Term Notify", value=True)
            with col_n2:
                auto_generate = st.button("🔄 Auto Generate", use_container_width=True)
            
            st.markdown("**Glossary Quick View (Top 5):**")
            glossary_path = "data/glossary.json"
            if os.path.exists(glossary_path):
                import json
                with open(glossary_path, 'r', encoding='utf-8-sig') as f:
                    g_data = json.load(f)
                terms = g_data.get("terms", [])[:5]
                for t in terms:
                    st.caption(f"{t.get('source', '')} → {t.get('target', '')}")
                if len(terms) >= 5:
                    st.link_button("Show all...", "/page/4_Glossary_Editor")
            else:
                st.caption("No glossary found")
        
        st.divider()
        
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            translate_btn = st.button("🚀 Start Translation", type="primary", use_container_width=True)
        with col_btn2:
            stop_btn = st.button("⏹️ Stop", use_container_width=True)
        
        st.divider()
        st.caption("Developed by Gemini CLI Agent | Novel-v1 Translation System")
    
    return {
        "novel": novel,
        "start_ch": start_ch,
        "end_ch": end_ch,
        "model": model,
        "lang_source": lang_source,
        "two_stage": two_stage,
        "use_glossary": use_glossary,
        "fast_mode": fast_mode,
        "enable_reflection": enable_reflection,
        "resume_failed": resume_failed,
        "translate_btn": translate_btn,
        "stop_btn": stop_btn,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "context_window": context_window,
    }