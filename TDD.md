# TDD.md — Test-Driven Development Specification
## Myanmar Novel Translation Pipeline

**Version:** 1.0  
**Test Framework:** pytest (Python)  
**Coverage Target:** ≥ 90% for core pipeline, 100% for rule engine

---

## 1. Testing Philosophy

> "If it cannot be tested, it cannot be merged."

Every component must have:
1. **Unit tests**: Isolated, fast, no I/O
2. **Integration tests**: Component interactions, mocked LLM
3. **Pipeline tests**: End-to-end with fixture chapters
4. **Quality regression tests**: Compare against human reference

Tests run in **3 layers**:
- **Fast** (unit): < 1s per test, run on every save
- **Medium** (integration): < 30s, run before commit
- **Slow** (regression): < 5min, run in CI / nightly

---

## 2. Unit Test Specifications

### 2.1 Pre-Processor Tests (test_preprocessor.py)

#### TEST-CHUNK-001: Basic Scene Chunking
**Input**: Chapter with 8 paragraphs, 2 scene breaks  
**Expected**: 3 chunks, scene break forces new chunk  
**Assert**: `len(chunks) == 3`, `chunks[1].source_text.startswith("---")`

#### TEST-CHUNK-002: Dialogue Block Preservation
**Input**: 4 consecutive dialogue paragraphs  
**Expected**: Single chunk (all dialogue kept together)  
**Assert**: `len(chunk.dialogue_lines) == 4`, `chunk.type == "dialogue-heavy"`

#### TEST-CHUNK-003: Overlap Injection
**Input**: 2 chunks with overlap=1  
**Expected**: Chunk[1] starts with last paragraph of Chunk[0]  
**Assert**: `chunks[1].preceding_overlap == chunks[0].paragraphs[-1]`

#### TEST-CHUNK-004: Min/Max Bounds
**Input**: Chapter with 1 paragraph  
**Expected**: 1 chunk (min bound respected)  
**Assert**: `len(chunks) == 1`, `len(chunks[0].paragraphs) >= min_chunk_paragraphs`

### 2.2 Prompt Builder Tests (test_prompt_builder.py)

#### TEST-PROMPT-001: Glossary Injection Order
**Input**: Glossary with "Haunted House" and "House"  
**Expected**: "Haunted House" injected before "House" (longest first)  
**Assert**: `prompt.index("Haunted House") < prompt.index("House")`

#### TEST-PROMPT-002: Context Window Limit
**Input**: Chunk with 4000 tokens, context with 5000 tokens  
**Expected**: Context summarized/truncated to fit within `max_ctx - 512`  
**Assert**: `estimate_tokens(prompt) <= max_ctx - 512`

#### TEST-PROMPT-003: Few-Shot Selection
**Input**: Chunk type "dialogue_male_informal"  
**Expected**: Few-shot examples from same category prioritized  
**Assert**: `few_shots[0].category == "dialogue_male_informal"`

### 2.3 Post-Processor Tests (test_postprocessor.py)

#### TEST-POST-001: Thinking Tag Stripping
**Input**: `"<think>I need to translate this</think>ဘာသာပြန်ချက်"`  
**Expected**: `"ဘာသာပြန်ချက်"`  
**Assert**: `"<think>" not in output`

#### TEST-POST-002: Quote Normalization
**Input**: `"Hello"` (straight quotes)  
**Expected**: `"Hello"` (Burmese quotes)  
**Assert**: `output.count('"') == 2`

#### TEST-POST-003: Glossary Auto-Fix
**Input**: `"ချန်ဂေါ် လာခဲ့သည်"` (wrong name)  
**Expected**: `"ချန်ဂီ လာခဲ့သည်"`  
**Assert**: `"ချန်ဂီ" in output`, `"ချန်ဂေါ်" not in output`

#### TEST-POST-004: Zero-Width Space Strip
**Input**: `"ဘ​ယ​်"` (with ZWSP)  
**Expected**: `"ဘယ့်"` (without ZWSP)  
**Assert**: `\u200b not in output`

### 2.4 Rule Engine Tests (test_rules.py)

#### TEST-RULE-001: Fatal Rule Blocks Approval
**Input**: Translation with glossary violation  
**Expected**: Verifier returns `pass=false`, severity `fatal`  
**Assert**: `not result.pass`, `result.issues[0].severity == "fatal"`

#### TEST-RULE-002: Auto-Fix Cap
**Input**: Chunk with 15 glossary errors, max_auto_fix=10  
**Expected**: 10 fixed, 5 flagged as errors  
**Assert**: `result.auto_fixed == 10`, `len(result.remaining_issues) == 5`

---

## 3. Integration Test Specifications

### 3.1 End-to-End Pipeline (test_pipeline_e2e.py)

#### TEST-E2E-001: Happy Path
**Input**: `chapter-en-0001.md` (fixture)  
**Config**: Default config with human glossary  
**Mock**: Ollama returns pre-defined Burmese text  
**Expected**: `chapter-my-0001.md` created with YAML frontmatter  
**Assert**:
- Output file exists
- YAML contains `title`, `grade`
- All glossary terms present
- No English fragments (except proper nouns)

#### TEST-E2E-002: Context Inheritance
**Input**: Chapter with 2 chunks, Chen Ge speaks in both  
**Expected**: Second chunk uses `ငါ` (consistent with first)  
**Assert**: `"ငါ" in chunk2.translated_text`, ContextBuffer updated

#### TEST-E2E-003: Verifier Revision Loop
**Input**: Chunk with intentional glossary error  
**Expected**: Verifier flags → sent back to Translator → fixed → re-verified  
**Assert**: Final chunk passes verification, issue count = 0

