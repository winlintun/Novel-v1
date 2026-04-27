import streamlit as st
import os
import sys
import subprocess
import time
from datetime import datetime
from pathlib import Path

# Add project root to path for imports
project_root = str(Path(__file__).parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from ui.components.sidebar import render_sidebar

st.set_page_config(page_title="Translate | ဘာသာပြန်", page_icon="📝", layout="wide")

settings = render_sidebar()

if not settings.get("novel") and not settings.get("input_file"):
    st.warning("Please add novel folders or .md files to data/input/ | ကျေးဇူးပြု၍ data/input/ တွင် ဝတ္ထုဖိုင်တွဲများ သို့မဟုတ် .md ဖိုင်များ ထည့်သွင်းပါ။")
    st.stop()

title_name = settings['novel'] if settings['novel'] else settings['input_file']
st.header(f"📚 {title_name} | {settings['lang_source']} → Myanmar")

# Initialize session state for process management
if 'running' not in st.session_state:
    st.session_state.running = False
if 'pid' not in st.session_state:
    st.session_state.pid = None
if 'start_time' not in st.session_state:
    st.session_state.start_time = None

# Check if process is still running
if st.session_state.running and st.session_state.pid:
    try:
        # Check if PID exists
        os.kill(st.session_state.pid, 0)
    except OSError:
        st.session_state.running = False
        st.session_state.pid = None
        st.success("Translation process completed. | ဘာသာပြန်ဆိုမှု ပြီးဆုံးပါပြီ။")

col_nav1, col_nav2, col_nav3 = st.columns([1, 1, 2])
with col_nav1:
    if settings.get('input_file'):
        st.metric("Mode", "Single File")
    else:
        st.metric("Current Chapter", f"{settings['start_ch']}")
with col_nav2:
    if st.session_state.running:
        if st.button("⏹️ Stop Translation", type="secondary"):
            import signal
            try:
                os.kill(st.session_state.pid, signal.SIGTERM)
                st.warning(f"Stop signal sent to PID {st.session_state.pid}.")
            except Exception as e:
                st.error(f"Failed to stop process: {e}")
            st.session_state.running = False
            st.session_state.pid = None
            st.rerun()
    else:
        if st.button("🚀 Start Translation", type="primary"):
            # Update config with all selected settings
            try:
                import yaml
                config_path = Path("config/settings.yaml")
                if config_path.exists():
                    with open(config_path, 'r') as f:
                        cfg = yaml.safe_load(f)
                    
                    if cfg:
                        # Update model settings
                        if 'models' not in cfg:
                            cfg['models'] = {}
                        if settings.get("model"):
                            cfg['models']['translator'] = settings["model"]
                            cfg['models']['editor'] = settings["model"]
                        
                        # Update processing settings from Advanced Model Settings
                        if 'processing' not in cfg:
                            cfg['processing'] = {}
                        if settings.get("temperature") is not None:
                            cfg['processing']['temperature'] = settings["temperature"]
                        if settings.get("max_tokens") is not None:
                            cfg['processing']['max_tokens'] = settings["max_tokens"]
                        
                        # Map context window to num_ctx
                        if settings.get("context_window"):
                            ctx_map = {"4K": 4096, "8K": 8192, "16K": 16384, "32K": 32768}
                            cfg['processing']['num_ctx'] = ctx_map.get(settings["context_window"], 8192)
                        
                        # Update batch processing settings
                        if 'batch_processing' not in cfg['processing']:
                            cfg['processing']['batch_processing'] = {}
                        if settings.get("batch_size") is not None:
                            cfg['processing']['batch_processing']['batch_size'] = settings["batch_size"]
                        
                        # Update retry settings
                        if settings.get("max_retries") is not None:
                            cfg['processing']['max_retries'] = settings["max_retries"]
                        
                        # Update glossary settings
                        if 'glossary_v3' not in cfg:
                            cfg['glossary_v3'] = {}
                        if settings.get("enable_glossary") is not None:
                            cfg['glossary_v3']['enabled'] = settings["enable_glossary"]
                        if settings.get("priority"):
                            cfg['glossary_v3']['priority'] = settings["priority"].lower()
                        
                        # Update pipeline mode settings
                        if 'translation_pipeline' not in cfg:
                            cfg['translation_pipeline'] = {}
                        if settings.get("enable_reflection") is not None:
                            cfg['translation_pipeline']['use_reflection'] = settings["enable_reflection"]
                        
                        with open(config_path, 'w') as f:
                            yaml.dump(cfg, f)
                        
                        st.info(f"Settings saved: model={settings.get('model')}, temp={settings.get('temperature')}")
            except Exception as e:
                st.warning(f"Could not update config: {e}")
            
            cmd = ["python3", "-m", "src.main"]
            
            if settings.get("input_file"):
                cmd.extend(["--input", f"data/input/{settings['input_file']}"])
            else:
                cmd.extend(["--novel", settings["novel"]])
                if settings["end_ch"] == 0:
                    cmd.extend(["--all", "--start", str(settings["start_ch"])])
                else:
                    if settings["start_ch"] == settings["end_ch"]:
                        cmd.extend(["--chapter", str(settings["start_ch"])])
                    else:
                        cmd.extend(["--all", "--start", str(settings["start_ch"])])
            
            if settings["fast_mode"]:
                cmd.append("--skip-refinement")
            
            # Optional source hint. Auto mode sends no language flag and lets CLI detect workflow.
            if settings["lang_source"] == "English":
                cmd.extend(["--lang", "en"])
            elif settings["lang_source"] == "Chinese":
                cmd.extend(["--lang", "zh"])
            
            # Note: use_glossary is handled internally based on config
            # Note: enable_reflection is saved to config above
            
            try:
                # Use project root as CWD
                project_root = Path(__file__).parent.parent.parent
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=str(project_root))
                st.session_state.running = True
                st.session_state.pid = process.pid
                st.session_state.start_time = datetime.now()
                st.success(f"Translation started (PID: {process.pid})")
                st.rerun()
            except Exception as e:
                st.error(f"Failed to start: {e}")

