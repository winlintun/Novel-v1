# 📜 Skill: Term Extraction & Pending Queue Manager
**ID:** `output.term_extractor` | **Version:** `1.0`

## 🎯 Description
Manages human-in-the-loop glossary expansion by deduplicating, formatting, and routing new terms for review.

## 📥 Input Schema
- `candidate_terms`: Array with Chinese, MM context, CN context, category guess
- `pending_queue_path`: `data/glossary_pending.json`
- `glossary_path`: `data/glossary.json`

## 📤 Output Schema
- `added_to_pending`: Newly queued terms
- `duplicates_skipped`: Already existing terms
- `pending_queue_size`: Integer count
- `reviewer_notification`: Boolean (true if threshold exceeded)

## ⚙️ Rules & Constraints
- 🔄 **Deduplication Keys:** `chinese_term_normalized`
- 🏷️ **Auto-Categorize:** Use context heuristics
- 🔔 **Alert Threshold:** `20` pending terms
- 🚫 **Never Auto-Approve:** `true`

## ✅ Validation & Behavior
- Verify term not in glossary before queuing
- Require context snippet for all new terms
- Sanitize JSON output
- Enforce max file size: `5MB`
- Notify reviewer when queue grows