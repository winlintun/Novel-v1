# 📜 Skill: Runtime Session Rules
**ID:** `memory.session_rules` | **Version:** `1.0`

## 🎯 Description
Dynamic configuration governing agent behavior, quality gates, model parameters, and retry logic during a translation session.

## 📥 Input Schema
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enable_stages` | `array` | `["translator","refiner","checker","qa"]` | Active pipeline stages |
| `batch_size` | `integer` | `1` | Paragraphs per API call |
| `retry_attempts` | `integer` | `3` | Max retries per paragraph |
| `min_myanmar_ratio` | `float` | `0.85` | Language guard threshold |
| `temperature` | `float` | `0.1` | Model creativity control |
| `top_p` | `float` | `0.9` | Nucleus sampling |
| `repeat_penalty` | `float` | `1.2` | Prevents term looping |

## 📤 Output Schema
- Active rule snapshot
- Hot-reload status
- Quality gate pass/fail flags

## ⚙️ Rules & Constraints
- 🔒 **Read Access:** `all_agents`
- ✍️ **Write Access:** `main_controller`, `human_override`
- 🔥 **Hot Reload:** `true`
- 🔄 **On Quality Fail:** `retry_with_stricter_params`
- 🛑 **On Max Retries:** `insert_placeholder_and_continue`
- 📊 **Log Level:** `DEBUG` (configurable)

## ✅ Validation & Behavior
- Validate parameter ranges before applying
- Block unauthorized runtime overrides
- Enforce strict language guard ratios
- Auto-fallback to conservative settings on repeated failures