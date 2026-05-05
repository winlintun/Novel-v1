# PLAN: Add YAML Merge Feature

## Feature Request
Merge two YAML config files directly via CLI flag instead of loading one YAML then applying Python dict overrides.

## Files to Touch

| File | Change |
|------|--------|
| `src/cli/parser.py` | Add `--merge` argument |
| `src/config/loader.py` | Add `load_and_merge_yaml()` function |

## What Could Break
- **None** — new feature, backwards compatible

## Testing
- Run: `python -m src.main --merge config/settings.yaml config/settings.pivot.yaml --novel test --ch 1`
- Verify merged config loads correctly

## Type
**Type 1 — Safe** (new functionality, no existing features touched)

## Approval Needed
- [ ] User approves plan
- [ ] User approves backup (not needed)

---