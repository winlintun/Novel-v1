# Long-Term Re-Review: What This Project Still Needs To Sound More Like A Human Translator
**Date:** 2026-05-24  
**Project:** Novel Translation Pipeline  
**Human Reference Corpus:** `/home/wangyi/Desktop/DownloadNovel/CreateNovelDataSet`

## Executive Summary

This project is no longer at the stage where the main problem is broken basics.

The codebase already has:

- a multi-stage translation pipeline,
- glossary and context memory,
- chapter summary injection,
- character voice persistence,
- human-correction ingestion,
- human-reference benchmarking code,
- and a fiction editor for natural Myanmar rewriting.

That foundation is useful.

The next quality ceiling is different:

**the system can produce acceptable Myanmar, but it still does not consistently translate like a human novel translator across many books.**

The biggest long-term gaps are:

1. no true per-book style model,
2. weak literary retrieval,
3. no routine human-reference comparison in the main pipeline,
4. shallow learning from the human corpus beyond term extraction,
5. no deliberate final “humanization” stage inside the normal workflow,
6. quality gates still focus more on validity than on literary effect.

For general novels, the project should move toward this principle:

**translate with book memory, retrieve from human examples, review against human chapters, and learn from human edits at paragraph level.**

---

## What The Project Already Does Well

The current system already has several strong architectural choices:

- paragraph-aware chunking instead of naive line splitting,
- multi-stage processing instead of one-shot translation,
- per-novel memory and glossary storage,
- chapter summary support for continuity,
- persistent character voice storage,
- optional RAG example injection,
- benchmark code that can compare model output with human translations,
- a fiction editor that can rewrite robotic Myanmar into more natural prose.

This means the project does **not** need a total rewrite.

It needs better use of the parts it already has, plus a stronger long-term data strategy.

---

## What Still Blocks Human-Sounding Translation

### 1. No real per-novel style system

The largest remaining gap is the lack of a true `book_profile` runtime layer.

Right now the system has glossary, context, voices, and some correction memory. That helps consistency. It does not fully solve style.

Human translators do not translate every novel with the same internal voice. They adapt to:

- narrator formality,
- emotional intensity,
- descriptive density,
- dialogue softness or bluntness,
- pacing,
- title and honorific habits,
- how literal or adaptive the prose should be.

Without a stable per-book style profile, the output can be clean but generic.

#### Recommendation

Add a persistent `book_profile` for each novel:

- narration register,
- dialogue register,
- preferred sentence length,
- preferred paragraph rhythm,
- genre tone,
- formality level,
- term adaptation policy,
- taboo wording list,
- 5-20 representative human-translated paragraph examples.

This profile should be loaded at chapter start and injected into translation, refinement, and optional editing stages.

---

### 2. The pipeline still does not learn enough from the human corpus

The human English/Myanmar chapter pairs are the most valuable long-term asset in this project.

At the moment, the codebase learns some things from humans, but not deeply enough. Most of the live system still behaves like:

- prompt engineering,
- memory injection,
- cleanup,
- and quality validation.

That is useful, but it is not yet strong corpus-guided translation.

#### What the raw `en/` + `mm/` files should teach

- narrator style,
- dialogue style,
- paragraph expansion or compression habits,
- scene pacing,
- emotional phrasing,
- honorific behavior,
- recurring title usage,
- character-specific speech habits,
- chapter opening and ending patterns.

#### Recommendation

Use the human corpus as four separate assets:

1. `reference_memory`  
Similar human paragraphs retrieved during translation.

2. `book_profile`  
Per-novel style summary extracted from human `mm/` chapters.

3. `voice_profile`  
Character dialogue behavior learned from human `mm/`.

4. `evaluation_ground_truth`  
Chapter-level comparison after translation.

This should matter more than adding more generic prompts.

---

### 3. Current RAG is still too weak for literary work

The translator already supports RAG example injection, but the active retriever remains weak for novel translation quality.

