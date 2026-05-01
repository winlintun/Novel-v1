# 📜 Skill: Dynamic Chapter Context Memory
**ID:** `memory.context` | **Version:** `2.0` (Novel-Scoped)

## 🎯 Description
Tracks ongoing story state, active characters, recent events, and pronoun mappings. **Maintains separate context files per novel** to preserve narrative continuity without cross-novel contamination.

## 📁 File Routing
- **Path Template:** `data/context/{novel_name}.json`
- **Auto-Creation:** ✅ Creates on Chapter 1 start
- **Chapter Lifecycle:** Loads at translation start → Updates in-memory → Persists at chapter end
- **Archive Strategy:** After chapter N, compress chapters 1 to N-5 into `{novel_name}_archive.json` to limit active context size

## 📥 Input Schema
| Field | Type | Description |
|-------|------|-------------|
| `novel_name` | `string` | Required for file routing |
| `chapter_num` | `integer` | Triggers context load/save |
| `active_entities` | `object` | Characters, locations, items with relevance scores |
| `narrative_state` | `object` | `recent_events`, `pronoun_map`, `tone`, `last_paragraph_index` |

## 📤 Output Schema
- In-memory context object for current chapter
- Persisted `{novel_name}.json` with updated entities & events
- Memory sync status: `success | partial | failed`

## ⚙️ Rules & Constraints
- 🔒 **Read Access:** `translator`, `refiner`, `checker`
- ✍️ **Write Access:** `translator`, `context_updater`
- 📦 **Scope:** Novel-level + chapter-level window
- ⏳ **Entity Decay:** Reduce relevance score after 3 unmentioned paragraphs
- 🧠 **Pronoun Resolution:** Use latest entity match within active window
- 📊 **Max Active Entities:** `150` per novel context

## ✅ Validation & Behavior
- Require explicit name mapping for all new characters
- Merge strategy: `append_new_events_prepend_recent`
- Validate tone consistency (`formal`, `casual`, `epic`, `melancholic`)
- Auto-prune entities with `relevance_score < 0.2` at chapter end
- Log context load/save timestamps with `novel_name`