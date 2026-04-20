# Main_Structure.md

## Project Overview: Chinese-to-Burmese Novel Translation System

This is an **AI-powered novel translation pipeline** that automatically translates Chinese novels into Burmese (Myanmar language). It's specifically designed for translating web novels, wuxia/xianxia stories, and other Chinese literary works while preserving the original tone, style, and emotional depth.

---

## Project Architecture

```
novel_translation_project/
│
├── 📄 Core Application Files
│   ├── main.py                     # Main orchestrator (entry point)
│   ├── web_ui.py                   # Flask web interface for live monitoring
│   ├── translate_novel.py          # Standalone translation script
│   └── translate_manual.py         # Manual translation utility
│
├── 📋 Configuration & Documentation
│   ├── names.json                  # Character/place name mappings (CN→MM)
│   ├── Structure.md                # AI translation thinking log
│   ├── SETUP_GUIDE.md              # Complete setup instructions
│   ├── AGENT.md                    # AI agent role definition
│   ├── SKILL.md                    # Translation skill instructions
│   ├── REVIEWER_AGENT.md           # Code review agent config
│   ├── Makefile                    # Build automation
│   └── requirements.txt            # Python dependencies
│
├── 📂 Input/Output Directories
│   ├── input_novels/               # Drop Chinese novels here (.md/.txt)
│   ├── translated_novels/          # Final Burmese translations (.md)
│   └── chinese_chapters/           # Source novel storage
│
├── 🔧 Scripts/ (Translation Pipeline)
│   ├── preprocessor.py             # Step 1: Clean & normalize text
│   ├── chunker.py                  # Step 2: Split into manageable chunks
│   ├── translator.py               # Step 3: AI translation engine
│   ├── checkpoint.py               # Step 4: Save/resume progress
│   ├── postprocessor.py            # Step 5: Fix names & punctuation
│   ├── assembler.py                # Step 6: Assemble final document
│   └── myanmar_checker.py          # Quality control checker
│
├── 📝 Templates
│   ├── chapter_template.md         # Chapter formatting template
│   └── novel_template.md           # Full novel structure template
│
└── 💾 working_data/ (Temporary Files)
    ├── checkpoints/                # Resume state files
    ├── chunks/                     # Pre-translation text chunks
    ├── translated_chunks/          # Post-translation chunks
    ├── preview/                    # Live preview files
    ├── readability_reports/        # Quality check reports
    ├── logs/                       # Translation logs
    └── clean/                      # Cleaned text files
```

---

## Translation Workflow (7 Steps)

When you run `python main.py`, here's what happens automatically:

```
┌─────────────────────────────────────────────────────────────────┐
│  1. SCAN                                                        │
│     Check input_novels/ for Chinese text files                  │
├─────────────────────────────────────────────────────────────────┤
│  2. PREPROCESS                                                  │
│     Clean text, enforce UTF-8, remove noise                     │
├─────────────────────────────────────────────────────────────────┤
│  3. CHUNK                                                       │
│     Split into 1500-2000 character chunks with overlap          │
├─────────────────────────────────────────────────────────────────┤
│  4. TRANSLATE                                                   │
│     Use AI (Ollama/OpenRouter/Gemini) to translate each chunk     │
├─────────────────────────────────────────────────────────────────┤
│  5. CHECKPOINT                                                  │
│     Save progress after each chunk (can resume anytime)         │
├─────────────────────────────────────────────────────────────────┤
│  6. POSTPROCESS                                                 │
│     Fix character names using names.json, correct punctuation   │
├─────────────────────────────────────────────────────────────────┤
│  7. ASSEMBLE                                                    │
│     Merge all chunks into final formatted Markdown file         │
└─────────────────────────────────────────────────────────────────┘
```

---

## Core Components Details

### 1. Main Orchestrator (main.py)

**Purpose:** Central controller that coordinates the entire translation pipeline.

**Key Functions:**
- Scans `input_novels/` directory for files to translate
- Manages the 7-step workflow
- Handles error recovery with retry logic
- Coordinates with checkpoint system for resume capability
- Integrates with web UI for real-time monitoring

