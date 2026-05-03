# Translation Quality Rules — Myanmar (Burmese) Novel Output

> This file is the **single source of truth** for post-translation quality review.
> Agents MUST check every rule below against the output file and report violations.

---

## 🔢 QUANTITATIVE CHECKS (Auto-Detectable by Script)

### Q1: Myanmar Character Ratio
| Metric | Threshold | Status |
|--------|-----------|--------|
| Myanmar ratio ≥ 70% | `myanmar_chars / total_chars` | ✅ PASS |
| Myanmar ratio 30-70% | — | ⚠️ NEEDS_REVIEW |
| Myanmar ratio < 30% | — | ❌ REJECTED |

**Check method**: Count chars in U+1000–U+109F, U+AA60–U+AA7F, U+A9E0–U+A9FF vs total non-whitespace

### Q2: Foreign Script Leakage
| Script | Unicode Range | Threshold |
|--------|--------------|-----------|
| Chinese | U+4E00–U+9FFF, U+3400–U+4DBF | 0 (any = REJECT) |
| Bengali | U+0980–U+09FF | 0 (any = REJECT) |
| Thai | U+0E00–U+0E7F | 0 (any = REJECT) |
| Korean | U+AC00–U+D7FF | 0 (any = REJECT) |
| Arabic | U+061F | 0 (any = REJECT) |

### Q3: English/Latin Word Leakage
| Metric | Threshold | Status |
|--------|-----------|--------|
| 3+ letter Latin words | ≤ 5 | ✅ PASS |
| English common words (the/and/for/are...) | ≤ 5 | ✅ PASS |
| English words > 30% of total | — | ⚠️ WARNING |

### Q4: Markdown Structure
| Check | Rule |
|-------|------|
| H1 heading count | Exactly 1 (chapter title) |
| H2 heading count | ≥ 0 (subtitles ok) |
| **bold** pairs | Must be even (balanced) |
| *italic* pairs | Must be even (balanced) |
| Chapter title format | Must match `# အခန်း N` with Myanmar digits |

### Q5: Content Completeness
| Check | Rule |
|-------|------|
| Total characters | ≥ 100 (not empty/summary) |
| Output chars vs input chars | Ratio ≥ 0.3 (not severely truncated) |
| `[TRANSLATION ERROR]` markers | Count = 0 |
| `【?term?】` placeholders | Count ≤ 3 (warn if unresolved) |

### Q6: Paragraph Structure
| Check | Rule |
|-------|------|
| Double-newlines (paragraph breaks) | ≥ 1 (text should have paragraphs) |
| Paragraph-to-break ratio | ≥ 0.3 (reasonable formatting) |
| Single-line file | ❌ FAIL (paragraphs missing) |

---

## 🇲🇲 LINGUISTIC CHECKS (Myanmar Language Quality)

### L1: Archaic Word Detection
```
MUST NOT appear:  သင်သည်, ဤ, ထို, သည်သည်ကို
MUST use instead: မင်း, ဒီ, အဲဒါ, အဲဒီ
```
Rule: Every instance of archaic word = -5 quality points

### L2: Particle Repetition (Hallucination Sentinel)
```
Pattern: (သည်|ကို|မှာ|အတွက်|ဖြင့်|၍){3,}
```
Rule: Same particle appearing ≥ 3 times consecutively = HALLUCINATION LOOP. -10 points.

### L3: SVO → SOV Sentence Structure
```
Chinese SVO:  Subject + Verb + Object
Myanmar SOV:  Subject + Object + Verb
```
Rule: Object MUST appear BEFORE the verb. Object after verb = STRUCTURE ERROR.

### L4: Register Consistency
```
NARRATION register (Formal):   သည်, ၏, သော, ဖြင့်, အတွက်
DIALOGUE register (Spoken):    တယ်, ဘူး, မယ်, မှာ, ရဲ့
```
Rule: Do NOT mix formal and colloquial particles in the same narration block. -10 points.

### L5: Dialogue Pronoun Hierarchy
```
Superior to Inferior:    မင်း, နင်, သင်
Equal:                   မင်း, ခင်ဗျား, ရှင်
Inferior to Superior:    ကျွန်တော် (male), ကျွန်မ (female)
Hostile/Enemy:           နင် (NEVER မင်း for enemy)
Self (casual):           ငါ
```
Rule: Appropriate pronoun based on character status. Mismatch = -10 points.

