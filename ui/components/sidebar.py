import streamlit as st
import os

from ui.utils.model_loader import get_available_models

def render_sidebar():
    with st.sidebar:
        st.header("🏯 Novel-v1 | ဝတ္ထုဘာသာပြန်")

        input_dir = "data/input"
        if os.path.exists(input_dir):
            # Include both directories and individual .md files
            items = os.listdir(input_dir)
            novels = [d for d in items if os.path.isdir(os.path.join(input_dir, d))]
            files = [f for f in items if os.path.isfile(os.path.join(input_dir, f)) and f.endswith(".md")]
            
            options = novels + files
        else:
            options = []
        
        selected_item = st.selectbox("📚 ဝတ္ထု သို့မဟုတ် ဖိုင် ရွေးချယ်ရန်", options if options else ["No items found"])
        
        is_file = selected_item.endswith(".md") if selected_item and selected_item != "No items found" else False
        novel = selected_item if not is_file else None
        input_file = selected_item if is_file else None
        
        st.markdown(f"**Source → Target:** Chinese → Myanmar")
        
        st.divider()
        
        with st.expander("📖 အခန်းရွေးချယ်ရန်", expanded=not is_file):
            if is_file:
                st.info(f"Individual file selected: {selected_item}")
                start_ch = 1
                end_ch = 1
            else:
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
            # Get available models from Ollama API or config
            available_models = get_available_models()
            
            model = st.selectbox("🤖 Model", available_models, index=0)
            
            lang_source = st.radio("🌐 Source Language", ["Auto", "Chinese", "English"], index=0)
            
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
            temperature = st.slider("Temperature", 0.0, 2.0, 0.3, key="adv_temp")
            max_tokens = st.number_input("Max Output Tokens", min_value=256, value=4096, step=256, key="adv_max_tokens")
            top_p = st.slider("Top P", 0.0, 1.0, 0.95, key="adv_top_p")
            freq_penalty = st.slider("Frequency Penalty", 0.0, 2.0, 1.1, key="adv_freq_penalty")
            pres_penalty = st.slider("Presence Penalty", 0.0, 2.0, 0.0, key="adv_pres_penalty")
            
            if st.button("🔄 Reset to Defaults"):
                st.rerun()
        
        st.divider()
        
        with st.expander("⚡ Translation Behavior"):
            batch_size = st.number_input("Batch Size", min_value=1, value=5, key="bh_batch_size")
            retry_on_fail = st.checkbox("Retry on Failure", value=True, key="bh_retry_on_fail")
            max_retries = st.number_input("Max Retries", min_value=1, value=3, key="bh_max_retries")
            delay_retry = st.number_input("Delay Between Retries (sec)", min_value=1, value=2, key="bh_delay_retry")
            
            fallback = st.selectbox("Fallback Strategy", ["Skip & Log", "Use Simpler Model", "Notify & Pause"], key="bh_fallback")
            concurrent_workers = st.number_input("Concurrent Workers", min_value=1, value=1, key="bh_concurrent_workers")
            
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                preserve_formatting = st.checkbox("Preserve Formatting", value=True, key="bh_preserve_formatting")
            with col_f2:
                term_separation = st.checkbox("Term Separation", value=True, key="bh_term_separation")
        
        st.divider()
        
        with st.expander("📚 Glossary Settings"):
            enable_glossary = st.checkbox("Enable Glossary for Translation", value=True, key="gs_enable_glossary")

            priority = st.radio("Glossary Priority", ["Strict", "Flexible"], key="gs_priority")

            col_n1, col_n2 = st.columns(2)
            with col_n1:
                new_term_notify = st.checkbox("New Term Notify", value=True, key="gs_new_term_notify")
            with col_n2:
                if st.button("🔄 Auto Generate", use_container_width=True, key="gs_auto_generate"):
                    # Trigger glossary generation
                    st.session_state.trigger_glossary_generation = True
                    st.info("Glossary generation will start with next translation")
            
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
                    if st.button("Show all...", use_container_width=True):
                        st.switch_page("pages/4_Glossary_Editor.py")
            else:
                st.caption("No glossary found")
        
        st.divider()

        st.caption("Developed by Gemini CLI Agent | Novel-v1 Translation System")

    return {
        "novel": novel,
        "input_file": input_file,
        "start_ch": start_ch,
        "end_ch": end_ch,
        "model": model,
        "lang_source": lang_source,
        "two_stage": two_stage,
        "use_glossary": use_glossary,
        "fast_mode": fast_mode,
        "enable_reflection": enable_reflection,
        "resume_failed": resume_failed,
        # Model Settings (Advanced)
        "temperature": temperature,
        "max_tokens": max_tokens,
        "context_window": context_window,
        "top_p": top_p,
        "freq_penalty": freq_penalty,
        "pres_penalty": pres_penalty,
        "api_key": api_key,
        # Translation Behavior
        "batch_size": batch_size,
        "retry_on_fail": retry_on_fail,
        "max_retries": max_retries,
        "delay_retry": delay_retry,
        "fallback": fallback,
        "concurrent_workers": concurrent_workers,
        "preserve_formatting": preserve_formatting,
        "term_separation": term_separation,
        # Glossary Settings
        "enable_glossary": enable_glossary,
        "priority": priority,
        "new_term_notify": new_term_notify,
    }
