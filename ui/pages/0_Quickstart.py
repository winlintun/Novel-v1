#!/usr/bin/env python3
"""
Quickstart Wizard — Guided 3-step setup for first-time users.

This page walks users through:
  Step 1: Select a novel (or upload one)
  Step 2: Configure the model (auto-select or manual)
  Step 3: Start translation with one click

Also serves as a landing page with quick --help examples for CLI users.
"""

import streamlit as st
import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = str(Path(__file__).parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

st.set_page_config(
    page_title="Quickstart | အစပျိုးလမ်းညွှန်",
    page_icon="🚀",
    layout="wide",
)

# ── CSS for step cards ──
st.markdown("""
<style>
.step-card {
    border: 1px solid #e0e0e0;
    border-radius: 10px;
    padding: 20px;
    margin: 10px 0;
    background-color: #fafafa;
}
.step-number {
    font-size: 2em;
    font-weight: bold;
    color: #1f77b4;
}
</style>
""", unsafe_allow_html=True)

st.title("🚀 Quickstart Wizard | အစပျိုးလမ်းညွှန်")

# Session state for wizard
if 'wizard_step' not in st.session_state:
    st.session_state.wizard_step = 1
if 'wizard_novel' not in st.session_state:
    st.session_state.wizard_novel = None
if 'wizard_input_file' not in st.session_state:
    st.session_state.wizard_input_file = None
if 'wizard_model' not in st.session_state:
    st.session_state.wizard_model = "padauk-gemma:q8_0"
if 'wizard_chapter' not in st.session_state:
    st.session_state.wizard_chapter = 1
if 'wizard_all' not in st.session_state:
    st.session_state.wizard_all = False

# ── Progress Bar ──
st.progress(st.session_state.wizard_step / 3, text=f"Step {st.session_state.wizard_step} of 3")

# ── STEP 1: Select Novel ──
if st.session_state.wizard_step == 1:
    st.markdown('<div class="step-card">', unsafe_allow_html=True)
    st.markdown('<span class="step-number">1️⃣</span> **Choose Your Novel**', unsafe_allow_html=True)
    st.markdown("---")

    input_dir = Path("data/input")
    if input_dir.exists():
        items = sorted(os.listdir(input_dir))
        novels = [d for d in items if os.path.isdir(input_dir / d)]
        files = [f for f in items if os.path.isfile(input_dir / f) and f.endswith(".md")]
        options = ["(none selected)"] + novels + files
    else:
        options = ["(none selected)"]

    st.info(
        "**Where to put your novel?**\n\n"
        "Drop your Chinese `.md` chapter files into `data/input/<your-novel-name>/`.\n"
        "Example: `data/input/reverend-insanity/chapter_001.md`\n\n"
        "Already have English source? Put English `.md` files instead — the pipeline auto-detects."
    )

    selected = st.selectbox(
        "📚 Available Novels & Files",
        options,
        index=0,
        help="Select a novel folder for multi-chapter translation, or a single .md file",
    )

    if selected and selected != "(none selected)":
        if selected.endswith(".md"):
            st.session_state.wizard_input_file = selected
            st.session_state.wizard_novel = None
            st.success(f"Selected file: `{selected}`")
        else:
            st.session_state.wizard_novel = selected
            st.session_state.wizard_input_file = None

            # Show chapters in the novel
            novel_path = input_dir / selected
            chapters = sorted(novel_path.glob("*.md"))
            if chapters:
                st.caption(f"📖 {len(chapters)} chapter files found:")
                for ch in chapters[:10]:
                    st.caption(f"  • {ch.name}")
                if len(chapters) > 10:
                    st.caption(f"  ... and {len(chapters) - 10} more")
            else:
                st.warning("No chapter files found in this folder. Add .md files to proceed.")
    else:
        st.session_state.wizard_novel = None
        st.session_state.wizard_input_file = None

    st.markdown('</div>', unsafe_allow_html=True)

    # Navigation
    col_prev, col_next = st.columns([1, 1])
    with col_next:
        if st.button("Next: Configure Model →", type="primary", use_container_width=True,
                     disabled=not (st.session_state.wizard_novel or st.session_state.wizard_input_file)):
            st.session_state.wizard_step = 2
            st.rerun()

    # Show CLI quickstart
    with st.expander("💻 CLI Power Users — Quick Start"):
        st.markdown("""```bash
# Quickest way to translate:
python -m src.main --novel reverend-insanity --all

# Translate a single chapter:
python -m src.main --novel reverend-insanity --chapter 1

# Translate a range of chapters:
python -m src.main --novel reverend-insanity --chapter-range 1-5

# View a translated chapter in terminal:
python -m src.main --view data/output/reverend-insanity/reverend-insanity_chapter_001.mm.md

# Review quality of a translated file:
python -m src.main --review data/output/reverend-insanity/reverend-insanity_chapter_001.mm.md

# Launch Web UI:
python -m src.main --ui

# Auto-detect source language (no --lang flag needed):
python -m src.main --novel reverend-insanity --all
# Pipeline auto-detects if source is Chinese or English!

# Full options:
python -m src.main --help
```""")

# ── STEP 2: Configure Model ──
elif st.session_state.wizard_step == 2:
    st.markdown('<div class="step-card">', unsafe_allow_html=True)
    st.markdown('<span class="step-number">2️⃣</span> **Configure Translation Model**', unsafe_allow_html=True)
    st.markdown("---")

    # Auto-detect available models from Ollama
    st.info(
        "**Recommended models for Myanmar translation:**\n\n"
        "- `padauk-gemma:q8_0` — Best Myanmar quality (primary)\n"
        "- `alibayram/hunyuan:7b` — Best Chinese comprehension (CN→EN pivot)\n"
        "- `burmese-gpt:7b` — Alternative Burmese model (experimental)\n\n"
        "Make sure models are installed via `ollama pull <model>` before starting."
    )

    # Model selection
    try:
        from ui.utils.model_loader import get_available_models
        models = get_available_models()
    except Exception:
        models = ["padauk-gemma:q8_0", "alibayram/hunyuan:7b", "qwen:7b"]

    st.session_state.wizard_model = st.selectbox(
        "🤖 Translator Model",
        models,
        index=models.index(st.session_state.wizard_model) if st.session_state.wizard_model in models else 0,
        help="This model will be used for translating the text to Myanmar",
    )

    # Quick settings
    col1, col2 = st.columns(2)
    with col1:
        temperature = st.slider("Temperature", 0.0, 1.0, 0.2, 0.05,
                                help="Lower = more consistent. 0.2 recommended for Myanmar.")
    with col2:
        chunk_size = st.selectbox("Chunk Size", [800, 1500, 2000], index=1,
                                  help="Characters per translation chunk. 1500 is a good default.")

    if st.session_state.wizard_input_file:
        st.caption("Single file mode — will translate one file.")
    else:
        col_ch1, col_ch2 = st.columns(2)
        with col_ch1:
            st.session_state.wizard_chapter = st.number_input(
                "Start Chapter", min_value=1, value=1,
            )
        with col_ch2:
            st.session_state.wizard_all = st.checkbox(
                "Translate ALL chapters", value=True,
                help="Uncheck to translate only the start chapter",
            )

    st.markdown('</div>', unsafe_allow_html=True)

    col_prev, col_next = st.columns([1, 1])
    with col_prev:
        if st.button("← Back to Novel Selection", use_container_width=True):
            st.session_state.wizard_step = 1
            st.rerun()
    with col_next:
        if st.button("Next: Start Translation →", type="primary", use_container_width=True):
            st.session_state.wizard_step = 3
            st.rerun()

# ── STEP 3: Review & Launch ──
elif st.session_state.wizard_step == 3:
    st.markdown('<div class="step-card">', unsafe_allow_html=True)
    st.markdown('<span class="step-number">3️⃣</span> **Review & Start Translation**', unsafe_allow_html=True)
    st.markdown("---")

    # Summary card
    target = st.session_state.wizard_novel or st.session_state.wizard_input_file
    scope = "ALL chapters" if st.session_state.wizard_all else f"Chapter {st.session_state.wizard_chapter}"

    st.markdown(f"""
| Setting | Value |
|---------|-------|
| 📚 Target | `{target}` |
| 🤖 Model | `{st.session_state.wizard_model}` |
| 📖 Scope | {scope} |
| 🌡️ Temperature | `{temperature}` |
| 📦 Chunk Size | `{chunk_size}` |
""")

    st.info(
        "**What happens next:**\n\n"
        "1. The translation pipeline will process each chapter\n"
        "2. Progress is shown in real-time\n"
        "3. Output files saved to `data/output/<novel>/`\n"
        "4. A quality report is generated for each chapter\n"
        "5. New terms are added to `glossary_pending.json` for your review\n\n"
        "⏱️ Expect ~2-5 minutes per chapter depending on model speed."
    )

    st.markdown('</div>', unsafe_allow_html=True)

    col_prev, col_launch = st.columns([1, 1])
    with col_prev:
        if st.button("← Back to Model Config", use_container_width=True):
            st.session_state.wizard_step = 2
            st.rerun()
    with col_launch:
        if st.button("🚀 Launch Translation!", type="primary", use_container_width=True):
            # Build command
            cmd = ["python", "-m", "src.main"]

            if st.session_state.wizard_novel:
                cmd.extend(["--novel", st.session_state.wizard_novel])
                if st.session_state.wizard_all:
                    cmd.append("--all")
                else:
                    cmd.extend(["--chapter", str(st.session_state.wizard_chapter)])
            else:
                input_path = str(Path("data/input") / st.session_state.wizard_input_file)
                cmd.extend(["--input", input_path])

            # Save settings to session for Translate page
            st.session_state.quickstart_cmd = cmd
            st.session_state.quickstart_model = st.session_state.wizard_model

            # Switch to Translate page
            st.switch_page("pages/2_Translate.py")

    # Show CLI equivalent
    with st.expander("💻 Equivalent CLI Command"):
        novel = st.session_state.wizard_novel
        if novel:
            cmd = f"python -m src.main --novel {novel} --all"
        else:
            cmd = f"python -m src.main --input data/input/{st.session_state.wizard_input_file}"
        st.code(cmd, language="bash")

# ── Footer ──
st.divider()
col1, col2, col3, col4 = st.columns(4)
with col1:
    if st.button("🏠 Dashboard", use_container_width=True):
        st.switch_page("streamlit_app.py")
with col2:
    if st.button("📝 Translate", use_container_width=True):
        st.switch_page("pages/2_Translate.py")
with col3:
    if st.button("📊 Progress", use_container_width=True):
        st.switch_page("pages/3_Progress.py")
with col4:
    if st.button("📚 Glossary", use_container_width=True):
        st.switch_page("pages/4_Glossary_Editor.py")
