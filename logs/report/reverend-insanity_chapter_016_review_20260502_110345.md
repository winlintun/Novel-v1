# Translation Quality Report

## 📋 File Info
- **Output file**: `data/output/reverend-insanity/reverend-insanity_chapter_016.mm.md`
- **Novel**: reverend-insanity
- **Chapter**: 16
- **Pipeline**: single_stage
- **Model**: padauk-gemma:q8_0
- **Duration**: 4496s
- **Reviewed at**: 2026-05-02T11:03:45.307009

## 📊 Overall Score: 73/100

| Status | Count |
|--------|-------|
| ✅ Passed | 13 |
| ⚠️ Warnings | 4 |
| 🔴 Critical | 0 |

## 📋 Detailed Checks

| Check | Result | Deduction | Details |
|-------|--------|-----------|---------|
| Myanmar Ratio | ✅ | -0 | 99.5% — PASS |
| Chinese Leakage | ✅ | -0 | No leakage |
| Bengali Leakage | ✅ | -0 | No leakage |
| Thai Leakage | ✅ | -0 | No leakage |
| Korean Leakage | ✅ | -0 | No leakage |
| Latin/English Leakage | ✅ | -0 | 0 words — acceptable |
| H1 Count | ✅ | -0 | 1 heading |
| Bold Balance | ✅ | -0 | Even ** count |
| Chapter Title Format | ⚠️ | -2 | Title has ':' — should be H1 on its own line |
| Content Completeness | ✅ | -0 | 9889 chars, no errors |
| Paragraph Structure | ✅ | -0 | 52 breaks, 50 content lines |
| Archaic Words | ⚠️ | -10 | Found: ဤ(11), ထို(19) — use modern alternatives |
| Particle Repetition | ✅ | -0 | No hallucination loops |
| Register Consistency | ⚠️ | -10 | Mixed registers: 135 formal + 45 casual particles |
| Sentence Length | ✅ | -0 | No overlong sentences |
| Sentence Enders | ⚠️ | -5 | 6 lines without sentence-enders — possible truncation |
| Paragraph Duplication | ✅ | -0 | No duplicated paragraphs |

## 🟡 WARNINGS (Should Fix)
- [ ] Title has ':' — should be H1 on its own line
- [ ] Found: ဤ(11), ထို(19) — use modern alternatives
- [ ] Mixed registers: 135 formal + 45 casual particles
- [ ] 6 lines without sentence-enders — possible truncation

## 🟢 PASSED CHECKS
- Myanmar Ratio: 99.5% — PASS
- Chinese Leakage: No leakage
- Bengali Leakage: No leakage
- Thai Leakage: No leakage
- Korean Leakage: No leakage
- Latin/English Leakage: 0 words — acceptable
- H1 Count: 1 heading
- Bold Balance: Even ** count
- Content Completeness: 9889 chars, no errors
- Paragraph Structure: 52 breaks, 50 content lines
- Particle Repetition: No hallucination loops
- Sentence Length: No overlong sentences
- Paragraph Duplication: No duplicated paragraphs

## 📝 AGENT TODO
🟡 Address warnings:
  - Title has ':' — should be H1 on its own line
  - Found: ဤ(11), ထို(19) — use modern alternatives
  - Mixed registers: 135 formal + 45 casual particles
  - 6 lines without sentence-enders — possible truncation
✅ Overall score 73/100 — PASS
