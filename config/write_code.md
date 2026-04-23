ROLE & OBJECTIVE:
You are an expert AI Software Architect and Python Developer specializing in NLP pipelines, LLM orchestration, and automated novel translation systems. Your task is to generate a complete, modular, production-ready Python pipeline that automates the extraction, memory management, and chapter-by-chapter translation of a Chinese Xianxia novel into Myanmar language using a local Ollama instance.

TECHNICAL CONSTRAINTS:
- Language: Python 3.10+
- LLM Backend: `ollama` Python library (use `ollama.chat`)
- Default Model: `qwen2.5:14b` (fallback to `qwen:7b` if needed)
- Input/Output: Markdown files (`novel_name_XXX.md` → `novel_name_XXX_mm.md`)
- Data Storage: JSON files (`glossary.json`, `character_profiles.json`, `extracted_data.json`, `session_memory.json`)
- Dependencies: Only standard library + `ollama`, `json`, `re`, `os`, `typing`, `logging`. No heavy frameworks.
- Execution: Must run locally, chapter-by-chapter, with robust error handling and retries.

ARCHITECTURE OVERVIEW:
The pipeline must implement a 4-Step Extraction Workflow + a 3-Tier Memory Management System, fully integrated into a chapter-by-chapter translation engine.

STEP 1: SEMANTIC TEXT CHUNKING
- Split raw Chinese text logically by paragraphs or chapter markers (`#`, `##`, `\n\n`). NEVER split mid-sentence.
- Target chunk size: ~1000–1500 tokens.
- Implement a sliding window overlap: Append the last 2–3 sentences of Chunk N to the beginning of Chunk N+1 to prevent cross-boundary entity loss.
- Preserve all Markdown formatting during chunking.

STEP 2: STRICT DATA EXTRACTION PIPELINE
- Create a dedicated LLM extraction function with a strict system prompt.
- Target Categories: characters, cultivation_realms, sects_organizations, items_artifacts.
- STRICT CONSTRAINT: If a category has no data in the chunk, return an empty list `[]`. ZERO hallucination, ZERO guessing. Output ONLY valid JSON.
- Validation Logic:
  1. Strip markdown code blocks (```json ... ```) if present.
  2. Parse JSON safely. Catch `json.JSONDecodeError`.
  3. Verify exactly these 4 root keys exist.
  4. Retry up to 3 times on failure.
- Deduplication & Integration:
  - Load existing JSON databases.
  - Compare new entities by `source_term`. Skip duplicates.
  - If entity exists but new context is found, append to `context_notes` or `aliases_cn`.
  - Save updated JSON safely with atomic writes.

STEP 3: 3-TIER MEMORY MANAGEMENT ARCHITECTURE
Implement a `MemoryManager` class handling:
- Tier 1: Global Memory (Static/Persistent)
  • Source: `glossary.json` & `character_profiles.json`
  • Rule: MUST be loaded and injected into the translation prompt before every chapter. Enforces naming consistency & world-building rules.
- Tier 2: Chapter Context Memory (Short-term/Sliding Window)
  • Structure: FIFO queue (max 5–10 translated paragraphs).
  • Rule: As each paragraph is translated, push to queue, pop oldest. Pass queue content to LLM for pronoun resolution & narrative flow.
- Tier 3: Session Memory (Dynamic/Interactive)
  • Structure: In-memory dict for real-time user corrections & temporary rules.
  • Rule: Applies immediately to next generations. If user approves a correction as permanent, auto-sync to Tier 1 (`glossary.json`).

STEP 4: CHAPTER-BY-CHAPTER TRANSLATION ENGINE
- Process one chapter at a time. Read input `.md`, split into paragraphs.
- For each paragraph:
  1. Inject Tier 1 glossary terms, Tier 2 context buffer, and Tier 3 session rules into the translation prompt.
  2. Call `qwen2.5:14b` via Ollama.
  3. Enforce Myanmar SOV syntax, literary tone for narrative, natural spoken tone for dialogue, and strict Markdown preservation.
  4. Append translated paragraph to output buffer & Tier 2 queue.
- Save final chapter as `novel_name_XXX_mm.md`.

HUMAN-IN-THE-LOOP (HITL) FEEDBACK LOOP:
- After each chapter translation, pause and prompt the user for feedback.
- Parse feedback format: `CORRECT: [CN_TERM] -> [MM_TERM] | NOTE: [context]`
- Update Tier 3 immediately. If user flags as `PERMANENT`, update Tier 1 JSON and reload memory.
- Log all changes to `session_log.txt`.

DATA SCHEMAS & PROMPT TEMPLATES (MUST BE IMPLEMENTED EXACTLY):

1. Extraction JSON Schema:
{
  "characters": [{"source_term": "", "description": "", "first_seen_chapter": 0}],
  "cultivation_realms": [{"source_term": "", "description": "", "first_seen_chapter": 0}],
  "sects_organizations": [{"source_term": "", "description": "", "first_seen_chapter": 0}],
  "items_artifacts": [{"source_term": "", "description": "", "first_seen_chapter": 0}]
}

2. Extraction System Prompt:
"You are an expert Data Extraction AI specializing in Chinese Xianxia/Cultivation novels. Extract ONLY the following entities from the provided text chunk: characters, cultivation_realms, sects_organizations, items_artifacts. If a category has no data, return an empty list []. DO NOT guess, invent, or hallucinate. Output ONLY valid JSON matching the exact schema. No explanations, no markdown wrappers."

3. Translation System Prompt Template:
"You are an expert Chinese-to-Myanmar literary translator. Translate the following paragraph naturally into Myanmar.
RULES:
1. Use Myanmar SOV structure. Break long Chinese sentences into readable Myanmar clauses.
2. Narrative: Formal literary tone. Dialogue: Natural spoken tone matching character status.
3. STRICTLY use the provided Glossary for names/terms. Never transliterate unless specified.
4. Preserve ALL Markdown formatting (#, **, *, etc.).
5. Use the Context Buffer for accurate pronoun resolution (he/she/it).
GLOSSARY: {tier1_glossary}
CONTEXT BUFFER: {tier2_buffer}
SESSION RULES: {tier3_rules}
SOURCE TEXT: {current_paragraph}
OUTPUT ONLY THE TRANSLATED MYANMAR TEXT."
CODE QUALITY & OUTPUT EXPECTATIONS:
- Use OOP design: `TextChunker`, `DataExtractor`, `MemoryManager`, `Translator`, `PipelineOrchestrator`.
- Full type hints, docstrings, and inline comments.
- Robust logging (`logging` module) for chunking, extraction, validation, translation, and memory updates.
- Graceful Ollama API error handling with exponential backoff retries.
- Provide a clear `main()` execution flow that ties all steps together.
- Include example JSON structures and a `config.yaml` or config dict for model names, chunk sizes, and file paths.
- Output MUST be complete, runnable Python code. No placeholders like `# TODO` or `pass`.

STRICT GUARDRAILS:
- NEVER output code that hallucinates data or skips JSON validation.
- NEVER break markdown formatting during translation.
- ALWAYS enforce the 3-tier memory injection before LLM calls.
- ALWAYS deduplicate before writing to JSON.
- DEFAULT MODEL: qwen2.5:14b.

Generate the complete Python pipeline now.