### 3.2 Ollama Integration (test_ollama_integration.py)

#### TEST-OLL-001: Model Reachability
**Action**: Ping Ollama `/api/tags`  
**Expected**: HTTP 200, target model in list  
**Assert**: `response.status_code == 200`, `model in response.json()["models"]`

#### TEST-OLL-002: Generation Timeout
**Action**: Request with `timeout=1ms`  
**Expected**: Retry triggered, then fallback  
**Assert**: `retry_count == 3`, final error code `E_TIMEOUT`

#### TEST-OLL-003: Empty Response Handling
**Mock**: Ollama returns `""`  
**Expected**: Retry with temperature 0.5  
**Assert**: Second request has `temperature=0.5`

---

## 4. Quality Regression Tests

### 4.1 Human Reference Comparison (test_regression.py)

#### TEST-REG-001: Glossary Term Recall
**Input**: Human-translated chapter 1  
**Pipeline**: Translate same source  
**Metric**: Term recall = (correct glossary terms) / (total glossary terms)  
**Pass Threshold**: ≥ 98%

#### TEST-REG-002: Style Similarity (Dialogue)
**Metric**: Compare dialogue particle usage ratios  
**Example**: Human uses `ကွာ` 12×, `ဗျာ` 8×. Pipeline should be within ±20%.  
**Pass Threshold**: Ratio difference ≤ 20%

#### TEST-REG-003: Sentence Length Distribution
**Metric**: Average sentence length (in Burmese syllables)  
**Pass Threshold**: Within ±15% of human reference

#### TEST-REG-004: Narration Ending Patterns
**Metric**: Frequency of `လေသည်` vs `ခြင်း ဖြစ်သည်` vs other  
**Pass Threshold**: Distribution within ±25% of human reference

### 4.2 Adversarial Tests

#### TEST-ADV-001: Glossary Poisoning
**Input**: Source with fake name "Chen Gei" (not in glossary)  
**Expected**: Flagged as new term, not translated as "ချန်ဂီ"  
**Assert**: `issues[0].category == "glossary"`, `"Chen Gei" in pending_glossary`

#### TEST-ADV-002: Context Confusion
**Input**: Two characters with same pronoun potential  
**Expected**: Verifier catches if wrong pronoun assigned  
**Assert**: Voice consistency error flagged

#### TEST-ADV-003: Markdown Corruption
**Input**: Source with nested markdown  
**Expected**: Output preserves structure  
**Assert**: `output_md == expected_md` (structurally)

---

## 5. Quality Gates

Each phase has mandatory quality gates:

### Gate 1: Post-Chunk (every chunk)
- [ ] All glossary terms present
- [ ] No untranslated English fragments
- [ ] Markdown structure valid
- [ ] Zero-width spaces removed

### Gate 2: Post-Chapter (after all chunks)
- [ ] Overlap paragraphs identical
- [ ] Scene breaks preserved
- [ ] YAML frontmatter complete
- [ ] Verifier issue count = 0 (fatal), ≤ 3 (warning)

### Gate 3: Post-Audit (final approval)
- [ ] Auditor grade ≥ B
- [ ] Literary quality score ≥ 80
- [ ] Terminology score = 100
- [ ] Human reviewer sign-off (if grade < A)

---

## 6. Test Data Fixtures

### Fixture 1: `fixtures/chapter-en-0001.md`
Actual source file from project. Used in all regression tests.

### Fixture 2: `fixtures/chapter-human-0001.md`
Human-translated reference. Gold standard for comparison.

### Fixture 3: `fixtures/glossary-minimal.json`
Minimal glossary with 5 terms for fast tests.

### Fixture 4: `fixtures/context-sample.json`
Pre-built context buffer for Chapter 1, Scene 2.

### Fixture 5: `fixtures/ollama-responses/`
Directory of mocked Ollama responses for offline testing.

---

## 7. Acceptance Criteria per Phase

### Phase 1 Acceptance
```gherkin
Given a source markdown file
When I run the pipeline with default config
Then a Burmese markdown file is created
And the file contains translated text
And no exceptions are raised
```

### Phase 2 Acceptance
```gherkin
Given a source file with dialogue and narration
When the pipeline completes
Then all glossary terms match the config exactly
And dialogue uses spoken register
And narration uses literary register
And context from chunk N-1 influences chunk N
```

### Phase 3 Acceptance
```gherkin
Given a translated chapter
When the Verifier runs
Then it catches ≥ 90% of intentional glossary errors
When the Auditor runs
Then it assigns a grade correlated ≥ 0.8 with human judgment
```

### Phase 4 Acceptance
```gherkin
Given an MCP client
When it calls `translate_chapter` tool
Then the chapter is translated and audited
And the response contains grade and metadata
```

---

## 8. Regression Test Suite

Run nightly via GitHub Actions / local cron:

```bash
pytest tests/regression/ -v --tb=short   --benchmark-json=benchmark.json   --cov=src --cov-report=xml
```

**Failure Policy**:
- Any regression test fails → Block merge, alert team
- Performance degrades > 10% → Investigate before release
- Glossary recall < 98% → Human audit required

---

## 9. Test Utilities

### `tests/utils/ollama_mock.py`
Mock server mimicking Ollama API. Returns pre-recorded responses based on prompt hash.

### `tests/utils/diff_engine.py`
Compares two Burmese texts semantically (not just string diff). Uses syllable tokenization.

### `tests/utils/term_scanner.py`
Extracts all glossary terms from a Burmese text and reports coverage.

---

*End of TDD.md*
