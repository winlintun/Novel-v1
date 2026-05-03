"""
Markdown Reader — ဘာသာပြန်ဖတ်ရှုသူ
Novel reader UI styled after novel_reader React app (same fonts, colors, typography).
"""

import re
import markdown as md_lib
import streamlit as st
from pathlib import Path
from typing import List, Tuple

st.set_page_config(
    page_title="Reader | ဘာသာပြန်ဖတ်ရှုသူ",
    page_icon="📖",
    layout="wide",
)

# ── Constants ─────────────────────────────────────────────────────────────────
OUTPUT_DIR = Path("data/output")

_FONT_FACE = {
    "myanmarsanpya": (
        "@font-face{font-family:'MyanmarSanpya';"
        "src:local('MyanmarSanpya'),"
        "url('https://cdn.jsdelivr.net/gh/saturngod/myanmar-unicode-fonts@master/docs/KhmerType/MyanmarSanpya.ttf')"
        "format('truetype');font-display:swap;}"
    ),
    "myanmartagu": (
        "@font-face{font-family:'MyanmarTagu';"
        "src:local('MyanmarTagu'),"
        "url('https://cdn.jsdelivr.net/gh/saturngod/myanmar-unicode-fonts@master/docs/KhmerType/MyanmarTagu.ttf')"
        "format('truetype');font-display:swap;}"
    ),
    "masterpiecestadium": (
        "@font-face{font-family:'MasterpieceStadium';"
        "src:local('MasterpieceStadium'),"
        "url('https://cdn.jsdelivr.net/gh/saturngod/myanmar-unicode-fonts@master/docs/masterpiece/MasterpieceStadium.ttf')"
        "format('truetype');font-display:swap;}"
    ),
    "pyidaungsu": (
        "@font-face{font-family:'Pyidaungsu';"
        "src:local('Pyidaungsu'),"
        "url('https://cdn.jsdelivr.net/gh/saturngod/myanmar-unicode-fonts@master/docs/other/Pyidaungsu.ttf')"
        "format('truetype');font-display:swap;}"
    ),
}

_FONT_STACK = {
    "system":           "system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif",
    "myanmarsanpya":    "'MyanmarSanpya',system-ui,sans-serif",
    "myanmartagu":      "'MyanmarTagu',system-ui,sans-serif",
    "masterpiecestadium": "'MasterpieceStadium',system-ui,sans-serif",
    "pyidaungsu":       "'Pyidaungsu',Georgia,serif",
}

_FONT_LABELS = {
    "system":           "System Font",
    "myanmarsanpya":    "Myanmar Sanpya",
    "myanmartagu":      "Myanmar Tagu",
    "masterpiecestadium": "Masterpiece Stadium",
    "pyidaungsu":       "Pyidaungsu",
}

_SIZES = {
    "small":  {"lg": "1rem",    "2xl": "1.25rem", "3xl": "1.5rem"},
    "medium": {"lg": "1.125rem","2xl": "1.5rem",  "3xl": "1.875rem"},
    "large":  {"lg": "1.25rem", "2xl": "1.625rem","3xl": "2rem"},
}

_COLORS = {
    "light": {
        "text":         "#1a1a1a",
        "text_sub":     "#4a4a4a",
        "text_muted":   "#6b6b6b",
        "bg":           "#ffffff",
        "bg_sec":       "#fafafa",
        "bg_elev":      "#ffffff",
        "border":       "#e5e5e5",
        "border_med":   "#d4d4d4",
        "btn_bg":       "#1a1a1a",
        "btn_text":     "#ffffff",
        "btn_hover":    "#333333",
        "sidebar_bg":   "#fafafa",
        "sidebar_text": "#1a1a1a",
    },
    "dark": {
        "text":         "#e5e5e5",
        "text_sub":     "#b5b5b5",
        "text_muted":   "#949494",
        "bg":           "#1a1a1a",
        "bg_sec":       "#0f0f0f",
        "bg_elev":      "#262626",
        "border":       "#404040",
        "border_med":   "#525252",
        "btn_bg":       "#e5e5e5",
        "btn_text":     "#1a1a1a",
        "btn_hover":    "#ffffff",
        "sidebar_bg":   "#0f0f0f",
        "sidebar_text": "#e5e5e5",
    },
}


# ── CSS builder ───────────────────────────────────────────────────────────────

