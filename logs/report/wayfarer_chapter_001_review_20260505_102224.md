# Translation Quality Report

## 📋 File Info
- **Output file**: `data/output/wayfarer/wayfarer_chapter_001.mm.md`
- **Novel**: wayfarer
- **Chapter**: 1
- **Pipeline**: unknown
- **Model**: unknown
- **Duration**: 0s
- **Reviewed at**: 2026-05-05T10:22:24.032565

## 📊 Overall Score: 40/100

| Status | Count |
|--------|-------|
| ✅ Passed | 13 |
| ⚠️ Warnings | 2 |
| 🔴 Critical | 3 |

## 📋 Detailed Checks

| Check | Result | Deduction | Details |
|-------|--------|-----------|---------|
| Fluency Score | ✅ | -0 | 95/100 — Excellent |
| Myanmar Ratio | ✅ | -0 | 97.5% — PASS |
| Chinese Leakage | ✅ | -0 | No leakage |
| Bengali Leakage | ✅ | -0 | No leakage |
| Thai Leakage | 🔴 | -5 | 7 characters found |
| Korean Leakage | ✅ | -0 | No leakage |
| Latin/English Leakage | ✅ | -0 | 0 words — acceptable |
| H1 Count | ✅ | -0 | 1 heading |
| Bold Balance | ✅ | -0 | Even ** count |
| Chapter Title Format | ✅ | -0 | Proper format |
| Content Completeness | ✅ | -0 | 14617 chars, no errors |
| Paragraph Structure | ✅ | -0 | 90 breaks, 83 content lines |
| Archaic Words | ⚠️ | -10 | Found: ဤ(1), ထို(20) — use modern alternatives |
| Particle Repetition | 🔴 | -10 | 1 phrase loop(s): " ကျွန်တော့…" ×5 |
| Register Consistency | ✅ | -0 | Register appears consistent |
| Sentence Length | ✅ | -0 | No overlong sentences |
| Sentence Enders | 🔴 | -10 | 22 lines without sentence-enders — significant truncation |
| Paragraph Duplication | ⚠️ | -25 | 5 duplicated paragraph boundary(ies) found — chunk overlap artifact |

## 🔴 CRITICAL ISSUES (Must Fix)
- [ ] 7 characters found
- [ ] 1 phrase loop(s): " ကျွန်တော့…" ×5
- [ ] 22 lines without sentence-enders — significant truncation

## 🟡 WARNINGS (Should Fix)
- [ ] Found: ဤ(1), ထို(20) — use modern alternatives
- [ ] 5 duplicated paragraph boundary(ies) found — chunk overlap artifact

## 🟢 PASSED CHECKS
- Fluency Score: 95/100 — Excellent
- Myanmar Ratio: 97.5% — PASS
- Chinese Leakage: No leakage
- Bengali Leakage: No leakage
- Korean Leakage: No leakage
- Latin/English Leakage: 0 words — acceptable
- H1 Count: 1 heading
- Bold Balance: Even ** count
- Chapter Title Format: Proper format
- Content Completeness: 14617 chars, no errors
- Paragraph Structure: 90 breaks, 83 content lines
- Register Consistency: Register appears consistent
- Sentence Length: No overlong sentences

## 📝 AGENT TODO
🔴 Fix critical issues first:
  - 7 characters found
  - 1 phrase loop(s): " ကျွန်တော့…" ×5
  - 22 lines without sentence-enders — significant truncation
🟡 Address warnings:
  - Found: ဤ(1), ထို(20) — use modern alternatives
  - 5 duplicated paragraph boundary(ies) found — chunk overlap artifact
❌ Overall score 40/100 — NEEDS FIX