with col_nav3:
    if st.session_state.running:
        elapsed = datetime.now() - st.session_state.start_time
        st.info(f"Running for: {str(elapsed).split('.')[0]} | PID: {st.session_state.pid}")
    else:
        st.info("Status: Ready | အသင်းသင်း အသုံးရန် အသင့်ပါ။")

st.divider()

col_src, col_tgt = st.columns(2)

with col_src:
    st.subheader("📄 Original Text | မူရင်း")
    if settings.get('input_file'):
        src_file = Path("data/input") / settings['input_file']
        if src_file.exists():
            with open(src_file, 'r', encoding='utf-8-sig') as f:
                src_content = f.read()
            st.text_area("Source", src_content, height=500, key="src_area", disabled=True)
    else:
        novel_dir = Path("data/input") / settings["novel"]
        if novel_dir.exists():
            files = sorted(list(novel_dir.glob("*.md")))
            if files:
                selected_file = st.selectbox("Select Chapter", [f.name for f in files], key="src_select")
                if selected_file:
                    with open(novel_dir / selected_file, 'r', encoding='utf-8-sig') as f:
                        src_content = f.read()
                    st.text_area("Source", src_content, height=500, key="src_area", disabled=True)
        else:
            st.info("No source files found.")

with col_tgt:
    st.subheader("🇲🇲 Myanmar Translation")

    if settings.get('input_file'):
        # For single file mode, output goes to data/output/sample/
        output_dir = Path("data/output/sample")
        output_dir.mkdir(parents=True, exist_ok=True)
    else:
        output_dir = Path("data/output") / settings["novel"]

    # Helper function to find output file in root or chapters/ subdirectory
    def find_output_file(output_dir: Path, filename: str):
        """Find output file in root or chapters/ subdirectory."""
        for location in [output_dir, output_dir / "chapters"]:
            file_path = location / filename
            if file_path.exists():
                return file_path
        return output_dir / filename  # Return default if not found

    out_files = []
    if output_dir.exists():
        # Check both root output dir and chapters/ subdirectory
        out_files = sorted(list(output_dir.glob("*.md")))
        chapters_dir = output_dir / "chapters"
        if chapters_dir.exists():
            out_files.extend(sorted(list(chapters_dir.glob("*.md"))))
    
    selected_out = st.selectbox("Select Output Chapter", [f.name for f in out_files] if out_files else ["-- None --"], key="out_select")
    
    if selected_out and selected_out != "-- None --":
        # Use helper to find file in root or chapters/ subdirectory
        file_path = find_output_file(output_dir, selected_out)
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                tgt_content = f.read()
        except FileNotFoundError:
            st.error(f"File not found: {file_path}")
            tgt_content = ""
    else:
        tgt_content = ""
    
    # Highlight glossary terms (per need_fix.md 3.3)
    highlight_terms = st.checkbox("🔍 Highlight Glossary Terms", value=False)
    if highlight_terms:
        glossary_path = Path("data/glossary.json")
        if glossary_path.exists():
            import json
            with open(glossary_path, 'r', encoding='utf-8-sig') as f:
                g_data = json.load(f)
            terms = g_data.get("terms", [])
            highlighted = tgt_content
            for term in terms[:20]:
                target = term.get('target', '')
                if target and target in tgt_content:
                    highlighted = highlighted.replace(target, f"**{target}**")
            if highlighted != tgt_content:
                st.markdown("### 📚 Highlighted Terms")
                st.markdown(highlighted, unsafe_allow_html=True)
            else:
                st.info("No glossary terms found in this chapter.")
        else:
            st.info("No glossary found.")
    
    edited = st.text_area("Translation", tgt_content, height=500, key="tgt_area")
    
    col_save, col_add = st.columns(2)
    with col_save:
        if st.button("💾 Save Edit"):
            if selected_out and selected_out != "-- None --" and edited != tgt_content:
                # Use helper to find correct path for saving
                file_path = find_output_file(output_dir, selected_out)
                try:
                    with open(file_path, 'w', encoding='utf-8-sig') as f:
                        f.write(edited)
                    st.success(f"Saved to {file_path.name}! | သိမ်းပါပါသည်။")
                except Exception as e:
                    st.error(f"Failed to save: {e}")
    with col_add:
        add_glossary = st.button("📚 Add to Glossary", use_container_width=True)