`src/data/rag_retriever.py` still disables Chroma and falls back to SQLite keyword-overlap retrieval. That is acceptable for basic term overlap. It is not strong enough for literary reuse.

Human-sounding translation needs retrieval based on more than words. It needs retrieval by:

- similar scene type,
- same novel first,
- same speaking characters,
- same relationship dynamic,
- same narration/dialogue mode,
- similar emotional temperature,
- similar term usage in prose context.

#### Recommendation

Upgrade RAG into **literary reference retrieval**:

- same-novel retrieval first,
- paragraph-level retrieval, not sentence-only retrieval,
- metadata filters: novel, chapter range, speaker, scene type, narration/dialogue,
- semantic similarity plus term overlap,
- separate retrieval pools for narration and dialogue.

The current fallback retriever is a start, not the finished system.

---

### 4. Human-reference comparison is still not part of normal pipeline behavior

`src/evaluation/benchmark.py` is one of the most strategically important files in the repo because it compares model output against human chapter references.

But it still feels like an evaluation utility, not a normal operating mode.

If the project goal is "sound more like a human translator," then the main feedback loop should not only be:

- Myanmar ratio,
- script leakage,
- repetition,
- glossary consistency,
- internal score thresholds.

It should also be:

- how far is this chapter from the human translator's version?

#### Recommendation

Promote benchmarking into routine workflow:

- add a first-class CLI path like `--compare-human`,
- save chapter comparison reports automatically,
- track per-novel drift over time,
- use paragraph similarity, length ratio, omitted-content indicators, and style differences,
- optionally fail or warn when output is much flatter than the human reference.

This is the clearest route to measurable human-likeness.

---

### 5. Character voice exists, but source quality for voice learning is still too shallow

The project can now store character voice. That is a real improvement.

But storing voice is not the same as learning it well.

The highest-quality voice source is not AI output. It is repeated patterns in the human `mm/` chapters:

- pronoun choice,
- honorific choice,
- sarcasm or softness,
- sentence endings,
- emotional restraint,
- speech rhythm,
- aggression level,
- social hierarchy markers.

#### Recommendation

Build a dedicated voice-learning pass from the human corpus:

- extract dialogue lines,
- cluster by speaker if speaker tagging is available or inferable,
- record consistent pronouns and register,
- store representative quotes,
- separate spoken voice from narrated description of the character.

Then use that data in the translator and refiner, not only in the editor.

---

### 6. Narration and dialogue should be treated as different translation problems

One major reason AI translation feels flat is that it often uses nearly one register everywhere.

Human novel translation does not do that.

Narration and dialogue need different handling:

- narration needs flow, rhythm, atmosphere, and scene control,
- dialogue needs voice, relationship awareness, and social accuracy.

#### Recommendation

Make this explicit in the pipeline:

- detect dialogue-heavy vs narration-heavy chunks,
- route them through different prompt variants,
- retrieve different human reference examples,
- evaluate them with partially different criteria,
- optionally apply different editor tones at the final stage.

This matters across all novels, not only wuxia/xianxia.

---

### 7. The fiction editor is useful, but it is still not a real pipeline stage

`src/agents/fiction_editor.py` is promising because it directly targets the gap between "correct translation" and "natural fiction prose."

Right now it behaves more like an auxiliary tool and web editor feature than a normal step in the main translation path.

#### Recommendation

Turn it into an optional formal stage such as:

- `humanize`,
- `literary`,
- `dramatic`,
- `casual`,
- or auto-selected based on chunk type and book profile.

Suggested position:

`translate -> refine -> consistency/quality -> fiction_editor(optional) -> final review`

This stage should be constrained:

- never change plot facts,
- never invent content,
- preserve glossary and protected names,
- rewrite only for flow, rhythm, register, and naturalness.

---

### 8. The project still learns corrections too narrowly

`--ingest-human-correction` is a strong step, but the feedback loop should expand.

Right now correction learning is still too term-centered.

Human corrections often teach more important things than vocabulary:

