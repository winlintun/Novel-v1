import streamlit as st
import yaml
import os

from ui.utils.model_loader import get_available_models

st.set_page_config(page_title="Settings", page_icon="⚙️", layout="wide")

st.title("⚙️ System Settings")

config_path = "config/settings.yaml"

def load_config():
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    return {}

config = load_config()

ollama_url_from_cfg = config.get('models', {}).get('ollama_base_url', 'http://localhost:11434')
available_models = get_available_models(
    config_path=config_path,
    ollama_base_url=ollama_url_from_cfg,
)

st.header("🤖 Model Configuration")
col1, col2 = st.columns(2)

with col1:
    current_translator = config.get('models', {}).get('translator', 'qwen2.5:14b')
    translator_index = available_models.index(current_translator) if current_translator in available_models else 0
    translator_model = st.selectbox("Translator Model", available_models, index=translator_index)
    
    current_editor = config.get('models', {}).get('editor', 'qwen2.5:14b')
    editor_index = available_models.index(current_editor) if current_editor in available_models else 0
    editor_model = st.selectbox("Editor Model", available_models, index=editor_index)

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
