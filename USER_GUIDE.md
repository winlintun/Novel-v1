# User Guide — Novel Translation Pipeline

## Quick Start

### Setup
```bash
pip install -r requirements.txt
ollama pull padauk-gemma:q8_0
ollama pull alibayram/hunyuan:7b
```

Place chapter files in `data/input/{novel_name}/`:
```
data/input/reverend-insanity/
├── reverend-insanity_chapter_001.md
├── reverend-insanity_chapter_002.md
└── ...
```

Supported file naming patterns (auto-detected):
- `{novel}_chapter_{XXX}.md`
- `{XXX}.md` (3-digit)
- `{novel}_{XXX}.md` (3 or 4-digit)

### Basic Translation
```bash
# Single chapter (auto-detects English vs Chinese)
python -m src.main --novel reverend-insanity --chapter 1

# Chapter range
python -m src.main --novel reverend-insanity --chapter-range 1-10

# All chapters
python -m src.main --novel reverend-insanity --all

# Starting from a specific chapter
python -m src.main --novel reverend-insanity --all --start 5
```

---

## Translation Workflows

The system auto-detects the source language and picks the right workflow:

### way1 — English → Myanmar (direct)
For English source files. Uses `padauk-gemma:q8_0` for all stages.
```bash
python -m src.main --novel reverend-insanity --chapter 1 --workflow way1
```

### way2 — Chinese → English → Myanmar (pivot)
For Chinese source files. Stage 1 uses `alibayram/hunyuan:7b` (CN→EN), Stage 2 uses `padauk-gemma:q8_0` (EN→MM).
```bash
python -m src.main --novel reverend-insanity --chapter 1 --workflow way2
```

**Auto-detection**: Omit `--workflow` and the system auto-detects:
```bash
python -m src.main --novel reverend-insanity --chapter 1   # auto-detects
python -m src.main --novel reverend-insanity --chapter 1 --lang zh  # hint
```

---

## Pipeline Modes

| Mode | Stages | Speed | Quality |
|------|--------|-------|---------|
| `full` | 1–6 (translate→refine→reflect→quality→consistency→QA) | Slow | Highest |
| `single_stage` | 1 only (translate) | Fast | Good (padauk-gemma) |
| `lite` | 1 + 2 (translate + refine) | Medium | Better |
| `fast` | Optimized single-stage | Fastest | Good |

```bash
python -m src.main --novel reverend-insanity --chapter 1 --mode single_stage
python -m src.main --novel reverend-insanity --all --mode fast
```

---

## Quality & Review

### Review a Translated Chapter
Generates a detailed quality report in `logs/report/`:
```bash
python -m src.main --review data/output/reverend-insanity/reverend-insanity_chapter_001.mm.md
```

Report checks:
- Myanmar ratio (≥70%)
- Foreign script leakage (Chinese, Bengali, Thai, Korean, Indic)
- Latin/English word leakage
- Markdown structure (headings, bold/italic)
- Content completeness (char count, placeholders)
- Paragraph structure (breaks, readability)
- Archaic words (ဤ, ထို, သင်သည်)
- Particle repetition (hallucination detection)
- Register consistency (formal vs casual)
- Fluency score (7-dimension heuristic)

### Quality Score Trends
Shows per-chapter scores, bar chart, and trend analysis:
```bash
python -m src.main --stats --novel reverend-insanity
```

Output includes:
- Per-chapter score, pass/warn/critical counts, duration
- Score bar chart (█ = score/5)
- Trend analysis (improving/degrading/stable)
- First half vs second half comparison

### View Translated File in Terminal
```bash
python -m src.main --view data/output/reverend-insanity/reverend-insanity_chapter_001.mm.md
```

---

## Glossary Management

### Generate Glossary from Chapters
Scans chapters and extracts proper nouns, cultivation terms, names:
```bash
python -m src.main --novel reverend-insanity --generate-glossary --chapter-range 1-5
```

### Auto-Promote Pending Terms
Promotes high-confidence terms (confidence ≥ 0.85, seen in ≥ 3 chapters):
```bash
python -m src.main --auto-promote --novel reverend-insanity
```

### Manual Glossary Workflow
1. Translation runs → new terms go to `data/glossary_pending_{novel}.json`
2. Review pending terms (edit status to `"approved"`)
3. Next translation run auto-promotes approved terms to `glossary_{novel}.json`

---

## Output Files

### Translated Chapters
```
data/output/{novel}/{novel}_chapter_{XXX}.mm.md    # Myanmar translation
data/output/{novel}/{novel}.mm.meta.json            # Cumulative metadata
```

### Quality Reports
```
logs/report/{novel}_chapter_{XXX}_review_{timestamp}.md
```

### Logs
```
logs/translation.log    # Main translation log
logs/progress/          # Per-chapter progress logs
```

---

## Configuration

Edit `config/settings.yaml`. Key settings:

```yaml
models:
  translator: padauk-gemma:q8_0
  editor: padauk-gemma:q8_0
  checker: qwen:7b
  timeout: 300

processing:
  chunk_size: 2000        # tokens per chunk (paragraph-safe)
  temperature: 0.2        # lower = more deterministic
  repeat_penalty: 1.15    # prevents repetition loops
  max_retries: 2
```

---

## Web UI

6-page Streamlit interface:
```bash
python -m src.main --ui
```

Pages:
- **Quickstart** — 3-step guided wizard for new users
- **Translate** — Configure and launch translations
- **Progress** — Live translation progress + log viewer
- **Glossary Editor** — View, approve, reject pending terms
- **Settings** — Edit model, processing, and output settings
- **Reader** — Browse translated chapters with Myanmar formatting

---

## Tips

### Speed
- Use `single_stage` mode for fastest translation (good quality with padauk-gemma)
- Chunk size 2000 tokens (auto-detected from model context window)
- Per-chunk timeout: 15 minutes (prevents stuck sessions)

### Quality
- Always run `--auto-promote` after adding new terms
- Run `--stats` periodically to track quality trends
- Use `--review` on any output file to get a detailed quality report

### Troubleshooting
```bash
# Clear Python cache
python -m src.main --clean

# Test pipeline with sample data
python -m src.main --test

# Use specific workflow if auto-detect fails
python -m src.main --novel reverend-insanity --chapter 1 --workflow way1
```
