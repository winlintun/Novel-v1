# 📜 Skill: Glossary Memory Manager
**ID:** `memory.glossary` | **Version:** `2.0` (Novel-Scoped)

## 🎯 Description
Approved terminology database for Wuxia/Xianxia terms. **Auto-creates and maintains novel-specific glossary files** to prevent term bleeding between different novels.

## 📁 File Routing
- **Path Template:** `data/glossary/{novel_name}.json`
- **Auto-Creation:** ✅ Creates file on first chapter translation if missing
- **Fallback:** If `{novel_name}.json` doesn't exist, initialize with empty `{}` structure
- **Merge Strategy:** New approved terms are appended; existing terms are updated only if `approved_by: "human_reviewer"`

## 📥 Input Schema
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `chinese_term` | `string` | ✅ | Original Chinese term |
| `myanmar_translation` | `string` | ✅ | Approved Myanmar equivalent |
| `category` | `string` | ❌ | `character`, `place`, `cultivation`, `item`, `sect`, `other` |
| `novel_name` | `string` | ✅ | Scope identifier for file routing |
| `approved_by` | `string` | ❌ | Default: `human_reviewer` |

## 📤 Output Schema
- Returns exact Myanmar term if match found in novel-specific glossary
- Returns `【?{chinese_term}?】` placeholder if not found
- Returns `null` if term is malformed or novel scope invalid

## ⚙️ Rules & Constraints
- 🔒 **Read Access:** `translator`, `refiner`, `checker`, `context_updater`
- ✍️ **Write Access:** `context_updater`, `human_reviewer`
- 📦 **Scope Isolation:** Glossary terms from `Novel A` NEVER leak to `Novel B`
- 🔄 **Auto-Save:** Triggers after each chapter completion
- 📏 **Max File Size:** 2MB per novel (archive older terms if exceeded)

## ✅ Validation & Behavior
- Validate novel name matches `[a-zA-Z0-9_\-\u4e00-\u9fff]+`
- Require valid Myanmar Unicode (`U+1000–U+109F`)
- Reject entries containing Latin/Thai characters
- Log all read/write operations with `novel_name` tag