Your review is sharp, accurate, and catches exactly the kinds of implementation pitfalls that cause rework. Every point is valid. Here’s the corrected, implementation-ready design with all fixes integrated.

---

## 🗄️ Revised Schema

### `novels` (New)
| Column | Type | Purpose |
|--------|------|---------|
| `id` | TEXT PK | `novel_<slug>` |
| `name` | TEXT | Display name |
| `source_language` | TEXT | `chinese` / `english` / `japanese` |
| `created_at` | TEXT | ISO timestamp |
| `updated_at` | TEXT | ISO timestamp |

### `glossary_terms`
| Column | Type | Purpose |
|--------|------|---------|
| `id` | TEXT PK | `term_<novel>_<hash>` |
| `novel_id` | TEXT FK | References `novels.id` |
| `source_term` | TEXT | Original term |
| `target_term` | TEXT | Approved translation |
| `canonical_form` | TEXT | Standardized source for enforcement |
| `category` | TEXT | `character` \| `location` \| `artifact` \| `concept` |
| `status` | TEXT | `pending` \| `approved` \| `locked` \| `deprecated` |
| `enforcement_level` | TEXT | `strict` \| `soft` \| `suggestion` |
| `context_condition` | TEXT NULLABLE | Optional disambiguation hint (e.g., `"when referring to cultivation path, not physical road"`) |
| `confidence` | REAL | Auto-calculated score (formula defined below) |
| `usage_count` | INTEGER | Total occurrences across chapters |
| `created_at` | TEXT | ISO timestamp |
| `reviewed_at` | TEXT NULLABLE | When human approved/rejected |

*(Removed `reviewed_by`, `series_id` moved to `novels` for later)*

### `term_variants`
| Column | Type | Purpose |
|--------|------|---------|
| `id` | INTEGER PK | Auto-increment |
| `term_id` | TEXT FK | References `glossary_terms.id` |
| `variant_text` | TEXT | Alternate form |
| `match_type` | TEXT | `exact` \| `pattern` \| `contextual` |
| `case_sensitive` | BOOLEAN | Casing requirement |

### `chapters`
| Column | Type | Purpose |
|--------|------|---------|
| `id` | TEXT PK | `chapter_<novel>_<num>` |
| `novel_id` | TEXT FK | References `novels.id` |
| `chapter_num` | INTEGER | Logical order |
| `file_path` | TEXT | Relative path to source file |
| `translation_status` | TEXT | `pending` \| `translated` \| `reviewed` \| `synced` |
| `last_processed_at` | TEXT | Last pipeline run |
| `paragraph_count` | INTEGER | For paragraph-index tracking |

*(Removed `last_synced_term_id`)*

### `term_usage`
| Column | Type | Purpose |
|--------|------|---------|
| `id` | INTEGER PK | Auto-increment |
| `term_id` | TEXT FK | References `glossary_terms.id` |
| `chapter_id` | TEXT FK | References `chapters.id` |
| `paragraph_idx` | INTEGER | Survives minor edits |
| `variant_used` | TEXT | Which variant appeared |
| `confidence` | REAL | Detection confidence |
| `context_snippet` | TEXT | ~50 words around occurrence |

### `context_snapshots`
| Column | Type | Purpose |
|--------|------|---------|
| `id` | INTEGER PK | Auto-increment |
| `chapter_id` | TEXT FK | References `chapters.id` |
| `summary_json` | TEXT | `{"active_chars":[], "events":[], "unresolved_refs":[], "new_terms":[]}` |
| `created_at` | TEXT | When generated |

*(Removed `token_estimate`)*

### `sync_jobs`
| Column | Type | Purpose |
|--------|------|---------|
| `id` | INTEGER PK | Auto-increment |
| `term_id` | TEXT FK | Which term changed |
| `old_value` | TEXT | Previous target/canonical |
| `new_value` | TEXT | New value |
| `status` | TEXT | `pending_review` \| `applied` \| `rolled_back` \| `cancelled` |
| `created_at` | TEXT | ISO timestamp |
| `applied_at` | TEXT NULLABLE | When committed |

*(Removed `affected_chapters` JSON array)*

### `sync_job_chapters` (New Junction Table)
| Column | Type | Purpose |
|--------|------|---------|
| `job_id` | INTEGER FK | References `sync_jobs.id` |
| `chapter_id` | TEXT FK | References `chapters.id` |
| `status` | TEXT | `pending` \| `applied` \| `failed` \| `skipped` |
| `applied_at` | TEXT NULLABLE | When this chapter was updated |

### `chapter_versions`
| Column | Type | Purpose |
|--------|------|---------|
| `id` | INTEGER PK | Auto-increment |
| `chapter_id` | TEXT FK | References `chapters.id` |
| `version_num` | INTEGER | Incrementing version |
| `file_snapshot_path` | TEXT | Path to backup file |
| `created_at` | TEXT | ISO timestamp |
| `reason` | TEXT | `sync_job_123` \| `manual_edit` \| `pre_translation` |

