# ROADMAP.md - Project Roadmap

## Project Overview
Chinese-to-Myanmar Wuxia/Xianxia novel translation system with AI-powered multi-agent pipeline.

## Version History

### v1.0 (Current) - Core Pipeline ✅ DONE
- [x] Multi-agent translation pipeline (Translator, Refiner, Checker, ContextUpdater)
- [x] Glossary and context memory system
- [x] Ollama integration with local models
- [x] Cloud API support (Gemini, OpenRouter)
- [x] CLI interface
- [x] BaseAgent refactoring
- [x] Reflection / Self-correction Agent (Integrated)
- [x] Myanmar Quality Checker (Integrated)

### v1.1 - Documentation & UI ✅ DONE
- [x] ROADMAP.md ✅
- [x] CONTRIBUTING.md ✅
- [x] GLOSSARY_GUIDE.md ✅
- [x] Web UI (Streamlit) - Multi-page version ✅
- [x] Better test coverage (Integrated with Agents)

### v2.0 - Automation & Scale (In Progress)
- [x] Auto Glossary Generation ✅
- [ ] Batch Processing with Queue System
- [ ] SQLite Progress Tracking
- [x] Resume from Failed Chapter (Partial via intermediate EN files)

### v2.1 - UI & Experience ✅ DONE
- [x] Web UI (Streamlit) ✅
- [x] Progress Dashboard ✅
- [x] Live Log Viewer ✅
- [x] Side-by-Side Preview (Basic integrated in Translate/Dashboard)

### v3.0 - Intelligence (Planned)
- [ ] RAG / Long-term Memory (ChromaDB)
- [ ] Reflection / Self-correction Agent (Basic integrated)
- [ ] Human-in-the-loop Editing (Integrated in Glossary Editor)
- [ ] Model Fine-tuning Dataset Export

---

## Development Priorities

| Priority | Feature | ETA |
|----------|---------|-----|
| High | Auto Glossary Generation | Q2 2026 |
| High | Web UI (Streamlit) | Q2 2026 |
| Medium | RAG Memory | Q3 2026 |
| Medium | Reflection Agent | Q3 2026 |
| Low | Fine-tuning Dataset | Q4 2026 |

---

## Contributing
See CONTRIBUTING.md for how to contribute to this project.