**Configuration Options:**
- Model selection (Ollama, OpenRouter, Gemini, DeepSeek, Qwen)
- Chunk size (100-5000 characters)
- Retry attempts and delays
- Readability check enable/disable

### 2. Web UI (web_ui.py)

**Purpose:** Flask-based web interface for monitoring translation progress.

**Features:**
- Real-time progress tracking at `localhost:5000`
- Live streaming of translated text
- Queue management for multiple novels
- Status indicators (pending, in-progress, completed, failed)
- Manual control (start/stop/resume)

**Technology Stack:**
- Flask web server
- Socket.IO for real-time updates
- WebSocket for live token streaming

### 3. Scripts/ Directory (The Pipeline)

#### preprocessor.py
- **Input:** Raw Chinese text files
- **Output:** Clean, normalized text
- **Functions:**
  - UTF-8 encoding enforcement
  - Remove HTML tags and special characters
  - Normalize whitespace
  - Extract metadata (title, chapter numbers)

#### chunker.py
- **Input:** Clean text
- **Output:** Array of text chunks
- **Functions:**
  - Split text into manageable chunks (default 1800 chars)
  - Maintain paragraph boundaries
  - Add overlap between chunks for context preservation
  - Analyze chunk distribution

#### translator.py
- **Input:** Text chunks + system prompt
- **Output:** Translated Burmese text
- **Functions:**
  - Interface with AI models (Ollama, APIs)
  - Stream tokens for real-time display
  - Handle multiple model providers
  - Retry logic for failed requests
  - System prompt management

#### checkpoint.py
- **Purpose:** Save and resume translation progress
- **Storage:** JSON files in `working_data/checkpoints/`
- **Data Saved:**
  - Current chunk index
  - Total chunks
  - Translated chunks cache
  - Status (in-progress, completed, failed)

#### postprocessor.py
- **Input:** Raw translated text
- **Output:** Polished Burmese text
- **Functions:**
  - Replace Chinese names with Burmese equivalents (using names.json)
  - Fix punctuation (add Burmese sentence endings: ။)
  - Remove artifacts or mixed-language output
  - Validate Myanmar script integrity

#### assembler.py
- **Input:** All translated chunks
- **Output:** Final formatted Markdown file
- **Functions:**
  - Merge chunks in correct order
  - Apply chapter templates
  - Add YAML front matter (metadata)
  - Format chapter headings in Burmese numerals (၁ ၂ ၃)
  - Add source attribution

#### myanmar_checker.py
- **Purpose:** Quality control for translated output
- **Checks:**
  - Myanmar script ratio (≥70%)
  - No Chinese character leakage
  - Valid sentence endings (။)
  - Minimum length validation
  - UTF-8 encoding integrity
- **Output:** Readability reports in JSON format

### 4. Configuration Files

#### names.json
**Purpose:** Dictionary for consistent name translation

**Structure:**
```json
{
  "Chinese_Name": "Burmese_Name",
  "罗青": "လော်ချင်",
  "蟠龙山": "ပန်လုံတောင်",
  "魔教": "မိစ္ဆာဂိုဏ်း"
}
```

**Categories:**
- Character names
- Place names
- Sect/organization names
- Technique/skill names
- Book titles

#### .env / .env.example
**Purpose:** Environment variables for API keys and configuration

**Variables:**
- `AI_MODEL`: Default model selection
- `OPENROUTER_API_KEY`: API key for OpenRouter
- `GEMINI_API_KEY`: API key for Google Gemini
- `DEEPSEEK_API_KEY`: API key for DeepSeek
- `REQUEST_DELAY`: Delay between API requests

### 5. Template System

#### chapter_template.md
**Purpose:** Standardized chapter formatting

**Structure:**
```markdown
# {chapter_title}

---

{chapter_content}

---
*Source: {source_title}*
*Chapter: {chapter_number}*
*Extracted: {timestamp}*
```

#### novel_template.md
**Purpose:** Full novel structure with metadata