### `audit_log`
| Column | Type | Purpose |
|--------|------|---------|
| `id` | INTEGER PK | Auto-increment |
| `table_name` | TEXT | Changed table |
| `record_id` | TEXT | Changed PK |
| `action` | TEXT | `insert` \| `update` \| `delete` |
| `old_data` | TEXT NULLABLE | JSON previous state |
| `new_data` | TEXT NULLABLE | JSON new state |
| `timestamp` | TEXT | ISO timestamp |
| `source` | TEXT | `cli` \| `pipeline` \| `manual` |

*(Removed `glossary_exports` table)*

---

## 📐 Explicit Definitions (Previously Missing)

### `enforcement_level` Behavior
| Level | Pre-LLM | Post-LLM | Failure Handling |
|-------|---------|----------|------------------|
| `strict` | Hard replace all variants → canonical | Verify target exists in output | Log warning + flag for review if missing |
| `soft` | No pre-replace | Replace in postprocessor output only | Warn if variant not found, continue |
| `suggestion` | No pre-replace | No auto-replace | Inject into review queue for human decision |

### `confidence` Formula (Deterministic)
```
confidence = (frequency_score × 0.4) + (translation_consistency × 0.3) + (llm_score × 0.3)

frequency_score = min(occurrences / 10, 1.0)
translation_consistency = unique_targets / total_occurrences (inverted, so 1.0 = always same target)
llm_score = model's internal confidence on term extraction (0.0–1.0, capped)
```
*Clamp to 0.0–1.0. Recalculate on each new chapter scan.*

### Ambiguous Term Handling
- Add `context_condition` (nullable TEXT) to `glossary_terms`
- Example: `source="道"`, `context_condition="when used as cultivation path or philosophy"`
- Postprocessor applies term **only** if `context_condition` matches surrounding paragraph keywords (simple regex or keyword match)
- If multiple terms share the same `source_term` but different `context_condition`, both are stored and applied conditionally
- **Documented limitation**: Pure AI disambiguation is deferred. Human sets `context_condition` during review.

---

## 🔄 Workflow Adjustments

### Migration Path for Existing JSON
1. `mkdir backups/glossary_migration_$(date +%Y%m%d)`
2. Copy all `glossary*.json` → backup folder
3. Run `novel migrate glossary --novel <slug>`
4. Import script:
   - Parses old JSON → inserts into `glossary_terms` with `status='approved'`
   - Extracts variants → `term_variants`
   - Scans existing chapters → populates `term_usage` + `chapters`
5. Rename originals → `.json.bak`
6. DB becomes sole runtime truth. Old JSONs ignored by pipeline.
7. First `novel glossary export` creates new Git-tracked snapshot.

### N+1 Context Edge Case
- Prompt builder queries `context_snapshots` for `chapter_num IN [N-3, N-2, N-1, N+1]`
- If `N+1` doesn't exist: query returns empty set → builder silently skips
- Builder validates token budget **after** merging available snapshots
- Never errors on missing chapters. Graceful degradation is explicit.

### Sync Workflow (Using Junction Table)
1. Term edited → create `sync_jobs` row
2. Query `term_usage` → insert each `(job_id, chapter_id, status='pending')` into `sync_job_chapters`
3. CLI shows impact report grouped by chapter
4. User approves → postprocessor runs per chapter
5. On success: `sync_job_chapters.status='applied'`, `chapter_versions` created, file updated
6. On failure: `status='failed'`, error logged, rollback available
7. Job complete when all junction rows are `applied`, `failed`, or `skipped`

---

## 📋 Final Implementation Readiness Checklist

| Area | Status | Notes |
|------|--------|-------|
| `novels` table | ✅ Added | All `novel_id` FKs now valid |
| `last_synced_term_id` | ✅ Removed | Sync history handled via junction table |
| `affected_chapters` JSON | ✅ Replaced | `sync_job_chapters` enables efficient querying |
| `enforcement_level` | ✅ Defined | Explicit pre/post-LLM behavior documented |
| `confidence` formula | ✅ Defined | Deterministic, reproducible calculation |
| Ambiguous terms | ✅ Supported | `context_condition` + manual disambiguation |
| JSON migration path | ✅ Defined | Backup → import → deprecate → export |
| N+1 edge case | ✅ Handled | Silent skip, graceful degradation |
| `reviewed_by` | ✅ Dropped | Redundant for single-user |
| `glossary_exports` table | ✅ Removed | Filesystem + timestamps sufficient |
| `token_estimate` | ✅ Dropped | Calculated at runtime during prompt build |
| Everything else | ✅ Solid | Schema normalized, workflows explicit |

---

## ✅ You Are Ready

This schema is now **implementation-ready**. It:
- Eliminates dangling references and conceptual mismatches
- Provides deterministic behavior for enforcement and confidence
- Handles real-world edge cases (ambiguity, missing chapters, sync tracking)
- Keeps the DB lean and filesystem-centric
- Matches your single-user, local, offline constraints exactly

