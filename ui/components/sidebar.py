import streamlit as st
import os

def render_sidebar():
    with st.sidebar:
        st.header("⚙️ Settings")
        
        # Novel selection
        input_dir = "data/input"
        if os.path.exists(input_dir):
            novels = [d for d in os.listdir(input_dir) if os.path.isdir(os.path.join(input_dir, d))]
        else:
            novels = []
        
        selected_novel = st.selectbox("Select Novel", novels if novels else ["No novels found"])
        
        st.divider()
        
        # Model selection
        st.subheader("Model")
        model_option = st.selectbox(
            "Translation Model",
            ["padauk-gemma:q8_0", "qwen2.5:14b", "qwen:7b"],
            index=0
        )
        
        st.divider()
        st.markdown("Developed by Gemini CLI Agent")
        
    return selected_novel, model_option
