import streamlit as st
import yaml
import os

st.set_page_config(page_title="Settings", page_icon="⚙️", layout="wide")

st.title("⚙️ System Settings")

config_path = "config/settings.yaml"

def load_config():
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    return {}

config = load_config()

st.header("🤖 Model Configuration")
col1, col2 = st.columns(2)

with col1:
    translator_model = st.text_input("Translator Model", config.get('models', {}).get('translator', 'qwen2.5:14b'))
    editor_model = st.text_input("Editor Model", config.get('models', {}).get('editor', 'qwen2.5:14b'))

with col2:
    ollama_url = st.text_input("Ollama Base URL", config.get('models', {}).get('ollama_base_url', 'http://localhost:11434'))
    timeout = st.number_input("Timeout (seconds)", value=config.get('models', {}).get('timeout', 300))

st.header("🛠️ Processing Settings")
chunk_size = st.number_input("Chunk Size", value=config.get('processing', {}).get('chunk_size', 1500))
temperature = st.slider("Temperature", 0.0, 1.0, float(config.get('processing', {}).get('temperature', 0.45)))

if st.button("💾 Save Settings"):
    # Update config dict
    if 'models' not in config: config['models'] = {}
    config['models']['translator'] = translator_model
    config['models']['editor'] = editor_model
    config['models']['ollama_base_url'] = ollama_url
    config['models']['timeout'] = timeout
    
    if 'processing' not in config: config['processing'] = {}
    config['processing']['chunk_size'] = chunk_size
    config['processing']['temperature'] = temperature
    
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(config, f)
    st.success("Settings saved to config/settings.yaml")
