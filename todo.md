Here is the concrete solve-path, split into **immediate recovery** (get chapter 1 clean) and **upstream prevention** (stop the 60 % reject rate from happening again).

---

## 1. Immediate Recovery — Re-Run Chapter 1 Through the New Gates

The committed `chapter-my-1.md` is a **pre-fix artifact**. The new `assembly.py` gates will reject it, which is the correct behavior. Do not try to patch the old file; regenerate it.

### Step 1.1 — Force a fresh translation
```bash
python -m src.pipeline.orchestrator \
  --novel my_house_of_horrors \
  --chapter 0001 \
  --force \
  --model padauk-gemma:q8_0
```

The `--force` flag must bypass any resume cache so the 9 previously-failed chunks are re-translated from scratch, not skipped.

### Step 1.2 — Verify the new gates fire correctly
After the run, inspect `metadata.json`:

```bash
cat output/my_house_of_horrors/metadata.json | jq '.assembly'
```

You should see:
- `script_gate_pass: true`
- `completeness_gate_pass: true`
- `dedup_dropped_count: >= 0` (overlap duplicates removed)
- `state: "APPROVED"` **only if** all 15 chunks are `verified`

If `state` is `NEEDS_HUMAN`, inspect `assembly.reason` to see which gate blocked.

### Step 1.3 — Spot-check the output for the old defects
Run a quick validation script on the new `chapter-my-1.md`:

```python
import regex

text = open("output/my_house_of_horrors/chapter-my-1.md").read()

# 1. Foreign script leak check (should return [])
thai = regex.findall(r'\p{Thai}', text)
bengali = regex.findall(r'\p{Bengali}', text)
assert len(thai) == 0, f"Thai leak: {thai}"
assert len(bengali) == 0, f"Bengali leak: {bengali}"

# 2. Unapproved Latin check (only allowlist words allowed)
latin_tokens = regex.findall(r'[A-Za-z]+', text)
allowlist = {"HP", "NPC", "QQ", "ID", "Level"}  # from glossary meta
bad_latin = [t for t in latin_tokens if t not in allowlist]
assert len(bad_latin) == 0, f"Unapproved Latin: {bad_latin}"

# 3. No ASCII art dividers
assert "_______________" not in text

# 4. Hygiene normalization
assert " – " not in text  # en-dash
assert "..." not in text  # triple-dot (should be … or ။)
assert "\u2018" not in text and "\u2019" not in text  # single curly quotes

print("All pre-fix defects absent.")
```

If any assertion fails, the gates are not wired correctly in `orchestrator.py`.

---

## 2. Fix the Root Cause — Model Instability (60 % Reject Rate)

The assembly gates catch pollution, but they do not fix the **why**: `padauk-gemma:q8_0` fails 9/15 chunks. You cannot scale to 100+ chapters with a 60 % reject rate.

### Step 2.1 — Benchmark alternative models on the 9 failed chunks
Extract the 9 failed chunk inputs and run them through candidates:

```bash
# Extract failed chunks from fleet.db or metadata.json
python scripts/extract_failed_chunks.py --chapter 0001 --output benchmark/chunks/

# Run benchmark
python scripts/benchmark_models.py \
  --chunks benchmark/chunks/ \
  --models padauk-gemma:q8_0,gemma4:31b,qwen3.6-27b \
  --output benchmark/results.json
```

**Acceptance criteria for a new model:**
- Reject rate < 15 % (down from 60 %)
- Fallback rate < 20 %
- Zero foreign-script leaks (R-FORBID-05 passes without assembly-gate rescue)
- No chunk length bias (passing chunks should be distributed across short, medium, and long inputs, not clustered at <500 tokens)

### Step 2.2 — If no model passes, shrink the chunk window
The report notes: *"passing chunks cluster at lower token counts."* If `padauk-gemma:q8_0` is your only option, reduce the chunk size:

| Current | Suggested |
|---|---|
| Overlap window ~266–1,869 tokens | Hard cap at **1,200 tokens** with **150-token overlap** |

Smaller chunks = more total chunks, but fewer failures per chunk. The trade-off is acceptable if it drops the reject rate below 15 %.

Update in `config/chunker.json` (or wherever the window is defined):
```json
{
  "max_tokens": 1200,
  "overlap_tokens": 150,
  "min_tokens": 200
}
```

---

## 3. Handle the Specific Blocking Defects

### 3.1 Thai/Bengali leaks (L21, L107)
These were caused by the model hallucinating wrong-script glyphs. The new `R-FORBID-05` + `assembly_script_gate` should catch them, but you should also add a **translator prompt hardening**:

