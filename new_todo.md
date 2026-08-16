Here's a concrete, prioritized action plan to get your pipeline back on track.

## 1. Immediate Triage: Do Not Run More Chapters
The `stop_the_line: true` flag is correct — **halt all new chapters now**. Running more will only compound the duplication and script-leak debt.

## 2. Fix the Three State-Machine Bugs First
These are causing false confidence and data corruption.

| Bug | What to change in code |
|---|---|
| **A. Verifier feedback gap** | In your `fix-mode` re-translate prompt builder, loop over **all** `critical`/`fatal`/`error` findings from the verifier, not just `R-GLOSS-01`. Concatenate them into the prompt context. |
| **B. False APPROVED** | In the orchestrator's commit logic, add: `if any(chunk.status != 'verified' for chunk in chapter.chunks): chapter.state = 'NEEDS_HUMAN'; chapter.verified = false`. Never let a partially-failed chapter reach `APPROVED`. |
| **C. Failed text leaked into output** | In the assembler, filter before writing: `verified_paragraphs = [p for p in chunks if p.status == 'verified']`. Only assemble verified chunks into `chapter-my-N.md`. |

## 3. Add Assembly-Time Hard Gates
The report shows foreign scripts and duplicates reached the final file. Move validation from **per-chunk only** to **per-chunk + at assembly**.

**Script whitelist gate:**
```python
import regex

def is_pure_myanmar(text):
    # Allowed: Myanmar block + ASCII punctuation/whitespace
    # Reject Thai, Bengali, Latin letters, etc.
    forbidden = regex.findall(r'[^\u1000-\u109F\s\p{P}\p{N}]', text)
    # Allow common ASCII (a-z, A-Z) only if it's inside an approved loanword list
    return len(forbidden) == 0
```

Run this on every paragraph before it hits the `.md` file. If it fails, mark the chunk `NEEDS_HUMAN` rather than committing it.

**Near-duplicate suppression:**
```python
from difflib import SequenceMatcher

def is_near_duplicate(para, prev_paras, threshold=0.85):
    for prev in prev_paras[-3:]:  # check last 3 paragraphs
        if SequenceMatcher(None, para, prev).ratio() > threshold:
            return True
    return False
```

If a paragraph is >85% similar to a recent one, drop it and log the collision.

## 4. Re-Process Chapter 1 Correctly
Before scaling, re-run the 9 failed chunks:

1. Load them in **fix-mode** with the full verifier error list (Bug A fix).
2. Run `clean_my_text()` + `looks_incomplete()` + the new script gate on every output.
3. Assemble only verified chunks (Bug C fix).
4. Force state to `NEEDS_HUMAN` if any chunk still fails (Bug B fix).

## 5. Evaluate Model Alternatives
Your root cause notes that `padauk-gemma:q8_0` is marginal on long inputs. Run a small benchmark:

- Take the same 9 failed chunks.
- Run them through `gemma4:31b` and `qwen3.6-27b` (or whatever larger models you have access to).
- Compare: reject rate, fallback rate, and whether the foreign-script leaks disappear.

If a larger model drops the reject rate below 15%, switch to it for the remaining chapters. If all local models struggle, consider chunking into smaller windows (the passing chunks were lower token-count).

## 6. Re-Run Audit & Fleet Reports
After the re-processed chapter 1 is clean:

1. Regenerate `fleet-report.json` and `audit-report.json`.
2. Confirm:
   - `SPC-REJECT` < 15%
   - `SPC-FALLBACK` < 20%
   - `SPC-GRADE` ≥ 85
   - `stop_the_line: false`
3. Only then proceed to chapter 2.

## 7. Quick Hygiene Fixes
- Normalize punctuation: pick one dash style (EM DASH `—`), one ellipsis (`…`), one quote style (`“ ”`), and enforce them in post-processing.
- Add a post-processor that strips stray ASCII art like `_______________`.
- For loanwords like "Level", add a glossary rule or transliteration mapping so the model doesn't emit raw Latin.

---

**Bottom line:** Fix bugs A→C, add the assembly gates, re-run chapter 1 with the new model candidate, and don't scale until `stop_the_line` clears. The pipeline architecture is sound; the leaks are happening because validation is only half-enforced.