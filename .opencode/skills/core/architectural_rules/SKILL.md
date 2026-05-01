# 📜 Skill: System-Wide Architectural Constraints
**ID:** `core.architectural_rules` | **Version:** `2.0` (Novel-Scoped)

## 🎯 Description
Enforces modularity, memory security, human-in-the-loop protocols, and **novel-scoped file isolation** across the entire pipeline.

## 🌐 Global Rules
| Rule | Enforcement |
|------|-------------|
| **Novel-Scoped Isolation** | All memory files use `{novel_name}` namespace. Zero cross-novel data leakage. |
| **Strict Modularity** | Agents communicate ONLY via `MemoryManager`. No direct JSON access or inter-agent calls. |
| **Memory Security** | All reads/writes routed through centralized interface. Access logged with `novel_name` tag. |
| **Human-in-the-Loop** | Unknown terms → `【?term?】`. Escalation to `{novel_name}_pending.json`. |
| **Output Integrity** | Must pass language guard, glossary compliance, markdown preservation, and meaning consistency. |

## 📂 File Path Convention
data/
├── glossary/
│ └── {novel_name}.json
├── context/
│ └── {novel_name}.json
├── pending/
│ └── {novel_name}pending.json
├── input/
│ └── {novel_name}/
│ └── chapter.md
└── output/
└── {novel_name}/
└── chapter_.md


## 🚨 Error Handling
| Scenario | Strategy |
|----------|----------|
| Novel file missing | Auto-create with empty schema on first access |
| Agent Failure | Retry with stricter params (max 3) → Fallback to placeholder + log |
| Memory Corruption | Halt pipeline → Alert → Restore from last checkpoint |
| Quality Gate Fail | Reject output → Retry → Notify human if persistent |

## 📊 Logging & Validation
- **Level:** `DEBUG` (configurable)
- **Format:** Structured JSON
- **Include:** `agent_id`, `timestamp`, `novel_name`, `input_hash`, `output_hash`, `memory_accesses`
- **Redact:** Full source text (log hashes only)
- **Enforce:** Skill version compatibility, audit trail retention (90 days)
- **Novel Validation:** Reject invalid novel names (`[^a-zA-Z0-9_\-\u4e00-\u9fff]`)