st.divider()

st.subheader("📊 Progress Tracking")

col_prog1, col_prog2, col_prog3 = st.columns([3, 1, 1])

with col_prog1:
    progress_bar = st.progress(0, text="Ready to translate")
with col_prog2:
    pct = st.metric("Progress", "0%")
with col_prog3:
    eta = st.metric("ETA", "--")

st.info("Status: Ready | အသင်းသင်း အသုံးရန် အသင့်ပါ။")

st.subheader("🔄 Translation Stages")
col_stage1, col_stage2, col_stage3, col_stage4 = st.columns(4)

with col_stage1:
    st.markdown("""
    <div style="text-align:center; padding:10px; background:#1f2937; border-radius:8px;">
    <span style="font-size:24px;">⚙️</span><br>
    <strong>Preprocess</strong>
    </div>
    """, unsafe_allow_html=True)
    
with col_stage2:
    st.markdown("""
    <div style="text-align:center; padding:10px; background:#1f2937; border-radius:8px;">
    <span style="font-size:24px;">🌐</span><br>
    <strong>Translate</strong>
    </div>
    """, unsafe_allow_html=True)
    
with col_stage3:
    st.markdown("""
    <div style="text-align:center; padding:10px; background:#1f2937; border-radius:8px;">
    <span style="font-size:24px;">🔍</span><br>
    <strong>Refine</strong>
    </div>
    """, unsafe_allow_html=True)
    
with col_stage4:
    st.markdown("""
    <div style="text-align:center; padding:10px; background:#1f2937; border-radius:8px;">
    <span style="font-size:24px;">✅</span><br>
    <strong>Checker</strong>
    </div>
    """, unsafe_allow_html=True)

st.divider()