def _build_css(theme: str, font_key: str, size_key: str) -> str:
    font_face = _FONT_FACE.get(font_key, "")
    ff = _FONT_STACK.get(font_key, _FONT_STACK["system"])
    sz = _SIZES.get(size_key, _SIZES["medium"])

    def _theme_block(c: dict) -> str:
        return f"""
        .stApp {{
            background-color: {c["bg"]} !important;
        }}
        section[data-testid="stSidebar"] > div:first-child {{
            background-color: {c["sidebar_bg"]} !important;
        }}
        section[data-testid="stSidebar"] .stMarkdown,
        section[data-testid="stSidebar"] label,
        section[data-testid="stSidebar"] p,
        section[data-testid="stSidebar"] span {{
            color: {c["sidebar_text"]} !important;
        }}
        .rd-page {{
            background-color: {c["bg"]};
            color: {c["text"]};
        }}
        .rd-info {{
            background-color: {c["bg_elev"]};
            border-bottom-color: {c["border"]};
            color: {c["text_muted"]};
        }}
        .rd-content h1 {{
            color: {c["text"]};
            border-bottom-color: {c["border"]};
        }}
        .rd-content h2 {{
            color: {c["text"]};
            border-bottom-color: {c["border"]};
        }}
        .rd-content h3 {{ color: {c["text"]}; }}
        .rd-content p   {{ color: {c["text"]}; }}
        .rd-content em  {{ color: {c["text_sub"]}; }}
        .rd-content strong {{ color: {c["text"]}; }}
        .rd-content hr  {{ border-top-color: {c["border"]}; }}
        .rd-content blockquote {{
            border-left-color: {c["border_med"]};
            background: {c["bg_sec"]};
            color: {c["text_sub"]};
        }}
        .rd-nav-btn {{
            background-color: {c["btn_bg"]} !important;
            color: {c["btn_text"]} !important;
            border-color: {c["btn_bg"]} !important;
        }}
        .rd-nav-btn:hover {{
            background-color: {c["btn_hover"]} !important;
            border-color: {c["btn_hover"]} !important;
        }}
        """

    if theme == "system":
        light_block = _theme_block(_COLORS["light"])
        dark_block  = _theme_block(_COLORS["dark"])
        theme_css = f"""
        {light_block}
        @media (prefers-color-scheme: dark) {{
            {dark_block}
        }}
        """
    else:
        theme_css = _theme_block(_COLORS[theme])

    return f"""
<style>
{font_face}

/* ── Reader page wrapper ── */
.rd-page {{
    max-width: 800px;
    margin: 0 auto;
    padding: 0 1.25rem 5rem;
    font-family: {ff};
    line-height: 1.75;
}}

/* ── Info bar ── */
.rd-info {{
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 0;
    border-bottom: 1px solid #e5e5e5;
    margin-bottom: 1.5rem;
    font-size: 0.875rem;
    font-family: {ff};
}}

/* ── Chapter content ── */
.rd-content {{
    font-family: {ff};
    font-size: {sz["lg"]};
    line-height: 1.75;
    word-wrap: break-word;
}}

.rd-content h1 {{
    text-align: center;
    font-size: {sz["3xl"]};
    margin: 2rem 0 1.5rem;
    font-weight: 700;
    line-height: 1.25;
    padding-bottom: 1rem;
    border-bottom: 1px solid #e5e5e5;
    font-family: {ff};
}}

.rd-content h2 {{
    font-size: {sz["2xl"]};
    margin: 0.25rem 0 1.5rem;
    font-weight: 600;
    line-height: 1.25;
    text-align: center;
    border-bottom: 1px solid #e5e5e5;
    padding-bottom: 0.75rem;
    font-family: {ff};
}}

.rd-content h3 {{
    font-size: {sz["lg"]};
    margin: 1.25rem 0 0.75rem;
    font-weight: 600;
    font-family: {ff};
}}

.rd-content p {{
    margin-bottom: 1.25rem;
    text-align: justify;
    font-size: {sz["lg"]};
    font-family: {ff};
}}

.rd-content img {{
    max-width: 100%;
    height: auto;
    margin: 1.25rem auto;
    display: block;
    border-radius: 6px;
}}

.rd-content blockquote {{
    border-left: 3px solid #d4d4d4;
    padding: 0.75rem 1rem;
    margin: 1rem 0;
    font-style: italic;
    border-radius: 0 4px 4px 0;
}}

.rd-content hr {{
    border: none;
    border-top: 1px solid #e5e5e5;
    margin: 2rem 0;
}}

/* ── Navigation buttons ── */
.rd-nav-btn {{
    display: inline-block;
    padding: 0.625rem 1.5rem;
    border-radius: 8px;
    font-size: {sz["lg"]};
    font-weight: 500;
    font-family: {ff};
    cursor: pointer;
    transition: opacity 0.15s ease, transform 0.15s ease;
    box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    border: 2px solid transparent;
    text-decoration: none;
}}

/* ── Placeholder warning ── */
.rd-placeholder-warn {{
    background: #fff3cd;
    border: 1px solid #ffc107;
    border-radius: 6px;
    padding: 8px 14px;
    margin: 0 0 1rem;
    font-size: 0.875rem;
    color: #856404;
}}

/* ── Streamlit overrides ── */
div.block-container {{ padding-top: 1rem !important; padding-bottom: 0 !important; }}
div[data-testid="stHorizontalBlock"] {{ gap: 0.75rem; }}

/* ── Bottom nav Streamlit button override ── */
div[data-testid="stHorizontalBlock"] button {{
    border-radius: 8px !important;
    font-family: {ff} !important;
    font-size: {sz["lg"]} !important;
    font-weight: 500 !important;
    padding: 0.625rem 1rem !important;
    transition: all 0.15s ease !important;
}}

{theme_css}
</style>
"""