**Structure:**
```markdown
---
title: "{burmese_title}"
source_title: "{chinese_title}"
language: Burmese (Myanmar Script)
source_language: Chinese
translated_date: {date}
font_recommendation: "Padauk, Noto Sans Myanmar"
total_chapters: {count}
---

# {burmese_title}

---

## အခန်း {number} — {title}

{content}
```

### 6. Working Data Directory

#### checkpoints/
- JSON files storing translation state
- Enable resume capability
- Format: `{novel_name}.json`

#### chunks/
- Pre-translation text segments
- Original Chinese text divided by chunker
- Format: `{novel_name}_chunk_{number}.txt`

#### translated_chunks/
- Post-translation Burmese segments
- Raw output from translator
- Format: `{novel_name}_translated_{number}.txt`

#### preview/
- Live preview files for in-progress translation
- Updated in real-time during streaming
- Readable at any time during translation

#### readability_reports/
- Quality check results in JSON format
- Per-chunk analysis scores
- Failure flagging and statistics

#### logs/
- Detailed translation logs
- Timestamped events
- Error tracking and debugging info

#### clean/
- Preprocessed, cleaned text files
- Intermediate step between raw input and chunking

---

## Key Features

| Feature | Description |
|---------|-------------|
| **Multi-Model Support** | Works with Ollama (local), OpenRouter, Gemini, DeepSeek, Qwen |
| **Live Web UI** | Real-time progress tracking at `localhost:5000` |
| **Resume Capability** | Can stop and resume translation anytime using checkpoints |
| **Name Consistency** | Maintains consistent character/place names across all chapters |
| **Quality Checking** | Automatic Myanmar script validation and readability scoring |
| **Checkpoint System** | Never lose progress, even if interrupted or system crashes |
| **Batch Processing** | Can queue and translate multiple novels in sequence |
| **Error Recovery** | Automatic retry with exponential backoff |
| **Template System** | Consistent formatting for all output files |
| **Logging** | Comprehensive logs for debugging and auditing |

---

## Language Support

### Source Language
- **Chinese (Simplified)** - Primary target
- **Chinese (Traditional)** - Supported via preprocessing

### Target Language
- **Burmese (Myanmar Script)** - Unicode range U+1000–U+109F
- **Font Recommendations:** Padauk, Noto Sans Myanmar, Myanmar Text

### Name Translation System
The `names.json` file maintains consistency for:
- **Character Names** - Protagonists, antagonists, side characters
- **Place Names** - Mountains, villages, cities, realms
- **Sect/Organization Names** - Cultivation sects, demon cults, orthodox schools
- **Technique Names** - Martial arts, cultivation methods, spells
- **Book/Artifact Names** - Manuals, treasures, legendary items

---

## Technical Stack

### Programming Language
- **Python 3.8+** - Core application language

### Web Framework
- **Flask** - Web server for monitoring interface
- **Flask-SocketIO** - Real-time WebSocket communication

### AI/ML Integration
- **Ollama** - Local LLM runner (supports Qwen, Llama, etc.)
- **OpenRouter API** - Cloud model access (DeepSeek, GPT, Claude)
- **Google Gemini API** - Google's translation models
- **DeepSeek API** - Chinese-specialized models

### Key Dependencies
```
ollama>=0.1.0           # Local AI model runner
flask>=2.0.0            # Web framework
flask-socketio>=5.0.0   # Real-time updates
python-dotenv>=0.19.0   # Environment management
requests>=2.26.0        # HTTP client for APIs
```

### Unicode Support
- Full Myanmar Unicode block support (U+1000–U+109F)
- Chinese Unicode block support (U+4E00–U+9FFF)
- UTF-8 encoding throughout the pipeline

---

## Usage Workflow

### 1. Preparation
```bash
# Place Chinese novel in input directory
cp my_novel.txt input_novels/

# Update name mappings in names.json
# Add new characters, places, sects as needed
```

### 2. Configuration
```bash
# Set environment variables
cp .env.example .env
# Edit .env with API keys and model selection
```

### 3. Execution
```bash
# Run the translation pipeline
python main.py

# Or with specific options
python main.py --model openrouter --max-chars 2000
```

