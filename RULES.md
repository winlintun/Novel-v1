# RULES.md — AI Translation Rules & Configuration
## Myanmar Novel Translation Pipeline

**Version:** 1.0  
**Applies To:** Translator Agent, Verifier Agent, Post-Processor  
**Enforcement:** Mandatory (locked rules cannot be overridden by prompt alone)

---

## 1. Rule Taxonomy

Rules are categorized by scope and severity:
- **Scope**: `global` (all text), `dialogue_only`, `narration_only`, `character_specific`
- **Severity**: `fatal` (blocks approval), `error` (must fix), `warning` (should fix), `info` (suggestion)
- **Enforcement**: `auto` (post-processor fixes), `verify` (verifier flags), `audit` (auditor evaluates)

---

## 2. Glossary Enforcement Rules (R-GLOSS-XX)

### R-GLOSS-01 — Exact Term Usage (FATAL)
**Rule**: Every glossary term must appear in output exactly as specified in `glossary.json`.  
**Example**: "Chen Ge" → "ချန်ဂီ" (never "ချန်ဂေါ်", never "ချန်ဂီး")  
**Enforcement**: Auto + Verify  
**Regex Strategy**: Match whole word with word boundaries; longest terms first.

### R-GLOSS-02 — Locked Terms Immutable (FATAL)
**Rule**: Terms with `"locked": true` cannot be translated differently even if context suggests variation.  
**Example**: "Haunted House" is always "သရဲစံအိမ်", never "သရဲအိမ်" or "ကြောက်စရာအိမ်".

### R-GLOSS-03 — New Term Detection (WARNING)
**Rule**: If source contains a proper noun not in glossary, flag for human review. Do not invent translation.  
**Enforcement**: Verify  
**Action**: Add to `pending_glossary.json` with source snippet.

### R-GLOSS-04 — Alias Resolution (ERROR)
**Rule**: If source uses an alias (e.g., "Boss" for Chen Ge), use the canonical Burmese from glossary, not literal translation.  
**Example**: "Boss!" → "ဆရာ!" (because Chen Ge is the boss, and glossary maps "Boss" → "ဆရာ" in this context).

---

## 3. Style & Tone Rules (R-STYLE-XX)

### R-STYLE-01 — Narration Register (ERROR)
**Rule**: Narration must use **literary Burmese** (စာပေဆန်သော).  
**Allowed endings**: `လေသည်`, `ခြင်း ဖြစ်သည်`, `ရလေသည်`  
**Forbidden endings in narration**: `တယ်`, `လား`, `ပဲ` (these are spoken/colloquial)

### R-STYLE-02 — Dialogue Register (ERROR)
**Rule**: Dialogue must use **spoken Burmese** (စကားပြောစတိုင်).  
**Allowed**: `တယ်`, `လား`, `ပဲ`, `ကွာ`, `နော်`, `ဗျာ`  
**Forbidden in dialogue**: Excessive `လေသည်` usage (makes characters sound robotic).

### R-STYLE-03 — Character Voice Consistency (FATAL)
**Rule**: Each character's pronoun and speech pattern must remain consistent.  
**Mapping**:
| Character | Gender | Formality | Pronoun (Dialogue) | Particles |
|-----------|--------|-----------|-------------------|-----------|
| Chen Ge | Male | Informal | `ငါ` | `ကွာ`, `ဗျာ` |
| Xu Wan | Female | Polite | `ကျွန်မ` | `နော်`, `ပါ` |
| Uncle Xu | Male | Formal/Elder | `ငါ` | `ကွာ`, `ဗျာ` |

**Enforcement**: Verify (check against ContextBuffer active_speakers)

### R-STYLE-04 — Internal Monologue Distinction (WARNING)
**Rule**: Internal thoughts (italicized or "he thought") use intermediate register—more literary than dialogue but less formal than narration.  
**Example**: `ငါ ပြောသားပဲ မဟုတ်လား` (internal) vs `ချန်ဂီက ပြောလိုက်သည်` (narration).

### R-STYLE-05 — Onomatopoeia & Sound Effects (INFO)
**Rule**: Do not translate literally. Use creative Burmese equivalents or retain with explanation.  
**Example**: "Creak" → `"ခရိယင်..."` (not `"ကြေးကြေးဟိန်း"` unless natural).

---

## 4. Structural Rules (R-STRUCT-XX)

### R-STRUCT-01 — Scene Boundary Preservation (ERROR)
**Rule**: Scene breaks in source (blank lines, `---`, setting changes) must be preserved in output.  
**Action**: Insert blank line or `---` in Burmese output at same relative position.

### R-STRUCT-02 — Paragraph Integrity (ERROR)
**Rule**: One source paragraph = one output paragraph. Do not merge or split.  
**Exception**: If source paragraph exceeds 200 words, split at natural clause and mark with `[split]`.

