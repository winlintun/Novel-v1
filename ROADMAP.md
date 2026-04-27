# ROADMAP.md - Project Roadmap

> **Note:** For detailed implementation status of individual components, see [CURRENT_STATE.md](CURRENT_STATE.md).

## Project Overview
Chinese-to-Myanmar Wuxia/Xianxia novel translation system with AI-powered multi-agent pipeline.

---

## Priority-Based Roadmap

### 🔴 HIGH PRIORITY (Current Focus)

| Feature | Status | Description | ETA |
|---------|--------|-------------|-----|
| Batch Processing with Queue System | 📋 Planned | Process multiple chapters with job queue management | Q2 2026 |
| SQLite Progress Tracking | 📋 Planned | Persistent tracking of translation progress per novel | Q2 2026 |
| Resume from Failed Chapter | ✅ DONE | Continue translation from where it stopped (via intermediate files) | Q1 2026 |
| Auto Glossary Generation | ✅ DONE | Extract terms from novel automatically | Q1 2026 |

### 🟡 MEDIUM PRIORITY (Next Phase)

| Feature | Status | Description | ETA |
|---------|--------|-------------|-----|
| RAG / Long-term Memory (ChromaDB) | 📋 Planned | Vector database for context-aware translation | Q3 2026 |
| Model Fine-tuning Dataset Export | 📋 Planned | Export translations for model training | Q4 2026 |
| Translation Quality Metrics | 📋 Planned | Automated scoring and quality reports | Q3 2026 |

### 🟢 LOW PRIORITY (Future Ideas)

| Feature | Status | Description | ETA |
|---------|--------|-------------|-----|
| Multi-novel Project Support | 📋 Planned | Manage multiple novels simultaneously | Q4 2026 |
| Translation Memory Sharing | 📋 Planned | Share glossaries across projects | Q4 2026 |
| Mobile-responsive Web UI | 📋 Planned | Better mobile experience for web interface | Q4 2026 |
| Cloud Deployment Scripts | 📋 Planned | Docker/AWS deployment guides | Q4 2026 |

---

## Completed Features Archive

### v1.0 - Core Pipeline
- ✅ Multi-agent translation pipeline (6 stages: Translate → Refine → Reflect → Myanmar Quality → Consistency Check → QA)
- ✅ Translator Agent (Stage 1) - Chinese → Myanmar
- ✅ Editor/Refiner Agent (Stage 2) - Literary quality refinement
- ✅ Reflection Agent (Stage 3) - Self-correction and iterative improvement
- ✅ Myanmar Quality Checker (Stage 4) - Linguistic validation for tone and naturalness
- ✅ Consistency Checker (Stage 5) - Glossary term verification
- ✅ QA Tester Agent (Stage 6) - Automated validation of output quality
- ✅ Glossary and context memory system (3-tier: Glossary → Context → Session)
- ✅ Ollama integration with local models
- ✅ Cloud API support (Gemini, OpenRouter)
- ✅ CLI interface (`src/main.py`)
- ✅ BaseAgent architectural pattern

### v1.1 - Documentation & Testing
- ✅ ROADMAP.md
- ✅ CONTRIBUTING.md
- ✅ GLOSSARY_GUIDE.md
- ✅ Test coverage (229 tests passing)
- ✅ CI/CD Pipeline (GitHub Actions)

### v2.0 - Architecture Refactoring (Major)
- ✅ **Modular Codebase Extraction**: Split monolithic `main.py` (1136 lines) into:
  - `src/cli/` - CLI parser, formatters, commands
  - `src/pipeline/` - TranslationPipeline orchestrator
  - `src/config/` - Pydantic configuration with validation
  - `src/core/` - Dependency injection container
  - `src/types/` - TypedDict definitions
  - `src/web/` - Web launcher utility
  - `src/exceptions.py` - Structured error hierarchy
- ✅ Two-Step Pivot Translation (CN→EN→MM workflow with file persistence)
- ✅ Pivot Translator Agent for native Chinese→English→Myanmar routing
- ✅ Rate Limit Handling with exponential backoff + jitter
- ✅ Multi-Model Router for intelligent model selection
- ✅ Translation Progress Logger with real-time log files
- ✅ Glossary Generator Agent (pre-translation term extraction)
- ✅ Glossary Sync Agent
- ✅ Glossary v3.0 with rich metadata (aliases, exceptions, examples)
- ✅ Linguistic Rules SVO→SOV conversion
- ✅ GPU Support (NVIDIA CUDA and AMD ROCm)

### v2.1 - Web UI & Experience
- ✅ Web UI (Streamlit) - Multi-page interface (Home, Translate, Progress, Glossary, Settings)
- ✅ Progress Dashboard with chapter status visualization
- ✅ Live Log Viewer for real-time translation monitoring
- ✅ Side-by-Side Preview (Basic source/translation comparison)
- ✅ Human-in-the-loop Editing (Integrated Glossary Editor)
- ✅ Myanmar localization for UI elements

---

## File Path Reference

| Component | Path | Purpose |
|-----------|------|---------|
| Main entry | `src/main.py` | CLI dispatcher |
| Web UI app | `ui/streamlit_app.py` | Streamlit multi-page application |
| Web launcher | `src/web/launcher.py` | Programmatic UI launcher utility |
| Config | `config/settings.yaml` | Application configuration |

---

## Contributing
See [CONTRIBUTING.md](CONTRIBUTING.md) for how to contribute to this project.

---

*Last Updated: 2026-04-28*
