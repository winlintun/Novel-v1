"""
Markdown Reader — ဘာသာပြန်ဖတ်ရှုသူ
Comfortable reading of translated .mm.md output files with proper Myanmar rendering.
"""

import re
import streamlit as st
from pathlib import Path
from typing import List, Optional, Tuple

st.set_page_config(
    page_title="Reader | ဘာသာပြန်ဖတ်ရှုသူ",
    page_icon="📖",
    layout="wide",
)

# --- CSS for comfortable reading ---
st.markdown("""
<style>
/* Google Fonts fallback for Myanmar */
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Myanmar:wght@400;600;700&display=swap');

/* Comfortable reading container */
.reader-container {
    max-width: 720px;
    margin: 0 auto;
    padding: 20px 16px;
    font-family: 'Noto Sans Myanmar', 'Padauk', 'Myanmar Text', sans-serif;
    font-size: 17px;
    line-height: 2.0;
    color: #1a1a1a;
}

.reader-container h1 {
    font-family: 'Noto Sans Myanmar', 'Padauk', 'Myanmar Text', sans-serif;
    font-size: 28px;
    font-weight: 700;
    color: #0d1b2a;
    text-align: center;
    margin: 30px 0 10px 0;
    padding-bottom: 12px;
    border-bottom: 2px solid #e0c97f;
}

.reader-container h2 {
    font-family: 'Noto Sans Myanmar', 'Padauk', 'Myanmar Text', sans-serif;
    font-size: 22px;
    font-weight: 600;
    color: #2c3e50;
    text-align: center;
    margin: 8px 0 30px 0;
}

.reader-container h3 {
    font-size: 19px;
    font-weight: 600;
    margin: 24px 0 12px 0;
}

.reader-container p {
    margin: 16px 0;
    text-align: justify;
}

.reader-container em, .reader-container i {
    color: #2c5282;
}

.reader-container strong, .reader-container b {
    color: #1a365d;
}

.reader-container blockquote {
    border-left: 3px solid #e0c97f;
    padding: 10px 16px;
    margin: 16px 0;
    background: #fefcfa;
    font-style: italic;
}

div.block-container {
    padding-top: 2rem;
}

.nav-bar {
    position: sticky;
    top: 0;
    z-index: 100;
    background: rgba(255,255,255,0.95);
    backdrop-filter: blur(8px);
    padding: 10px 16px;
    border-bottom: 1px solid #e2e8f0;
    margin-bottom: 16px;
}

.reader-container hr {
    border: none;
    border-top: 1px solid #e2e0d5;
    margin: 24px 0;
}

.placeholder-warning {
    background: #fff3cd;
    border: 1px solid #ffc107;
    border-radius: 6px;
    padding: 8px 14px;
    margin: 12px 0;
    font-size: 14px;
    color: #856404;
}
</style>
""", unsafe_allow_html=True)

# --- Constants ---
OUTPUT_DIR = Path("data/output")


def discover_novels() -> List[str]:
    """Find novels with translated output files."""
    if not OUTPUT_DIR.exists():
        return []
    novels = []
    for d in OUTPUT_DIR.iterdir():
        if d.is_dir():
            mm_files = list(d.glob("*.mm.md"))
            if mm_files:
                novels.append(d.name)
    return sorted(novels)


def discover_chapters(novel: str) -> List[Tuple[int, Path]]:
    """Get sorted list of (chapter_number, path) for a novel."""
    novel_dir = OUTPUT_DIR / novel
    if not novel_dir.exists():
        return []

    chapters = []
    for f in novel_dir.glob("*.mm.md"):
        stem = f.stem.replace(".mm", "")
        # Extract chapter number: prefer patterns like _0001, _chapter_001, or trailing digits
        m = re.search(r'[_\s]*(\d{2,4})$', stem)
        if not m:
            m = re.search(r'(\d+)', stem)
        if m:
            num = int(m.group(1))
            chapters.append((num, f))

    return sorted(chapters, key=lambda x: x[0])


def load_chapter(path: Path) -> str:
    """Load chapter content with BOM handling and encoding fallback."""
    try:
        with open(path, 'r', encoding='utf-8-sig') as f:
            return f.read()
    except UnicodeDecodeError:
        st.warning(f"Encoding fallback for {path.name}")
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()


def preprocess_content(content: str) -> str:
    """Apply postprocessing fixes for clean display.
    
    Delegates to src.utils.postprocessor which is the single source of truth
    for heading deduplication and collapsed text recovery.
    """
    from src.utils.postprocessor import (
        _split_into_lines_if_needed,
        fix_chapter_heading_format,
        remove_duplicate_headings,
    )
    content = _split_into_lines_if_needed(content)
    content = fix_chapter_heading_format(content)
    content = remove_duplicate_headings(content)
    return content