with st.expander("📋 Live Translation Logs", expanded=True):
    log_type = st.radio("Log Type", ["Progress (Markdown)", "Technical (Full Log)"], horizontal=True)
    
    col_log_opts1, col_log_opts2, col_log_opts3 = st.columns(3)
    
    with col_log_opts1:
        auto_refresh = st.toggle("Auto Refresh", value=True)
    
    with col_log_opts2:
        log_level = st.selectbox("Log Level", ["All", "Info", "Warning", "Error"])
    
    with col_log_opts3:
        log_filter = st.text_input("Filter Logs", placeholder="Search...")
    
    if log_type == "Progress (Markdown)":
        log_dir = Path("logs/progress")
        pattern = "*.md"
    else:
        log_dir = Path("logs")
        pattern = "*.log"

    if log_dir.exists():
        log_files = sorted(list(log_dir.glob(pattern)), key=os.path.getmtime, reverse=True)[:5]
        
        if log_files:
            selected_log = st.selectbox(f"Select {log_type}", [f.name for f in log_files])
            
            if selected_log:
                log_path = log_dir / selected_log
                with open(log_path, 'r', encoding='utf-8-sig') as f:
                    log_content = f.read()
                
                # Filter by level (only for Technical logs)
                if log_type == "Technical (Full Log)":
                    if log_level == "Error":
                        log_content = "\n".join([l for l in log_content.split('\n') if 'ERROR' in l or 'Error' in l])
                    elif log_level == "Warning":
                        log_content = "\n".join([l for l in log_content.split('\n') if 'WARNING' in l or 'Warning' in l])
                
                # Filter by search
                if log_filter:
                    log_content = "\n".join([l for l in log_content.split('\n') if log_filter.lower() in l.lower()])
                
                # Show line count
                line_count = len(log_content.split('\n'))
                error_count = log_content.count('ERROR') + log_content.count('Error')
                warning_count = log_content.count('WARNING') + log_content.count('Warning')
                
                col_stats1, col_stats2, col_stats3 = st.columns(3)
                with col_stats1:
                    st.metric("Lines", line_count)
                with col_stats2:
                    st.metric("Errors", error_count)
                with col_stats3:
                    st.metric("Warnings", warning_count)
                
                if log_type == "Progress (Markdown)":
                    st.markdown(log_content)
                else:
                    st.text_area("Logs", log_content, height=300, key="log_view")
                
                col_log1, col_log2, col_log3 = st.columns([1, 1, 1])
                with col_log1:
                    if st.button("🔄 Refresh Logs"):
                        st.rerun()
                with col_log2:
                    st.download_button("📥 Download Logs", log_content, file_name=f"{selected_log}", mime="text/plain")
                with col_log3:
                    st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")
        else:
            st.info(f"No {log_type.lower()}s yet.")
    else:
        st.info("No logs directory found. Start translation to create logs.")

st.divider()

with st.expander("💾 RAM Monitor & System Status", expanded=False):
    from src.utils.ram_monitor import RAMMonitor, ModelUnloader
    
    monitor = RAMMonitor()
    
    col_ram1, col_ram2, col_ram3 = st.columns(3)
    
    with col_ram1:
        usage = monitor.get_memory_usage()
        st.metric("RAM Used", f"{usage['ram_used_mb']} MB", f"{usage['ram_percent']}%")
    
    with col_ram2:
        if usage.get('vram_total_mb', 0) > 0:
            st.metric("VRAM Used", f"{usage['vram_used_mb']} MB", f"{usage['vram_percent']}%")
        else:
            st.metric("VRAM", "No GPU detected")
    
    with col_ram3:
        running_models = ModelUnloader.list_models()
        st.metric("Running Models", len(running_models))
    
    if running_models:
        st.write("**Running Ollama Models:**")
        for model in running_models:
            col_m1, col_m2 = st.columns([3, 1])
            with col_m1:
                st.code(model)
            with col_m2:
                if st.button(f"🗑️ Unload", key=f"unload_{model}"):
                    if ModelUnloader.unload_model(model):
                        st.success(f"Unloaded {model}")
                        st.rerun()
    
    if st.button("🔄 Refresh Memory"):
        st.rerun()

st.divider()

if st.session_state.running:
    # Auto-refresh logic for live log view
    time.sleep(2)
    st.rerun()