- better sentence rhythm,
- less literal rendering,
- stronger atmosphere,
- pronoun fixes,
- relationship-sensitive wording,
- paragraph restructuring,
- dialogue tone changes.

#### Recommendation

Expand correction ingestion into structured learning categories:

- terminology correction,
- voice correction,
- register correction,
- paragraph-flow correction,
- omission/addition correction,
- narrator-style correction.

These should become reusable memory, not just one-off fixes.

---

### 9. Paragraph-level learning should be the main unit, not sentence-level learning

This project already chunks by paragraph, which is correct.

The next step is to make more systems paragraph-aware because human literary translation quality is usually expressed at paragraph level:

- pacing,
- emphasis,
- sentence grouping,
- emotional buildup,
- transition handling,
- atmosphere.

#### Recommendation

Make paragraph-level comparison the main unit for:

- retrieval,
- correction learning,
- benchmark evaluation,
- humanization,
- style drift detection.

Sentence-level matching is still useful, but it should not dominate the design.

---

### 10. Quality gates still emphasize "valid Myanmar" more than "good novel prose"

The project has strong safety and cleanup logic. That is necessary.

But long-term quality gains will come from scoring literary properties more directly.

The current question is often:

- is the output acceptable?

The better question is:

- does the output read like finished translated fiction?

#### Recommendation

Add literary quality checks for:

- narrator consistency,
- dialogue distinctiveness,
- emotional naturalness,
- paragraph rhythm,
- atmosphere preservation,
- over-literal phrasing,
- generic AI phrasing,
- tone drift across chapters.

These do not need to fully block output at first. Even warning-level reports would improve iteration.

---

## Long-Term Pipeline Direction

For general novels, the strongest pipeline direction is:

### Stage 1: Pre-translation analysis

- detect source language and chapter type,
- load `book_profile`,
- load active character voice profiles,
- retrieve relevant glossary and style rules,
- retrieve 2-5 human reference paragraphs.

### Stage 2: Translation

- translate with glossary, voice, summary, and retrieved examples,
- use different prompt templates for narration-heavy vs dialogue-heavy chunks.

### Stage 3: Refinement

- improve fluency while preserving meaning,
- keep paragraph structure aligned,
- enforce book-level tone.

### Stage 4: Literary humanization

- optional `fiction_editor` stage,
- selected by tone or book profile,
- rewrite only for naturalness and literary feel.

### Stage 5: Quality and consistency

- current safety checks,
- glossary checks,
- script leakage checks,
- repetition checks,
- missing-content checks.

### Stage 6: Human-reference comparison

- compare to human chapter if available,
- store benchmark report,
- log paragraph-level mismatches,
- extract reusable correction signals.

### Stage 7: Memory update

- update chapter summary,
- update character voice confidence,
- update book-style evidence,
- ingest human corrections into structured feedback memory.

---

## Highest-Value Next Improvements

If the project wants the biggest long-term gains, the best order is:

1. Build a real `book_profile` system from the human corpus.
2. Upgrade RAG into paragraph-level literary reference retrieval.
3. Add a normal `--compare-human` workflow to the main CLI and pipeline reports.
4. Learn character voice from human `mm/` chapters, not mainly from AI output.
5. Promote `fiction_editor` into an optional real pipeline stage.
6. Expand human-correction ingestion from term diffs to style and paragraph diffs.
7. Add literary scoring so quality means more than “clean Myanmar.”

---

## Final Judgment

This project is already much better than a basic prompt-to-translation script.

Its next problem is not whether it can generate Myanmar.

Its next problem is whether it can build **book-specific literary behavior** over time.

For long-term, general-novel quality, the project should stop thinking mainly in terms of:

- more prompts,
- more cleanup,
- more generic validation.

It should think in terms of:

- per-book style memory,
- human paragraph retrieval,
- voice learning from human translations,
- chapter comparison against human references,
- and structured learning from human edits.

That is the path from “AI translated this correctly” to “this reads like a human translator wrote it.”