# ── Helper functions ──────────────────────────────────────────────────────────

def discover_novels() -> List[str]:
    if not OUTPUT_DIR.exists():
        return []
    return sorted(
        d.name for d in OUTPUT_DIR.iterdir()
        if d.is_dir() and list(d.glob("*.mm.md"))
    )


def discover_chapters(novel: str) -> List[Tuple[int, str, str, Path]]:
    """Return sorted (num, title, subtitle, path) for every translated chapter."""
    novel_dir = OUTPUT_DIR / novel
    if not novel_dir.exists():
        return []

    chapters = []
    for f in novel_dir.glob("*.mm.md"):
        stem = f.stem.replace(".mm", "")
        m = re.search(r'[_\s]*(\d{2,4})$', stem) or re.search(r'(\d+)', stem)
        if not m:
            continue
        num = int(m.group(1))
        title, subtitle = _extract_headings(f)
        chapters.append((num, title, subtitle, f))

    return sorted(chapters, key=lambda x: x[0])


def _extract_headings(path: Path) -> Tuple[str, str]:
    """Read the first H1 and H2 from a chapter file."""
    try:
        with open(path, "r", encoding="utf-8-sig") as fh:
            lines = fh.read().splitlines()
    except Exception:
        return "", ""

    title = subtitle = ""
    for line in lines[:25]:
        s = line.strip()
        if not title and s.startswith("# "):
            title = s[2:].strip()
        elif not subtitle and s.startswith("## "):
            subtitle = s[3:].strip()
        if title and subtitle:
            break
    return title, subtitle


def _load_chapter(path: Path) -> str:
    try:
        with open(path, "r", encoding="utf-8-sig") as fh:
            return fh.read()
    except UnicodeDecodeError:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()


def _preprocess(content: str) -> str:
    try:
        from src.utils.postprocessor import (
            _split_into_lines_if_needed,
            fix_chapter_heading_format,
            remove_duplicate_headings,
        )
        content = _split_into_lines_if_needed(content)
        content = fix_chapter_heading_format(content)
        content = remove_duplicate_headings(content)
    except Exception:
        pass
    return content


def _to_html(content: str) -> str:
    return md_lib.markdown(
        content,
        extensions=["nl2br", "sane_lists", "tables"],
    )