In `prompts/prompt.md`, add an explicit instruction:
```
CRITICAL: Output must use ONLY Myanmar script (U+1000-U+109F). 
Never emit Thai, Bengali, Devanagari, Chinese, or Korean characters.
If you are unsure of a Myanmar spelling, transliterate phonetically 
using Myanmar letters only — never switch scripts.
```

### 3.2 Duplicate scene cards (L175–L185, L181/L183)
The "Midnight Murderer" card was emitted twice because the overlap window split the UI block across two chunks, and each chunk independently rendered the full list.

**Fix in chunker logic:**
Detect UI/list blocks (markdown tables, bullet lists, app interface blocks) and do **not** split inside them. Add a `no_split_inside` rule:

```python
# In chunker.py
NO_SPLIT_PATTERNS = [
    r'^\|.*\|$',           # Markdown tables
    r'^[-•]\s',            # List items
    r'【.*?】',              # UI labels (e.g., 【Scene Card】)
]
```

If a chunk boundary falls inside a matched block, extend the chunk to the end of the block.

### 3.3 Unapproved English heading (L15: `# Chapter 1: Dying House of Horrors`)
The heading was kept verbatim. This is likely because the chunker sent the markdown heading to the translator, and the translator treated it as metadata not to be translated.

**Fix:** Pre-process headings before chunking:
```python
def localize_headings(text):
    # Translate H1/H2 headings using a deterministic template
    text = re.sub(r'^#\s+Chapter\s+(\d+):\s*(.+)$', 
                  r'# အခန်း \1: \2', text)  # Then translate the title
    return text
```

Or simpler: strip headings from the translator input and re-inject translated headings at assembly time.

### 3.4 Glossary drift (Jiujiang → ကျိုကျန်နောက်ဘက် vs ကျိုကျန်)
The body drifted from the glossary canonical form. The verifier catches this with `R-GLOSS-01`, but the fix-mode loop may not be enforcing it strongly enough.

**Harden the fix-mode prompt:**
When `R-GLOSS-01` fires, include the exact glossary entry in the fix prompt:
```
GLOSSARY MISMATCH: "Jiujiang City" must be "ကျိုကျန်မြို့".
Your output used "ကျိုကျန်နောက်ဘက်ခြံ".
Replace with the canonical form: ကျိုကျန်မြို့
```

---

## 4. Verify the Fix End-to-End

After re-running chapter 1, confirm all exit criteria:

| Check | Command / Method | Pass Criteria |
|---|---|---|
| Script gate | `assembly_script_gate()` in metadata | `true` |
| No duplicates | `dedup_dropped_count` in metadata | `0` (or logged and approved) |
| Fleet report | `fleet-report.json` | `stop_the_line: false` |
| Reject rate | `fleet-report.json` | `SPC-REJECT < 15%` |
| Grade | `audit-report.json` | `SPC-GRADE >= 85` (A or A-) |
| Manual spot-check | Read `chapter-my-1.md` L20–L25, L105–L110, L150–L155, L175–L185 | No Thai/Bengali, no `Level`, no duplicate cards, no `___` dividers |

---

## 5. Scaling Decision Gate

**Do not run chapter 2 until:**

1. Chapter 1 re-run produces `stop_the_line: false`.
2. You have decided on either:
   - A better model (gemma4:31b / qwen3.6-27b), or
   - A smaller chunk window for `padauk-gemma:q8_0`.
3. The benchmark from Step 2.1 shows <15 % reject rate on a 5-chapter sample.

If you skip this gate, you will generate more `NEEDS_HUMAN` chapters faster than you can review them.

---

## Summary of Actions

| Priority | Action | Owner | File |
|---|---|---|---|
| P0 | Re-run ch001 with `--force` | You | `orchestrator.py` |
| P0 | Verify assertions pass | You | `validate_chapter.py` (new) |
| P1 | Benchmark models on 9 failed chunks | You | `scripts/benchmark_models.py` |
| P1 | OR shrink chunk window to 1,200 tokens | You | `config/chunker.json` |
| P2 | Harden translator prompt (no foreign scripts) | You | `prompts/prompt.md` |
| P2 | Fix heading localization | You | `chunker.py` / `assembly.py` |
| P2 | Add `no_split_inside` for UI blocks | You | `chunker.py` |
| P3 | Scale to chapter 2+ only after fleet report clears | You | `fleet-report.json` |