### R-STRUCT-03 — Dialogue Block Preservation (ERROR)
**Rule**: Consecutive dialogue lines by same speaker must remain consecutive.  
**Example**:
```
"Dialogue 1," he said.
"Dialogue 2," he continued.
```
Must not insert narration between them.

### R-STRUCT-04 — Overlap Consistency (FATAL)
**Rule**: Overlap paragraphs shared between chunk[i] and chunk[i+1] must be **character-identical** in final output.  
**Enforcement**: Post-processor diff check.

---

## 5. Formatting Rules (R-FORMAT-XX)

### R-FORMAT-01 — Burmese Quotation Marks (ERROR)
**Rule**: Use standard Burmese quotation marks `"..."` for dialogue.  
**Forbidden**: English straight quotes `"..."` in final output (post-processor converts).

### R-FORMAT-02 — YAML Frontmatter Preservation (ERROR)
**Rule**: Output must contain YAML frontmatter with translated title, original metadata, plus pipeline metadata.  
**Required fields**: `title`, `novel`, `chapter`, `index`, `translated_by`, `glossary_version`, `grade`.

### R-FORMAT-03 — Markdown Header Levels (WARNING)
**Rule**: `#` = Chapter title, `##` = Scene title (if any), no deeper nesting unless source has it.

### R-FORMAT-04 — Zero-Width Spaces (FATAL)
**Rule**: Do not insert zero-width spaces (U+200B) between Burmese characters.  
**Enforcement**: Post-processor regex strip.

---

## 6. Forbidden Patterns (R-FORBID-XX)

### R-FORBID-01 — Machine-Like Particles (ERROR)
**Pattern**: `ဖြစ်သည်` used excessively where `လေသည်` or `ခြင်း ဖြစ်သည်` is more literary.  
**Exception**: Technical descriptions may use `ဖြစ်သည်`.

### R-FORBID-02 — Literal English Word Order (WARNING)
**Pattern**: Burmese sentence follows English SVO order unnaturally.  
**Example**: `"ငါ အဲ့ဒါကို မကြိုက်ဘူး"` (OK) vs `"ငါ မကြိုက်ဘူး အဲ့ဒါကို"` (awkward literal).

### R-FORBID-03 — Untranslated Fragments (FATAL)
**Pattern**: English words left untranslated in output.  
**Exception**: Proper nouns in glossary, onomatopoeia, and world-specific terms with `[note]`.

### R-FORBID-04 — Mixed Register (ERROR)
**Pattern**: Same sentence mixes literary `လေသည်` with spoken `တယ်`.  
**Example**: `"သူ လာခဲ့လေသည် တယ်"` → FORBIDDEN.

### R-FORBID-05 — Honorific Mismatch (ERROR)
**Pattern**: Character uses wrong honorific for social relationship.  
**Example**: Xu Wan calling Chen Ge "မင်း" (too rude) instead of "ဆရာ" or implicit polite form.

---

## 7. Context Inheritance Rules (R-CTX-XX)

### R-CTX-01 — Pronoun Continuity (ERROR)
**Rule**: If ContextBuffer shows Chen Ge last used `ငါ`, next dialogue by Chen Ge must also use `ငါ` unless emotional shift is explicit.

### R-CTX-02 — Emotional Tone Carry (WARNING)
**Rule**: If preceding chunk tone is "angry", current chunk should not abruptly shift to "calm" without transition.

### R-CTX-03 — Scene Summary Accuracy (ERROR)
**Rule**: ContextBuffer scene summary must accurately reflect what happened, not hallucinate events.

---

## 8. Rule Priority Matrix

When rules conflict, resolve by priority:

1. **R-GLOSS-01** (Exact term) — Highest
2. **R-STRUCT-04** (Overlap consistency)
3. **R-STYLE-03** (Character voice)
4. **R-FORBID-03** (No untranslated fragments)
5. **R-STYLE-01/02** (Register)
6. **R-STRUCT-01** (Scene boundaries)
7. **R-CTX-01** (Pronoun continuity)
8. **R-STYLE-05** (Onomatopoeia) — Lowest

---

## 9. Config File Schema

Rules are materialized in `config/rules.json`:

```json
{
  "version": "1.0",
  "rules": [
    {
      "id": "R-GLOSS-01",
      "enabled": true,
      "severity": "fatal",
      "scope": "global",
      "enforcement": "auto",
      "regex": "\b(Chen Ge)\b",
      "replacement": "ချန်ဂီ",
      "description": "Exact glossary term usage"
    }
  ],
  "priorities": ["R-GLOSS-01", "R-STRUCT-04", "R-STYLE-03"],
  "auto_fix_enabled": true,
  "max_auto_fix_per_chunk": 10
}
```

---

*End of RULES.md*