def _chapter_label(num: int, title: str, subtitle: str) -> str:
    if title:
        return f"{title}" + (f"  —  {subtitle}" if subtitle else "")
    return f"အခန်း {num}"


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 📚 ဝတ္ထုရွေးချယ်ရန်")

    novels = discover_novels()
    if not novels:
        st.warning("No translated files found. Translate a chapter first.")
        st.stop()

    # ── Novel selector ──
    saved_novel = st.session_state.get("reader_novel", novels[0])
    novel_idx   = novels.index(saved_novel) if saved_novel in novels else 0
    selected_novel = st.selectbox("Novel | ဝတ္ထု", novels, index=novel_idx, key="reader_novel")

    # ── Chapter list ──
    chapters = discover_chapters(selected_novel)
    if not chapters:
        st.warning(f"No translated chapters for **{selected_novel}**.")
        st.stop()

    chapter_nums   = [c[0] for c in chapters]
    chapter_labels = [_chapter_label(c[0], c[1], c[2]) for c in chapters]

    saved_ch = st.session_state.get("reader_chapter", chapter_nums[0])
    cur_idx  = chapter_nums.index(saved_ch) if saved_ch in chapter_nums else 0

    selected_label = st.selectbox("မာတိကာ", chapter_labels, index=cur_idx, key="reader_chapter_select")
    sel_idx = chapter_labels.index(selected_label)
    st.session_state.reader_chapter = chapter_nums[sel_idx]
    chapter_path = chapters[sel_idx][3]

    # ── Prev / Next ──
    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        if sel_idx > 0 and st.button("◀ ရှေ့", use_container_width=True):
            st.session_state.reader_chapter = chapter_nums[sel_idx - 1]
            st.rerun()
    with c2:
        if sel_idx < len(chapters) - 1 and st.button("နောက် ▶", use_container_width=True):
            st.session_state.reader_chapter = chapter_nums[sel_idx + 1]
            st.rerun()

    # ── Settings ──
    st.markdown("---")
    st.markdown("**⚙️ ဖတ်ရှုမှုဆိုင်ရာ**")

    theme = st.radio(
        "Theme",
        ["light", "dark", "system"],
        format_func=lambda x: {"light": "☀️ Light", "dark": "🌙 Dark", "system": "🖥 System"}[x],
        index=["light", "dark", "system"].index(
            st.session_state.get("reader_theme", "light")
        ),
        key="reader_theme",
        horizontal=True,
    )

    font_key = st.radio(
        "Font | စာလုံးပုံစံ",
        list(_FONT_LABELS.keys()),
        format_func=lambda x: _FONT_LABELS[x],
        index=list(_FONT_LABELS.keys()).index(
            st.session_state.get("reader_font_key", "pyidaungsu")
        ),
        key="reader_font_key",
    )

    size_key = st.radio(
        "Font Size | စာလုံးအရွယ်",
        ["small", "medium", "large"],
        format_func=lambda x: {"small": "🔡 Small", "medium": "🔤 Medium", "large": "🔠 Large"}[x],
        index=["small", "medium", "large"].index(
            st.session_state.get("reader_size_key", "medium")
        ),
        key="reader_size_key",
        horizontal=True,
    )

    # ── File info ──
    st.markdown("---")
    fsize = chapter_path.stat().st_size
    st.caption(f"📄 {chapter_path.name}")
    st.caption(f"📏 {fsize/1024:.1f} KB" if fsize > 1024 else f"📏 {fsize} B")


# ── Inject CSS ────────────────────────────────────────────────────────────────
st.markdown(_build_css(theme, font_key, size_key), unsafe_allow_html=True)


# ── Load & render chapter ─────────────────────────────────────────────────────
content = _load_chapter(chapter_path)
content = _preprocess(content)
html    = _to_html(content)

ch_num   = chapters[sel_idx][0]
ch_title = chapters[sel_idx][1] or f"အခန်း {ch_num}"
safe_novel = selected_novel.replace("<", "&lt;").replace(">", "&gt;")

# Info bar
st.markdown(
    f'<div class="rd-page">'
    f'  <div class="rd-info">'
    f'    <span>📖 {ch_title}</span>'
    f'    <span style="flex:1"></span>'
    f'    <span>{len(content):,} chars</span>'
    f'  </div>',
    unsafe_allow_html=True,
)

# Placeholder warning
if "【?term?" in content:
    st.markdown(
        '<div class="rd-placeholder-warn">'
        "⚠️ This chapter contains unreviewed <strong>【?term?】</strong> placeholders. "
        "Review the Glossary page to resolve them."
        "</div>",
        unsafe_allow_html=True,
    )

# Chapter content
st.markdown(
    f'<div class="rd-content">{html}</div>'
    f'</div>',  # closes .rd-page
    unsafe_allow_html=True,
)

# ── Bottom navigation ─────────────────────────────────────────────────────────
st.markdown("---")
b1, b2 = st.columns(2)
with b1:
    if sel_idx > 0:
        prev_title = chapters[sel_idx - 1][1] or f"အခန်း {chapters[sel_idx-1][0]}"
        if st.button(f"◀  {prev_title}", use_container_width=True, key="nav_prev_bottom"):
            st.session_state.reader_chapter = chapter_nums[sel_idx - 1]
            st.rerun()
with b2:
    if sel_idx < len(chapters) - 1:
        next_title = chapters[sel_idx + 1][1] or f"အခန်း {chapters[sel_idx+1][0]}"
        if st.button(f"{next_title}  ▶", use_container_width=True, key="nav_next_bottom"):
            st.session_state.reader_chapter = chapter_nums[sel_idx + 1]
            st.rerun()