### L6: Emotional Quality — "Show, Don't Tell"
```
❌ FAIL:   သူ ဝမ်းနည်းသွားတယ်  (abstract "he was sad")
✅ PASS:   သူ့ရင်ထဲမှာ တစ်ခုခုကနဲဖြတ်သွားသလို ဖြစ်မိတယ်  (physical sensation)
```
Rule: Check for abstract emotion words (ဝမ်းနည်း, ပျော်, ဒေါသ) without physical descriptors.

### L7: Sentence Flow & Rhythm
| Scene Type | Sentence Length | Rule |
|------------|----------------|------|
| Action/combat | 3–7 words | Short, punchy |
| Confrontation | Short, drop ခဲ့ | Present tense accusation |
| Narration | 10–18 words | Literary flow |
| Dialogue | Natural spoken length | Informal particles |

Rule: Sentences ≥ 50 words = -3 points each.

### L8: Sentence-Enders
```
Expected enders:   ။ (full stop), ၏ (formal ender), ၊ (comma), " (quote close)
```
Rule: Each paragraph should end with ။ or ၏. Lines ending without ender = possible truncation.

### L9: Glossary Consistency
Rule: All character names, place names, and cultivation terms MUST match `data/glossary.json` exactly.
- Mismatch flag: `【?term?】` placeholder indicates unresolved term
- Phonetic variants not in glossary = ISSUE

### L10: Markdown Formatting
Rule: Chapter heading MUST be:
```
# အခန်း N

## Chapter Title in Myanmar
```
NOT: `# Chapter N: Title` (all on one line)

---

## 📊 QUALITY SCORING MATRIX

| Score Range | Status | Action |
|-------------|--------|--------|
| 90–100 | 🟢 EXCELLENT | Ready to publish |
| 70–89 | 🟢 GOOD | Minor improvements optional |
| 50–69 | 🟡 FAIR | Needs revision (auto-retry) |
| 30–49 | 🟠 POOR | Manual fix required |
| 0–29 | 🔴 BAD | Re-translate entirely |

**PASS threshold: Overall score ≥ 70**

### Scoring Formula
```
total_score = 100
- 5 per archaic word
- 10 per particle hallucination
- 10 per register inconsistency
- 10 per pronoun mismatch  
- 3 per overlong sentence (>50 words)
- 5 per foreign script character
- 15 if Myanmar ratio < 70%
- 30 if Myanmar ratio < 50%
- 10 if paragraph breaks < 2
- 5 per unresolved 【?term?】
```

---

## 🔍 AUTO-REVIEW REPORT FORMAT

The report saved to `logs/report/{novel}_chapter_{N}_review_{timestamp}.md` MUST contain:

```markdown
# Translation Quality Report

## 📋 File Info
- **Output file**: `path/to/output.mm.md`
- **Novel**: {novel_name}
- **Chapter**: {chapter_number}
- **Pipeline**: {pipeline_mode}
- **Model**: {model_name}
- **Duration**: {duration_seconds}s
- **Reviewed at**: {ISO8601}

## 📊 Scores

| Dimension | Score | Status |
|-----------|-------|--------|
| Myanar Ratio | {ratio}% | PASS/WARN/FAIL |
| Markdown Structure | {score}/100 | PASS/FAIL |
| Foreign Script | clean/dirty | PASS/FAIL |
| Archaic Words | {count} found | PASS/WARN |
| Particle Repetition | clean/dirty | PASS/WARN |
| Register Consistency | {pass/fail} | PASS/FAIL |
| Paragraph Structure | {breaks} breaks | PASS/WARN |

## 🔴 CRITICAL ISSUES (Must Fix)
- [ ] Issue 1...
- [ ] Issue 2...

## 🟡 WARNINGS (Should Fix)
- [ ] Issue 1...

## 🟢 PASSED CHECKS
- Check 1...
- Check 2...

## 📝 AGENT TODO
- [ ] Task 1...
- [ ] Task 2...
```

---

## 🚀 USAGE

After translation completes, run:
```bash
opencode run 'review the result file at data/output/{novel}/{file}.mm.md and log file at logs/translation_*.log against working_data/translation_rules.md and report what needs to fix in logs/report/'
```

Or via CLI:
```bash
python -m src.main --review data/output/novel/chapter.mm.md
```