### 4. Monitoring
- Open browser to `http://localhost:5000`
- Watch real-time progress
- View live translation streaming
- Check queue status

### 5. Collection
- Find completed translations in `translated_novels/`
- Readability reports in `working_data/readability_reports/`
- Logs in `working_data/logs/`

---

## Quality Assurance

### Automated Checks
1. **Myanmar Script Ratio** - ≥70% of output must be Myanmar characters
2. **No Chinese Leakage** - Zero Chinese characters allowed in output
3. **Sentence Boundaries** - Must contain valid Myanmar sentence endings (။)
4. **Length Validation** - Output must be ≥30% of input length
5. **Encoding Integrity** - No replacement characters (U+FFFD)

### Manual Review
- Structure.md tracks AI translation thinking
- Logs provide detailed error tracking
- Preview files allow mid-translation reading
- Checkpoint system enables chunk-by-chunk review

---

## Advantages Over Generic Translation Tools

| Aspect | Generic Tools | This System |
|--------|---------------|-------------|
| **Literary Style** | Often literal | Preserves tone and emotion |
| **Consistency** | Variable per request | Maintained via names.json |
| **Xianxia Terms** | Poor handling | Specialized dictionaries |
| **Long Novels** | Timeout/errors | Checkpoint/resume system |
| **Formatting** | Plain text | Structured Markdown |
| **Monitoring** | None | Real-time web UI |
| **Quality Control** | Manual only | Automated checking |

---

## Example Translation Flow

### Input (Chinese)
```
第002章 蟠龙山
罗青左顾右看，四周黑沉沉的，什么也没发现，
但听得耳边风声凛冽，呼呼作响，身子也轻飘飘的，
像是悬浮在半空一般。
```

### Processing Steps
1. **Preprocessor** → Clean text, extract chapter metadata
2. **Chunker** → Split into 1800-char segments
3. **Translator** → AI translates to Burmese
4. **Checkpoint** → Save progress
5. **Postprocessor** → Apply name mappings (罗青→လော်ချင်)
6. **Assembler** → Format with template

### Output (Burmese)
```markdown
# 古道仙鸿 - 第002章 蟠龙山

---

အခန်း ၂ - ပန်လုံတောင်

လော်ချင် ဘယ်ညာရှုကြည့်လိုက်ရာ အရပ်ဝန်းကျင်သည် 
မည်းမှောင်နေပြီး ဘာမှ မတွေ့ရပေ။ သို့သော် နားထဲတွင် 
လေပြင်းတိုက်သံက ပြင်းထန်စွာ ကြားလာပြီး ကိုယ်ခန္ဓာလည်း 
ပေါ့ပါးသွားသကဲ့သို့ ခံစားရပြီး လေထဲတွင် ရပ်တန့်နေသကဲ့သို့ 
ဖြစ်နေသည်။

---
*ရင်းမြစ်- 古道仙鸿*
*အခန်း- 第002章 蟠龙山*
*ထုတ်ယူ- 2026-04-20*
```

---

## Maintenance & Updates

### Regular Tasks
1. **Update names.json** - Add new names for each novel
2. **Review readability reports** - Check for quality issues
3. **Archive completed translations** - Move from translated_novels/
4. **Clean working_data/** - Remove old checkpoints and chunks

### System Updates
1. **Model Updates** - Pull latest Ollama models
2. **Dependency Updates** - Update pip packages
3. **Template Updates** - Modify formatting as needed
4. **Script Improvements** - Enhance pipeline components

---

## Conclusion

This is a **production-ready, end-to-end novel translation system** specifically architected for Chinese-to-Burmese literary translation. It combines AI translation capabilities with robust workflow management, quality assurance, and monitoring tools to handle large-scale novel translation projects efficiently and consistently.

The modular design allows for easy extension to other language pairs, while the checkpoint system ensures reliability for long-running translation tasks.

---

*Last Updated: April 20, 2026*
*Project: Novel Translation System*
*Language Pair: Chinese (Simplified) → Burmese*