# --- Sidebar: Novel & Chapter selection ---
with st.sidebar:
    st.markdown("### 📚 ဝတ္ထုရွေးချယ်ရန်")

    novels = discover_novels()
    if not novels:
        st.warning("No translated files found. Translate a chapter first using the **Translate** page.")
        st.stop()

    # Novel selector
    novel_idx = 0
    if "reader_novel" in st.session_state:
        try:
            novel_idx = novels.index(st.session_state.reader_novel)
        except ValueError:
            novel_idx = 0

    selected_novel = st.selectbox(
        "Novel | ဝတ္ထု",
        novels,
        index=novel_idx,
        key="reader_novel_select"
    )
    st.session_state.reader_novel = selected_novel

    # Chapter list
    chapters = discover_chapters(selected_novel)
    if not chapters:
        st.warning(f"No translated chapters for '{selected_novel}'")
        st.stop()

    chapter_labels = [f"အခန်း {num}" for num, _ in chapters]
    chapter_nums = [num for num, _ in chapters]

    # Find current chapter index
    current_chapter = st.session_state.get("reader_chapter", chapter_nums[0])
    try:
        current_idx = chapter_nums.index(current_chapter)
    except ValueError:
        current_idx = 0

    selected_label = st.selectbox(
        "Chapter | အခန်း",
        chapter_labels,
        index=current_idx,
        key="reader_chapter_select"
    )

    selected_idx = chapter_labels.index(selected_label)
    st.session_state.reader_chapter = chapter_nums[selected_idx]
    chapter_path = chapters[selected_idx][1]

    # Navigation buttons
    st.markdown("---")
    col_prev, col_next = st.columns(2)
    with col_prev:
        if selected_idx > 0:
            if st.button("◀ ရှေ့အခန်း", use_container_width=True):
                st.session_state.reader_chapter = chapter_nums[selected_idx - 1]
                st.rerun()
    with col_next:
        if selected_idx < len(chapters) - 1:
            if st.button("နောက်အခန်း ▶", use_container_width=True):
                st.session_state.reader_chapter = chapter_nums[selected_idx + 1]
                st.rerun()

    # Chapter info
    st.markdown("---")
    file_size = chapter_path.stat().st_size
    size_str = f"{file_size / 1024:.1f} KB" if file_size > 1024 else f"{file_size} B"
    st.caption(f"📄 {chapter_path.name}")
    st.caption(f"📏 {size_str}")

    # Dark mode toggle
    dark_mode = st.toggle("🌙 Dark Mode", key="reader_dark")
    font_size = st.slider("Font Size | စာလုံးအရွယ်", 14, 24, 17, key="reader_font_size")


# --- Dark mode styling ---
if dark_mode:
    st.markdown(f"""
    <style>
    .reader-container {{
        background: #1a1a2e;
        color: #e0e0e0;
    }}
    .reader-container h1 {{ color: #e0c97f; border-bottom-color: #e0c97f; }}
    .reader-container h2 {{ color: #ccc; }}
    .reader-container strong {{ color: #e0c97f; }}
    .reader-container em {{ color: #88b4e0; }}
    .reader-container blockquote {{
        background: #16213e;
        border-left-color: #e0c97f;
    }}
    .nav-bar {{
        background: rgba(26,26,46,0.95);
        border-bottom-color: #333;
    }}
    .placeholder-warning {{
        background: #3d2e00;
        border-color: #e0c97f;
        color: #ffd54f;
    }}
    </style>
    """, unsafe_allow_html=True)


# --- Main content: load and render chapter ---
content = load_chapter(chapter_path)
content = preprocess_content(content)

# Safe novel name for display (no HTML injection)
safe_novel = selected_novel.replace("<", "&lt;").replace(">", "&gt;")

# Reading nav bar
st.markdown(
    f'<div class="nav-bar" style="display:flex;align-items:center;gap:12px;">'
    f'<span style="color:#888;font-size:14px;">📖 Chapter {st.session_state.reader_chapter}</span>'
    f'<span style="color:#aaa;font-size:12px;">— {safe_novel}</span>'
    f'<span style="flex:1;"></span>'
    f'<span style="color:#888;font-size:12px;">{len(content):,} chars</span>'
    f'</div>',
    unsafe_allow_html=True
)

# Content font size override
st.markdown(
    f'<style>'
    f'.block-container .stMarkdown p {{ font-size:{font_size}px !important; }}'
    f'.block-container .stMarkdown h1 {{ font-size:{font_size + 10}px !important; }}'
    f'.block-container .stMarkdown h2 {{ font-size:{font_size + 4}px !important; }}'
    f'</style>',
    unsafe_allow_html=True
)

# Warn if placeholder terms present
if '【?term?' in content:
    st.warning(
        '⚠️ This chapter contains unreviewed **【?term?】** placeholders. '
        'Review the glossary to replace them with proper translations.'
    )

# Render markdown in a centered column for comfortable reading
_, col_reader, _ = st.columns([1, 3, 1])
with col_reader:
    st.markdown(content)

# Footer
total_lines = content.count('\n') + 1
st.caption(f"📄 {total_lines:,} lines | {len(content):,} characters")
st.markdown("---")
st.caption("💡 Use the sidebar to switch novels and chapters. Click ◀ ▶ to navigate.")
