---
description: Reads agent_skill_create/SKILL_*.md and creates or refreshes the matching opencode subagents (.opencode/agents/<role>.md). Use after editing a SKILL_*.md file to keep the pipeline agents in sync.
agent: build
---

Read all skill definition files matching `agent_skill_create/SKILL_*.md` from the repo root.

For each SKILL file, create or refresh the matching opencode subagent file below. If a target already exists, regenerate it in place (edit, never duplicate) so the file reflects the current SKILL source of truth.

| Skill source file            | Subagent file                  |
|------------------------------|--------------------------------|
| `agent_skill_create/SKILL_orchestrator.md` | `.opencode/agents/orchestrator.md` |
| `agent_skill_create/SKILL_translator.md`   | `.opencode/agents/translator.md`   |
| `agent_skill_create/SKILL_verifier.md`     | `.opencode/agents/verifier.md`     |
| `agent_skill_create/SKILL_auditor.md`      | `.opencode/agents/auditor.md`      |

Each generated agent file must follow the established project convention:

1. **Frontmatter**: `name` (matches the file name, e.g. `translator`), a `description` saying what the agent does + when to use it (third person, front-loaded trigger keywords), and `mode: subagent`. Do not add unknown frontmatter fields.
2. **Body** = the agent prompt, which must contain:
   - A **"Mandatory first step"** clause: on every invocation, read the corresponding `agent_skill_create/SKILL_<role>.md` and `SPEC.md`.
   - **SPEC.md as Single Source of Truth**: it overrides all other specs on conflict (state machine §4, error matrix §6, data models §3, micro-prompting §8).
   - The SKILL file's hard rules encoded concretely (glossary terms are law, structure/overlap identity, register separation, voice consistency, JSON-only output schemas, auto-fix limits).
   - **Project architecture** from AGENTS.md: offline ollama, Myanmar Unicode only, resume-safety, commit-per-batch.
3. **Voice**: keep the existing tone and structure of the current agents; only change what the SKILL file changed.

After writing every file, verify each one: frontmatter has exactly the allowed fields, the `name` matches the filename, and the body references the correct SKILL source path. Do not touch anything outside `.opencode/agents/`.

When done, report the files created/updated. If the user supplied extra instructions, apply them to the generated agents.

Extra user instructions (may be empty): $ARGUMENTS